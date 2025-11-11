"""
LCNAF Reconciliation API

Simple Flask API for reconciling names against the Library of Congress Name Authority File (LCNAF)
using MARISA trie data structure.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import marisa_trie
import msgpack
import gzip
import string
import unicodedata
import re
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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


def normalize_string(name):
    """
    Normalize string exactly like the create_trie.py script does:
    1. Remove punctuation
    2. Normalize unicode (NFKD) and remove non-ASCII
    3. Convert to lowercase
    4. Remove spaces
    5. Sort characters
    6. Move non-letter characters to the end
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
    """
    Calculate Levenshtein distance between two strings.
    Used for finding best match when multiple labels map to the same normalized form.
    """
    len1 = len(s1)
    len2 = len(s2)

    # Create matrix
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    # Initialize first column and row
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j

    # Fill matrix
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,      # deletion
                matrix[i][j - 1] + 1,      # insertion
                matrix[i - 1][j - 1] + cost  # substitution
            )

    return matrix[len1][len2]


def find_best_match(original_input, labels):
    """
    Find best matching label using Levenshtein distance.
    Labels is a list of [lccn, label] pairs (arrays with 2 elements).
    Returns the best matching lccn, label, and distance.
    """
    # Normalize input for comparison (remove non-alphanumeric)
    normalized_input = ''.join(c for c in original_input.lower() if c.isalnum())

    best_match = None
    best_distance = float('inf')

    for item in labels:
        # Item is [lccn, label] format
        lccn_num = item[0]
        label = item[1]

        # Normalize label for comparison (remove non-alphanumeric)
        normalized_label = ''.join(c for c in label.lower() if c.isalnum())

        distance = levenshtein_distance(normalized_input, normalized_label)

        if distance < best_distance:
            best_distance = distance
            best_match = {
                'lccn': lccn_num,
                'label': label,
                'distance': distance
            }

    return best_match


def convert_lccn(numeric_lccn):
    """
    Convert numeric LCCN (compressed format) back to prefixed format.
    Examples: 179012345 -> nb79012345, 685012345 -> n85012345
    """
    if not isinstance(numeric_lccn, int):
        return numeric_lccn

    lccn_str = str(numeric_lccn)
    first_digit = lccn_str[0]

    prefix = LCCN_PREFIX_MAP.get(first_digit)
    if not prefix:
        # Default to 'n' prefix
        return f"n{lccn_str.zfill(8)}"

    return prefix + lccn_str[1:]


def load_data():
    """Load the trie and lookup data from the web-reconcile public directory."""
    global trie, lookup

    # Paths to the data files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    trie_path = os.path.join(base_dir, '..', 'web-reconcile', 'public', 'trie.marisa.bin')
    lookup_path = os.path.join(base_dir, '..', 'web-reconcile', 'public', 'trie_lookup.msgpack.bin')

    print(f"Loading trie from: {trie_path}")
    print(f"Loading lookup from: {lookup_path}")

    # Load and decompress trie
    with open(trie_path, 'rb') as f:
        trie_compressed = f.read()

    trie_data = gzip.decompress(trie_compressed)

    # Write to temporary file for marisa_trie to load
    temp_trie_path = '/tmp/trie_temp.marisa'
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

    # Clean up temp file
    os.remove(temp_trie_path)


@app.route('/')
def index():
    """API information endpoint."""
    return jsonify({
        'name': 'LCNAF Reconciliation API',
        'version': '1.0.0',
        'description': 'Reconcile names against the Library of Congress Name Authority File',
        'endpoints': {
            '/reconcile': 'GET - Reconcile a name (query parameter: q)',
            '/health': 'GET - Health check'
        },
        'stats': {
            'total_keys': len(trie) if trie else 0,
            'total_entries': len(lookup) if lookup else 0
        }
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    if trie is None or lookup is None:
        return jsonify({
            'status': 'unhealthy',
            'message': 'Data not loaded'
        }), 503

    return jsonify({
        'status': 'healthy',
        'trie_size': len(trie),
        'lookup_size': len(lookup)
    })


@app.route('/reconcile')
def reconcile():
    """
    Reconcile a name against LCNAF.

    Query parameters:
        q: The name to reconcile (required)

    Returns:
        JSON response with reconciliation result
    """
    # Get query parameter
    name = request.args.get('q', '').strip()

    if not name:
        return jsonify({
            'error': 'Missing required parameter: q',
            'example': '/reconcile?q=Woolf, Virginia, 1882-1941'
        }), 400

    # Normalize the name
    normalized = normalize_string(name)

    # Look up in trie
    trie_id = trie.get(normalized)

    if trie_id is None:
        # Not found
        return jsonify({
            'query': name,
            'normalized': normalized,
            'found': False,
            'message': 'Name not found in LCNAF'
        })

    # Get LCCN data from lookup
    lccn_data = lookup[trie_id]

    # Handle result based on type
    if isinstance(lccn_data, list):
        # Multiple labels map to this normalized form
        # Find best match using Levenshtein distance
        best_match = find_best_match(name, lccn_data)

        if best_match:
            lccn_formatted = convert_lccn(best_match['lccn'])

            # Create alternatives list
            # Items are [lccn, label] format
            alternatives = []
            for item in lccn_data:
                alt_lccn = convert_lccn(item[0])
                if alt_lccn != lccn_formatted:
                    alternatives.append({
                        'lccn': alt_lccn,
                        'label': item[1],
                        'uri': f"http://id.loc.gov/authorities/names/{alt_lccn}"
                    })

            return jsonify({
                'query': name,
                'normalized': normalized,
                'found': True,
                'lccn': lccn_formatted,
                'uri': f"http://id.loc.gov/authorities/names/{lccn_formatted}",
                'matched_label': best_match['label'],
                'levenshtein_distance': best_match['distance'],
                'match_quality': 'exact' if best_match['distance'] == 0 else 'fuzzy',
                'total_matches': len(lccn_data),
                'alternatives': alternatives
            })
    else:
        # Single LCCN value (integer)
        lccn_formatted = convert_lccn(lccn_data)

        return jsonify({
            'query': name,
            'normalized': normalized,
            'found': True,
            'lccn': lccn_formatted,
            'uri': f"http://id.loc.gov/authorities/names/{lccn_formatted}",
            'match_quality': 'exact'
        })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': ['/reconcile', '/health', '/']
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


if __name__ == '__main__':
    print("Loading LCNAF data...")
    load_data()
    print("Data loaded successfully!")
    print("\nStarting Flask server...")
    print("API available at: http://localhost:5723")
    print("Example: http://localhost:5723/reconcile?q=Woolf, Virginia, 1882-1941")
    app.run(debug=True, host='0.0.0.0', port=5723)
