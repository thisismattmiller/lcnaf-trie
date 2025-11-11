const fs = require('fs');
const path = require('path');
const pako = require('pako');
const MarisaModule = require('../public/marisa.js');

async function loadMarisaTrie(trieFilePath) {
  // Initialize the WASM module
  const Module = await MarisaModule();

  // Read the compressed .marisa.bin file and decompress it
  const compressedData = fs.readFileSync(trieFilePath);
  const trieData = pako.ungzip(compressedData);

  const fileName = '/trie.marisa';
  Module.FS.writeFile(fileName, trieData);

  // Create a trie instance and load the file
  const trie = new Module.MarisaTrie();
  const loaded = trie.load(fileName);

  if (!loaded) {
    throw new Error('Failed to load MARISA trie file');
  }

  return { Module, trie };
}

async function main() {
  const trieFilePath = path.join(__dirname, '../public/trie.marisa.bin');

  console.log('Loading MARISA trie from public/trie.marisa.bin...');
  const { Module, trie } = await loadMarisaTrie(trieFilePath);

  console.log(`\n✓ Trie loaded successfully!`);
  console.log(`  Number of keys: ${trie.size().toLocaleString()}`);
  console.log(`  Number of nodes: ${trie.numNodes().toLocaleString()}`);

  // Example: Lookup a key
  console.log('\n--- Lookup Example ---');
  const testKey = 'example';
  const id = trie.lookup(testKey);
  console.log(`Lookup "${testKey}": ${id === -1 ? 'Not found' : `ID ${id}`}`);

  // Example: Reverse lookup (get key by ID)
  console.log('\n--- Reverse Lookup Example (first 10 keys) ---');
  for (let i = 0; i < Math.min(10, trie.size()); i++) {
    const key = trie.reverseLookup(i);
    console.log(`  ID ${i}: ${key}`);
  }

  // Example: Common prefix search
  console.log('\n--- Common Prefix Search Example ---');
  const prefixQuery = 'test';
  const prefixResults = trie.commonPrefixSearch(prefixQuery);
  console.log(`Common prefix search for "${prefixQuery}":`,
              prefixResults.length > 0 ? prefixResults.length + ' results' : 'No results');
  if (prefixResults.length > 0 && prefixResults.length <= 5) {
    for (let i = 0; i < prefixResults.length; i++) {
      console.log(`  - ${prefixResults[i]}`);
    }
  }

  // Example: Predictive search
  console.log('\n--- Predictive Search Example ---');
  const predictQuery = 'abc';
  const predictResults = trie.predictiveSearch(predictQuery);
  console.log(`Predictive search for "${predictQuery}":`,
              predictResults.length > 0 ? predictResults.length + ' results' : 'No results');
  if (predictResults.length > 0 && predictResults.length <= 5) {
    for (let i = 0; i < predictResults.length; i++) {
      console.log(`  - ${predictResults[i]}`);
    }
  }

  console.log('\n--- Usage Examples ---');
  console.log('To lookup a specific key:');
  console.log('  const id = trie.lookup("your-key");');
  console.log('\nTo get a key by ID:');
  console.log('  const key = trie.reverseLookup(id);');
  console.log('\nTo export all keys (WARNING: may be slow for large tries):');
  console.log('  const allKeys = trie.getAllKeys();');
  console.log('  console.log(allKeys);');
}

// Run the example
if (require.main === module) {
  main().catch(console.error);
}

// Export for use as a module
module.exports = { loadMarisaTrie };
