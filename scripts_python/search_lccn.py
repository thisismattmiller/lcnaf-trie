#!/usr/bin/env python3
"""
Search for an LCCN number in the lookup array and return its index position(s).
"""

import msgpack
import gzip

def load_lookup_data(filepath):
    """Load and decompress the MessagePack lookup file."""
    print(f"Loading lookup data from {filepath}...")
    with open(filepath, 'rb') as f:
        compressed = f.read()

    print("Decompressing...")
    decompressed = gzip.decompress(compressed)

    print("Decoding MessagePack...")
    data = msgpack.unpackb(decompressed, strict_map_key=False)

    print(f"Loaded {len(data):,} entries")
    return data

def search_lccn(lookup_data, target_lccn):
    """Search for LCCN and return all matching index positions."""
    matches = []

    for idx, value in enumerate(lookup_data):
        if value == target_lccn:
            matches.append(idx)
        elif isinstance(value, list) and target_lccn in value:
            matches.append(idx)

    return matches

def main():
    # Load the lookup data
    filepath = '/Volumes/UsedGlum/naco/trie_lookup.msgpack.bin'
    lookup_data = load_lookup_data(filepath)

    while True:
        # Get input from user
        user_input = input("\nEnter LCCN number to search (or 'quit' to exit): ").strip()

        if user_input.lower() in ('quit', 'exit', 'q'):
            print("Goodbye!")
            break

        try:
            lccn = int(user_input)
        except ValueError:
            print(f"Error: '{user_input}' is not a valid number")
            continue

        # Search for the LCCN
        print(f"Searching for LCCN {lccn:,}...")
        matches = search_lccn(lookup_data, lccn)

        if matches:
            print(f"\nFound {len(matches)} match(es):")
            for idx in matches:
                value = lookup_data[idx]
                print(f"  Index: {idx:,} -> Value: {value}")
        else:
            print(f"LCCN {lccn:,} not found in lookup data")

if __name__ == '__main__':
    main()
