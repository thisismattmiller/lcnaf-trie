import pickle
import json

# Load the pickle file
print("Loading pickle file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.pickle', 'rb') as handle:
    lookup = pickle.load(handle)

print(f"Loaded {len(lookup)} entries")

# Save as JSON
print("Writing JSON file...")
with open('/Volumes/UsedGlum/naco/trie_lookup.json', 'w', encoding='utf-8') as f:
    json.dump(lookup, f, ensure_ascii=False)

print("Done! JSON file created at: /Volumes/UsedGlum/naco/trie_lookup.json")
