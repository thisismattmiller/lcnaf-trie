import { loadLookupData } from './lookup-decoder.js';
import { processMARCFile } from './marc.js';
import pako from 'pako';

let trie = null;
let Module = null;
let MarisaModule = null;
let lookupDecoder = null;

// LCCN prefix mapping
const LCCN_PREFIX_MAP = {
  '1': 'nb',
  '2': 'nn',
  '3': 'no',
  '4': 'nr',
  '5': 'ns',
  '6': 'n'
};

// Format number with commas
function formatNumber(num) {
  return num.toLocaleString();
}

// Update status message
function setStatus(message, type = 'loading', progress = null) {
  const statusEl = document.getElementById('status');
  const statusText = document.getElementById('statusText');
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  const spinner = statusEl.querySelector('.spinner');

  statusEl.className = `status ${type}`;

  if (statusText) {
    statusText.textContent = message;
  }

  if (progress !== null && progressBar) {
    progressBar.style.width = `${progress}%`;
    if (progressText) {
      progressText.textContent = `${Math.round(progress)}%`;
    }
  }

  // Hide spinner when ready or error
  if (spinner && (type === 'ready' || type === 'error')) {
    spinner.style.display = 'none';
  }

  // Fade out success messages after 5 seconds
  if (type === 'ready') {
    setTimeout(() => {
      statusEl.classList.add('fade-out');
    }, 5000);
  }
}

// Levenshtein distance for string matching
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
        matrix[i - 1][j] + 1,      // deletion
        matrix[i][j - 1] + 1,      // insertion
        matrix[i - 1][j - 1] + cost // substitution
      );
    }
  }

  return matrix[len1][len2];
}

// Find best matching label using Levenshtein distance
function findBestMatch(originalInput, labels) {
  const normalizedInput = originalInput.toLowerCase().replace(/[^a-z0-9]/g, '');
  let bestMatch = null;
  let bestDistance = Infinity;

  for (const item of labels) {
    const label = item[1]; // [lccn, label] format
    const normalizedLabel = label.toLowerCase().replace(/[^a-z0-9]/g, '');
    const distance = levenshteinDistance(normalizedInput, normalizedLabel);

    if (distance < bestDistance) {
      bestDistance = distance;
      bestMatch = item;
    }
  }

  return bestMatch;
}

// Convert numeric LCCN to prefixed format
function convertLCCN(numericLccn) {
  const lccnStr = String(numericLccn);
  const firstDigit = lccnStr[0];
  const prefix = LCCN_PREFIX_MAP[firstDigit];

  if (!prefix) {
    console.warn(`Unknown LCCN prefix for digit: ${firstDigit}`);
    return null;
  }

  return prefix + lccnStr.substring(1);
}

// Create LCCN link
function createLCCNLink(numericLccn, label = null) {
  const convertedLccn = convertLCCN(numericLccn);
  if (!convertedLccn) {
    return `<span>LCCN: ${formatNumber(numericLccn)} (invalid format)</span>`;
  }

  const url = `http://id.loc.gov/authorities/names/${convertedLccn}`;
  let html = `<a href="${url}" target="_blank">${convertedLccn}</a>`;

  if (label) {
    html += ` <span class="result-meta">(${label})</span>`;
  }

  return html;
}

// Load the MARISA trie
async function loadTrie() {
  try {
    setStatus('Initializing WebAssembly module...', 'loading', 10);

    // Load the marisa.js script which defines MarisaModule globally
    const script = document.createElement('script');
    script.src = '/marisa.js';
    script.type = 'text/javascript';

    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });

    // Wait a bit for the module to be available
    await new Promise(resolve => setTimeout(resolve, 100));

    // Now MarisaModule should be available globally
    if (typeof window.MarisaModule === 'undefined') {
      throw new Error('MarisaModule not loaded');
    }

    Module = await window.MarisaModule();
    setStatus('Downloading trie data (52 MB)...', 'loading', 20);

    const response = await fetch('/trie.marisa.bin');
    if (!response.ok) {
      throw new Error('Failed to fetch trie.marisa.bin');
    }

    const compressedBuffer = await response.arrayBuffer();
    setStatus('Decompressing trie data...', 'loading', 40);

    const data = pako.ungzip(new Uint8Array(compressedBuffer));
    setStatus('Loading trie into memory...', 'loading', 60);

    Module.FS.writeFile('/trie.marisa', data);

    trie = new Module.MarisaTrie();
    const loaded = trie.load('/trie.marisa');

    if (!loaded) {
      throw new Error('Failed to load MARISA trie');
    }

    const totalKeys = trie.size();
    setStatus('Loading LCCN lookup data (52 MB)...', 'loading', 70);

    // Load lookup data with progress callback
    try {
      lookupDecoder = await loadLookupData((progress) => {
        setStatus('Processing LCCN data...', 'loading', progress);
      });
      setStatus(`✓ All data loaded! ${formatNumber(totalKeys)} keys ready to search.`, 'ready', 100);
    } catch (lookupError) {
      console.warn('Could not load lookup data:', lookupError);
      setStatus(`✓ Trie loaded! ${formatNumber(totalKeys)} keys ready (LCCN data not available).`, 'ready', 100);
    }

    // Show search sections
    document.getElementById('mainSearchSection').style.display = 'block';
    document.getElementById('otherSearchSection').style.display = 'block';

    // Focus on main search input
    document.getElementById('mainSearch').focus();

  } catch (error) {
    console.error('Error loading trie:', error);
    setStatus(`✗ Error: ${error.message}`, 'error');
  }
}

// Normalize string like the Python script does
function normalizeString(str) {
  // Remove punctuation
  let norm = str.replace(/[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/g, '');

  // Normalize unicode (NFKD) and remove non-ASCII
  norm = norm.normalize('NFKD').replace(/[^\x00-\x7F]/g, '');

  // Convert to lowercase
  norm = norm.toLowerCase();

  // Remove spaces
  norm = norm.replace(/\s+/g, '');

  // Sort characters
  norm = norm.split('').sort().join('');

  // Move non-letter characters to the end
  const match = norm.match(/[a-z]/);
  if (match) {
    const firstLetterIndex = match.index;
    const firstPart = norm.substring(0, firstLetterIndex);
    const secondPart = norm.substring(firstLetterIndex);
    norm = secondPart + firstPart;
  }

  return norm;
}

// Main search function
function performMainSearch() {
  const input = document.getElementById('mainSearch').value.trim();
  const resultsEl = document.getElementById('mainResults');

  if (!input) {
    resultsEl.style.display = 'none';
    return;
  }

  // Normalize the input
  const normalized = normalizeString(input);

  // Look up the normalized key
  const id = trie.lookup(normalized);

  resultsEl.style.display = 'block';
  if (id === -1) {
    resultsEl.innerHTML = '<div class="no-results">Name not found in trie</div>';
  } else {
    // Get LCCN data
    const lccn = lookupDecoder ? lookupDecoder.get(id) : null;

    if (lccn === null) {
      resultsEl.innerHTML = `
        <h3>Found Match</h3>
        <div class="result-item">
          <div>No LCCN data available for this entry</div>
          <div class="result-meta">Normalized: ${normalized}</div>
        </div>
      `;
    } else if (Array.isArray(lccn)) {
      // Multi-label result - find best match using Levenshtein distance
      const bestMatch = findBestMatch(input, lccn);

      if (bestMatch) {
        const [selectedLccn, label] = bestMatch;
        const lcnLink = createLCCNLink(selectedLccn, label);

        // Generate unique ID for this result
        const resultId = `result-${Date.now()}`;

        // Create alternatives HTML
        const alternativesHtml = lccn.length > 1 ? `
          <span class="show-alternatives" onclick="toggleAlternatives('${resultId}')">
            (show ${lccn.length - 1} other option${lccn.length > 2 ? 's' : ''})
          </span>
          <div class="alternative-matches" id="${resultId}">
            <h4>Alternative matches:</h4>
            ${lccn.map(([lccnNum, lbl]) => {
              if (lccnNum === selectedLccn) return ''; // Skip the selected one
              return `<div class="alternative-item">${createLCCNLink(lccnNum, lbl)}</div>`;
            }).join('')}
          </div>
        ` : '';

        resultsEl.innerHTML = `
          <h3>Found Match</h3>
          <div class="result-item">
            <div>${lcnLink}</div>
            <div class="result-meta">
              Best match from ${lccn.length} options using similarity to "${input}"
              ${alternativesHtml}
            </div>
            <div class="result-meta">Normalized key: ${normalized}</div>
          </div>
        `;
      } else {
        resultsEl.innerHTML = '<div class="no-results">Could not determine best match</div>';
      }
    } else {
      // Single LCCN value
      const lcnLink = createLCCNLink(lccn);
      resultsEl.innerHTML = `
        <h3>Found Match</h3>
        <div class="result-item">
          <div>${lcnLink}</div>
          <div class="result-meta">Normalized key: ${normalized}</div>
        </div>
      `;
    }
  }
}

// Toggle alternative matches visibility
window.toggleAlternatives = function(id) {
  const element = document.getElementById(id);
  if (element) {
    element.classList.toggle('visible');
  }
};

// Lookup key
function lookupKey() {
  const input = document.getElementById('lookupInput').value.trim();
  const resultsEl = document.getElementById('lookupResults');

  if (!input) {
    resultsEl.style.display = 'none';
    return;
  }

  const id = trie.lookup(input);

  resultsEl.style.display = 'block';
  if (id === -1) {
    resultsEl.innerHTML = '<div class="no-results">Key not found</div>';
  } else {
    const lccn = lookupDecoder ? lookupDecoder.get(id) : null;
    let lccnHtml = '';
    if (lccn !== null) {
      if (Array.isArray(lccn)) {
        lccnHtml = `<br><strong>LCCNs:</strong> ${lccn.map(item => {
          const [num, label] = item;
          return createLCCNLink(num, label);
        }).join(', ')}`;
      } else {
        lccnHtml = `<br>${createLCCNLink(lccn)}`;
      }
    }

    resultsEl.innerHTML = `
      <h3>Result</h3>
      <div class="result-item">
        <span class="result-id">ID: ${formatNumber(id)}</span>
        <strong>${input}</strong>${lccnHtml}
      </div>
    `;
  }
}

// Reverse lookup
function reverseLookup() {
  const input = document.getElementById('reverseInput').value.trim();
  const resultsEl = document.getElementById('reverseResults');

  if (!input) {
    resultsEl.style.display = 'none';
    return;
  }

  const id = parseInt(input, 10);
  if (isNaN(id) || id < 0 || id >= trie.size()) {
    resultsEl.style.display = 'block';
    resultsEl.innerHTML = `<div class="no-results">Invalid ID (must be 0-${formatNumber(trie.size() - 1)})</div>`;
    return;
  }

  const key = trie.reverseLookup(id);

  resultsEl.style.display = 'block';
  if (!key) {
    resultsEl.innerHTML = '<div class="no-results">No key found for this ID</div>';
  } else {
    const lccn = lookupDecoder ? lookupDecoder.get(id) : null;
    let lccnHtml = '';
    if (lccn !== null) {
      if (Array.isArray(lccn)) {
        lccnHtml = `<br><strong>LCCNs:</strong> ${lccn.map(item => {
          const [num, label] = item;
          return createLCCNLink(num, label);
        }).join(', ')}`;
      } else {
        lccnHtml = `<br>${createLCCNLink(lccn)}`;
      }
    }

    resultsEl.innerHTML = `
      <h3>Result</h3>
      <div class="result-item">
        <span class="result-id">ID: ${formatNumber(id)}</span>
        <strong>${key}</strong>${lccnHtml}
      </div>
    `;
  }
}

// Predictive search
function predictiveSearch() {
  const input = document.getElementById('predictInput').value.trim();
  const resultsEl = document.getElementById('predictResults');

  if (!input) {
    resultsEl.style.display = 'none';
    return;
  }

  const startTime = performance.now();
  const results = trie.predictiveSearch(input);
  const endTime = performance.now();
  const searchTime = (endTime - startTime).toFixed(2);

  resultsEl.style.display = 'block';

  if (results.length === 0) {
    resultsEl.innerHTML = '<div class="no-results">No results found</div>';
    return;
  }

  // Limit to first 50 results for display
  const displayLimit = 50;
  const displayResults = Math.min(results.length, displayLimit);

  let html = `<h3>Found ${formatNumber(results.length)} results in ${searchTime}ms`;
  if (results.length > displayLimit) {
    html += ` (showing first ${displayLimit})`;
  }
  html += '</h3>';

  for (let i = 0; i < displayResults; i++) {
    const key = results[i];
    const id = trie.lookup(key);

    const lccn = lookupDecoder ? lookupDecoder.get(id) : null;
    let lccnHtml = '';
    if (lccn !== null) {
      if (Array.isArray(lccn)) {
        lccnHtml = `<br>${lccn.map(item => {
          const [num, label] = item;
          return createLCCNLink(num, label);
        }).join(', ')}`;
      } else {
        lccnHtml = `<br>${createLCCNLink(lccn)}`;
      }
    }

    html += `
      <div class="result-item">
        <span class="result-id">ID: ${formatNumber(id)}</span>
        <strong>${key}</strong>${lccnHtml}
      </div>
    `;
  }

  resultsEl.innerHTML = html;
}

// Toggle other search methods
document.getElementById('otherSearchToggle').addEventListener('click', () => {
  const content = document.getElementById('otherSearchContent');
  const arrow = document.querySelector('.arrow');
  content.classList.toggle('visible');
  arrow.classList.toggle('rotated');
});

// Main search - auto-search on input and Enter
const mainSearchInput = document.getElementById('mainSearch');
let searchTimeout;

mainSearchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(performMainSearch, 300); // Debounce 300ms
});

mainSearchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    clearTimeout(searchTimeout);
    performMainSearch();
  }
});

// Other search methods event listeners
document.getElementById('lookupBtn').addEventListener('click', lookupKey);
document.getElementById('lookupInput').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') lookupKey();
});

document.getElementById('reverseBtn').addEventListener('click', reverseLookup);
document.getElementById('reverseInput').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') reverseLookup();
});

document.getElementById('predictBtn').addEventListener('click', predictiveSearch);
document.getElementById('predictInput').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') predictiveSearch();
});

// Night mode toggle
const nightModeToggle = document.getElementById('nightModeToggle');
const savedTheme = localStorage.getItem('theme');

// Apply saved theme on load
if (savedTheme === 'dark') {
  document.body.classList.add('dark-mode');
  nightModeToggle.textContent = '☀ Light Mode';
}

nightModeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');

  if (document.body.classList.contains('dark-mode')) {
    nightModeToggle.textContent = '☀ Light Mode';
    localStorage.setItem('theme', 'dark');
  } else {
    nightModeToggle.textContent = '☾ Night Mode';
    localStorage.setItem('theme', 'light');
  }
});

// MARC File Processing
let currentMARCResult = null;

// File upload handling
const fileUploadArea = document.getElementById('fileUploadArea');
const marcFileInput = document.getElementById('marcFileInput');
const marcProgress = document.getElementById('marcProgress');
const marcReport = document.getElementById('marcReport');

fileUploadArea.addEventListener('click', () => {
  marcFileInput.click();
});

fileUploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  fileUploadArea.classList.add('drag-over');
});

fileUploadArea.addEventListener('dragleave', () => {
  fileUploadArea.classList.remove('drag-over');
});

fileUploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  fileUploadArea.classList.remove('drag-over');

  const files = e.dataTransfer.files;
  if (files.length > 0) {
    handleMARCFile(files[0]);
  }
});

marcFileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    handleMARCFile(e.target.files[0]);
  }
});

// Example file buttons
document.querySelectorAll('.example-link').forEach(button => {
  button.addEventListener('click', async (e) => {
    const filePath = e.target.getAttribute('data-file');
    try {
      const response = await fetch(filePath);
      const blob = await response.blob();
      const fileName = filePath.split('/').pop();
      const file = new File([blob], fileName, { type: blob.type });
      handleMARCFile(file);
    } catch (error) {
      console.error('Error loading example file:', error);
      alert('Failed to load example file: ' + error.message);
    }
  });
});

async function handleMARCFile(file) {
  // Reset UI
  marcProgress.style.display = 'block';
  marcReport.style.display = 'none';
  document.getElementById('reportDetails').style.display = 'none';

  try {
    currentMARCResult = await processMARCFile(file, trie, lookupDecoder, (progress) => {
      document.getElementById('marcProgressText').textContent = progress.message;
      document.getElementById('marcProgressPercent').textContent = `${progress.percent}%`;
      document.getElementById('marcProgressBar').style.width = `${progress.percent}%`;
    });

    // Hide progress, show report
    marcProgress.style.display = 'none';
    marcReport.style.display = 'block';

    // Update report summary
    const { report } = currentMARCResult;
    document.getElementById('reportTotalRecords').textContent = report.totalRecords;
    document.getElementById('reportFieldsProcessed').textContent = report.totalFieldsProcessed;
    document.getElementById('reportFieldsUpdated').textContent = report.fieldsUpdated;
    document.getElementById('reportFieldsNotFound').textContent = report.fieldsNotFound;
    document.getElementById('reportFieldsPoorMatch').textContent = report.fieldsPoorMatch;

  } catch (error) {
    console.error('MARC processing error:', error);
    marcProgress.style.display = 'none';
    alert(`Error processing MARC file: ${error.message}`);
  }
}

// Download enhanced MARC file
document.getElementById('downloadMarcBtn').addEventListener('click', () => {
  if (!currentMARCResult) return;

  const url = URL.createObjectURL(currentMARCResult.outputBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = currentMARCResult.outputFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// Download report as JSON
document.getElementById('downloadReportBtn').addEventListener('click', () => {
  if (!currentMARCResult) return;

  const jsonBlob = new Blob([JSON.stringify(currentMARCResult.report, null, 2)], {
    type: 'application/json'
  });

  const url = URL.createObjectURL(jsonBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'marc_processing_report.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// Toggle report details
document.getElementById('toggleDetailsBtn').addEventListener('click', () => {
  const detailsEl = document.getElementById('reportDetails');
  const btn = document.getElementById('toggleDetailsBtn');

  if (detailsEl.style.display === 'none') {
    // Show details
    renderReportDetails();
    detailsEl.style.display = 'block';
    btn.textContent = 'Hide Details';
  } else {
    // Hide details
    detailsEl.style.display = 'none';
    btn.textContent = 'Show Details';
  }
});

function renderReportDetails() {
  if (!currentMARCResult) return;

  const detailsEl = document.getElementById('reportDetails');
  const { report } = currentMARCResult;

  let html = '';

  for (const detail of report.details) {
    let statusClass = detail.status;
    let statusText = detail.status.replace('_', ' ').toUpperCase();

    html += `<div class="detail-item">`;
    html += `<span class="detail-status ${statusClass}">${statusText}</span>`;
    html += `<strong>Record ${detail.recordIndex}, Field ${detail.field}:</strong> ${detail.name}`;

    if (detail.status === 'updated' && detail.lccnUri) {
      html += `<br><span style="color: #666;">→ Added: <a href="${detail.lccnUri}" target="_blank">${detail.lccnUri}</a></span>`;
      if (detail.matchedLabel) {
        html += `<br><span style="color: #999; font-size: 0.85em;">Matched: "${detail.matchedLabel}" (distance: ${detail.levenshteinDistance})</span>`;
      }
    } else if (detail.reason) {
      html += `<br><span style="color: #999; font-size: 0.85em;">${detail.reason}</span>`;
      if (detail.matchedLabel) {
        html += ` (matched: "${detail.matchedLabel}", distance: ${detail.levenshteinDistance})`;
      }
    }

    html += `</div>`;
  }

  detailsEl.innerHTML = html;
}

// Load trie on page load
loadTrie().then(() => {
  // Show MARC processor section after trie is loaded
  document.getElementById('marcProcessorSection').style.display = 'block';
  document.getElementById('otherSearchSection').style.display = 'block';
});
