"""
LCNAF OpenRefine Reconciliation Service

OpenRefine reconciliation service for the Library of Congress Name Authority File (LCNAF)
using MARISA trie data structure.

Implements the OpenRefine Reconciliation API v0.2:
https://reconciliation-api.github.io/specs/latest/
"""

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import marisa_trie
import msgpack
import gzip
import string
import unicodedata
import re
import os
import json

app = Flask(__name__)
CORS(app)

# Global variables for trie and lookup data
trie = None
lookup = None

# LCCN prefix mapping
LCCN_PREFIX_MAP = {
    '1': 'nb',
    '2': 'nn',
    '3': 'no',
    '4': 'nr',
    '5': 'ns',
    '6': 'n'
}

# Service configuration
SERVICE_BASE_URL = "http://localhost:5724"
SERVICE_NAME = "LCNAF Reconciliation Service"
SERVICE_VERSION = "0.2"


def normalize_string(name):
    """
    Normalize string exactly like the create_trie.py script does.
    """
    # Remove punctuation
    norm = name.translate(str.maketrans('', '', string.punctuation))

    # Normalize unicode (NFKD) and remove non-ASCII
    norm = unicodedata.normalize('NFKD', norm).encode('ascii', 'ignore').decode('utf-8')

    # Convert to lowercase
    norm = norm.lower()

    # Remove spaces
    norm = norm.replace(' ', '')

    # Sort characters
    norm = ''.join(sorted(norm))

    # Move non-letter characters to the end
    try:
        match = re.search(r"[a-z]", norm)
        if match:
            first_letter_index = match.start()
            first_part = norm[:first_letter_index]
            second_part = norm[first_letter_index:]
            norm = second_part + first_part
    except:
        pass

    return norm


def levenshtein_distance(s1, s2):
    """Calculate Levenshtein distance between two strings."""
    len1 = len(s1)
    len2 = len(s2)

    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost
            )

    return matrix[len1][len2]


def calculate_match_score(original_input, label, distance):
    """
    Calculate a match score (0-100) based on Levenshtein distance.
    Higher score = better match.
    """
    # Normalize both for comparison
    normalized_input = ''.join(c for c in original_input.lower() if c.isalnum())
    normalized_label = ''.join(c for c in label.lower() if c.isalnum())

    max_len = max(len(normalized_input), len(normalized_label))
    if max_len == 0:
        return 100

    # Score: 100 - (distance/max_length * 100)
    score = 100 - (distance / max_len * 100)
    return max(0, min(100, score))  # Clamp between 0-100


def convert_lccn(numeric_lccn):
    """Convert numeric LCCN back to prefixed format."""
    if not isinstance(numeric_lccn, int):
        return numeric_lccn

    lccn_str = str(numeric_lccn)
    first_digit = lccn_str[0]

    prefix = LCCN_PREFIX_MAP.get(first_digit)
    if not prefix:
        return f"n{lccn_str.zfill(8)}"

    return prefix + lccn_str[1:]


def reconcile_name(query_text):
    """
    Reconcile a name against LCNAF.
    Returns a list of candidates sorted by match quality.
    """
    # Normalize the query
    normalized = normalize_string(query_text)

    # Look up in trie
    trie_id = trie.get(normalized)

    if trie_id is None:
        return []

    # Get LCCN data from lookup
    lccn_data = lookup[trie_id]

    candidates = []

    if isinstance(lccn_data, list):
        # Multiple labels map to this normalized form
        # Calculate distance for each and return all
        normalized_input = ''.join(c for c in query_text.lower() if c.isalnum())

        for item in lccn_data:
            lccn_num = item[0]
            label = item[1]

            normalized_label = ''.join(c for c in label.lower() if c.isalnum())
            distance = levenshtein_distance(normalized_input, normalized_label)
            score = calculate_match_score(query_text, label, distance)

            lccn_formatted = convert_lccn(lccn_num)

            candidates.append({
                'id': f"http://id.loc.gov/authorities/names/{lccn_formatted}",
                'name': label,
                'score': score,
                'match': distance == 0,
                'type': [{'id': 'LCNAF_Name', 'name': 'LCNAF Name'}]
            })

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x['score'], reverse=True)

    else:
        # Single LCCN value
        lccn_formatted = convert_lccn(lccn_data)

        candidates.append({
            'id': f"http://id.loc.gov/authorities/names/{lccn_formatted}",
            'name': query_text,  # Use original query as we don't have the label
            'score': 100,
            'match': True,
            'type': [{'id': 'LCNAF_Name', 'name': 'LCNAF Name'}]
        })

    return candidates


def load_data():
    """Load the trie and lookup data."""
    global trie, lookup

    base_dir = os.path.dirname(os.path.abspath(__file__))
    trie_path = os.path.join(base_dir, '..', 'web-reconcile', 'public', 'trie.marisa.bin')
    lookup_path = os.path.join(base_dir, '..', 'web-reconcile', 'public', 'trie_lookup.msgpack.bin')

    print(f"Loading trie from: {trie_path}")
    print(f"Loading lookup from: {lookup_path}")

    # Load and decompress trie
    with open(trie_path, 'rb') as f:
        trie_compressed = f.read()

    trie_data = gzip.decompress(trie_compressed)

    temp_trie_path = '/tmp/trie_temp_openrefine.marisa'
    with open(temp_trie_path, 'wb') as f:
        f.write(trie_data)

    trie = marisa_trie.Trie()
    trie.load(temp_trie_path)

    print(f"Trie loaded: {len(trie):,} keys")

    # Load and decompress lookup data
    with open(lookup_path, 'rb') as f:
        lookup_compressed = f.read()

    lookup_data = gzip.decompress(lookup_compressed)
    lookup = msgpack.unpackb(lookup_data, raw=False)

    print(f"Lookup loaded: {len(lookup):,} entries")

    os.remove(temp_trie_path)


# OpenRefine Reconciliation API Endpoints

@app.route('/')
def index():
    """Root endpoint - returns service information."""
    return jsonify({
        'name': SERVICE_NAME,
        'version': SERVICE_VERSION,
        'identifierSpace': 'http://id.loc.gov/authorities/names/',
        'schemaSpace': 'http://id.loc.gov/authorities/names/',
        'documentation': 'Library of Congress Name Authority File reconciliation service'
    })


@app.route('/reconcile', methods=['GET', 'POST'])
def reconcile():
    """
    Main reconciliation endpoint.
    GET: Returns service manifest
    POST: Processes reconciliation queries
    """

    if request.method == 'GET':
        # Return manifest
        manifest = {
            'versions': ['0.2'],
            'name': SERVICE_NAME,
            'identifierSpace': 'http://id.loc.gov/authorities/names/',
            'schemaSpace': 'http://id.loc.gov/authorities/names/',
            'defaultTypes': [
                {
                    'id': 'LCNAF_Name',
                    'name': 'LCNAF Name'
                }
            ],
            'view': {
                'url': f'{SERVICE_BASE_URL}/view?id={{{{id}}}}'
            },
            'preview': {
                'url': f'{SERVICE_BASE_URL}/preview?id={{{{id}}}}',
                'width': 400,
                'height': 100
            }
        }
        return jsonify(manifest)

    if request.method == 'POST':
        # Process reconciliation queries
        queries_json = request.form.get('queries')

        if not queries_json:
            return jsonify({'error': 'No queries provided'}), 400

        try:
            queries = json.loads(queries_json)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON in queries'}), 400

        results = {}

        for query_id, query_data in queries.items():
            if isinstance(query_data, dict) and 'query' in query_data:
                query_text = query_data['query']

                # Reconcile the query
                candidates = reconcile_name(query_text)

                results[query_id] = {
                    'result': candidates
                }
            else:
                results[query_id] = {
                    'result': []
                }

        return jsonify(results)


@app.route('/view')
def view():
    """Redirect to the id.loc.gov page for the entity."""
    entity_id = request.args.get('id', '')

    if entity_id:
        return redirect(entity_id, code=302)

    return 'No ID provided', 400


@app.route('/preview')
def preview():
    """Return a simple HTML preview showing the LCCN."""
    entity_id = request.args.get('id', '')

    if not entity_id:
        return '<html><body>No ID provided</body></html>'

    # Extract LCCN from the URL
    lccn = entity_id.split('/')[-1] if '/' in entity_id else entity_id

    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 10px;
                font-size: 12px;
            }}
            .lccn-link {{
                color: #0066cc;
                text-decoration: none;
                font-weight: bold;
            }}
            .lccn-link:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div>
            <strong>LCCN:</strong> <a href="{entity_id}" target="_blank" class="lccn-link">{lccn}</a>
        </div>
        <div style="margin-top: 10px; font-size: 11px; color: #666;">
            Click to view full record at id.loc.gov
        </div>
    </body>
    </html>
    """

    return html


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': ['/reconcile', '/view', '/preview', '/']
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


if __name__ == '__main__':
    print("="*70)
    print("LCNAF OpenRefine Reconciliation Service")
    print("="*70)
    print("Loading LCNAF data...")
    load_data()
    print("Data loaded successfully!")
    print("\nStarting Flask server...")
    print(f"Service URL: {SERVICE_BASE_URL}/reconcile")
    print(f"Add this URL to OpenRefine to use the reconciliation service")
    print("="*70)
    app.run(debug=True, host='0.0.0.0', port=5724)
