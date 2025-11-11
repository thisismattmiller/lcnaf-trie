import json

print("Loading JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json', 'r', encoding='utf-8') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup):,} entries\n")

# Data quality checks
issues = {
    'nulls': [],
    'very_large': [],
    'strings': [],
    'invalid_format': [],
    'large_lists': []
}

# Define thresholds
MAX_NORMAL_LCCN = 100000000000  # 100 billion
VERY_LARGE_LCCN = 1000000000000  # 1 trillion

print("Analyzing data quality issues...\n")

for idx, entry in enumerate(lookup):
    if idx % 1000000 == 0 and idx > 0:
        print(f"  Analyzed {idx:,} entries...")

    # Check for nulls
    if entry is None:
        if len(issues['nulls']) < 20:  # Keep first 20
            issues['nulls'].append(idx)

    # Check single integers
    elif isinstance(entry, int):
        if entry > VERY_LARGE_LCCN:
            issues['very_large'].append({
                'index': idx,
                'value': entry,
                'type': 'single_int'
            })

    # Check strings (malformed data)
    elif isinstance(entry, str):
        issues['strings'].append({
            'index': idx,
            'value': entry
        })

    # Check lists
    elif isinstance(entry, list):
        # Check if list is very long
        if len(entry) > 10:
            issues['large_lists'].append({
                'index': idx,
                'count': len(entry),
                'sample': entry[:3]
            })

        # Check each item in list
        for item in entry:
            if isinstance(item, list) and len(item) >= 2:
                # Format: [lccn, label]
                lccn = item[0]
                if isinstance(lccn, int) and lccn > VERY_LARGE_LCCN:
                    issues['very_large'].append({
                        'index': idx,
                        'value': lccn,
                        'label': item[1] if len(item) > 1 else None,
                        'type': 'list_item'
                    })
            else:
                # Invalid format
                if len(issues['invalid_format']) < 20:
                    issues['invalid_format'].append({
                        'index': idx,
                        'item': item
                    })

print("\n" + "="*80)
print("DATA QUALITY REPORT")
print("="*80)

# Report nulls
print(f"\n1. NULL VALUES: {len(issues['nulls']):,} found")
if issues['nulls']:
    print(f"   First 20 indices with null values:")
    for i, idx in enumerate(issues['nulls'][:20], 1):
        print(f"     {i}. Index {idx:,}")

# Report strings
print(f"\n2. STRING VALUES (malformed data): {len(issues['strings']):,} found")
if issues['strings']:
    print(f"   All string values:")
    for item in issues['strings']:
        print(f"     Index {item['index']:,}: \"{item['value']}\"")

# Report very large numbers
print(f"\n3. VERY LARGE LCCN VALUES (> 1 trillion): {len(issues['very_large']):,} found")
if issues['very_large']:
    print(f"   Details:")
    for item in issues['very_large'][:50]:  # Show first 50
        if item['type'] == 'single_int':
            print(f"     Index {item['index']:,}: {item['value']:,} (single int)")
        else:
            label = item.get('label', 'N/A')
            print(f"     Index {item['index']:,}: {item['value']:,} (label: \"{label}\")")

# Report large lists
print(f"\n4. LARGE LISTS (>10 items): {len(issues['large_lists']):,} found")
if issues['large_lists']:
    print(f"   Top 20 largest:")
    sorted_lists = sorted(issues['large_lists'], key=lambda x: x['count'], reverse=True)
    for item in sorted_lists[:20]:
        print(f"     Index {item['index']:,}: {item['count']} items - Sample: {item['sample'][:2]}")

# Report invalid format
print(f"\n5. INVALID FORMAT: {len(issues['invalid_format']):,} found")
if issues['invalid_format']:
    print(f"   First 20 invalid entries:")
    for item in issues['invalid_format'][:20]:
        print(f"     Index {item['index']:,}: {item['item']}")

# Statistics on LCCN value ranges
print(f"\n" + "="*80)
print("LCCN VALUE STATISTICS")
print("="*80)

all_lccns = []
for entry in lookup:
    if isinstance(entry, int):
        all_lccns.append(entry)
    elif isinstance(entry, list):
        for item in entry:
            if isinstance(item, list) and len(item) >= 1:
                if isinstance(item[0], int):
                    all_lccns.append(item[0])

if all_lccns:
    all_lccns.sort()
    print(f"Total LCCN values: {len(all_lccns):,}")
    print(f"Minimum: {all_lccns[0]:,}")
    print(f"Maximum: {all_lccns[-1]:,}")
    print(f"Median: {all_lccns[len(all_lccns)//2]:,}")

    # Show distribution
    ranges = [
        (0, 100000000, "< 100M"),
        (100000000, 1000000000, "100M - 1B"),
        (1000000000, 10000000000, "1B - 10B"),
        (10000000000, 100000000000, "10B - 100B"),
        (100000000000, 1000000000000, "100B - 1T"),
        (1000000000000, float('inf'), "> 1T (suspicious)")
    ]

    print(f"\nValue distribution:")
    for min_val, max_val, label in ranges:
        count = sum(1 for x in all_lccns if min_val <= x < max_val)
        if count > 0:
            percentage = (count / len(all_lccns)) * 100
            print(f"  {label:20s}: {count:10,} ({percentage:5.2f}%)")

print("\n" + "="*80)
print("QA COMPLETE")
print("="*80)
