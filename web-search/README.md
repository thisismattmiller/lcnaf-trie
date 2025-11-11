# LCNAF Search

A web application for searching the Library of Congress Name Authority File (LCNAF) using exact string matching.

## Features

- Fast exact string lookup using MARISA trie data structure
- Real-time progress indicators for loading
- Clean, modern UI
- No normalization - searches for exact authorized headings
- Returns LCCN (Library of Congress Control Number) for matched headings

## Development

Install dependencies:
```bash
npm install
```

Run development server:
```bash
npm run dev
```

Build for production:
```bash
npm run build
```

## Data Files

This app uses:
- `trie_unnormalized.marisa.bin` - MARISA trie structure with unnormalized headings
- `trie_lookup_unnormalized.msgpack.bin` - MessagePack lookup array for LCCNs

Both files are gzipped for efficient transfer and decompressed in the browser using pako.

## How It Works

1. On page load, the app downloads and decompresses the trie structure and lookup data
2. Users enter an exact authorized LCNAF heading
3. The app searches the trie for an exact match
4. If found, it retrieves the corresponding LCCN from the lookup array
5. Results are displayed with the LCCN formatted for easy reading
