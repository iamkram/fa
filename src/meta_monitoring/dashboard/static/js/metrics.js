/**
 * Metrics & Trends Dashboard Page Logic
 */

let charts = {};

/**
 * Initialize the metrics page
 */
async function initMetrics() {
    console.log('Initializing metrics page...');

    // Load initial data
    await loadCurrentMetrics();
    await loadMetricTrends();

    // Set up filter listener
    document.getElementById('timeframe-filter').addEventListener('change', loadMetricTrends);

    updateLastUpdatedTime();
}

/**
 * Load current metrics summary
 */
async function loadCurrentMetrics() {
    try {
        const metrics = await api.getLatestMetrics();

        if (!metrics || !metrics.metrics) {
            console.warn('No metrics data available');
            return;
        }

        const m = metrics.metrics;

        // Update current values
        setTextContent('current-fact-accuracy', formatPercent(m.fact_accuracy || 0));
        setTextContent('current-guardrail-rate', formatPercent(m.guardrail_pass_rate || 0));
        setTextContent('current-response-time', formatDuration(m.avg_response_time_ms || 0));
        setTextContent('evaluation-count', m.total_evaluations || 0);

        // Update trends (placeholder - would need historical data)
        updateTrendIndicator('fact-accuracy-trend', 0.02);
        updateTrendIndicator('guardrail-trend', 0.01);
        updateTrendIndicator('response-time-trend', -0.05);
        updateTrendIndicator('evaluation-trend', 0.1);
    } catch (error) {
        handleApiError(error, 'loading current metrics');
    }
}

/**
 * Update trend indicator
 */
function updateTrendIndicator(elementId, change) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const arrow = change > 0 ? '↑' : change < 0 ? '↓' : '→';
    const color = change > 0 ? 'var(--success)' : change < 0 ? 'var(--error)' : 'var(--text-secondary)';

    element.innerHTML = `<span style="color: ${color}; font-size: 0.875rem;">${arrow} ${formatPercent(Math.abs(change), 1)}</span>`;
}

/**
 * Load metric trends and render charts
 */
async function loadMetricTrends() {
    try {
        const timeframe = document.getElementById('timeframe-filter').value;
        const trends = await api.getMetricTrends({ timeframe });

        if (!trends || trends.length === 0) {
            console.warn('No trend data available');
            return;
        }

        // Prepare data for charts
        const labels = trends.map(t => formatDateTime(t.evaluated_at));
        const factAccuracyData = trends.map(t => (t.metrics?.fact_accuracy || 0) * 100);
        const guardrailData = trends.map(t => (t.metrics?.guardrail_pass_rate || 0) * 100);
        const responseTimeData = trends.map(t => t.metrics?.avg_response_time_ms || 0);

        // Render charts
        renderFactAccuracyChart(labels, factAccuracyData);
        renderGuardrailChart(labels, guardrailData);
        renderResponseTimeChart(labels, responseTimeData);
        renderMetricsTable(trends);

        updateLastUpdatedTime();
    } catch (error) {
        handleApiError(error, 'loading metric trends');
    }
}

/**
 * Render fact accuracy chart
 */
function renderFactAccuracyChart(labels, data) {
    const ctx = document.getElementById('fact-accuracy-chart');
    if (!ctx) return;

    // Destroy existing chart
    if (charts.factAccuracy) {
        charts.factAccuracy.destroy();
    }

    charts.factAccuracy = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Fact Accuracy (%)',
                data: data,
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: (value) => value + '%'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

/**
 * Render guardrail performance chart
 */
function renderGuardrailChart(labels, data) {
    const ctx = document.getElementById('guardrail-chart');
    if (!ctx) return;

    // Destroy existing chart
    if (charts.guardrail) {
        charts.guardrail.destroy();
    }

    charts.guardrail = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Guardrail Pass Rate (%)',
                data: data,
                borderColor: 'rgb(16, 185, 129)',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: (value) => value + '%'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

/**
 * Render response time chart
 */
function renderResponseTimeChart(labels, data) {
    const ctx = document.getElementById('response-time-chart');
    if (!ctx) return;

    // Destroy existing chart
    if (charts.responseTime) {
        charts.responseTime.destroy();
    }

    charts.responseTime = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Response Time (ms)',
                data: data,
                borderColor: 'rgb(245, 158, 11)',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value + ' ms'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

/**
 * Render metrics table
 */
function renderMetricsTable(trends) {
    const container = document.getElementById('metrics-table-container');
    if (!container) return;

    if (!trends || trends.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No metrics data available</p>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'table';

    // Table header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Timestamp</th>
            <th>Fact Accuracy</th>
            <th>Guardrail Pass Rate</th>
            <th>Avg Response Time</th>
            <th>Total Queries</th>
        </tr>
    `;
    table.appendChild(thead);

    // Table body
    const tbody = document.createElement('tbody');
    trends.forEach(trend => {
        const m = trend.metrics || {};
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formatDateTime(trend.evaluated_at)}</td>
            <td>${formatPercent(m.fact_accuracy || 0)}</td>
            <td>${formatPercent(m.guardrail_pass_rate || 0)}</td>
            <td>${formatDuration(m.avg_response_time_ms || 0)}</td>
            <td>${m.total_queries || 0}</td>
        `;
        tbody.appendChild(row);
    });
    table.appendChild(tbody);

    container.innerHTML = '';
    container.appendChild(table);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initMetrics);
