#!/usr/bin/env python3
"""
LCNAF MARC Reconciliation Tool

Command-line tool for reconciling LCNAF names in MARC records.
Processes MARC binary or XML files and adds $0 subfields with id.loc.gov URIs.

Usage:
    python3 reconcile_marc.py /path/to/marcfile.mrc
    python3 reconcile_marc.py /path/to/marcfile.xml
"""

import sys
import os
import gzip
import string
import unicodedata
import re
import json
from pathlib import Path
import marisa_trie
import msgpack
from pymarc import MARCReader, Record, Field, parse_xml_to_array
from pymarc.writer import MARCWriter, XMLWriter


# LCCN prefix mapping
LCCN_PREFIX_MAP = {
    '1': 'nb',
    '2': 'nn',
    '3': 'no',
    '4': 'nr',
    '5': 'ns',
    '6': 'n'
}

# Maximum Levenshtein distance for matching
MAX_LEVENSHTEIN_DISTANCE = 10

# Fields to process
FIELDS_TO_PROCESS = ['100', '110', '700', '710']

# Subfields to combine (in order)
SUBFIELDS_TO_COMBINE = ['a', 'b', 'c', 'q', 'd', 'g']

# Global variables for trie and lookup data
trie = None
lookup = None


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


def find_best_match(original_input, labels):
    """
    Find the best match from multiple labels using Levenshtein distance.
    Returns (lccn, label, distance) or None if no good match found.
    """
    normalized_input = ''.join(c for c in original_input.lower() if c.isalnum())

    best_match = None
    best_distance = float('inf')

    for item in labels:
        lccn_num = item[0]
        label = item[1]

        normalized_label = ''.join(c for c in label.lower() if c.isalnum())
        distance = levenshtein_distance(normalized_input, normalized_label)

        if distance < best_distance:
            best_distance = distance
            best_match = (lccn_num, label, distance)

    if best_distance <= MAX_LEVENSHTEIN_DISTANCE:
        return best_match

    return None


def reconcile_name(name):
    """
    Reconcile a name against LCNAF.
    Returns (lccn, matched_label, distance) or None if no match found.
    """
    # Normalize the name
    normalized = normalize_string(name)

    # Look up in trie
    trie_id = trie.get(normalized)

    if trie_id is None:
        return None

    # Get LCCN data from lookup
    lccn_data = lookup[trie_id]

    if isinstance(lccn_data, list):
        # Multiple labels map to this normalized form
        return find_best_match(name, lccn_data)
    else:
        # Single LCCN value
        return (lccn_data, name, 0)


def extract_name_from_field(field):
    """
    Extract name string from a MARC field by combining specific subfields.
    Combines subfields in order: a, b, c, q, d, g
    """
    parts = []

    for code in SUBFIELDS_TO_COMBINE:
        values = field.get_subfields(code)
        for value in values:
            parts.append(value.strip())

    return ' '.join(parts)


def add_zero_subfield(field, lccn):
    """
    Add $0 subfield to the end of a field with the id.loc.gov URI.
    """
    uri = f"http://id.loc.gov/authorities/names/{lccn}"

    # Check if $0 already exists to avoid duplicates
    existing_zeros = field.get_subfields('0')
    if uri in existing_zeros:
        return False

    # Add $0 at the end
    field.add_subfield('0', uri)
    return True


def load_trie_data():
    """Load the trie and lookup data."""
    global trie, lookup

    # Get paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(script_dir, '..')
    trie_path = os.path.join(base_dir, 'web-reconcile', 'public', 'trie.marisa.bin')
    lookup_path = os.path.join(base_dir, 'web-reconcile', 'public', 'trie_lookup.msgpack.bin')

    print(f"Loading trie from: {trie_path}")
    print(f"Loading lookup from: {lookup_path}")

    # Load and decompress trie
    with open(trie_path, 'rb') as f:
        trie_compressed = f.read()

    trie_data = gzip.decompress(trie_compressed)

    temp_trie_path = '/tmp/trie_temp_marc.marisa'
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


def process_marc_file(input_path):
    """
    Process a MARC file (binary or XML) and reconcile names.
    Outputs reconciled MARC file and generates a report.
    """
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Determine file type
    is_xml = input_path.suffix.lower() in ['.xml', '.marcxml']

    # Create output filenames
    output_filename = f"reconciled_{input_path.name}"
    report_filename = f"report_{input_path.stem}.txt"
    report_json_filename = f"report_{input_path.stem}.json"

    output_path = input_path.parent / output_filename
    report_path = input_path.parent / report_filename
    report_json_path = input_path.parent / report_json_filename

    print(f"\nProcessing: {input_path}")
    print(f"Output file: {output_path}")
    print(f"Report file: {report_path}")
    print(f"JSON report: {report_json_path}")
    print("=" * 70)

    # Statistics
    stats = {
        'total_records': 0,
        'total_fields_processed': 0,
        'fields_reconciled': 0,
        'fields_not_found': 0,
        'fields_poor_match': 0
    }

    # Detailed results for report
    results = []

    # Read records based on format
    if is_xml:
        with open(input_path, 'rb') as fh:
            records = parse_xml_to_array(fh)
        writer = XMLWriter(open(output_path, 'wb'))
    else:
        with open(input_path, 'rb') as fh:
            records = [record for record in MARCReader(fh)]
        writer = MARCWriter(open(output_path, 'wb'))

    # Process each record
    for record in records:
        stats['total_records'] += 1

        # Get system ID from 001
        system_id = record['001'].value() if record['001'] else 'NO_ID'

        # Process name fields
        for field_tag in FIELDS_TO_PROCESS:
            fields = record.get_fields(field_tag)

            for field in fields:
                stats['total_fields_processed'] += 1

                # Extract name
                name = extract_name_from_field(field)

                if not name:
                    continue

                # Reconcile
                result = reconcile_name(name)

                if result:
                    lccn_num, matched_label, distance = result
                    lccn = convert_lccn(lccn_num)

                    # Add $0 subfield
                    added = add_zero_subfield(field, lccn)

                    if distance <= MAX_LEVENSHTEIN_DISTANCE:
                        stats['fields_reconciled'] += 1
                        status = 'RECONCILED'
                        if distance > 0:
                            status += f' (distance: {distance})'
                    else:
                        stats['fields_poor_match'] += 1
                        status = f'POOR_MATCH (distance: {distance})'

                    results.append({
                        'record': stats['total_records'],
                        'system_id': system_id,
                        'field': field_tag,
                        'name': name,
                        'matched_label': matched_label,
                        'lccn': lccn,
                        'distance': distance,
                        'status': status
                    })
                else:
                    stats['fields_not_found'] += 1
                    results.append({
                        'record': stats['total_records'],
                        'system_id': system_id,
                        'field': field_tag,
                        'name': name,
                        'matched_label': None,
                        'lccn': None,
                        'distance': None,
                        'status': 'NOT_FOUND'
                    })

        # Write modified record
        writer.write(record)

    writer.close()

    # Generate report
    with open(report_path, 'w', encoding='utf-8') as report:
        report.write("=" * 70 + "\n")
        report.write("LCNAF MARC Reconciliation Report\n")
        report.write("=" * 70 + "\n\n")

        report.write("STATISTICS\n")
        report.write("-" * 70 + "\n")
        report.write(f"Total records processed:     {stats['total_records']:>10,}\n")
        report.write(f"Total fields processed:      {stats['total_fields_processed']:>10,}\n")
        report.write(f"Fields reconciled:           {stats['fields_reconciled']:>10,}\n")
        report.write(f"Fields not found:            {stats['fields_not_found']:>10,}\n")
        report.write(f"Fields with poor match:      {stats['fields_poor_match']:>10,}\n")

        if stats['total_fields_processed'] > 0:
            success_rate = (stats['fields_reconciled'] / stats['total_fields_processed']) * 100
            report.write(f"Success rate:                {success_rate:>9.1f}%\n")

        report.write("\n" + "=" * 70 + "\n\n")

        report.write("DETAILED RESULTS\n")
        report.write("-" * 70 + "\n\n")

        for result in results:
            report.write(f"Record: {result['record']} | System ID: {result['system_id']}\n")
            report.write(f"Field:  {result['field']}\n")
            report.write(f"Name:   {result['name']}\n")
            report.write(f"Status: {result['status']}\n")

            if result['lccn']:
                report.write(f"LCCN:   {result['lccn']}\n")
                if result['matched_label'] != result['name']:
                    report.write(f"Matched: {result['matched_label']}\n")

            report.write("\n")

    # Generate JSON report
    json_report = {
        'input_file': str(input_path),
        'output_file': str(output_path),
        'processing_date': None,  # Could add timestamp if needed
        'statistics': {
            'total_records': stats['total_records'],
            'total_fields_processed': stats['total_fields_processed'],
            'fields_reconciled': stats['fields_reconciled'],
            'fields_not_found': stats['fields_not_found'],
            'fields_poor_match': stats['fields_poor_match'],
            'success_rate': (stats['fields_reconciled'] / stats['total_fields_processed'] * 100) if stats['total_fields_processed'] > 0 else 0
        },
        'results': results
    }

    with open(report_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(json_report, json_file, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)
    print(f"\nTotal records processed:     {stats['total_records']:>10,}")
    print(f"Total fields processed:      {stats['total_fields_processed']:>10,}")
    print(f"Fields reconciled:           {stats['fields_reconciled']:>10,}")
    print(f"Fields not found:            {stats['fields_not_found']:>10,}")
    print(f"Fields with poor match:      {stats['fields_poor_match']:>10,}")

    if stats['total_fields_processed'] > 0:
        success_rate = (stats['fields_reconciled'] / stats['total_fields_processed']) * 100
        print(f"Success rate:                {success_rate:>9.1f}%")

    print(f"\nOutput written to:      {output_path}")
    print(f"Text report written to: {report_path}")
    print(f"JSON report written to: {report_json_path}")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python3 reconcile_marc.py /path/to/marcfile")
        print("\nSupports both Binary MARC (.mrc) and MARCXML (.xml) formats")
        sys.exit(1)

    input_file = sys.argv[1]

    print("=" * 70)
    print("LCNAF MARC Reconciliation Tool")
    print("=" * 70)
    print("\nLoading LCNAF data...")

    load_trie_data()

    print("\nData loaded successfully!")

    process_marc_file(input_file)


if __name__ == '__main__':
    main()
