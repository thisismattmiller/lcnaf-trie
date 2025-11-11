/**
 * MessagePack Lookup Decoder for LCNAF data
 *
 * Format: Gzipped MessagePack array
 *   - Array contains integers, lists, or null values
 *   - Index position matches trie IDs
 */

import pako from 'pako';
import { decode } from '@msgpack/msgpack';

export class LookupDecoder {
  constructor(dataArray) {
    this.data = dataArray;
  }

  /**
   * Get entry at specific index
   */
  get(index) {
    if (index < 0 || index >= this.data.length) {
      return null;
    }
    return this.data[index];
  }

  /**
   * Get number of entries
   */
  get length() {
    return this.data.length;
  }
}

/**
 * Load and initialize the lookup decoder
 */
export async function loadLookupData(progressCallback = null) {
  console.log('Loading compressed lookup data (52 MB download)...');

  const response = await fetch('/trie_lookup.msgpack.bin');

  if (!response.ok) {
    throw new Error('Failed to fetch lookup data file');
  }

  if (progressCallback) progressCallback(75);
  console.log('Downloaded, now decompressing...');

  const compressedData = await response.arrayBuffer();

  console.log(`Downloaded ${(compressedData.byteLength / 1024 / 1024).toFixed(2)} MB compressed`);

  if (progressCallback) progressCallback(85);

  // Decompress using pako
  const decompressed = pako.ungzip(new Uint8Array(compressedData));

  console.log(`Decompressed to ${(decompressed.byteLength / 1024 / 1024).toFixed(2)} MB`);

  if (progressCallback) progressCallback(95);

  // Decode MessagePack
  const dataArray = decode(decompressed);

  console.log(`Decoded ${dataArray.length.toLocaleString()} entries`);

  return new LookupDecoder(dataArray);
}
