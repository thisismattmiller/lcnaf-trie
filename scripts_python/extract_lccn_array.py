import json

# Load the JSON file
print("Loading JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.json', 'r', encoding='utf-8') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup)} entries")

# Process the data
print("Processing entries...")
processed = []

for i, entry in enumerate(lookup):
    if i % 1000000 == 0 and i > 0:
        print(f"  Processed {i:,} entries...")

    if entry is None:
        processed.append(None)
    elif isinstance(entry, int):
        # Keep integers as-is
        processed.append(entry)
    elif isinstance(entry, list):
        # Extract lccn_new values from list of dicts
        lccn_list = [item['lccn_new'] for item in entry]
        processed.append(lccn_list)
    else:
        # Shouldn't happen, but keep as-is
        processed.append(entry)

# Save as JSON
print("Writing processed JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn.json', 'w', encoding='utf-8') as f:
    json.dump(processed, f, ensure_ascii=False)

print(f"Done! Processed {len(processed)} entries")
print("File created at: /Volumes/UsedGlum/naco/trie_lookup_lccn.json")

# Show some statistics
num_ints = sum(1 for x in processed if isinstance(x, int))
num_lists = sum(1 for x in processed if isinstance(x, list))
num_none = sum(1 for x in processed if x is None)

print(f"\nStatistics:")
print(f"  Integers: {num_ints:,}")
print(f"  Lists: {num_lists:,}")
print(f"  None values: {num_none:,}")
