import json
import msgpack
import gzip
import os

print("Loading cleaned JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json', 'r', encoding='utf-8') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup):,} entries")

# MessagePack encode
print("\nEncoding to MessagePack format...")
msgpack_data = msgpack.packb(lookup, use_bin_type=True)

print(f"MessagePack size: {len(msgpack_data) / 1024 / 1024:.2f} MB")

# Save uncompressed MessagePack
print("Writing uncompressed MessagePack file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.msgpack', 'wb') as f:
    f.write(msgpack_data)

# Gzip compress the MessagePack data
print("Compressing with gzip...")
compressed = gzip.compress(msgpack_data, compresslevel=9)

print(f"Compressed size: {len(compressed) / 1024 / 1024:.2f} MB")

# Save as .bin file (gzipped MessagePack, but using .bin extension for GitHub Pages)
print("Writing compressed file as .bin...")
with open('/Volumes/UsedGlum/naco/trie_lookup.msgpack.bin', 'wb') as f:
    f.write(compressed)

# Get original sizes for comparison
json_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup_lccn_smaller.json')

print("\n" + "="*70)
print("COMPRESSION RESULTS")
print("="*70)
print(f"Original JSON:           {json_size / 1024 / 1024:8.2f} MB")
print(f"MessagePack:             {len(msgpack_data) / 1024 / 1024:8.2f} MB")
print(f"MessagePack gzipped:     {len(compressed) / 1024 / 1024:8.2f} MB")
print(f"\nCompression ratio: {(1 - len(compressed)/json_size)*100:.1f}%")
print(f"Savings vs JSON: {(json_size - len(compressed)) / 1024 / 1024:.2f} MB")
print("="*70)

print("\nFiles created:")
print(f"  /Volumes/UsedGlum/naco/trie_lookup.msgpack (uncompressed)")
print(f"  /Volumes/UsedGlum/naco/trie_lookup.msgpack.bin (gzipped, for web)")

# Verify integrity by decoding
print("\nVerifying data integrity...")
decoded = msgpack.unpackb(msgpack_data, raw=False)
print(f"✓ Decoded {len(decoded):,} entries")
print(f"✓ First entry: {decoded[0]}")
print(f"✓ Last entry: {decoded[-1]}")

# Verify from compressed
print("\nVerifying compressed data...")
decompressed = gzip.decompress(compressed)
decoded_compressed = msgpack.unpackb(decompressed, raw=False)
print(f"✓ Decompressed and decoded {len(decoded_compressed):,} entries")
print(f"✓ Data matches: {decoded == decoded_compressed}")

print("\n✅ MessagePack encoding complete!")
