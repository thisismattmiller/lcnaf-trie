import sys
import math
import marisa_trie
import json
import msgpack
import gzip
import os

# trie = marisa_trie.Trie()

# print(trie.set('hello'))

# # dict/lookup = 11741073 469.33 MB

known_prefixes = {'nb':'1', 'nn':'2', 'no':'3', 'nr':'4', 'ns':'5', 'n':'6'}

# Threshold for corrupt data
CORRUPTION_THRESHOLD = 1000000000000  # 1 trillion


def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])




count = 0
all_keys = []
all_lccn = []
all_lccn_prefix = {}
label_dupe = {}
lookup = []
corrupt_count = 0
null_count = 0

with open('/Volumes/UsedGlum/naco/names.madsrdf.nt') as infile:

	for line in infile:


		if '# BEGIN' in line:
			lccn = line.split('/')[-1].strip()
			if '-' in lccn:
				# do not use the internal indriect geo headings
				lccn = "SKIP-SKIP-SKIP"
				lccn_new = None
			else:
				lccn_new = None
				for p in known_prefixes:
					if lccn.startswith(p):
						lccn_new = lccn.replace(p,known_prefixes[p])
						try:
							lccn_new = int(lccn_new)
						except:
							lccn_new = lccn

						break

			# print("lccn_new",lccn_new)



		if '<http://www.loc.gov/mads/rdf/v1#authoritativeLabel>' in line and lccn in line:

			# TODO Test for non-latin here

			label = line.split('> "')[1].strip()[:-3]

			# NO normalization - use the exact original label as the key
			key = label

			# Check for corrupt or null LCCN values
			if lccn_new is None:
				null_count += 1
				continue

			if isinstance(lccn_new, int) and lccn_new > CORRUPTION_THRESHOLD:
				corrupt_count += 1
				print(f"Skipping corrupt LCCN: {lccn_new} for label: {label}")
				continue

			lookup.append(None)

			# Store both the original label and the LCCN
			if key in label_dupe:
				label_dupe[key].append({'label': label, 'lccn_new':lccn_new})
			else:
				label_dupe[key] = [{'label': label, 'lccn_new':lccn_new}]

			count=count+1
			all_keys.append(key)
			all_lccn.append(lccn)
			if count % 500000 == 0:
				print(count)
				# print(len(trie), convert_size(sys.getsizeof(trie)))
				# trie.save('/Volumes/UsedGlum/naco/trie.marisa')


				# print(len(lookup), convert_size(sys.getsizeof(lookup)))


print(f"\nSkipped {null_count} null LCCNs")
print(f"Skipped {corrupt_count} corrupt LCCNs")

trie = marisa_trie.Trie(all_keys)
print(f'\nTrie length: {len(trie):,}')
trie.save('/Volumes/UsedGlum/naco/trie_unnormalized.marisa')
print('Trie saved to: /Volumes/UsedGlum/naco/trie_unnormalized.marisa')

# Gzip compress the trie file for web
print('Compressing trie file with gzip...')
with open('/Volumes/UsedGlum/naco/trie_unnormalized.marisa', 'rb') as f:
	trie_data = f.read()
trie_compressed = gzip.compress(trie_data, compresslevel=9)
with open('/Volumes/UsedGlum/naco/trie_unnormalized.marisa.bin', 'wb') as f:
	f.write(trie_compressed)
print(f'Trie compressed: {len(trie_data) / 1024 / 1024:.2f} MB -> {len(trie_compressed) / 1024 / 1024:.2f} MB')

# Build lookup array
# Since we're using exact labels as keys, there should be no duplicates
duplicate_count = 0

for x in trie:
	pos = trie[x]
	if len(label_dupe[x]) == 1:
		# Single entry - store just the LCCN
		lookup[pos] = label_dupe[x][0]['lccn_new']
	else:
		# Multiple entries (shouldn't happen with exact labels, but handle it)
		duplicate_count += 1
		lookup[pos] = label_dupe[x]

print(f'\nFound {duplicate_count} duplicate labels (unexpected with exact matching)')

# Save as JSON
print("\nWriting JSON lookup file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_unnormalized.json', 'w', encoding='utf-8') as f:
	json.dump(lookup, f, ensure_ascii=False)

json_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup_unnormalized.json')
print(f"JSON file size: {json_size / 1024 / 1024:.2f} MB")

# MessagePack encode lookup array
print("\nEncoding lookup to MessagePack format...")
msgpack_data = msgpack.packb(lookup, use_bin_type=True)
print(f"Lookup MessagePack size: {len(msgpack_data) / 1024 / 1024:.2f} MB")

# Save uncompressed MessagePack
print("Writing uncompressed MessagePack file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_unnormalized.msgpack', 'wb') as f:
	f.write(msgpack_data)

# Gzip compress the MessagePack data
print("Compressing lookup with gzip...")
compressed = gzip.compress(msgpack_data, compresslevel=9)
print(f"Lookup compressed size: {len(compressed) / 1024 / 1024:.2f} MB")

# Save as .bin file (gzipped MessagePack, but using .bin extension for web)
print("Writing compressed lookup file as .bin...")
with open('/Volumes/UsedGlum/naco/trie_lookup_unnormalized.msgpack.bin', 'wb') as f:
	f.write(compressed)

# Statistics
num_ints = sum(1 for x in lookup if isinstance(x, int))
num_lists = sum(1 for x in lookup if isinstance(x, list))
num_none = sum(1 for x in lookup if x is None)

print("\n" + "="*70)
print("RESULTS")
print("="*70)
print(f"Total entries:           {len(lookup):,}")
print(f"Single integers:         {num_ints:,}")
print(f"Lists (duplicates):      {num_lists:,}")
print(f"None values:             {num_none:,}")
print(f"\nOriginal JSON:           {json_size / 1024 / 1024:8.2f} MB")
print(f"MessagePack:             {len(msgpack_data) / 1024 / 1024:8.2f} MB")
print(f"MessagePack gzipped:     {len(compressed) / 1024 / 1024:8.2f} MB")
print(f"\nCompression ratio: {(1 - len(compressed)/json_size)*100:.1f}%")
print(f"Savings vs JSON: {(json_size - len(compressed)) / 1024 / 1024:.2f} MB")
print("="*70)

print("\nFiles created:")
print(f"  /Volumes/UsedGlum/naco/trie_unnormalized.marisa")
print(f"  /Volumes/UsedGlum/naco/trie_unnormalized.marisa.bin (gzipped, for web)")
print(f"  /Volumes/UsedGlum/naco/trie_lookup_unnormalized.json")
print(f"  /Volumes/UsedGlum/naco/trie_lookup_unnormalized.msgpack")
print(f"  /Volumes/UsedGlum/naco/trie_lookup_unnormalized.msgpack.bin (gzipped, for web)")

print("\n✅ Processing complete!")
