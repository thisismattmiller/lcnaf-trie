import json

# Load the JSON file
print("Loading JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.json', 'r', encoding='utf-8') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup):,} entries")

# Process the data to compact format
print("Converting to compact format...")
compacted = []

for i, entry in enumerate(lookup):
    if i % 1000000 == 0 and i > 0:
        print(f"  Processed {i:,} entries...")

    if entry is None:
        # Keep None as-is
        compacted.append(None)
    elif isinstance(entry, int):
        # Keep single integers as-is
        compacted.append(entry)
    elif isinstance(entry, str):
        # Keep strings as-is (malformed data)
        compacted.append(entry)
    elif isinstance(entry, list):
        # Convert list of dicts to list of [lccn, label] pairs
        pairs = []
        for item in entry:
            if isinstance(item, dict):
                # Extract lccn_new and label
                lccn = item.get('lccn_new')
                label = item.get('label', '')
                pairs.append([lccn, label])
            else:
                # Shouldn't happen, but keep as-is
                pairs.append(item)
        compacted.append(pairs)
    else:
        # Keep anything else as-is
        compacted.append(entry)

# Save as JSON
print("Writing compacted JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json', 'w', encoding='utf-8') as f:
    json.dump(compacted, f, ensure_ascii=False)

# Get file sizes for comparison
import os
original_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup.json')
new_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json')

print(f"\nDone! File created at: /Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json")
print(f"\nSize comparison:")
print(f"  Original:   {original_size / 1024 / 1024:.2f} MB")
print(f"  Compacted:  {new_size / 1024 / 1024:.2f} MB")
print(f"  Savings:    {(1 - new_size/original_size) * 100:.1f}%")

# Show some statistics
num_ints = sum(1 for x in compacted if isinstance(x, int))
num_lists = sum(1 for x in compacted if isinstance(x, list))
num_none = sum(1 for x in compacted if x is None)
num_strings = sum(1 for x in compacted if isinstance(x, str))

print(f"\nStatistics:")
print(f"  Single integers:  {num_ints:,}")
print(f"  Lists (duplicates): {num_lists:,}")
print(f"  None values:      {num_none:,}")
print(f"  Strings:          {num_strings:,}")
