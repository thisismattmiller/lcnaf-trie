# LCNAF OpenRefine Reconciliation Service

An OpenRefine reconciliation service for the Library of Congress Name Authority File (LCNAF) using MARISA trie data structure. This service implements the [OpenRefine Reconciliation API v0.2](https://reconciliation-api.github.io/specs/latest/).

## Features

- Fast name reconciliation using MARISA trie
- String normalization matching the LCNAF trie creation logic
- Levenshtein distance scoring for multiple matches
- Returns all candidate matches sorted by score
- Simple preview showing LCCN
- Direct link to id.loc.gov records

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Start the Service

```bash
python app.py
```

The service will start on `http://localhost:5724`

### Add to OpenRefine

1. In OpenRefine, click on a column dropdown
2. Select "Reconcile" → "Start reconciling..."
3. Click "Add Standard Service..."
4. Enter the service URL: `http://localhost:5724/reconcile`
5. The service will appear as "LCNAF Reconciliation Service"
6. Select "LCNAF Name" as the entity type

## API Endpoints

### `GET /reconcile` - Service Manifest

Returns the OpenRefine service manifest describing the reconciliation service.

**Example:**
```bash
curl http://localhost:5724/reconcile
```

**Response:**
```json
{
  "versions": ["0.2"],
  "name": "LCNAF Reconciliation Service",
  "identifierSpace": "http://id.loc.gov/authorities/names/",
  "schemaSpace": "http://id.loc.gov/authorities/names/",
  "defaultTypes": [
    {
      "id": "LCNAF_Name",
      "name": "LCNAF Name"
    }
  ],
  "view": {
    "url": "http://localhost:5724/view?id={{id}}"
  },
  "preview": {
    "url": "http://localhost:5724/preview?id={{id}}",
    "width": 400,
    "height": 100
  }
}
```

### `POST /reconcile` - Reconcile Queries

Reconciles one or more queries against LCNAF.

**Example:**
```bash
curl -X POST http://localhost:5724/reconcile \
  -d 'queries={"q0":{"query":"Woolf, Virginia, 1882-1941"}}'
```

**Response:**
```json
{
  "q0": {
    "result": [
      {
        "id": "http://id.loc.gov/authorities/names/n79041849",
        "name": "Woolf, Virginia, 1882-1941",
        "score": 100,
        "match": true,
        "type": [
          {
            "id": "LCNAF_Name",
            "name": "LCNAF Name"
          }
        ]
      }
    ]
  }
}
```

**Example with Multiple Matches:**
```bash
curl -X POST http://localhost:5724/reconcile \
  -d 'queries={"q0":{"query":"S. E. A."}}'
```

**Response:**
```json
{
  "q0": {
    "result": [
      {
        "id": "http://id.loc.gov/authorities/names/no2011145831",
        "name": "S. E. A.",
        "score": 100,
        "match": true,
        "type": [{"id": "LCNAF_Name", "name": "LCNAF Name"}]
      },
      {
        "id": "http://id.loc.gov/authorities/names/nr2003003148",
        "name": "E. A. S.",
        "score": 83.3,
        "match": false,
        "type": [{"id": "LCNAF_Name", "name": "LCNAF Name"}]
      },
      {
        "id": "http://id.loc.gov/authorities/names/n82079605",
        "name": "Esa",
        "score": 66.7,
        "match": false,
        "type": [{"id": "LCNAF_Name", "name": "LCNAF Name"}]
      }
    ]
  }
}
```

### `GET /view?id=<ID>` - View Entity

Redirects to the id.loc.gov page for the entity.

**Example:**
```bash
curl -L http://localhost:5724/view?id=http://id.loc.gov/authorities/names/n79041849
```

### `GET /preview?id=<ID>` - Preview Entity

Returns a simple HTML preview showing the LCCN as a link.

**Example:**
```bash
curl http://localhost:5724/preview?id=http://id.loc.gov/authorities/names/n79041849
```

### `GET /` - Service Information

Returns basic information about the service.

**Example:**
```bash
curl http://localhost:5724/
```

## How It Works

### Normalization

Names are normalized using the same algorithm as the LCNAF trie:

1. Remove punctuation
2. Normalize Unicode (NFKD) and remove non-ASCII characters
3. Convert to lowercase
4. Remove spaces
5. Sort characters alphabetically
6. Move numeric characters to the end

Example: "Woolf, Virginia, 1882-1941" → "afiilnoorvw"

### Matching & Scoring

1. **Single Match**: If only one LCCN maps to the normalized form, return it with a score of 100
2. **Multiple Matches**: If multiple labels normalize to the same form:
   - Calculate Levenshtein distance between the query and each label
   - Convert distance to a score (0-100), where lower distance = higher score
   - Return all candidates sorted by score (highest first)
   - Mark exact matches (distance = 0) with `"match": true`

### Score Calculation

```
max_length = max(len(query), len(label))
score = 100 - (levenshtein_distance / max_length * 100)
```

This ensures:
- Exact matches get a score of 100
- Similar strings get high scores (e.g., 80-99)
- Very different strings get low scores (e.g., 0-50)

## Using with OpenRefine

### Basic Reconciliation

1. Load your data into OpenRefine
2. Select the column containing names
3. Choose "Reconcile" → "Start reconciling..."
4. Add the service URL: `http://localhost:5724/reconcile`
5. Select "LCNAF Name" as the type
6. Click "Start Reconciling"

OpenRefine will:
- Send each name in the column to the service
- Display match scores for each candidate
- Allow you to review and accept/reject matches
- Show previews when hovering over candidates
- Link to id.loc.gov records when clicking on matches

### Match Review

- **Green**: Automatic match (high confidence)
- **Yellow**: Multiple candidates (review needed)
- **Red**: No match found

Click on any match to:
- See the preview (LCCN link)
- Click through to the full id.loc.gov record
- Accept or reject the match

## Data Files

The service uses the normalized trie files from `web-reconcile/public/`:

- `trie.marisa.bin` - Gzipped MARISA trie structure (52 MB)
- `trie_lookup.msgpack.bin` - Gzipped MessagePack lookup array (52 MB)

These files are loaded on startup and decompressed into memory (~150 MB total).

## Performance

- Trie lookup: O(k) where k is the length of the normalized key
- Levenshtein distance: O(m*n) where m and n are string lengths
- Memory usage: ~150 MB for loaded data structures
- Typical reconciliation: <100ms per query

## OpenRefine Reconciliation API Compliance

This service implements the OpenRefine Reconciliation API v0.2 specification:

- ✅ Service manifest (GET /reconcile)
- ✅ Query batching (POST /reconcile with multiple queries)
- ✅ Entity types (LCNAF_Name)
- ✅ Match scores (0-100)
- ✅ Preview service (HTML preview with LCCN link)
- ✅ View service (redirect to id.loc.gov)
- ❌ Suggest API (not implemented)
- ❌ Extend API (not implemented)
- ❌ Data extension (not implemented)

## Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5724 app:app
```

This will run 4 worker processes on port 5724.

## Differences from api-simple

The `api-simple` service provides a basic REST API for name reconciliation, while this service:

- Implements the OpenRefine Reconciliation API specification
- Returns multiple candidates with scores (not just the best match)
- Provides preview and view endpoints for OpenRefine integration
- Uses form-encoded POST data (OpenRefine format)
- Returns results in OpenRefine's expected JSON structure

Both services use the same underlying trie data and normalization logic.
