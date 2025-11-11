import { TrieLoader } from './trieLoader.js';

// DOM elements
const loadingSection = document.getElementById('loadingSection');
const searchSection = document.getElementById('searchSection');
const searchInput = document.getElementById('searchInput');
const resultsCard = document.getElementById('resultsCard');
const resultsContent = document.getElementById('resultsContent');
const trieFill = document.getElementById('trieFill');
const trieProgress = document.getElementById('trieProgress');
const lookupFill = document.getElementById('lookupFill');
const lookupProgress = document.getElementById('lookupProgress');
const trieSizeEl = document.getElementById('trieSize');
const searchStats = document.getElementById('searchStats');

// Initialize
const loader = new TrieLoader();
let isLoading = false;

// Load trie on page load
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const stats = await loader.loadWithProgress((type, percent, message) => {
            if (type === 'trie') {
                trieFill.style.width = `${percent}%`;
                trieProgress.textContent = `${percent}%`;
            } else if (type === 'lookup') {
                lookupFill.style.width = `${percent}%`;
                lookupProgress.textContent = `${percent}%`;
            }
        });

        // Hide loading, show search
        loadingSection.classList.add('hidden');
        searchSection.classList.add('ready');

        // Update stats
        trieSizeEl.textContent = stats.trieSize.toLocaleString();

        // Show stats after data is loaded
        searchStats.classList.add('visible');

        // Focus search input
        searchInput.focus();
    } catch (error) {
        console.error('Failed to load:', error);
        showError('Failed to load the database. Please refresh the page.');
    }
});

// Generate permutations of the search query
function generateQueryPermutations(query) {
    const permutations = new Set();

    // Add original query
    permutations.add(query);

    // Split into words
    const words = query.split(/\s+/);

    if (words.length === 1) {
        // Single word - try different capitalizations
        const word = words[0];
        permutations.add(word.toLowerCase());
        permutations.add(word.toUpperCase());
        permutations.add(word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
    } else if (words.length >= 2) {
        // Multiple words - try various combinations

        // All lowercase
        permutations.add(words.join(' ').toLowerCase());

        // All uppercase
        permutations.add(words.join(' ').toUpperCase());

        // Title case (capitalize each word)
        const titleCase = words.map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
        permutations.add(titleCase);

        // First word capitalized only
        const firstCap = words[0].charAt(0).toUpperCase() + words[0].slice(1).toLowerCase() + ' ' +
                        words.slice(1).map(w => w.toLowerCase()).join(' ');
        permutations.add(firstCap);

        // Try with comma after first word (for partial searches like "woolf vir" -> "Woolf, Vir")
        for (let i = 1; i < words.length; i++) {
            // Comma after position i-1
            const beforeComma = words.slice(0, i).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
            const afterComma = words.slice(i).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
            permutations.add(beforeComma.join(' ') + ', ' + afterComma.join(' '));

            // Also try with lowercase after comma
            const afterCommaLower = words.slice(i).map(w => w.toLowerCase());
            permutations.add(beforeComma.join(' ') + ', ' + afterCommaLower.join(' '));
        }

        // Last name, First name format (with comma) for 2 words
        if (words.length === 2) {
            // "firstname lastname" -> "Lastname, Firstname"
            const lastFirst = words[1].charAt(0).toUpperCase() + words[1].slice(1).toLowerCase() + ', ' +
                            words[0].charAt(0).toUpperCase() + words[0].slice(1).toLowerCase();
            permutations.add(lastFirst);

            // Also try with lowercase after comma
            const lastFirstLower = words[1].charAt(0).toUpperCase() + words[1].slice(1).toLowerCase() + ', ' +
                                  words[0].toLowerCase();
            permutations.add(lastFirstLower);
        }

        // For 3+ words, try "Last, First Middle" format
        if (words.length >= 3) {
            const last = words[words.length - 1];
            const rest = words.slice(0, -1);
            const lastFirstMiddle = last.charAt(0).toUpperCase() + last.slice(1).toLowerCase() + ', ' +
                                   rest.map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
            permutations.add(lastFirstMiddle);
        }
    }

    return Array.from(permutations);
}

// Search functionality
function performSearch() {
    const query = searchInput.value.trim();

    if (!query) {
        return;
    }

    if (isLoading) {
        return;
    }

    try {
        // Generate all permutations of the query
        const queryPermutations = generateQueryPermutations(query);

        // Try exact matches for all permutations
        const exactResults = [];
        for (const permutation of queryPermutations) {
            const result = loader.search(permutation);
            if (result) {
                exactResults.push(result);
            }
        }

        // Always try predictive search with all permutations
        const allPredictions = new Map(); // Use map to deduplicate by key

        for (const permutation of queryPermutations) {
            const predictions = loader.predictiveSearch(permutation);
            for (const pred of predictions) {
                // Use the key as unique identifier to avoid duplicates
                if (!allPredictions.has(pred.key)) {
                    allPredictions.set(pred.key, pred);
                }
            }
        }

        const allPredictionsArray = Array.from(allPredictions.values());
        const predictions = allPredictionsArray.slice(0, 500);
        const hasMore = allPredictionsArray.length > 500;

        if (exactResults.length > 0) {
            // Show exact matches AND predictive results
            showSuccessWithPredictions(exactResults, query, predictions, hasMore, allPredictionsArray);
        } else {
            // No exact match, just show predictive results
            if (predictions.length > 0) {
                showPredictiveResults(query, predictions, hasMore, allPredictionsArray);
            } else {
                showNotFound(query);
            }
        }
    } catch (error) {
        console.error('Search error:', error);
        showError('An error occurred during search.');
    }
}

function showSuccess(results, originalQuery) {
    // Handle both single result and array of results
    const resultArray = Array.isArray(results) ? results : [results];

    // Remove duplicates based on LCCN
    const uniqueResults = [];
    const seenLCCNs = new Set();

    for (const result of resultArray) {
        if (!seenLCCNs.has(result.lccn)) {
            seenLCCNs.add(result.lccn);
            uniqueResults.push(result);
        }
    }

    if (uniqueResults.length === 1) {
        // Single result
        const result = uniqueResults[0];
        const formattedLCCN = formatLCCN(result.lccn);

        resultsContent.innerHTML = `
            <div class="result-success">
                <div class="result-icon">✓</div>
                <div class="result-label">${escapeHtml(result.query)}</div>
                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}" target="_blank" class="result-lccn" style="text-decoration: none;">${formattedLCCN}</a>
            </div>
        `;
    } else {
        // Multiple results
        const resultsHTML = uniqueResults.map(result => {
            const formattedLCCN = formatLCCN(result.lccn);
            return `
                <div style="margin: 15px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <div style="font-size: 1rem; color: #333; margin-bottom: 8px; font-weight: 500;">${escapeHtml(result.query)}</div>
                    <a href="https://id.loc.gov/authorities/names/${formattedLCCN}" target="_blank" class="result-lccn" style="text-decoration: none; font-size: 1.2rem;">${formattedLCCN}</a>
                </div>
            `;
        }).join('');

        resultsContent.innerHTML = `
            <div class="result-success">
                <div class="result-icon">✓</div>
                <div style="font-size: 1.1rem; color: #333; margin-bottom: 20px;">Found ${uniqueResults.length} match${uniqueResults.length !== 1 ? 'es' : ''} for: <strong>${escapeHtml(originalQuery)}</strong></div>
                ${resultsHTML}
            </div>
        `;
    }

    resultsCard.classList.add('visible');
}

function showSuccessWithPredictions(results, originalQuery, predictions, hasMore, allPredictions) {
    // Handle both single result and array of results
    const resultArray = Array.isArray(results) ? results : [results];

    // Remove duplicates based on LCCN
    const uniqueResults = [];
    const seenLCCNs = new Set();

    for (const result of resultArray) {
        if (!seenLCCNs.has(result.lccn)) {
            seenLCCNs.add(result.lccn);
            uniqueResults.push(result);
        }
    }

    // Build exact match section
    let exactMatchHTML = '';
    if (uniqueResults.length === 1) {
        const result = uniqueResults[0];
        const formattedLCCN = formatLCCN(result.lccn);
        exactMatchHTML = `
            <div class="result-success">
                <div class="result-icon">✓</div>
                <div class="result-label">${escapeHtml(result.query)}</div>
                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}" target="_blank" class="result-lccn" style="text-decoration: none;">${formattedLCCN}</a>
            </div>
        `;
    } else {
        const resultsHTML = uniqueResults.map(result => {
            const formattedLCCN = formatLCCN(result.lccn);
            return `
                <div style="margin: 15px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px;">
                    <div style="font-size: 1rem; color: #333; margin-bottom: 8px; font-weight: 500;">${escapeHtml(result.query)}</div>
                    <a href="https://id.loc.gov/authorities/names/${formattedLCCN}" target="_blank" class="result-lccn" style="text-decoration: none; font-size: 1.2rem;">${formattedLCCN}</a>
                </div>
            `;
        }).join('');

        exactMatchHTML = `
            <div class="result-success">
                <div class="result-icon">✓</div>
                <div style="font-size: 1.1rem; color: #333; margin-bottom: 20px;">Found ${uniqueResults.length} match${uniqueResults.length !== 1 ? 'es' : ''} for: <strong>${escapeHtml(originalQuery)}</strong></div>
                ${resultsHTML}
            </div>
        `;
    }

    // Build predictive results section
    const predictiveHTML = predictions.map(pred => {
        const formattedLCCN = formatLCCN(pred.lccn);
        return `
            <div class="prediction-item">
                <div class="prediction-label">${escapeHtml(pred.key)}</div>
                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}"
                   target="_blank"
                   class="prediction-lccn">${formattedLCCN}</a>
            </div>
        `;
    }).join('');

    const moreButton = hasMore ? `
        <div style="text-align: center; padding: 20px; border-top: 1px solid #e8e8e8;">
            <button id="showMoreBtn" style="background: none; border: none; color: #666; font-size: 0.9rem; cursor: pointer; padding: 10px 20px; text-decoration: underline;">
                ${allPredictions.length - 500} more results
            </button>
        </div>
    ` : '';

    // Combine both sections
    resultsContent.innerHTML = `
        ${exactMatchHTML}
        <div style="margin-top: 40px; padding-top: 30px; border-top: 2px solid #e0e0e0;">
            <div style="font-size: 1rem; color: #666; margin-bottom: 20px; font-weight: 500;">All matching entries:</div>
            <div class="result-predictions">
                <div class="predictions-list" id="predictionsList">
                    ${predictiveHTML}
                </div>
                ${moreButton}
            </div>
        </div>
    `;

    // Add event listener for the "more results" button
    if (hasMore) {
        setTimeout(() => {
            const showMoreBtn = document.getElementById('showMoreBtn');
            if (showMoreBtn) {
                showMoreBtn.addEventListener('click', () => {
                    const remainingPredictions = allPredictions.slice(500);
                    const remainingHTML = remainingPredictions.map(pred => {
                        const formattedLCCN = formatLCCN(pred.lccn);
                        return `
                            <div class="prediction-item">
                                <div class="prediction-label">${escapeHtml(pred.key)}</div>
                                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}"
                                   target="_blank"
                                   class="prediction-lccn">${formattedLCCN}</a>
                            </div>
                        `;
                    }).join('');

                    const predictionsList = document.getElementById('predictionsList');
                    predictionsList.innerHTML += remainingHTML;
                    showMoreBtn.remove();
                });
            }
        }, 0);
    }

    resultsCard.classList.add('visible');
}

function showPredictiveResults(query, predictions, hasMore, allPredictions) {
    const resultsList = predictions.map(pred => {
        const formattedLCCN = formatLCCN(pred.lccn);
        return `
            <div class="prediction-item">
                <div class="prediction-label">${escapeHtml(pred.key)}</div>
                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}"
                   target="_blank"
                   class="prediction-lccn">${formattedLCCN}</a>
            </div>
        `;
    }).join('');

    const moreButton = hasMore ? `
        <div style="text-align: center; padding: 20px; border-top: 1px solid #e8e8e8;">
            <button id="showMoreBtn" style="background: none; border: none; color: #666; font-size: 0.9rem; cursor: pointer; padding: 10px 20px; text-decoration: underline;">
                ${allPredictions.length - 500} more results
            </button>
        </div>
    ` : '';

    resultsContent.innerHTML = `
        <div class="result-predictions">
            <div class="predictions-list" id="predictionsList">
                ${resultsList}
            </div>
            ${moreButton}
        </div>
    `;

    // Add event listener for the "more results" button
    if (hasMore) {
        setTimeout(() => {
            const showMoreBtn = document.getElementById('showMoreBtn');
            if (showMoreBtn) {
                showMoreBtn.addEventListener('click', () => {
                    const remainingPredictions = allPredictions.slice(500);
                    const remainingHTML = remainingPredictions.map(pred => {
                        const formattedLCCN = formatLCCN(pred.lccn);
                        return `
                            <div class="prediction-item">
                                <div class="prediction-label">${escapeHtml(pred.key)}</div>
                                <a href="https://id.loc.gov/authorities/names/${formattedLCCN}"
                                   target="_blank"
                                   class="prediction-lccn">${formattedLCCN}</a>
                            </div>
                        `;
                    }).join('');

                    const predictionsList = document.getElementById('predictionsList');
                    predictionsList.innerHTML += remainingHTML;
                    showMoreBtn.remove();
                });
            }
        }, 0);
    }

    resultsCard.classList.add('visible');
}

function showNotFound(query) {
    resultsContent.innerHTML = `
        <div class="result-error">
            <div class="error-icon">🔍</div>
            <div class="error-message">
                No match found for:<br>
                <strong>${escapeHtml(query)}</strong>
            </div>
            <p style="margin-top: 20px; color: #999; font-size: 0.9rem;">
                Try a different search term
            </p>
        </div>
    `;
    resultsCard.classList.add('visible');
}

function showError(message) {
    resultsContent.innerHTML = `
        <div class="result-error">
            <div class="error-icon">⚠️</div>
            <div class="error-message">${escapeHtml(message)}</div>
        </div>
    `;
    resultsCard.classList.add('visible');
}

function formatLCCN(lccn) {
    if (typeof lccn === 'number') {
        // Convert back from compressed format
        const lccnStr = lccn.toString();
        // Map prefix numbers back to letters
        const prefixMap = {'1': 'nb', '2': 'nn', '3': 'no', '4': 'nr', '5': 'ns', '6': 'n'};
        const firstChar = lccnStr[0];

        if (prefixMap[firstChar]) {
            // This was a prefixed LCCN
            const prefix = prefixMap[firstChar];
            const number = lccnStr.substring(1);
            return `${prefix}${number}`;
        } else {
            // Default to 'n' prefix
            return `n${lccnStr.padStart(8, '0')}`;
        }
    }
    return lccn;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
// Debounce timer for auto-search
let searchTimeout;

searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        clearTimeout(searchTimeout);
        performSearch();
    }
});

searchInput.addEventListener('input', () => {
    // Hide results when user starts typing again
    if (resultsCard.classList.contains('visible')) {
        resultsCard.classList.remove('visible');
    }

    // Auto-search after typing at least 4 characters
    const query = searchInput.value.trim();

    // Clear previous timeout
    clearTimeout(searchTimeout);

    if (query.length >= 4) {
        // Debounce: wait 500ms after user stops typing
        searchTimeout = setTimeout(() => {
            performSearch();
        }, 500);
    }
});

console.log('LCNAF Search app initialized');
