/**
 * MARC21 File Processing for LCNAF URI Enhancement
 *
 * Handles both Binary MARC21 (ISO 2709) and MARCXML formats.
 * Processes name fields (100, 110, 700, 710) and adds LCCN URIs to $0 subfields.
 */

// MARC21 Binary format constants
const RECORD_TERMINATOR = 0x1D;
const FIELD_TERMINATOR = 0x1E;
const SUBFIELD_DELIMITER = 0x1F;

// Levenshtein distance threshold for accepting matches
const MAX_LEVENSHTEIN_DISTANCE = 10;

/**
 * Calculate Levenshtein distance between two strings
 */
function levenshteinDistance(str1, str2) {
  const len1 = str1.length;
  const len2 = str2.length;
  const matrix = [];

  for (let i = 0; i <= len1; i++) {
    matrix[i] = [i];
  }

  for (let j = 0; j <= len2; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= len1; i++) {
    for (let j = 1; j <= len2; j++) {
      const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      );
    }
  }

  return matrix[len1][len2];
}

/**
 * Normalize string for trie lookup (same as main search)
 */
function normalizeString(str) {
  let norm = str.replace(/[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/g, '');
  norm = norm.normalize('NFKD').replace(/[^\x00-\x7F]/g, '');
  norm = norm.toLowerCase();
  norm = norm.replace(/\s+/g, '');
  norm = norm.split('').sort().join('');

  const match = norm.match(/[a-z]/);
  if (match) {
    const firstLetterIndex = match.index;
    const firstPart = norm.substring(0, firstLetterIndex);
    const secondPart = norm.substring(firstLetterIndex);
    norm = secondPart + firstPart;
  }

  return norm;
}

/**
 * Extract name from MARC field subfields (100, 110, 700, 710)
 */
function extractNameFromSubfields(subfields) {
  const parts = [];
  const order = ['a', 'b', 'c', 'q', 'd', 'g'];

  for (const code of order) {
    if (subfields[code]) {
      parts.push(subfields[code]);
    }
  }

  return parts.join(' ').trim();
}

/**
 * Convert numeric LCCN to prefixed format
 */
function convertLCCN(numericLccn) {
  const prefixMap = {
    '1': 'nb',
    '2': 'nn',
    '3': 'no',
    '4': 'nr',
    '5': 'ns',
    '6': 'n'
  };

  const lccnStr = String(numericLccn);
  const firstDigit = lccnStr[0];
  const prefix = prefixMap[firstDigit];

  if (!prefix) {
    return null;
  }

  return prefix + lccnStr.substring(1);
}

/**
 * Create LCCN URI from numeric value
 */
function createLCCNUri(numericLccn) {
  const converted = convertLCCN(numericLccn);
  if (!converted) return null;
  return `http://id.loc.gov/authorities/names/${converted}`;
}

/**
 * Find best LCCN match from trie lookup results
 */
function findBestLCCNMatch(originalName, lccnData) {
  if (!Array.isArray(lccnData)) {
    // Single value
    return { lccn: lccnData, label: null, distance: 0 };
  }

  // Multiple options - find best match using Levenshtein distance
  const normalizedInput = originalName.toLowerCase().replace(/[^a-z0-9]/g, '');
  let bestMatch = null;
  let bestDistance = Infinity;

  for (const item of lccnData) {
    const [lccn, label] = item;
    const normalizedLabel = label.toLowerCase().replace(/[^a-z0-9]/g, '');
    const distance = levenshteinDistance(normalizedInput, normalizedLabel);

    if (distance < bestDistance) {
      bestDistance = distance;
      bestMatch = { lccn, label, distance };
    }
  }

  return bestMatch;
}

/**
 * Parse Binary MARC21 (ISO 2709) file
 */
export class BinaryMARCParser {
  constructor(arrayBuffer) {
    this.data = new Uint8Array(arrayBuffer);
    this.decoder = new TextDecoder('utf-8');
    this.records = [];
  }

  parse() {
    let offset = 0;

    while (offset < this.data.length) {
      // Check for end of data
      if (this.data[offset] === 0 || offset + 24 >= this.data.length) {
        break;
      }

      try {
        const record = this.parseRecord(offset);
        if (record) {
          this.records.push(record);
          offset = record.endOffset;
        } else {
          break;
        }
      } catch (e) {
        console.error('Error parsing record at offset', offset, e);
        break;
      }
    }

    return this.records;
  }

  parseRecord(startOffset) {
    // Read leader (24 bytes)
    const leaderBytes = this.data.slice(startOffset, startOffset + 24);
    const leader = this.decoder.decode(leaderBytes);

    // Get record length from leader
    const recordLength = parseInt(leader.substring(0, 5), 10);
    if (isNaN(recordLength) || recordLength <= 0) {
      return null;
    }

    // Get base address of data
    const baseAddress = parseInt(leader.substring(12, 17), 10);

    const record = {
      startOffset,
      endOffset: startOffset + recordLength,
      leader,
      fields: [],
      rawData: this.data.slice(startOffset, startOffset + recordLength)
    };

    // Parse directory (starts at offset 24, ends at baseAddress - 1)
    let directoryOffset = startOffset + 24;
    const directoryEnd = startOffset + baseAddress - 1;

    while (directoryOffset < directoryEnd) {
      const tag = this.decoder.decode(this.data.slice(directoryOffset, directoryOffset + 3));
      const fieldLength = parseInt(this.decoder.decode(this.data.slice(directoryOffset + 3, directoryOffset + 7)), 10);
      const fieldStart = parseInt(this.decoder.decode(this.data.slice(directoryOffset + 7, directoryOffset + 12)), 10);

      if (tag === '\x1E' || tag === '') break;

      const fieldDataOffset = startOffset + baseAddress + fieldStart;
      const fieldData = this.data.slice(fieldDataOffset, fieldDataOffset + fieldLength - 1); // -1 to exclude field terminator

      const field = {
        tag,
        offset: fieldDataOffset,
        length: fieldLength
      };

      // Control fields (001-009)
      if (tag.match(/^00/)) {
        field.data = this.decoder.decode(fieldData);
      } else {
        // Data fields
        field.ind1 = String.fromCharCode(fieldData[0]);
        field.ind2 = String.fromCharCode(fieldData[1]);
        field.subfields = this.parseSubfields(fieldData.slice(2));
        field.rawData = fieldData;
      }

      record.fields.push(field);
      directoryOffset += 12;
    }

    return record;
  }

  parseSubfields(data) {
    const subfields = {};
    let i = 0;

    while (i < data.length) {
      if (data[i] === SUBFIELD_DELIMITER) {
        const code = String.fromCharCode(data[i + 1]);
        let end = i + 2;

        while (end < data.length && data[end] !== SUBFIELD_DELIMITER && data[end] !== FIELD_TERMINATOR) {
          end++;
        }

        const value = this.decoder.decode(data.slice(i + 2, end));

        if (!subfields[code]) {
          subfields[code] = value;
        } else {
          // Handle multiple subfields with same code
          if (!Array.isArray(subfields[code])) {
            subfields[code] = [subfields[code]];
          }
          subfields[code].push(value);
        }

        i = end;
      } else {
        i++;
      }
    }

    return subfields;
  }

  /**
   * Rebuild complete binary MARC record from scratch
   */
  rebuildRecord(record) {
    const encoder = new TextEncoder();

    // Build all fields data
    const fieldDataParts = [];
    const directoryEntries = [];
    let currentOffset = 0;

    for (const field of record.fields) {
      let fieldData;

      if (field.tag.match(/^00/)) {
        // Control field
        fieldData = encoder.encode(field.data);
      } else {
        // Data field - rebuild with all subfields
        const parts = [
          field.ind1.charCodeAt(0),
          field.ind2.charCodeAt(0)
        ];

        // Add all subfields in order
        for (const [code, value] of Object.entries(field.subfields)) {
          const values = Array.isArray(value) ? value : [value];
          for (const v of values) {
            parts.push(SUBFIELD_DELIMITER);
            parts.push(code.charCodeAt(0));
            const encoded = encoder.encode(v);
            for (let i = 0; i < encoded.length; i++) {
              parts.push(encoded[i]);
            }
          }
        }

        fieldData = new Uint8Array(parts);
      }

      // Add field terminator
      const fieldDataWithTerminator = new Uint8Array(fieldData.length + 1);
      fieldDataWithTerminator.set(fieldData);
      fieldDataWithTerminator[fieldDataWithTerminator.length - 1] = FIELD_TERMINATOR;

      fieldDataParts.push(fieldDataWithTerminator);

      // Create directory entry: tag (3) + length (4) + offset (5)
      const fieldLength = fieldDataWithTerminator.length;
      const tag = field.tag.padEnd(3, ' ');
      const length = String(fieldLength).padStart(4, '0');
      const offset = String(currentOffset).padStart(5, '0');

      directoryEntries.push(encoder.encode(tag + length + offset));
      currentOffset += fieldLength;
    }

    // Combine all field data
    let totalFieldDataLength = 0;
    for (const part of fieldDataParts) {
      totalFieldDataLength += part.length;
    }

    const fieldData = new Uint8Array(totalFieldDataLength);
    let fieldDataOffset = 0;
    for (const part of fieldDataParts) {
      fieldData.set(part, fieldDataOffset);
      fieldDataOffset += part.length;
    }

    // Build directory
    const directoryLength = directoryEntries.length * 12 + 1; // +1 for field terminator
    const directory = new Uint8Array(directoryLength);
    let dirOffset = 0;
    for (const entry of directoryEntries) {
      directory.set(entry, dirOffset);
      dirOffset += 12;
    }
    directory[dirOffset] = FIELD_TERMINATOR;

    // Calculate base address (24 byte leader + directory)
    const baseAddress = 24 + directoryLength;

    // Calculate total record length
    const recordLength = baseAddress + fieldData.length + 1; // +1 for record terminator

    // Build leader
    const leaderParts = [];
    leaderParts.push(String(recordLength).padStart(5, '0')); // Record length
    leaderParts.push(record.leader.substring(5, 12)); // Record status and type
    leaderParts.push(String(baseAddress).padStart(5, '0')); // Base address
    leaderParts.push(record.leader.substring(17, 20)); // Indicator/identifier lengths
    leaderParts.push('4500'); // Entry map: field length, start pos, impl def, undef

    const leader = encoder.encode(leaderParts.join('').padEnd(24, ' ').substring(0, 24));

    // Combine everything
    const completeRecord = new Uint8Array(recordLength);
    completeRecord.set(leader, 0);
    completeRecord.set(directory, 24);
    completeRecord.set(fieldData, baseAddress);
    completeRecord[recordLength - 1] = RECORD_TERMINATOR;

    return completeRecord;
  }

  /**
   * Export all records as Binary MARC
   */
  exportBinary() {
    const recordParts = [];
    let totalLength = 0;

    for (const record of this.records) {
      const rebuilt = this.rebuildRecord(record);
      recordParts.push(rebuilt);
      totalLength += rebuilt.length;
    }

    // Combine all records
    const output = new Uint8Array(totalLength);
    let offset = 0;
    for (const part of recordParts) {
      output.set(part, offset);
      offset += part.length;
    }

    return output;
  }
}

/**
 * Parse MARCXML file
 */
export class MARCXMLParser {
  constructor(xmlString) {
    this.xmlString = xmlString;
    this.parser = new DOMParser();
    this.records = [];
  }

  parse() {
    const doc = this.parser.parseFromString(this.xmlString, 'text/xml');

    // Check for parsing errors
    const parserError = doc.querySelector('parsererror');
    if (parserError) {
      throw new Error('XML parsing error: ' + parserError.textContent);
    }

    const ns = 'http://www.loc.gov/MARC21/slim';
    const recordElements = doc.getElementsByTagNameNS(ns, 'record');

    for (let i = 0; i < recordElements.length; i++) {
      const recordEl = recordElements[i];
      const record = {
        index: i,
        element: recordEl,
        leader: null,
        fields: []
      };

      // Get leader
      const leaderEl = recordEl.getElementsByTagNameNS(ns, 'leader')[0];
      if (leaderEl) {
        record.leader = leaderEl.textContent;
      }

      // Get control fields
      const controlFields = recordEl.getElementsByTagNameNS(ns, 'controlfield');
      for (let j = 0; j < controlFields.length; j++) {
        const cf = controlFields[j];
        record.fields.push({
          tag: cf.getAttribute('tag'),
          data: cf.textContent,
          element: cf
        });
      }

      // Get data fields
      const dataFields = recordEl.getElementsByTagNameNS(ns, 'datafield');
      for (let j = 0; j < dataFields.length; j++) {
        const df = dataFields[j];
        const field = {
          tag: df.getAttribute('tag'),
          ind1: df.getAttribute('ind1') || ' ',
          ind2: df.getAttribute('ind2') || ' ',
          subfields: {},
          element: df
        };

        const subfields = df.getElementsByTagNameNS(ns, 'subfield');
        for (let k = 0; k < subfields.length; k++) {
          const sf = subfields[k];
          const code = sf.getAttribute('code');
          const value = sf.textContent;

          if (!field.subfields[code]) {
            field.subfields[code] = value;
          } else {
            if (!Array.isArray(field.subfields[code])) {
              field.subfields[code] = [field.subfields[code]];
            }
            field.subfields[code].push(value);
          }
        }

        record.fields.push(field);
      }

      this.records.push(record);
    }

    return this.records;
  }

  /**
   * Update or add $0 subfield to a field
   */
  updateSubfieldZero(field, uri) {
    const ns = 'http://www.loc.gov/MARC21/slim';

    // Find existing $0 subfield
    const subfields = field.element.getElementsByTagNameNS(ns, 'subfield');
    let zeroSubfield = null;

    for (let i = 0; i < subfields.length; i++) {
      if (subfields[i].getAttribute('code') === '0') {
        zeroSubfield = subfields[i];
        break;
      }
    }

    if (zeroSubfield) {
      // Replace existing $0
      zeroSubfield.textContent = uri;
    } else {
      // Create new $0 subfield
      const newSubfield = field.element.ownerDocument.createElementNS(ns, 'subfield');
      newSubfield.setAttribute('code', '0');
      newSubfield.textContent = uri;
      field.element.appendChild(newSubfield);
    }

    // Update our internal representation
    field.subfields['0'] = uri;
  }

  /**
   * Serialize back to XML string
   */
  serialize() {
    const serializer = new XMLSerializer();
    return serializer.serializeToString(this.records[0].element.ownerDocument);
  }
}

/**
 * Sleep helper to yield to UI thread
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Process MARC file and add LCCN URIs
 */
export async function processMARCFile(file, trie, lookupDecoder, progressCallback) {
  const fileType = detectFileType(file);
  let parser;
  let records;

  progressCallback({ stage: 'reading', percent: 0, message: 'Reading file...' });

  if (fileType === 'binary') {
    const arrayBuffer = await file.arrayBuffer();
    const fileSize = arrayBuffer.byteLength;
    progressCallback({ stage: 'parsing', percent: 5, message: `Parsing Binary MARC (${(fileSize / 1024 / 1024).toFixed(1)} MB)...` });

    // Give UI a chance to update
    await sleep(1);

    parser = new BinaryMARCParser(arrayBuffer);
    records = parser.parse();

    progressCallback({ stage: 'parsing', percent: 15, message: `Parsed ${records.length} records` });
  } else if (fileType === 'xml') {
    const fileSize = file.size;
    const fileSizeMB = fileSize / 1024 / 1024;

    // Warn about large XML files upfront (text strings use 2x memory in JS + XML parsing overhead)
    // Binary MARC files don't have this limitation - they use ArrayBuffer which is much more efficient
    if (fileSizeMB > 500) {
      throw new Error(`XML file is ${fileSizeMB.toFixed(1)} MB which exceeds browser text string limits (~500 MB). MARCXML uses 2-3x more memory than Binary MARC due to UTF-16 encoding and XML parsing. Please convert to Binary MARC format (.mrc) instead.`);
    }

    progressCallback({ stage: 'reading', percent: 2, message: `Reading MARCXML file (${fileSizeMB.toFixed(1)} MB)...` });

    await sleep(1);

    let text;
    try {
      text = await file.text();
    } catch (error) {
      throw new Error(`Failed to read file: ${error.message}. Large XML files may exceed browser memory limits. Consider using Binary MARC format instead.`);
    }

    if (!text || text.length === 0) {
      throw new Error(`File could not be read (returned empty). This XML file (${fileSizeMB.toFixed(1)} MB) likely exceeds browser memory limits. Please convert to Binary MARC format (.mrc) instead.`);
    }

    progressCallback({ stage: 'parsing', percent: 5, message: `Parsing MARCXML (${(text.length / 1024 / 1024).toFixed(1)} MB)...` });

    // Give UI a chance to update
    await sleep(1);

    parser = new MARCXMLParser(text);
    records = parser.parse();

    progressCallback({ stage: 'parsing', percent: 15, message: `Parsed ${records.length} records` });
  } else {
    throw new Error('Unsupported file type. Please upload a MARC21 Binary (.mrc) or MARCXML (.xml) file.');
  }

  progressCallback({ stage: 'processing', percent: 20, message: `Processing ${records.length} records...` });

  // Give UI a chance to update before heavy processing
  await sleep(1);

  const report = {
    totalRecords: records.length,
    totalFieldsProcessed: 0,
    fieldsUpdated: 0,
    fieldsNotFound: 0,
    fieldsPoorMatch: 0,
    details: []
  };

  const nameFieldTags = ['100', '110', '700', '710'];

  for (let i = 0; i < records.length; i++) {
    const record = records[i];
    const percent = 20 + Math.floor(((i + 1) / records.length) * 75);

    // Update progress every 10 records, or on the last record
    if (i % 10 === 0 || i === records.length - 1) {
      progressCallback({
        stage: 'processing',
        percent,
        message: `Processing record ${i + 1} of ${records.length}...`
      });
      await sleep(0); // Yield to UI thread
    }

    for (const field of record.fields) {
      if (!nameFieldTags.includes(field.tag)) continue;
      if (!field.subfields) continue;

      report.totalFieldsProcessed++;

      // Extract name from subfields
      const name = extractNameFromSubfields(field.subfields);
      if (!name) continue;

      // Normalize and lookup in trie
      const normalized = normalizeString(name);
      const trieId = trie.lookup(normalized);

      if (trieId === -1) {
        report.fieldsNotFound++;
        report.details.push({
          recordIndex: i + 1,
          field: field.tag,
          name,
          status: 'not_found',
          reason: 'Name not found in LCNAF trie'
        });
        continue;
      }

      // Get LCCN from lookup
      const lccnData = lookupDecoder.get(trieId);
      if (!lccnData) {
        report.fieldsNotFound++;
        report.details.push({
          recordIndex: i + 1,
          field: field.tag,
          name,
          status: 'not_found',
          reason: 'No LCCN data available for trie match'
        });
        continue;
      }

      // Find best match
      const match = findBestLCCNMatch(name, lccnData);

      // Check Levenshtein distance threshold
      if (match.distance > MAX_LEVENSHTEIN_DISTANCE) {
        report.fieldsPoorMatch++;
        report.details.push({
          recordIndex: i + 1,
          field: field.tag,
          name,
          status: 'poor_match',
          reason: `Match quality too low (distance: ${match.distance})`,
          matchedLabel: match.label,
          levenshteinDistance: match.distance
        });
        continue;
      }

      // Create LCCN URI
      const uri = createLCCNUri(match.lccn);
      if (!uri) {
        report.fieldsNotFound++;
        report.details.push({
          recordIndex: i + 1,
          field: field.tag,
          name,
          status: 'error',
          reason: 'Failed to convert LCCN to URI'
        });
        continue;
      }

      // Update $0 subfield
      if (fileType === 'xml') {
        parser.updateSubfieldZero(field, uri);
      } else {
        // For binary, update subfields object (full rebuild needed for export)
        field.subfields['0'] = uri;
      }

      report.fieldsUpdated++;
      report.details.push({
        recordIndex: i + 1,
        field: field.tag,
        name,
        status: 'updated',
        lccnUri: uri,
        matchedLabel: match.label,
        levenshteinDistance: match.distance
      });
    }
  }

  progressCallback({ stage: 'finalizing', percent: 95, message: 'Finalizing...' });

  // Generate output file
  let outputBlob;
  let outputFilename;

  if (fileType === 'xml') {
    const xmlString = parser.serialize();
    outputBlob = new Blob([xmlString], { type: 'application/xml' });
    outputFilename = file.name.replace(/\.xml$/, '_enhanced.xml');
  } else {
    // Binary MARC - rebuild all records
    const binaryData = parser.exportBinary();
    outputBlob = new Blob([binaryData], { type: 'application/marc' });
    outputFilename = file.name.replace(/\.(mrc|marc)$/, '_enhanced.mrc');
  }

  progressCallback({ stage: 'complete', percent: 100, message: 'Processing complete!' });

  return {
    outputBlob,
    outputFilename,
    report
  };
}

/**
 * Detect file type (binary MARC or XML)
 */
function detectFileType(file) {
  const name = file.name.toLowerCase();

  if (name.endsWith('.xml')) {
    return 'xml';
  } else if (name.endsWith('.mrc') || name.endsWith('.marc')) {
    return 'binary';
  }

  // Try to detect by content
  return 'xml'; // Default to XML for now
}
