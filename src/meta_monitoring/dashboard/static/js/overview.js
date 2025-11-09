/**
 * Overview Dashboard Page Logic
 * Handles data loading and auto-refresh for the overview page
 */

// Auto-refresh interval (30 seconds)
const REFRESH_INTERVAL = 30000;
let refreshTimer = null;

/**
 * Initialize the overview dashboard
 */
async function initOverview() {
    console.log('Initializing overview dashboard...');

    // Load all data
    await loadAllData();

    // Set up auto-refresh
    startAutoRefresh();
}

/**
 * Load all dashboard data
 */
async function loadAllData() {
    try {
        await Promise.all([
            loadSystemHealth(),
            loadKeyMetrics(),
            loadRecentAlerts(),
            loadProposalsSummary()
        ]);

        updateLastUpdatedTime();
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

/**
 * Load system health overview
 */
async function loadSystemHealth() {
    try {
        const health = await api.getHealth();

        // Update overall status
        const statusElement = document.getElementById('overall-status');
        if (statusElement && health.status) {
            statusElement.textContent = health.status;
            statusElement.className = `status-badge ${getStatusClass(health.status)}`;
        }

        // Update active alerts count
        setTextContent('active-alerts-count', health.active_alerts_count || 0);

        // Update critical alerts count
        setTextContent('critical-alerts-count', health.critical_alerts_count || 0);

        // Update latest evaluation time
        const evalTime = document.getElementById('latest-eval-time');
        if (evalTime && health.latest_evaluation_at) {
            evalTime.textContent = formatDateTime(health.latest_evaluation_at);
        }
    } catch (error) {
        handleApiError(error, 'loading system health');
    }
}

/**
 * Load key metrics
 */
async function loadKeyMetrics() {
    try {
        const metrics = await api.getLatestMetrics();

        if (!metrics || !metrics.metrics) {
            console.warn('No metrics data available');
            return;
        }

        const m = metrics.metrics;

        // Update fact accuracy
        setTextContent('fact-accuracy', formatPercent(m.fact_accuracy || 0));

        // Update guardrail pass rate
        setTextContent('guardrail-rate', formatPercent(m.guardrail_pass_rate || 0));

        // Update average response time
        setTextContent('response-time', formatDuration(m.avg_response_time_ms || 0));

        // Calculate SLA compliance (example: 95% threshold)
        const slaCompliance = calculateSLACompliance(m);
        setTextContent('sla-compliance', formatPercent(slaCompliance));
    } catch (error) {
        handleApiError(error, 'loading metrics');
    }
}

/**
 * Calculate SLA compliance based on metrics
 */
function calculateSLACompliance(metrics) {
    // Simple calculation: average of key metrics
    const factAccuracy = metrics.fact_accuracy || 0;
    const guardrailRate = metrics.guardrail_pass_rate || 0;
    const responseTimeCompliance = metrics.avg_response_time_ms < 2000 ? 1.0 : 0.8;

    return (factAccuracy + guardrailRate + responseTimeCompliance) / 3;
}

/**
 * Load recent alerts
 */
async function loadRecentAlerts() {
    try {
        const alerts = await api.getAlerts({ limit: 5, status: 'active' });

        const container = document.getElementById('recent-alerts-container');
        if (!container) return;

        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No active alerts</p>';
            return;
        }

        // Create alerts table
        const table = document.createElement('table');
        table.className = 'table';

        // Table header
        const thead = document.createElement('thead');
        thead.innerHTML = `
            <tr>
                <th>Alert</th>
                <th>Severity</th>
                <th>Time</th>
                <th>Status</th>
            </tr>
        `;
        table.appendChild(thead);

        // Table body
        const tbody = document.createElement('tbody');
        alerts.forEach(alert => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <strong>${alert.alert_title || 'Unknown Alert'}</strong><br>
                    <small style="color: var(--text-secondary);">${truncate(alert.description || '', 60)}</small>
                </td>
                <td>
                    <span class="severity-badge ${getSeverityClass(alert.severity)}">
                        ${alert.severity || 'unknown'}
                    </span>
                </td>
                <td>${formatDateTime(alert.triggered_at)}</td>
                <td>${alert.status || 'active'}</td>
            `;
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        container.innerHTML = '';
        container.appendChild(table);
    } catch (error) {
        handleApiError(error, 'loading recent alerts');
        const container = document.getElementById('recent-alerts-container');
        if (container) {
            container.innerHTML = '<p style="color: var(--error);">Error loading alerts</p>';
        }
    }
}

/**
 * Load proposals summary
 */
async function loadProposalsSummary() {
    try {
        const proposals = await api.getProposals({ limit: 5, status: 'pending_approval' });

        const container = document.getElementById('proposals-summary');
        if (!container) return;

        if (!proposals || proposals.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No pending proposals</p>';
            return;
        }

        // Create proposals table
        const table = document.createElement('table');
        table.className = 'table';

        // Table header
        const thead = document.createElement('thead');
        thead.innerHTML = `
            <tr>
                <th>Proposal</th>
                <th>Type</th>
                <th>Impact</th>
                <th>Created</th>
                <th>Action</th>
            </tr>
        `;
        table.appendChild(thead);

        // Table body
        const tbody = document.createElement('tbody');
        proposals.forEach(proposal => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <strong>${proposal.proposal_title || 'Unknown Proposal'}</strong><br>
                    <small style="color: var(--text-secondary);">${truncate(proposal.description || '', 60)}</small>
                </td>
                <td>${proposal.proposal_type || 'unknown'}</td>
                <td>${proposal.estimated_impact || 'N/A'}</td>
                <td>${formatDateTime(proposal.created_at)}</td>
                <td>
                    <a href="/dashboard/proposals?id=${proposal.proposal_id}" class="btn-link">Review →</a>
                </td>
            `;
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        container.innerHTML = '';
        container.appendChild(table);
    } catch (error) {
        handleApiError(error, 'loading proposals');
        const container = document.getElementById('proposals-summary');
        if (container) {
            container.innerHTML = '<p style="color: var(--error);">Error loading proposals</p>';
        }
    }
}

/**
 * Start auto-refresh timer
 */
function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    refreshTimer = setInterval(async () => {
        console.log('Auto-refreshing dashboard data...');
        await loadAllData();
    }, REFRESH_INTERVAL);

    console.log(`Auto-refresh enabled (every ${REFRESH_INTERVAL / 1000} seconds)`);
}

/**
 * Stop auto-refresh timer
 */
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
        console.log('Auto-refresh disabled');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initOverview);

// Clean up on page unload
window.addEventListener('beforeunload', stopAutoRefresh);
