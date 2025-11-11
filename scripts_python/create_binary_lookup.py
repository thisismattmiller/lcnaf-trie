import json
import struct
import gzip

"""
Binary format for LCNAF lookup data:
- Maintains index positions (index N in array → byte offset calculation)
- Each entry has a type byte followed by data
- Supports: null, single int, list of ints, or string (for malformed data)

Entry format:
  Type byte:
    0x00 = null
    0x01 = single integer (followed by 5 bytes for the int value)
    0x02 = list of integers (followed by 1 byte count + 5 bytes per int)
    0x03 = string (followed by 1 byte length + UTF-8 bytes)

Integer encoding: 8 bytes (64 bits) to handle all values safely
"""

def encode_int64(value):
    """Encode an integer as 8 bytes (64 bits)"""
    if value is None:
        return b'\x00\x00\x00\x00\x00\x00\x00\x00'
    if not isinstance(value, int):
        # Return marker for invalid data - will be handled as string
        return None
    # Use unsigned 64-bit if within range, otherwise truncate
    if value < 0 or value >= 2**64:
        # Handle overflow - store as 0 (corrupted data marker)
        return b'\x00\x00\x00\x00\x00\x00\x00\x00'
    return struct.pack('>Q', value)

def decode_int64(data):
    """Decode 8 bytes to an integer"""
    return struct.unpack('>Q', data)[0]

def encode_entry(entry):
    """Encode a single lookup entry"""
    if entry is None:
        # Type 0x00: null
        return b'\x00'
    elif isinstance(entry, str):
        # Type 0x03: string (malformed data)
        encoded_str = entry.encode('utf-8')
        if len(encoded_str) > 255:
            encoded_str = encoded_str[:255]  # Truncate if too long
        return b'\x03' + struct.pack('B', len(encoded_str)) + encoded_str
    elif isinstance(entry, int):
        # Type 0x01: single integer
        return b'\x01' + encode_int64(entry)
    elif isinstance(entry, list):
        # Type 0x02: list of integers (or strings)
        count = len(entry)
        if count > 255:
            raise ValueError(f"List too long: {count} items")
        data = struct.pack('B', count)
        for val in entry:
            if isinstance(val, str):
                # Handle string in list - encode as mini-entry
                encoded_str = val.encode('utf-8')
                if len(encoded_str) > 255:
                    encoded_str = encoded_str[:255]
                # Use a marker: 0xFF followed by length and string
                data += b'\xff' + struct.pack('B', len(encoded_str)) + encoded_str
            else:
                encoded_int = encode_int64(val)
                if encoded_int is None:
                    # Shouldn't happen, but handle it
                    data += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                else:
                    data += encoded_int
        return b'\x02' + data
    else:
        raise ValueError(f"Unexpected type: {type(entry)}")

# Load JSON
print("Loading JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup_lccn.json', 'r') as f:
    lookup = json.load(f)

print(f"Loaded {len(lookup):,} entries")

# Encode to binary
print("Encoding to binary format...")
binary_data = bytearray()
entry_offsets = []  # Track offset of each entry for random access

for i, entry in enumerate(lookup):
    if i % 1000000 == 0 and i > 0:
        print(f"  Encoded {i:,} entries... ({len(binary_data):,} bytes)")

    entry_offsets.append(len(binary_data))
    encoded = encode_entry(entry)
    binary_data.extend(encoded)

print(f"\nTotal binary size: {len(binary_data):,} bytes ({len(binary_data)/1024/1024:.2f} MB)")

# Save uncompressed binary
print("Writing uncompressed binary file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.bin', 'wb') as f:
    f.write(binary_data)

# Save gzipped version
print("Writing gzip compressed file...")
with gzip.open('/Volumes/UsedGlum/naco/trie_lookup.bin.gz', 'wb', compresslevel=9) as f:
    f.write(binary_data)

# Save offset index for random access (optional - for O(1) access)
print("Writing offset index...")
offset_data = struct.pack(f'>{len(entry_offsets)}I', *entry_offsets)
with gzip.open('/Volumes/UsedGlum/naco/trie_lookup_offsets.bin.gz', 'wb', compresslevel=9) as f:
    f.write(offset_data)

# Statistics
import os
bin_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup.bin')
gz_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup.bin.gz')
offset_size = os.path.getsize('/Volumes/UsedGlum/naco/trie_lookup_offsets.bin.gz')

print("\n" + "="*60)
print("COMPRESSION RESULTS")
print("="*60)
print(f"Original JSON:        137 MB")
print(f"Binary uncompressed:  {bin_size/1024/1024:.2f} MB")
print(f"Binary gzipped:       {gz_size/1024/1024:.2f} MB")
print(f"Offset index (gz):    {offset_size/1024/1024:.2f} MB")
print(f"Total download:       {(gz_size+offset_size)/1024/1024:.2f} MB")
print(f"Compression ratio:    {(1 - gz_size/(137*1024*1024))*100:.1f}%")
print("="*60)

# Verification test
print("\nVerifying encoding/decoding...")
test_indices = [0, 1000, 10000, 100000, 1000000]
for idx in test_indices:
    if idx < len(lookup):
        offset = entry_offsets[idx]

        # Read and decode
        type_byte = binary_data[offset]
        original = lookup[idx]

        if type_byte == 0x00:
            decoded = None
        elif type_byte == 0x01:
            decoded = decode_int64(binary_data[offset+1:offset+9])
        elif type_byte == 0x02:
            count = binary_data[offset+1]
            decoded = []
            for i in range(count):
                pos = offset + 2 + (i * 8)
                decoded.append(decode_int64(binary_data[pos:pos+8]))
        elif type_byte == 0x03:
            length = binary_data[offset+1]
            decoded = binary_data[offset+2:offset+2+length].decode('utf-8')

        match = "✓" if decoded == original else "✗"
        print(f"  Index {idx}: {match} Original={original}, Decoded={decoded}")

print("\n✓ Done! Files created:")
print("  - /Volumes/UsedGlum/naco/trie_lookup.bin")
print("  - /Volumes/UsedGlum/naco/trie_lookup.bin.gz (use this for web)")
print("  - /Volumes/UsedGlum/naco/trie_lookup_offsets.bin.gz (use this for web)")
