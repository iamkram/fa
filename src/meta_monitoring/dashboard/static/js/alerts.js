/**
 * Alerts Dashboard Page Logic
 */

let currentAlertId = null;

/**
 * Initialize the alerts page
 */
async function initAlerts() {
    console.log('Initializing alerts page...');

    // Load initial data
    await loadAlertStats();
    await loadAlerts();

    // Set up filter listeners
    document.getElementById('severity-filter').addEventListener('change', loadAlerts);
    document.getElementById('status-filter').addEventListener('change', loadAlerts);

    updateLastUpdatedTime();
}

/**
 * Load alert statistics
 */
async function loadAlertStats() {
    try {
        const stats = await api.getAlertStats();

        setTextContent('critical-count', stats.critical_count || 0);
        setTextContent('high-count', stats.high_count || 0);
        setTextContent('active-count', stats.active_count || 0);
        setTextContent('resolved-count', stats.resolved_24h || 0);
    } catch (error) {
        handleApiError(error, 'loading alert statistics');
    }
}

/**
 * Load alerts with current filters
 */
async function loadAlerts() {
    try {
        const severityFilter = document.getElementById('severity-filter').value;
        const statusFilter = document.getElementById('status-filter').value;

        const params = {};
        if (severityFilter) params.severity = severityFilter;
        if (statusFilter) params.status = statusFilter;

        const alerts = await api.getAlerts(params);

        const container = document.getElementById('alerts-container');
        if (!container) return;

        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No alerts found</p>';
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
                <th>Type</th>
                <th>Severity</th>
                <th>Triggered</th>
                <th>Status</th>
                <th>Actions</th>
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
                    <small style="color: var(--text-secondary);">${truncate(alert.description || '', 80)}</small>
                </td>
                <td>${alert.alert_type || 'unknown'}</td>
                <td>
                    <span class="severity-badge ${getSeverityClass(alert.severity)}">
                        ${alert.severity || 'unknown'}
                    </span>
                </td>
                <td>${formatDateTime(alert.triggered_at)}</td>
                <td>${alert.status || 'active'}</td>
                <td>
                    <button class="btn-link" onclick="viewAlertDetails('${alert.alert_id}')">View →</button>
                </td>
            `;
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        container.innerHTML = '';
        container.appendChild(table);

        updateLastUpdatedTime();
    } catch (error) {
        handleApiError(error, 'loading alerts');
    }
}

/**
 * View alert details in modal
 */
async function viewAlertDetails(alertId) {
    try {
        // For now, find the alert from the loaded list
        // In a production system, you'd make an API call to get full details
        const params = {};
        const alerts = await api.getAlerts(params);
        const alert = alerts.find(a => a.alert_id === alertId);

        if (!alert) {
            showToast('Alert not found', 'error');
            return;
        }

        currentAlertId = alertId;

        // Populate modal
        document.getElementById('modal-title').textContent = alert.alert_title || 'Alert Details';

        const modalContent = document.getElementById('modal-content');
        modalContent.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <strong>Alert ID:</strong> ${alert.alert_id}<br>
                <strong>Type:</strong> ${alert.alert_type || 'unknown'}<br>
                <strong>Severity:</strong> <span class="severity-badge ${getSeverityClass(alert.severity)}">${alert.severity}</span><br>
                <strong>Status:</strong> ${alert.status || 'active'}<br>
                <strong>Triggered:</strong> ${formatDateTime(alert.triggered_at)}<br>
                ${alert.acknowledged_at ? `<strong>Acknowledged:</strong> ${formatDateTime(alert.acknowledged_at)}<br>` : ''}
                ${alert.resolved_at ? `<strong>Resolved:</strong> ${formatDateTime(alert.resolved_at)}<br>` : ''}
            </div>
            <div style="margin-bottom: 1rem;">
                <strong>Description:</strong><br>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">${alert.description || 'No description available'}</p>
            </div>
            ${alert.context_data ? `
                <div style="margin-bottom: 1rem;">
                    <strong>Context Data:</strong><br>
                    <pre style="background: var(--bg-primary); padding: 0.5rem; border-radius: 0.25rem; overflow-x: auto; margin-top: 0.5rem;">${JSON.stringify(alert.context_data, null, 2)}</pre>
                </div>
            ` : ''}
        `;

        // Show/hide action buttons based on status
        const acknowledgeBtn = document.getElementById('acknowledge-btn');
        const resolveBtn = document.getElementById('resolve-btn');

        if (alert.status === 'active') {
            acknowledgeBtn.style.display = 'inline-block';
            resolveBtn.style.display = 'inline-block';
        } else if (alert.status === 'acknowledged') {
            acknowledgeBtn.style.display = 'none';
            resolveBtn.style.display = 'inline-block';
        } else {
            acknowledgeBtn.style.display = 'none';
            resolveBtn.style.display = 'none';
        }

        // Show modal
        const modal = document.getElementById('alert-modal');
        modal.style.display = 'flex';
    } catch (error) {
        handleApiError(error, 'loading alert details');
    }
}

/**
 * Close alert modal
 */
function closeAlertModal() {
    const modal = document.getElementById('alert-modal');
    modal.style.display = 'none';
    currentAlertId = null;
}

/**
 * Acknowledge current alert
 */
async function acknowledgeAlert() {
    if (!currentAlertId) return;

    try {
        await api.acknowledgeAlert(currentAlertId);
        showToast('Alert acknowledged successfully', 'success');
        closeAlertModal();
        await loadAlerts();
        await loadAlertStats();
    } catch (error) {
        handleApiError(error, 'acknowledging alert');
    }
}

/**
 * Resolve current alert
 */
async function resolveAlert() {
    if (!currentAlertId) return;

    try {
        await api.resolveAlert(currentAlertId);
        showToast('Alert resolved successfully', 'success');
        closeAlertModal();
        await loadAlerts();
        await loadAlertStats();
    } catch (error) {
        handleApiError(error, 'resolving alert');
    }
}

// Attach button handlers
document.addEventListener('DOMContentLoaded', () => {
    initAlerts();

    const acknowledgeBtn = document.getElementById('acknowledge-btn');
    if (acknowledgeBtn) {
        acknowledgeBtn.addEventListener('click', acknowledgeAlert);
    }

    const resolveBtn = document.getElementById('resolve-btn');
    if (resolveBtn) {
        resolveBtn.addEventListener('click', resolveAlert);
    }
});
