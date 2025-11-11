#!/usr/bin/env python3
"""
Create MARC21 test files (both Binary and XML formats) from source data.
Extracts records with 100, 110, 700, or 710 fields for testing.
"""

import os
from pymarc import MARCReader, XMLWriter
import xml.etree.ElementTree as ET

# Source files
BINARY_SOURCE = '/Volumes/Lately/lcmarc/BooksAll.2016.part01.utf8'
XML_SOURCE = '/Users/m/Downloads/2020445551_2019/Books.All.2019.combined.part01.xml'

# Output directory
OUTPUT_DIR = '/Users/m/git/lcnaf-trie/marc_test_files'


def has_name_fields(record):
    """Check if record has 100, 110, 700, or 710 fields."""
    name_fields = ['100', '110', '700', '710']
    return any(record.get_fields(tag) for tag in name_fields)


def has_woolf_in_100(record):
    """Check if record has 'Woolf, Virginia' in 100 field."""
    field_100 = record.get_fields('100')
    if field_100:
        for field in field_100:
            subfield_a = field.get_subfields('a')
            if subfield_a:
                name = subfield_a[0]
                if 'Woolf, Virginia,' in name:
                    return True
    return False


def extract_from_binary(source_file, output_base, max_records=1000):
    """Extract records from binary MARC file."""
    print(f"Reading binary MARC from: {source_file}")

    records = []
    woolf_record = None

    with open(source_file, 'rb') as fh:
        reader = MARCReader(fh, to_unicode=True, force_utf8=True)

        for record in reader:
            if not record:
                continue

            # Look for Woolf record for single file example
            if woolf_record is None and has_woolf_in_100(record):
                woolf_record = record
                print(f"  Found Woolf record for single file example!")
                field_100 = record.get_fields('100')[0]
                subfield_a = field_100.get_subfields('a')[0]
                print(f"    100$a: {subfield_a}")

            if has_name_fields(record):
                records.append(record)

                # Show progress periodically
                if len(records) % 100 == 0:
                    print(f"  Collected {len(records)} records...")

                # Show first few records in detail
                if len(records) <= 5:
                    name_fields = []
                    for tag in ['100', '110', '700', '710']:
                        for field in record.get_fields(tag):
                            subfield_a = field.get_subfields('a')
                            if subfield_a:
                                name_fields.append(f"{tag}: {subfield_a[0][:50]}")

                    if name_fields:
                        print(f"  Found record #{len(records)}: {', '.join(name_fields[:2])}")

                if len(records) >= max_records:
                    break

    print(f"Collected {len(records)} records with name fields")

    # Write single record file - use Woolf record if found, otherwise first record
    if woolf_record:
        single_file = f"{output_base}_single.mrc"
        with open(single_file, 'wb') as out:
            out.write(woolf_record.as_marc())
        print(f"✓ Created: {single_file} (Woolf record)")
    elif records:
        single_file = f"{output_base}_single.mrc"
        with open(single_file, 'wb') as out:
            out.write(records[0].as_marc())
        print(f"✓ Created: {single_file}")

    # Write multiple records file
    if len(records) >= 3:
        multi_file = f"{output_base}_multiple.mrc"
        with open(multi_file, 'wb') as out:
            for record in records:  # All records
                out.write(record.as_marc())
        print(f"✓ Created: {multi_file} ({len(records)} records)")

    return records


def extract_from_xml(source_file, output_base, max_records=1000):
    """Extract records from MARCXML file."""
    print(f"Reading MARCXML from: {source_file}")

    # Parse XML incrementally to handle large files with multiple collections
    ns = {'marc': 'http://www.loc.gov/MARC21/slim'}
    selected_records = []
    woolf_record = None

    # Use iterparse to handle large files
    context = ET.iterparse(source_file, events=('end',))

    for event, elem in context:
        if elem.tag == '{http://www.loc.gov/MARC21/slim}record':
            # Check for Woolf in 100 field for single file example
            if woolf_record is None:
                for datafield in elem.findall('marc:datafield', ns):
                    if datafield.get('tag') == '100':
                        for subfield in datafield.findall('marc:subfield', ns):
                            if subfield.get('code') == 'a' and subfield.text and 'Woolf, Virginia' in subfield.text:
                                woolf_record = ET.fromstring(ET.tostring(elem))
                                print(f"  Found Woolf record for single file example!")
                                print(f"    100$a: {subfield.text}")
                                break

            # Check for 100, 110, 700, or 710 fields
            has_names = False
            name_info = []

            for datafield in elem.findall('marc:datafield', ns):
                tag = datafield.get('tag')
                if tag in ['100', '110', '700', '710']:
                    has_names = True
                    # Get subfield 'a' for display
                    for subfield in datafield.findall('marc:subfield', ns):
                        if subfield.get('code') == 'a':
                            name_info.append(f"{tag}: {subfield.text[:50] if subfield.text else ''}")
                            break

            if has_names:
                # Store a copy of the element
                selected_records.append(ET.fromstring(ET.tostring(elem)))

                # Show progress periodically
                if len(selected_records) % 100 == 0:
                    print(f"  Collected {len(selected_records)} records...")

                # Show first few records in detail
                if name_info and len(selected_records) <= 5:
                    print(f"  Found record #{len(selected_records)}: {', '.join(name_info[:2])}")

                if len(selected_records) >= max_records:
                    break

            # Clear element to save memory
            elem.clear()

    print(f"Collected {len(selected_records)} records with name fields")

    # Create new XML collection for single record - use Woolf if found
    if woolf_record:
        single_file = f"{output_base}_single.xml"
        collection = ET.Element('{http://www.loc.gov/MARC21/slim}collection')
        collection.set('xmlns', 'http://www.loc.gov/MARC21/slim')
        collection.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        collection.set('xsi:schemaLocation',
                      'http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd')
        collection.append(woolf_record)

        tree = ET.ElementTree(collection)
        ET.indent(tree, space='  ')
        tree.write(single_file, encoding='utf-8', xml_declaration=True)
        print(f"✓ Created: {single_file} (Woolf record)")
    elif selected_records:
        single_file = f"{output_base}_single.xml"
        collection = ET.Element('{http://www.loc.gov/MARC21/slim}collection')
        collection.set('xmlns', 'http://www.loc.gov/MARC21/slim')
        collection.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        collection.set('xsi:schemaLocation',
                      'http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd')
        collection.append(selected_records[0])

        tree = ET.ElementTree(collection)
        ET.indent(tree, space='  ')
        tree.write(single_file, encoding='utf-8', xml_declaration=True)
        print(f"✓ Created: {single_file}")

    # Create new XML collection for multiple records
    if len(selected_records) >= 3:
        multi_file = f"{output_base}_multiple.xml"
        collection = ET.Element('{http://www.loc.gov/MARC21/slim}collection')
        collection.set('xmlns', 'http://www.loc.gov/MARC21/slim')
        collection.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        collection.set('xsi:schemaLocation',
                      'http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd')

        for record in selected_records:  # All records
            collection.append(record)

        tree = ET.ElementTree(collection)
        ET.indent(tree, space='  ')
        tree.write(multi_file, encoding='utf-8', xml_declaration=True)
        print(f"✓ Created: {multi_file} ({len(selected_records)} records)")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Creating MARC21 Test Files")
    print("=" * 60)

    # Extract from binary MARC
    print("\n--- Processing Binary MARC ---")
    try:
        extract_from_binary(
            BINARY_SOURCE,
            os.path.join(OUTPUT_DIR, 'test_binary'),
            max_records=10000
        )
    except Exception as e:
        print(f"Error processing binary MARC: {e}")

    # Extract from XML MARC
    print("\n--- Processing MARCXML ---")
    try:
        extract_from_xml(
            XML_SOURCE,
            os.path.join(OUTPUT_DIR, 'test_xml'),
            max_records=10000
        )
    except Exception as e:
        print(f"Error processing MARCXML: {e}")

    print("\n" + "=" * 60)
    print(f"Test files created in: {OUTPUT_DIR}")
    print("=" * 60)

    # List created files
    print("\nCreated files:")
    for filename in sorted(os.listdir(OUTPUT_DIR)):
        filepath = os.path.join(OUTPUT_DIR, filename)
        size = os.path.getsize(filepath)
        print(f"  {filename:<30} ({size:,} bytes)")


if __name__ == '__main__':
    main()
