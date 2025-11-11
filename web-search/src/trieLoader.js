import pako from 'pako';
import * as msgpack from '@msgpack/msgpack';

export class TrieLoader {
    constructor() {
        this.trie = null;
        this.lookup = null;
        this.Module = null;
    }

    async loadWithProgress(onProgress) {
        try {
            // Load WASM Module
            onProgress('trie', 0, 'Initializing WASM module...');

            // Load the marisa.js script dynamically
            const script = document.createElement('script');
            // Use relative path based on current page location
            const basePath = import.meta.env.BASE_URL || './';
            script.src = `${basePath}marisa.js`;

            await new Promise((resolve, reject) => {
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });

            // MarisaModule is now available globally
            this.Module = await window.MarisaModule();
            onProgress('trie', 10, 'WASM module loaded');

            // Load and decompress trie
            onProgress('trie', 20, 'Downloading trie structure...');
            const trieResponse = await fetch(`${basePath}trie_unnormalized.marisa.bin`);
            const trieTotal = parseInt(trieResponse.headers.get('content-length') || '0');

            const trieReader = trieResponse.body.getReader();
            const trieChunks = [];
            let trieReceived = 0;

            while (true) {
                const { done, value } = await trieReader.read();
                if (done) break;

                trieChunks.push(value);
                trieReceived += value.length;

                if (trieTotal > 0) {
                    const percent = 20 + Math.floor((trieReceived / trieTotal) * 30);
                    onProgress('trie', percent, `Downloading... ${this.formatBytes(trieReceived)}`);
                }
            }

            onProgress('trie', 50, 'Decompressing trie...');
            const trieCompressed = new Uint8Array(trieReceived);
            let offset = 0;
            for (const chunk of trieChunks) {
                trieCompressed.set(chunk, offset);
                offset += chunk.length;
            }

            const trieData = pako.ungzip(trieCompressed);
            onProgress('trie', 70, 'Loading trie into memory...');

            // Write to WASM filesystem and load
            const fileName = '/trie.marisa';
            this.Module.FS.writeFile(fileName, trieData);

            this.trie = new this.Module.MarisaTrie();
            const loaded = this.trie.load(fileName);

            if (!loaded) {
                throw new Error('Failed to load MARISA trie');
            }

            onProgress('trie', 100, 'Trie ready');

            // Load and decompress lookup data
            onProgress('lookup', 0, 'Downloading lookup data...');
            const lookupResponse = await fetch(`${basePath}trie_lookup_unnormalized.msgpack.bin`);
            const lookupTotal = parseInt(lookupResponse.headers.get('content-length') || '0');

            const lookupReader = lookupResponse.body.getReader();
            const lookupChunks = [];
            let lookupReceived = 0;

            while (true) {
                const { done, value } = await lookupReader.read();
                if (done) break;

                lookupChunks.push(value);
                lookupReceived += value.length;

                if (lookupTotal > 0) {
                    const percent = Math.floor((lookupReceived / lookupTotal) * 50);
                    onProgress('lookup', percent, `Downloading... ${this.formatBytes(lookupReceived)}`);
                }
            }

            onProgress('lookup', 50, 'Decompressing lookup data...');
            const lookupCompressed = new Uint8Array(lookupReceived);
            offset = 0;
            for (const chunk of lookupChunks) {
                lookupCompressed.set(chunk, offset);
                offset += chunk.length;
            }

            const lookupData = pako.ungzip(lookupCompressed);

            onProgress('lookup', 80, 'Parsing lookup data...');
            this.lookup = msgpack.decode(lookupData);

            onProgress('lookup', 100, 'Lookup data ready');

            return {
                trieSize: this.trie.size(),
                lookupSize: this.lookup.length
            };
        } catch (error) {
            console.error('Error loading trie:', error);
            throw error;
        }
    }

    search(query) {
        if (!this.trie || !this.lookup) {
            throw new Error('Trie not loaded');
        }

        // Search in trie (exact match only)
        const id = this.trie.lookup(query);

        if (id === -1) {
            // No exact match, try predictive search
            return null;
        }

        // Get LCCN from lookup (just an integer)
        const lccn = this.lookup[id];

        return {
            query,
            id,
            lccn,
            exact: true
        };
    }

    predictiveSearch(query, limit) {
        if (!this.trie || !this.lookup) {
            throw new Error('Trie not loaded');
        }

        // Get all keys that start with the query
        const matches = this.trie.predictiveSearch(query);

        // Limit results if specified, otherwise return all
        const limitedMatches = limit ? matches.slice(0, limit) : matches;

        const results = limitedMatches.map(key => {
            const id = this.trie.lookup(key);
            const lccn = this.lookup[id];

            return {
                key,
                lccn,
                id
            };
        });

        return results;
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }

    getTrieSize() {
        return this.trie ? this.trie.size() : 0;
    }

    getLookupSize() {
        return this.lookup ? this.lookup.length : 0;
    }
}
