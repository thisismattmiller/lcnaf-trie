# LCNAF Reconciliation API

A simple Flask API for reconciling names against the Library of Congress Name Authority File (LCNAF) using MARISA trie data structure.

## Features

- Fast name reconciliation using MARISA trie
- String normalization matching the web-reconcile logic
- Levenshtein distance for finding best matches when multiple options exist
- Returns LCCN and LOC URI for matched names
- Uses compressed data files (.bin) directly from web-reconcile

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Start the API Server

```bash
python app.py
```

The API will start on `http://localhost:5723`

### API Endpoints

#### `/reconcile` - Reconcile a name

Reconcile a name against the LCNAF database.

**Parameters:**
- `q` (required): The name to reconcile

**Example:**
```bash
curl "http://localhost:5723/reconcile?q=Woolf, Virginia, 1882-1941"
```

**Response (exact match):**
```json
{
  "query": "Woolf, Virginia, 1882-1941",
  "normalized": "afiilnoorvw",
  "found": true,
  "lccn": "n79041849",
  "uri": "http://id.loc.gov/authorities/names/n79041849",
  "match_quality": "exact"
}
```

**Response (multiple matches - best match selected):**
```bash
curl "http://localhost:5723/reconcile?q=S.%20E.%20A."
```

```json
{
  "query": "S. E. A.",
  "normalized": "aes",
  "found": true,
  "lccn": "no2011145831",
  "uri": "http://id.loc.gov/authorities/names/no2011145831",
  "matched_label": "S. E. A.",
  "levenshtein_distance": 0,
  "match_quality": "exact",
  "total_matches": 3,
  "alternatives": [
    {
      "lccn": "n82079605",
      "label": "Esa",
      "uri": "http://id.loc.gov/authorities/names/n82079605"
    },
    {
      "lccn": "nr2003003148",
      "label": "E. A. S.",
      "uri": "http://id.loc.gov/authorities/names/nr2003003148"
    }
  ]
}
```

**Response (not found):**
```json
{
  "query": "Unknown Person",
  "normalized": "eknnnnooprsuw",
  "found": false,
  "message": "Name not found in LCNAF"
}
```

#### `/health` - Health check

Check if the API is running and data is loaded.

**Example:**
```bash
curl http://localhost:5723/health
```

**Response:**
```json
{
  "status": "healthy",
  "trie_size": 11741073,
  "lookup_size": 11741073
}
```

#### `/` - API Information

Get information about the API and its endpoints.

**Example:**
```bash
curl http://localhost:5723/
```

## How It Works

### Normalization

The API normalizes names using the same algorithm as the trie creation script:

1. Remove punctuation
2. Normalize Unicode (NFKD) and remove non-ASCII characters
3. Convert to lowercase
4. Remove spaces
5. Sort characters alphabetically
6. Move numeric characters to the end

Example: "Woolf, Virginia, 1882-1941" → "afiilnoorvw"

### Matching

1. **Exact Match**: If the normalized query exactly matches a key in the trie, return the corresponding LCCN
2. **Multiple Matches**: If multiple labels normalize to the same key, use Levenshtein distance to find the best match based on the original (non-normalized) query
3. **Not Found**: If no match is found, return a not found response

### Data Files

The API uses the compressed data files from the `web-reconcile/public/` directory:

- `trie.marisa.bin` - Gzipped MARISA trie structure (52 MB)
- `trie_lookup.msgpack.bin` - Gzipped MessagePack lookup array (52 MB)

These files are loaded on startup and decompressed into memory.

## Architecture

- **Flask**: Web framework for the API
- **MARISA Trie**: Memory-efficient trie data structure for fast prefix searches
- **MessagePack**: Binary serialization for compact lookup data
- **CORS**: Enabled for cross-origin requests

## Performance

- Trie lookup: O(k) where k is the length of the normalized key
- Levenshtein distance calculation: O(m*n) where m and n are string lengths
- Memory usage: ~150 MB for loaded data structures

## Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `400`: Bad request (missing query parameter)
- `404`: Endpoint not found
- `500`: Internal server error
- `503`: Service unavailable (data not loaded)

## Development

To run in development mode with auto-reload:

```bash
python app.py
```

The Flask debug mode is enabled by default for development.

## Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5723 app:app
```

This will run 4 worker processes on port 5723.
