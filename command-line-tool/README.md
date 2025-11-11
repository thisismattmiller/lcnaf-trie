# LCNAF MARC Reconciliation Tool

Command-line tool for reconciling Library of Congress Name Authority File (LCNAF) names in MARC records using MARISA trie data structure.

## Features

- Process Binary MARC (.mrc) and MARCXML (.xml) files
- Reconcile names in fields 100, 110, 700, 710
- Add `$0` subfields with id.loc.gov URIs
- Generate detailed reconciliation reports
- Use Levenshtein distance for fuzzy matching
- Fast trie-based lookup

## Installation

Install Python dependencies:

```bash
pip3 install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python3 reconcile_marc.py /path/to/marcfile.mrc
```

Or for MARCXML:

```bash
python3 reconcile_marc.py /path/to/marcfile.xml
```

### Output Files

The tool generates three files in the same directory as the input file:

1. **`reconciled_<originalfilename>.marc`** - Modified MARC file with `$0` subfields added
2. **`report_<originalfilename>.txt`** - Detailed human-readable reconciliation report
3. **`report_<originalfilename>.json`** - Machine-readable JSON report with full statistics and results

## How It Works

### 1. Name Extraction

The tool processes these MARC fields:
- **100** - Main Entry - Personal Name
- **110** - Main Entry - Corporate Name
- **700** - Added Entry - Personal Name
- **710** - Added Entry - Corporate Name

For each field, it combines the following subfields in order:
- `$a` - Personal/corporate name
- `$b` - Numeration / Subordinate unit
- `$c` - Titles and other words / Location
- `$q` - Fuller form of name
- `$d` - Dates
- `$g` - Miscellaneous information

**Example:**
```
700 1_ $a Woolf, Virginia, $d 1882-1941
```
Extracts: `"Woolf, Virginia, 1882-1941"`

### 2. Normalization

Names are normalized using the same algorithm as the LCNAF trie:

1. Remove punctuation
2. Normalize Unicode (NFKD) and remove non-ASCII characters
3. Convert to lowercase
4. Remove spaces
5. Sort characters alphabetically
6. Move numeric characters to the end

**Example:** `"Woolf, Virginia, 1882-1941"` → `"afiilnoorvw18821941"`

### 3. Reconciliation

- Lookup normalized name in the trie
- If single match: use it
- If multiple matches: calculate Levenshtein distance for each
- Use best match if distance ≤ 10 (threshold)
- If no match or distance > 10: mark as not found

### 4. Adding $0 Subfields

When a match is found, the tool adds a `$0` subfield at the end of the field:

**Before:**
```
700 1_ $a Woolf, Virginia, $d 1882-1941
```

**After:**
```
700 1_ $a Woolf, Virginia, $d 1882-1941 $0 http://id.loc.gov/authorities/names/n79041849
```

### 5. Report Generation

The report includes:

**Statistics:**
- Total records processed
- Total fields processed
- Fields successfully reconciled
- Fields not found
- Fields with poor matches (distance > 10)
- Success rate percentage

**Detailed Results:**
For each processed field:
- Record number
- System ID (from field 001)
- Field tag (100, 110, 700, 710)
- Original name
- Reconciliation status
- LCCN (if found)
- Matched label (if different from original)
- Levenshtein distance (if applicable)

## Example

### Input MARC Record

```
001    12345678
100 1_ $a Smith, John, $d 1950-
245 10 $a The great book
700 1_ $a Woolf, Virginia, $d 1882-1941
710 2_ $a Library of Congress
```

### Command

```bash
python3 reconcile_marc.py input.mrc
```

### Output

**reconciled_input.mrc:**
```
001    12345678
100 1_ $a Smith, John, $d 1950- $0 http://id.loc.gov/authorities/names/n79123456
245 10 $a The great book
700 1_ $a Woolf, Virginia, $d 1882-1941 $0 http://id.loc.gov/authorities/names/n79041849
710 2_ $a Library of Congress $0 http://id.loc.gov/authorities/names/n79022889
```

**report_input.txt:**
```
======================================================================
LCNAF MARC Reconciliation Report
======================================================================

STATISTICS
----------------------------------------------------------------------
Total records processed:                  1
Total fields processed:                   3
Fields reconciled:                        3
Fields not found:                         0
Fields with poor match:                   0
Success rate:                         100.0%

======================================================================

DETAILED RESULTS
----------------------------------------------------------------------

Record: 1 | System ID: 12345678
Field:  100
Name:   Smith, John, 1950-
Status: RECONCILED
LCCN:   n79123456

Record: 1 | System ID: 12345678
Field:  700
Name:   Woolf, Virginia, 1882-1941
Status: RECONCILED
LCCN:   n79041849

Record: 1 | System ID: 12345678
Field:  710
Name:   Library of Congress
Status: RECONCILED
LCCN:   n79022889
```

**report_input.json:**
```json
{
  "input_file": "/path/to/input.mrc",
  "output_file": "/path/to/reconciled_input.mrc",
  "processing_date": null,
  "statistics": {
    "total_records": 1,
    "total_fields_processed": 3,
    "fields_reconciled": 3,
    "fields_not_found": 0,
    "fields_poor_match": 0,
    "success_rate": 100.0
  },
  "results": [
    {
      "record": 1,
      "system_id": "12345678",
      "field": "100",
      "name": "Smith, John, 1950-",
      "matched_label": "Smith, John, 1950-",
      "lccn": "n79123456",
      "distance": 0,
      "status": "RECONCILED"
    },
    {
      "record": 1,
      "system_id": "12345678",
      "field": "700",
      "name": "Woolf, Virginia, 1882-1941",
      "matched_label": "Woolf, Virginia, 1882-1941",
      "lccn": "n79041849",
      "distance": 0,
      "status": "RECONCILED"
    },
    {
      "record": 1,
      "system_id": "12345678",
      "field": "710",
      "name": "Library of Congress",
      "matched_label": "Library of Congress",
      "lccn": "n79022889",
      "distance": 0,
      "status": "RECONCILED"
    }
  ]
}
```

## Configuration

### Levenshtein Distance Threshold

The maximum Levenshtein distance for accepting a match is set to 10. You can modify this in the script:

```python
MAX_LEVENSHTEIN_DISTANCE = 10
```

### Fields to Process

To process additional fields, modify the list in the script:

```python
FIELDS_TO_PROCESS = ['100', '110', '700', '710']
```

### Subfields to Combine

To change which subfields are combined, modify:

```python
SUBFIELDS_TO_COMBINE = ['a', 'b', 'c', 'q', 'd', 'g']
```

## Data Files

The tool uses the normalized trie files from `web-reconcile/public/`:

- `trie.marisa.bin` - Gzipped MARISA trie structure
- `trie_lookup.msgpack.bin` - Gzipped MessagePack lookup array

These files must be present in the `../web-reconcile/public/` directory relative to the script.

## Reconciliation Status Values

- **RECONCILED** - Name successfully matched (distance ≤ 10)
- **RECONCILED (distance: N)** - Matched with Levenshtein distance N
- **NOT_FOUND** - No match found in LCNAF
- **POOR_MATCH (distance: N)** - Match found but distance > 10 (not used)

## JSON Report Structure

The JSON report (`report_<filename>.json`) provides machine-readable data for further processing:

```json
{
  "input_file": "Path to input MARC file",
  "output_file": "Path to output reconciled MARC file",
  "processing_date": null,
  "statistics": {
    "total_records": 0,
    "total_fields_processed": 0,
    "fields_reconciled": 0,
    "fields_not_found": 0,
    "fields_poor_match": 0,
    "success_rate": 0.0
  },
  "results": [
    {
      "record": 1,
      "system_id": "Field 001 value",
      "field": "Field tag (100, 110, 700, 710)",
      "name": "Original name from MARC field",
      "matched_label": "Label from LCNAF (null if not found)",
      "lccn": "LCCN (null if not found)",
      "distance": 0,
      "status": "RECONCILED | NOT_FOUND | POOR_MATCH"
    }
  ]
}
```

### Using the JSON Report

The JSON report can be easily parsed for:
- Batch analysis of reconciliation results
- Integration with other systems
- Statistical analysis across multiple files
- Identifying patterns in successful/failed matches

**Example Python usage:**
```python
import json

with open('report_myfile.json', 'r') as f:
    report = json.load(f)

# Get statistics
stats = report['statistics']
print(f"Success rate: {stats['success_rate']:.1f}%")

# Filter for not-found names
not_found = [r for r in report['results'] if r['status'] == 'NOT_FOUND']
print(f"Names not found: {len(not_found)}")

# Get all reconciled LCCNs
lccns = [r['lccn'] for r in report['results'] if r['lccn']]
```

## Performance

- Trie lookup: O(k) where k is the length of the normalized key
- Levenshtein distance: O(m*n) where m and n are string lengths
- Memory usage: ~150 MB for loaded data structures
- Typical processing: 50-200 records per second

## Error Handling

- If input file not found: exits with error message
- If no system ID in 001 field: uses "NO_ID" in report
- If `$0` already exists with same URI: skips adding duplicate
- Records with parsing errors are skipped with warning

## Differences from web-reconcile

This command-line tool:
- Processes entire MARC files instead of individual records
- Outputs modified MARC files
- Generates detailed text reports
- Uses best match only (highest score)
- Applies Levenshtein distance threshold of 10
- Supports both Binary MARC and MARCXML formats

Both tools use the same underlying trie data and normalization logic.

## Troubleshooting

### "File not found" error
Ensure the path to the MARC file is correct.

### "Loading trie from..." path error
The tool expects the trie files to be in `../web-reconcile/public/` relative to the script location. Verify these files exist.

### Memory errors
Large MARC files may require more RAM. The trie data uses ~150 MB, and each record adds a small amount.

### Empty output file
Check that the input MARC file is valid and contains fields 100, 110, 700, or 710.
