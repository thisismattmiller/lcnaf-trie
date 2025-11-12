# LCNAF Trie

A collection of tools for reconciling Library of Congress Name Authority File (LCNAF) names using MARISA trie data structures for fast, memory-efficient lookups.

Blog post: https://thisismattmiller.com/post/lcnaf-trie/

View Apps: https://thisismattmiller.github.io/lcnaf-trie/

## Project Overview

This project provides multiple interfaces for reconciling names against LCNAF:
- Web-based reconciliation tools
- REST APIs for programmatic access
- OpenRefine integration
- Command-line tools for MARC file processing

All tools use the same underlying MARISA trie data structure for consistent, fast name lookups with fuzzy matching via Levenshtein distance.

## Directory Structure

### Web Applications

#### [web-reconcile/](web-reconcile/)
Browser-based MARC file reconciliation tool. Upload MARC21 binary or MARCXML files and reconcile names in fields 100, 110, 700, 710. Adds $0 subfields with id.loc.gov URIs and generates detailed reports.

**Features:**
- Drag-and-drop MARC file upload
- Real-time reconciliation progress
- Download reconciled MARC files
- CSV and JSON reports
- Supports both Binary MARC and MARCXML

**Live Demo:** [web-reconcile/](web-reconcile/)

#### [web-search/](web-search/)
Simple browser-based name search interface. Enter a name and get instant LCNAF matches with LCCN identifiers.

**Features:**
- Real-time search as you type
- Multiple match display with scores
- Direct links to id.loc.gov records
- Fuzzy matching with Levenshtein distance

**Live Demo:** [web-search/](web-search/)

### REST APIs

#### [api-simple/](api-simple/)
Simple REST API for name reconciliation. Single endpoint accepts a name query parameter and returns LCCN.

**Endpoint:** `GET /reconcile?q=<name>`

**Features:**
- Fast trie-based lookup
- Best match selection with Levenshtein distance
- Returns LCCN and id.loc.gov URI
- Alternative matches for ambiguous names

**Port:** 5723

**Documentation:** [api-simple/README.md](api-simple/README.md)

#### [api-open-refine/](api-open-refine/)
OpenRefine Reconciliation API v0.2 compliant service. Full-featured reconciliation service that integrates with OpenRefine for batch name reconciliation workflows.

**Features:**
- OpenRefine Reconciliation API v0.2 compliant
- Service manifest with preview/view endpoints
- Batch query support
- Match scoring (0-100)
- Multiple candidate results

**Port:** 5724

**Documentation:** [api-open-refine/README.md](api-open-refine/README.md)

### Command-Line Tools

#### [command-line-tool/](command-line-tool/)
Python command-line tool for reconciling names in MARC files. Processes Binary MARC or MARCXML files and adds $0 subfields with id.loc.gov URIs.

**Usage:**
```bash
python3 reconcile_marc.py /path/to/marcfile.mrc
```

**Features:**
- Binary MARC and MARCXML support
- Processes fields 100, 110, 700, 710
- Adds $0 subfields with id.loc.gov URIs
- Generates text and JSON reports
- Best match selection with Levenshtein threshold

**Output:**
- `reconciled_<filename>.marc` - Modified MARC file
- `report_<filename>.txt` - Human-readable report
- `report_<filename>.json` - Machine-readable JSON report

**Documentation:** [command-line-tool/README.md](command-line-tool/README.md)

### Scripts

#### [scripts_python/](scripts_python/)
Python scripts for building and maintaining the trie data structures.

**Data Building Scripts:**
- **[create_trie.py](scripts_python/create_trie.py)** - Creates normalized MARISA trie from LCNAF data. Normalizes names by removing punctuation, sorting characters, and moving numbers to end. Main script for building the searchable trie structure.

- **[create_trie_unnormalized.py](scripts_python/create_trie_unnormalized.py)** - Creates unnormalized MARISA trie with original LCNAF labels. Preserves exact name forms for display while enabling fuzzy matching. Generates gzipped MessagePack lookup files for web deployment.

- **[create_binary_lookup.py](scripts_python/create_binary_lookup.py)** - Creates binary lookup array from trie data. Converts LCCN mappings to efficient binary format for fast access.

- **[create_msgpack_lookup.py](scripts_python/create_msgpack_lookup.py)** - Converts lookup data to MessagePack format. Creates compressed, efficient binary format for JavaScript/Python interoperability.

- **[create_label_lookup.py](scripts_python/create_label_lookup.py)** - Builds label lookup index for reverse LCCN-to-name mappings. Used for displaying original name forms in search results.

- **[compact_lookup_format.py](scripts_python/compact_lookup_format.py)** - Compacts lookup data by removing redundant entries. Optimizes file size while maintaining functionality.

**Utility Scripts:**
- **[extract_lccn_array.py](scripts_python/extract_lccn_array.py)** - Extracts LCCN array from source data files. Helper for initial data processing.

- **[search_lccn.py](scripts_python/search_lccn.py)** - Command-line tool to search trie by LCCN or name. Quick testing utility for verifying trie contents.

- **[un_pickle_trie_lookup.py](scripts_python/un_pickle_trie_lookup.py)** - Unpickles and inspects trie lookup files. Debug utility for examining serialized data.

**Quality Assurance:**
- **[qa_lookup_data.py](scripts_python/qa_lookup_data.py)** - Quality assurance checks for lookup data integrity. Validates LCCN formats, checks for duplicates, and verifies data consistency.

- **[remove_corrupt_lccns.py](scripts_python/remove_corrupt_lccns.py)** - Removes corrupt or invalid LCCN entries from data. Filters out malformed records that could cause lookup errors.

**Testing:**
- **[create_marc_test_files.py](scripts_python/create_marc_test_files.py)** - Creates MARC21 test files from source data. Extracts sample records with name fields (100, 110, 700, 710) for testing reconciliation tools.

- **[dict_test.py](scripts_python/dict_test.py)** - Basic dictionary/trie performance tests. Benchmarking utility.

## Data Files

The compiled trie data is stored in `web-reconcile/public/`:

- **trie.marisa.bin** - Gzipped MARISA trie structure (~52 MB compressed, ~150 MB in memory)
- **trie_lookup.msgpack.bin** - Gzipped MessagePack lookup array mapping trie IDs to LCCNs and labels (~52 MB compressed)

These files are shared by all tools (web apps, APIs, command-line) for consistent results.

## How It Works

### Normalization

All tools normalize names using the same algorithm:

1. Remove punctuation
2. Normalize Unicode (NFKD) and remove non-ASCII characters
3. Convert to lowercase
4. Remove spaces
5. Sort characters alphabetically
6. Move numeric characters to the end

**Example:** `"Woolf, Virginia, 1882-1941"` → `"afiilnoorvw18821941"`

### Matching

1. **Exact Match:** If normalized name exactly matches a trie key, return the corresponding LCCN(s)
2. **Multiple Matches:** If multiple labels normalize to the same key, calculate Levenshtein distance on the original (non-normalized) input
3. **Best Match:** Select the match with lowest Levenshtein distance (threshold of 10 for command-line tool)

### LCCN Format

LCCNs are stored in compact numeric format and converted to prefixed format:

- `179041849` → `nb79041849`
- `279041849` → `nn79041849`
- `379041849` → `no79041849`
- `479041849` → `nr79041849`
- `579041849` → `ns79041849`
- `679041849` → `n79041849`

## Installation

### Prerequisites

- Python 3.7+
- Node.js 16+ (for web tools development)

### Python Dependencies

For API and command-line tools:

```bash
pip install -r requirements.txt
```

Common dependencies:
- marisa-trie==1.2.0
- msgpack==1.0.7
- Flask==3.0.0 (for APIs)
- pymarc==5.1.2 (for MARC processing)

### Web Tools

The web applications are static HTML/JavaScript and require no installation. Simply open `index.html` in a browser or serve via a web server.

For development:
```bash
cd web-reconcile  # or web-search
npm install
npm run dev
```

## Quick Start

### Web Interface
1. Open `index.html` in your browser
2. Click on [web-reconcile](web-reconcile/) or [web-search](web-search/)
3. Start reconciling or searching names

### API
```bash
# Simple API
cd api-simple
python app.py
curl "http://localhost:5723/reconcile?q=Woolf, Virginia, 1882-1941"

# OpenRefine API
cd api-open-refine
python app.py
# Add http://localhost:5724/reconcile to OpenRefine
```

### Command-Line
```bash
cd command-line-tool
python3 reconcile_marc.py /path/to/marcfile.mrc
```

## Performance

- **Trie Size:** 11.7M keys
- **Memory Usage:** ~150 MB for loaded data structures
- **Lookup Speed:** O(k) where k is the normalized key length
- **Typical Query:** <100ms including Levenshtein distance calculation
- **MARC Processing:** 50-200 records per second

