/**
 * Batch Processing Dashboard JavaScript
 * Provides real-time monitoring and visualization of batch processing runs
 */

// State
let batchData = {
    runs: [],
    currentRun: null,
    stats: {}
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
    setupEventListeners();
    loadInitialData();
});

function initializeDashboard() {
    console.log('📊 Initializing Batch Processing Dashboard...');
}

function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Refresh button
    document.getElementById('refreshButton')?.addEventListener('click', refreshData);

    // Runs limit selector
    document.getElementById('runsLimit')?.addEventListener('change', (e) => {
        loadBatchRuns(e.target.value);
    });

    // Stock run selector
    document.getElementById('stockRunSelector')?.addEventListener('change', (e) => {
        if (e.target.value) {
            loadStockDetails(e.target.value);
        }
    });

    // Auto-refresh every 30 seconds
    setInterval(refreshData, 30000);
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === `${tabName}-pane`);
    });

    // Load data for specific tabs
    if (tabName === 'runs') {
        loadBatchRuns(20);
    } else if (tabName === 'insights') {
        loadInsights();
    }
}

async function loadInitialData() {
    try {
        updateStatus('loading', 'Loading data...');

        await Promise.all([
            loadLatestRun(),
            loadBatchRuns(20)
        ]);

        updateStatus('success', 'Connected');
    } catch (error) {
        console.error('Error loading initial data:', error);
        updateStatus('error', 'Connection error');
    }
}

async function refreshData() {
    console.log('🔄 Refreshing data...');
    await loadInitialData();
}

function updateStatus(status, text) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    if (statusDot) {
        statusDot.classList.remove('error');
        if (status === 'error') {
            statusDot.classList.add('error');
        }
    }

    if (statusText) {
        statusText.textContent = text;
    }
}

async function loadLatestRun() {
    try {
        // Mock data - replace with actual API call
        const response = await fetch('/api/batch/latest-run');
        const data = await response.json();

        updateLatestRunDisplay(data);
        updateSummaryCards(data);
    } catch (error) {
        console.error('Error loading latest run:', error);
        // Use mock data for development
        loadMockLatestRun();
    }
}

function loadMockLatestRun() {
    const mockData = {
        run_id: '4ee113ff-e366-42b0-889a-79553aaf60c3',
        run_date: '2025-11-11 13:55:32',
        total_stocks: 5,
        successful: 5,
        failed: 0,
        duration_ms: 186000,
        avg_hook_words: 150,
        avg_medium_words: 300,
        avg_expanded_words: 500,
        hook_retries: 2,
        medium_retries: 1,
        expanded_retries: 0,
        hook_fact_check_rate: 1.0,
        medium_fact_check_rate: 1.0,
        expanded_fact_check_rate: 1.0
    };

    updateLatestRunDisplay(mockData);
    updateSummaryCards(mockData);
}

function updateLatestRunDisplay(data) {
    document.getElementById('latestRunId').textContent = data.run_id.substring(0, 8);
    document.getElementById('latestRunDate').textContent = new Date(data.run_date).toLocaleString();
    document.getElementById('latestStocksProcessed').textContent = data.total_stocks;
    document.getElementById('latestDuration').textContent = formatDuration(data.duration_ms);
    document.getElementById('latestSuccessful').textContent = data.successful;
    document.getElementById('latestFailed').textContent = data.failed;

    const badge = document.getElementById('latestStatus');
    if (badge) {
        badge.textContent = data.failed === 0 ? 'COMPLETED' : 'COMPLETED WITH ERRORS';
        badge.className = data.failed === 0 ? 'badge success' : 'badge warning';
    }

    // Performance bars
    updateMetricBar('hook', data.avg_hook_words, 200);
    updateMetricBar('medium', data.avg_medium_words, 400);
    updateMetricBar('expanded', data.avg_expanded_words, 600);

    // Retries
    document.getElementById('hookRetries').textContent = data.hook_retries || 0;
    document.getElementById('mediumRetries').textContent = data.medium_retries || 0;
    document.getElementById('expandedRetries').textContent = data.expanded_retries || 0;
}

function updateMetricBar(type, value, max) {
    const percentage = Math.min((value / max) * 100, 100);
    const bar = document.getElementById(`${type}Bar`);
    const valueEl = document.getElementById(`${type}Value`);

    if (bar) bar.style.width = `${percentage}%`;
    if (valueEl) valueEl.textContent = `${Math.round(value)} words`;
}

function updateSummaryCards(data) {
    const successRate = data.total_stocks > 0
        ? ((data.successful / data.total_stocks) * 100).toFixed(1)
        : 0;

    document.getElementById('successRate').textContent = `${successRate}%`;
    document.getElementById('totalProcessed').textContent = data.total_stocks;
    document.getElementById('avgTime').textContent = formatDuration(data.duration_ms / data.total_stocks);

    const avgFactCheckRate = (
        (data.hook_fact_check_rate + data.medium_fact_check_rate + data.expanded_fact_check_rate) / 3 * 100
    ).toFixed(1);
    document.getElementById('factCheckRate').textContent = `${avgFactCheckRate}%`;

    // Update quality bars in insights tab
    updateQualityBar('hook', data.hook_fact_check_rate);
    updateQualityBar('medium', data.medium_fact_check_rate);
    updateQualityBar('expanded', data.expanded_fact_check_rate);
}

function updateQualityBar(type, rate) {
    const percentage = (rate * 100).toFixed(1);
    const bar = document.getElementById(`${type}QualityBar`);
    const valueEl = document.getElementById(`${type}QualityValue`);

    if (bar) {
        bar.style.width = `${percentage}%`;
        bar.className = `quality-fill ${getQualityClass(rate)}`;
    }
    if (valueEl) valueEl.textContent = `${percentage}%`;
}

function getQualityClass(rate) {
    if (rate >= 0.9) return 'success';
    if (rate >= 0.7) return 'warning';
    return 'error';
}

async function loadBatchRuns(limit = 20) {
    try {
        const response = await fetch(`/api/batch/runs?limit=${limit}`);
        const runs = await response.json();

        updateRunsTable(runs);
        populateRunSelector(runs);
    } catch (error) {
        console.error('Error loading batch runs:', error);
        // Load mock data for development
        loadMockBatchRuns(limit);
    }
}

function loadMockBatchRuns(limit) {
    const mockRuns = [
        {
            run_id: '4ee113ff-e366-42b0-889a-79553aaf60c3',
            run_date: '2025-11-11 13:55:32',
            total_stocks: 5,
            successful: 5,
            failed: 0,
            duration_ms: 186000
        },
        {
            run_id: '8592f714-3c64-43dd-8e3f-6dd5dbd96ec2',
            run_date: '2025-11-11 14:06:48',
            total_stocks: 5,
            successful: 5,
            failed: 0,
            duration_ms: 191000
        }
    ];

    updateRunsTable(mockRuns.slice(0, limit));
    populateRunSelector(mockRuns);
}

function updateRunsTable(runs) {
    const tbody = document.getElementById('runsTableBody');
    if (!tbody) return;

    if (runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="info">No batch runs found</td></tr>';
        return;
    }

    tbody.innerHTML = runs.map(run => {
        const successRate = ((run.successful / run.total_stocks) * 100).toFixed(1);
        const statusClass = run.failed === 0 ? 'success' : 'error';

        return `
            <tr>
                <td>${new Date(run.run_date).toLocaleString()}</td>
                <td><span class="mono">${run.run_id.substring(0, 8)}</span></td>
                <td>${run.total_stocks}</td>
                <td class="success">${run.successful}</td>
                <td class="error">${run.failed}</td>
                <td><span class="status-badge ${statusClass}">${successRate}%</span></td>
                <td>${formatDuration(run.duration_ms)}</td>
                <td>
                    <button class="action-button" onclick="viewRunDetails('${run.run_id}')">
                        View
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function populateRunSelector(runs) {
    const selector = document.getElementById('stockRunSelector');
    if (!selector) return;

    selector.innerHTML = '<option value="">Select a batch run...</option>' +
        runs.map(run => `
            <option value="${run.run_id}">
                ${new Date(run.run_date).toLocaleString()} - ${run.total_stocks} stocks
            </option>
        `).join('');
}

async function loadStockDetails(runId) {
    try {
        const response = await fetch(`/api/batch/runs/${runId}/stocks`);
        const stocks = await response.json();

        updateStocksTable(stocks);
    } catch (error) {
        console.error('Error loading stock details:', error);
        // Load mock data
        loadMockStockDetails();
    }
}

function loadMockStockDetails() {
    const mockStocks = [
        {
            ticker: 'AAPL',
            success: true,
            hook_wc: 148,
            medium_wc: 297,
            expanded_wc: 512,
            hook_fact_check: 'passed',
            medium_fact_check: 'passed',
            expanded_fact_check: 'passed',
            total_retries: 0,
            processing_time_ms: 35421
        },
        {
            ticker: 'MSFT',
            success: true,
            hook_wc: 152,
            medium_wc: 305,
            expanded_wc: 498,
            hook_fact_check: 'passed',
            medium_fact_check: 'passed',
            expanded_fact_check: 'passed',
            total_retries: 1,
            processing_time_ms: 38129
        }
    ];

    updateStocksTable(mockStocks);
}

function updateStocksTable(stocks) {
    const tbody = document.getElementById('stocksTableBody');
    if (!tbody) return;

    if (stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="info">No stock data found for this run</td></tr>';
        return;
    }

    tbody.innerHTML = stocks.map(stock => {
        const statusClass = stock.success ? 'success' : 'error';
        const factCheckEmoji = stock.hook_fact_check === 'passed' ? '✅' : '⚠️';

        return `
            <tr>
                <td><strong>${stock.ticker}</strong></td>
                <td><span class="status-badge ${statusClass}">${stock.success ? 'Success' : 'Failed'}</span></td>
                <td>${stock.hook_wc}w</td>
                <td>${stock.medium_wc}w</td>
                <td>${stock.expanded_wc}w</td>
                <td>${factCheckEmoji} ${stock.hook_fact_check}</td>
                <td>${stock.total_retries}</td>
                <td>${stock.processing_time_ms}ms</td>
            </tr>
        `;
    }).join('');
}

function viewRunDetails(runId) {
    // Switch to stocks tab and load details
    switchTab('stocks');
    const selector = document.getElementById('stockRunSelector');
    if (selector) {
        selector.value = runId;
        loadStockDetails(runId);
    }
}

async function loadInsights() {
    // Load quality metrics and generate recommendations
    const recommendations = generateRecommendations(batchData);
    displayRecommendations(recommendations);
}

function generateRecommendations(data) {
    const recommendations = [];

    // Example recommendations logic
    recommendations.push({
        icon: '💡',
        title: 'System performing well',
        text: 'All batch runs completing successfully with good quality metrics'
    });

    return recommendations;
}

function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendations');
    if (!container) return;

    container.innerHTML = recommendations.map(rec => `
        <div class="recommendation">
            <div class="recommendation-icon">${rec.icon}</div>
            <div class="recommendation-content">
                <div class="recommendation-title">${rec.title}</div>
                <div class="recommendation-text">${rec.text}</div>
            </div>
        </div>
    `).join('');
}

// Utility Functions
function formatDuration(ms) {
    if (!ms) return '--';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
}

function formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
}

// Export for debugging
window.batchDashboard = {
    loadInitialData,
    refreshData,
    switchTab,
    viewRunDetails
};

console.log('📊 Batch Dashboard loaded successfully');
