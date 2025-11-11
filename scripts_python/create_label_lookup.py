#!/usr/bin/env python3
"""
Create a MessagePack lookup file where keys are LCCN (numeric) and values are labels.
This is an alternative approach to the trie-based lookup to compare file sizes.
"""

import sys
import msgpack

known_prefixes = {'nb':'1', 'nn':'2', 'no':'3', 'nr':'4', 'ns':'5', 'n':'6'}

# Threshold for corrupt data (from remove_corrupt_lccns.py)
CORRUPTION_THRESHOLD = 1000000000000  # 1 trillion

count = 0
label_lookup = {}
skipped_corrupt = 0
skipped_dash = 0

print("Opening names.madsrdf.nt...")
print("Processing lines...\n")

with open('/Volumes/UsedGlum/naco/names.madsrdf.nt') as infile:
    lccn = None
    line_count = 0

    for line in infile:
        line_count += 1
        if line_count % 100000 == 0:
            print(f"Processed {line_count:,} lines, {count:,} labels found, {len(label_lookup):,} unique LCCNs, {skipped_corrupt:,} corrupt, {skipped_dash:,} with dashes")

        if '# BEGIN' in line:
            lccn = line.split('/')[-1].strip()

            # Skip indirect geo headings with dashes
            if '-' in lccn:
                skipped_dash += 1
                lccn = None
                continue

            # Convert prefix to number
            for p in known_prefixes:
                if lccn.startswith(p):
                    lccn_new = lccn.replace(p, known_prefixes[p])
                    try:
                        lccn = int(lccn_new)
                    except:
                        lccn = None
                        break

                    # Check for corrupt LCCN (too large)
                    if lccn and lccn > CORRUPTION_THRESHOLD:
                        skipped_corrupt += 1
                        lccn = None
                    break

        if lccn and '<http://www.loc.gov/mads/rdf/v1#authoritativeLabel>' in line:
            # Extract label - use raw label without normalization
            label = line.split('> "')[1].strip()[:-3]

            # Store in lookup: key = LCCN (int), value = label (string)
            # If duplicate LCCN, store as list
            if lccn in label_lookup:
                # Convert to list if needed
                if not isinstance(label_lookup[lccn], list):
                    prev_value = label_lookup[lccn]
                    label_lookup[lccn] = [prev_value]
                label_lookup[lccn].append(label)
            else:
                label_lookup[lccn] = label

            count += 1

            lccn = None  # Reset for next record

print(f"\n{'='*60}")
print(f"Processing complete!")
print(f"Total labels processed: {count:,}")
print(f"Unique LCCNs: {len(label_lookup):,}")
print(f"Skipped corrupt LCCNs: {skipped_corrupt:,}")
print(f"Skipped dash LCCNs: {skipped_dash:,}")
print(f"{'='*60}")

# Write MessagePack file
output_path = '/Volumes/UsedGlum/naco/label_lookup.msgpack'
print(f"\nPacking data with MessagePack...")

packed = msgpack.packb(label_lookup, use_bin_type=True)
packed_size_mb = len(packed) / (1024**2)
print(f"Packed size: {len(packed):,} bytes ({packed_size_mb:.2f} MB)")

print(f"Writing to {output_path}...")
with open(output_path, 'wb') as f:
    f.write(packed)

import os
file_size = os.path.getsize(output_path)
print(f"\n{'='*60}")
print(f"File written successfully!")
print(f"Final file size: {file_size:,} bytes ({file_size / (1024**2):.2f} MB)")
print(f"{'='*60}")
print("Done!")
