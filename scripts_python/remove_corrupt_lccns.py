import json

# Threshold for corrupt data
CORRUPTION_THRESHOLD = 1000000000000  # 1 trillion
REMOVE_NULLS = True  # Set to True to remove trailing nulls

print("Loading JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json', 'r', encoding='utf-8') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup):,} entries")

# Clean the data
print("Cleaning corrupt LCCN values and nulls...")
cleaned = []
corruption_count = 0
null_count = 0
corruption_details = []

for idx, entry in enumerate(lookup):
    if idx % 1000000 == 0 and idx > 0:
        print(f"  Processed {idx:,} entries...")

    if entry is None:
        # Skip nulls if removing them
        if REMOVE_NULLS:
            null_count += 1
            continue
        else:
            cleaned.append(None)
    elif isinstance(entry, int):
        # Check if single integer is corrupt
        if entry > CORRUPTION_THRESHOLD:
            corruption_count += 1
            corruption_details.append({
                'index': idx,
                'value': entry,
                'type': 'single_int'
            })
            # Replace with None
            cleaned.append(None)
        else:
            cleaned.append(entry)
    elif isinstance(entry, str):
        # Keep strings as-is (already marked as malformed)
        cleaned.append(entry)
    elif isinstance(entry, list):
        # Clean list entries
        cleaned_list = []
        for item in entry:
            if isinstance(item, list) and len(item) >= 2:
                lccn = item[0]
                label = item[1]

                # Check if LCCN is corrupt
                if isinstance(lccn, int) and lccn > CORRUPTION_THRESHOLD:
                    corruption_count += 1
                    corruption_details.append({
                        'index': idx,
                        'value': lccn,
                        'label': label,
                        'type': 'list_item'
                    })
                    # Skip this item (don't add to cleaned list)
                else:
                    cleaned_list.append(item)
            else:
                # Keep other items as-is
                cleaned_list.append(item)

        # If list is now empty, store None; if only 1 item, extract the LCCN as single int
        if len(cleaned_list) == 0:
            cleaned.append(None)
        elif len(cleaned_list) == 1:
            # Single item - extract just the LCCN number
            cleaned.append(cleaned_list[0][0])
        else:
            cleaned.append(cleaned_list)
    else:
        # Keep anything else as-is
        cleaned.append(entry)

print(f"\nFound and removed {corruption_count} corrupt LCCN values")
print(f"Removed {null_count:,} null values")

print("\nCorrupted entries:")
for item in corruption_details:
    if item['type'] == 'single_int':
        print(f"  Index {item['index']:,}: {item['value']:,} (single int) -> removed")
    else:
        print(f"  Index {item['index']:,}: {item['value']:,} (label: \"{item['label']}\") -> removed from list")

# Save cleaned data
print("\nWriting cleaned JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned, f, ensure_ascii=False)

# Get file size
import os
new_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json')
original_size = 148.33  # MB from before

print(f"\nDone! Cleaned file saved.")
print(f"Original size: {original_size:.2f} MB")
print(f"New size: {new_size / 1024 / 1024:.2f} MB")
print(f"Savings: {original_size - (new_size / 1024 / 1024):.2f} MB")
print(f"\nRemoved:")
print(f"  Corrupt values: {corruption_count}")
print(f"  Null values: {null_count:,}")

# Statistics
num_ints = sum(1 for x in cleaned if isinstance(x, int))
num_lists = sum(1 for x in cleaned if isinstance(x, list))
num_none = sum(1 for x in cleaned if x is None)

print(f"\nFinal statistics:")
print(f"  Total entries:    {len(cleaned):,}")
print(f"  Single integers:  {num_ints:,}")
print(f"  Lists:            {num_lists:,}")
print(f"  None values:      {num_none:,}")
