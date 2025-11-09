/**
 * Manual Controls Dashboard Page Logic
 */

let activityLog = [];

/**
 * Initialize the controls page
 */
async function initControls() {
    console.log('Initializing controls page...');

    // Load initial data
    await loadSystemStatus();
    await loadAlertOptions();
    await loadProposalOptions();
    await loadActivityLog();

    updateLastUpdatedTime();
}

/**
 * Load system status
 */
async function loadSystemStatus() {
    try {
        const health = await api.getHealth();

        // Update system status
        const statusElement = document.getElementById('system-status');
        if (statusElement && health.status) {
            statusElement.textContent = health.status;
            statusElement.className = `status-badge ${getStatusClass(health.status)}`;
        }

        // Update scheduler status (placeholder - would need API endpoint)
        setTextContent('scheduler-status', 'Running');

        // Update last/next evaluation
        setTextContent('last-eval', formatDateTime(health.latest_evaluation_at));

        // Calculate next scheduled evaluation (example: every hour)
        if (health.latest_evaluation_at) {
            const nextEval = new Date(health.latest_evaluation_at);
            nextEval.setHours(nextEval.getHours() + 1);
            setTextContent('next-eval', formatDateTime(nextEval));
        }
    } catch (error) {
        handleApiError(error, 'loading system status');
    }
}

/**
 * Load alert options for dropdown
 */
async function loadAlertOptions() {
    try {
        const alerts = await api.getAlerts({ status: 'active', limit: 20 });

        const select = document.getElementById('alert-select');
        if (!select) return;

        // Clear existing options except the first one
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add alert options
        alerts.forEach(alert => {
            const option = document.createElement('option');
            option.value = alert.alert_id;
            option.textContent = `${alert.alert_title} (${alert.severity})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading alert options:', error);
    }
}

/**
 * Load proposal options for dropdown
 */
async function loadProposalOptions() {
    try {
        const proposals = await api.getProposals({ status: 'pending_approval', limit: 20 });

        const select = document.getElementById('proposal-select');
        if (!select) return;

        // Clear existing options except the first one
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add proposal options
        proposals.forEach(proposal => {
            const option = document.createElement('option');
            option.value = proposal.proposal_id;
            option.textContent = `${proposal.proposal_title} (${proposal.proposal_type})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading proposal options:', error);
    }
}

/**
 * Trigger manual evaluation
 */
async function triggerEvaluation() {
    const statusElement = document.getElementById('eval-status');

    try {
        statusElement.textContent = 'Running evaluation...';
        statusElement.style.color = 'var(--primary)';

        const result = await api.triggerEvaluation();

        statusElement.textContent = `✓ Evaluation completed successfully`;
        statusElement.style.color = 'var(--success)';

        // Add to activity log
        addActivityLogEntry('Manual Evaluation', 'Triggered manual meta-evaluation', 'success');

        // Reload system status
        setTimeout(async () => {
            await loadSystemStatus();
            statusElement.textContent = '';
        }, 3000);

        showToast('Evaluation triggered successfully', 'success');
    } catch (error) {
        statusElement.textContent = '✗ Evaluation failed';
        statusElement.style.color = 'var(--error)';
        handleApiError(error, 'triggering evaluation');

        addActivityLogEntry('Manual Evaluation', 'Failed to trigger evaluation', 'error');
    }
}

/**
 * Trigger proposal generation
 */
async function triggerProposal() {
    const alertSelect = document.getElementById('alert-select');
    const statusElement = document.getElementById('proposal-status');

    const alertId = alertSelect.value;
    if (!alertId) {
        statusElement.textContent = '⚠ Please select an alert';
        statusElement.style.color = 'var(--warning)';
        return;
    }

    try {
        statusElement.textContent = 'Generating proposal...';
        statusElement.style.color = 'var(--primary)';

        const result = await api.triggerProposal(alertId);

        statusElement.textContent = `✓ Proposal generated successfully`;
        statusElement.style.color = 'var(--success)';

        addActivityLogEntry('Generate Proposal', `Generated proposal for alert ${alertId}`, 'success');

        setTimeout(() => {
            statusElement.textContent = '';
        }, 3000);

        showToast('Proposal generated successfully', 'success');
    } catch (error) {
        statusElement.textContent = '✗ Proposal generation failed';
        statusElement.style.color = 'var(--error)';
        handleApiError(error, 'generating proposal');

        addActivityLogEntry('Generate Proposal', 'Failed to generate proposal', 'error');
    }
}

/**
 * Trigger validation
 */
async function triggerValidation() {
    const proposalSelect = document.getElementById('proposal-select');
    const statusElement = document.getElementById('validation-status');

    const proposalId = proposalSelect.value;
    if (!proposalId) {
        statusElement.textContent = '⚠ Please select a proposal';
        statusElement.style.color = 'var(--warning)';
        return;
    }

    try {
        statusElement.textContent = 'Running validation...';
        statusElement.style.color = 'var(--primary)';

        const result = await api.triggerValidation(proposalId);

        statusElement.textContent = `✓ Validation completed`;
        statusElement.style.color = 'var(--success)';

        addActivityLogEntry('Validate Proposal', `Validated proposal ${proposalId}`, 'success');

        setTimeout(() => {
            statusElement.textContent = '';
        }, 3000);

        showToast('Validation triggered successfully', 'success');
    } catch (error) {
        statusElement.textContent = '✗ Validation failed';
        statusElement.style.color = 'var(--error)';
        handleApiError(error, 'running validation');

        addActivityLogEntry('Validate Proposal', 'Failed to validate proposal', 'error');
    }
}

/**
 * Add entry to activity log
 */
function addActivityLogEntry(action, details, status) {
    activityLog.unshift({
        action,
        details,
        status,
        timestamp: new Date()
    });

    // Keep only last 20 entries
    if (activityLog.length > 20) {
        activityLog = activityLog.slice(0, 20);
    }

    renderActivityLog();
}

/**
 * Load and render activity log
 */
async function loadActivityLog() {
    renderActivityLog();
}

/**
 * Render activity log table
 */
function renderActivityLog() {
    const container = document.getElementById('activity-log');
    if (!container) return;

    if (activityLog.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No recent activity</p>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'table';

    // Table header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Action</th>
            <th>Details</th>
            <th>Status</th>
            <th>Timestamp</th>
        </tr>
    `;
    table.appendChild(thead);

    // Table body
    const tbody = document.createElement('tbody');
    activityLog.forEach(entry => {
        const statusBadge = entry.status === 'success'
            ? '<span class="status-badge healthy">Success</span>'
            : '<span class="status-badge critical">Failed</span>';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${entry.action}</strong></td>
            <td>${entry.details}</td>
            <td>${statusBadge}</td>
            <td>${formatDateTime(entry.timestamp)}</td>
        `;
        tbody.appendChild(row);
    });
    table.appendChild(tbody);

    container.innerHTML = '';
    container.appendChild(table);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initControls);
