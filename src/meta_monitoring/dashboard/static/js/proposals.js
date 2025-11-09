/**
 * Proposals Dashboard Page Logic
 */

let currentProposalId = null;

/**
 * Initialize the proposals page
 */
async function initProposals() {
    console.log('Initializing proposals page...');

    // Load initial data
    await loadProposalStats();
    await loadProposals();

    // Set up filter listeners
    document.getElementById('status-filter').addEventListener('change', loadProposals);
    document.getElementById('type-filter').addEventListener('change', loadProposals);

    updateLastUpdatedTime();
}

/**
 * Load proposal statistics
 */
async function loadProposalStats() {
    try {
        const stats = await api.getProposalStats();

        setTextContent('pending-count', stats.pending_count || 0);
        setTextContent('approved-count', stats.approved_count || 0);
        setTextContent('rejected-count', stats.rejected_count || 0);
        setTextContent('implemented-count', stats.implemented_count || 0);
    } catch (error) {
        handleApiError(error, 'loading proposal statistics');
    }
}

/**
 * Load proposals with current filters
 */
async function loadProposals() {
    try {
        const statusFilter = document.getElementById('status-filter').value;
        const typeFilter = document.getElementById('type-filter').value;

        const params = {};
        if (statusFilter) params.status = statusFilter;
        if (typeFilter) params.proposal_type = typeFilter;

        const proposals = await api.getProposals(params);

        const container = document.getElementById('proposals-container');
        if (!container) return;

        if (!proposals || proposals.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No proposals found</p>';
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
                <th>Status</th>
                <th>Actions</th>
            </tr>
        `;
        table.appendChild(thead);

        // Table body
        const tbody = document.createElement('tbody');
        proposals.forEach(proposal => {
            const row = document.createElement('tr');

            // Status badge styling
            let statusClass = 'status-badge';
            if (proposal.status === 'approved') statusClass += ' healthy';
            else if (proposal.status === 'rejected') statusClass += ' critical';
            else statusClass += ' degraded';

            row.innerHTML = `
                <td>
                    <strong>${proposal.proposal_title || 'Unknown Proposal'}</strong><br>
                    <small style="color: var(--text-secondary);">${truncate(proposal.description || '', 80)}</small>
                </td>
                <td>${proposal.proposal_type || 'unknown'}</td>
                <td>${proposal.estimated_impact || 'N/A'}</td>
                <td>${formatDateTime(proposal.created_at)}</td>
                <td><span class="${statusClass}">${proposal.status || 'pending'}</span></td>
                <td>
                    <button class="btn-link" onclick="viewProposalDetails('${proposal.proposal_id}')">Review →</button>
                </td>
            `;
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        container.innerHTML = '';
        container.appendChild(table);

        updateLastUpdatedTime();
    } catch (error) {
        handleApiError(error, 'loading proposals');
    }
}

/**
 * View proposal details in modal
 */
async function viewProposalDetails(proposalId) {
    try {
        const proposal = await api.getProposal(proposalId);

        if (!proposal) {
            showToast('Proposal not found', 'error');
            return;
        }

        currentProposalId = proposalId;

        // Populate modal
        document.getElementById('modal-title').textContent = proposal.proposal_title || 'Proposal Details';

        const modalContent = document.getElementById('modal-content');
        modalContent.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <strong>Proposal ID:</strong> ${proposal.proposal_id}<br>
                <strong>Type:</strong> ${proposal.proposal_type || 'unknown'}<br>
                <strong>Status:</strong> ${proposal.status || 'pending'}<br>
                <strong>Created:</strong> ${formatDateTime(proposal.created_at)}<br>
                ${proposal.approved_at ? `<strong>Approved:</strong> ${formatDateTime(proposal.approved_at)}<br>` : ''}
                ${proposal.rejected_at ? `<strong>Rejected:</strong> ${formatDateTime(proposal.rejected_at)}<br>` : ''}
                ${proposal.implemented_at ? `<strong>Implemented:</strong> ${formatDateTime(proposal.implemented_at)}<br>` : ''}
            </div>
            <div style="margin-bottom: 1rem;">
                <strong>Description:</strong><br>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">${proposal.description || 'No description available'}</p>
            </div>
            <div style="margin-bottom: 1rem;">
                <strong>Estimated Impact:</strong> ${proposal.estimated_impact || 'Not specified'}<br>
                <strong>Confidence Score:</strong> ${proposal.confidence_score ? formatPercent(proposal.confidence_score, 0) : 'N/A'}
            </div>
            ${proposal.proposed_changes ? `
                <div style="margin-bottom: 1rem;">
                    <strong>Proposed Changes:</strong><br>
                    <pre style="background: var(--bg-primary); padding: 0.5rem; border-radius: 0.25rem; overflow-x: auto; margin-top: 0.5rem;">${JSON.stringify(proposal.proposed_changes, null, 2)}</pre>
                </div>
            ` : ''}
            ${proposal.research_summary ? `
                <div style="margin-bottom: 1rem;">
                    <strong>Research Summary:</strong><br>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem; white-space: pre-wrap;">${proposal.research_summary}</p>
                </div>
            ` : ''}
            ${proposal.rejection_reason ? `
                <div style="margin-bottom: 1rem;">
                    <strong>Rejection Reason:</strong><br>
                    <p style="color: var(--error); margin-top: 0.5rem;">${proposal.rejection_reason}</p>
                </div>
            ` : ''}
        `;

        // Show appropriate action buttons
        const actionsContainer = document.getElementById('modal-actions');
        actionsContainer.innerHTML = '';

        if (proposal.status === 'pending_approval') {
            actionsContainer.innerHTML = `
                <button class="btn btn-primary" style="background-color: var(--success);" onclick="approveProposal()">Approve</button>
                <button class="btn btn-primary" style="background-color: var(--error);" onclick="rejectProposal()">Reject</button>
                <button class="btn" onclick="closeProposalModal()">Close</button>
            `;
        } else {
            actionsContainer.innerHTML = `
                <button class="btn" onclick="closeProposalModal()">Close</button>
            `;
        }

        // Show modal
        const modal = document.getElementById('proposal-modal');
        modal.style.display = 'flex';
    } catch (error) {
        handleApiError(error, 'loading proposal details');
    }
}

/**
 * Close proposal modal
 */
function closeProposalModal() {
    const modal = document.getElementById('proposal-modal');
    modal.style.display = 'none';
    currentProposalId = null;
}

/**
 * Approve current proposal
 */
async function approveProposal() {
    if (!currentProposalId) return;

    try {
        await api.approveProposal(currentProposalId);
        showToast('Proposal approved successfully', 'success');
        closeProposalModal();
        await loadProposals();
        await loadProposalStats();
    } catch (error) {
        handleApiError(error, 'approving proposal');
    }
}

/**
 * Reject current proposal
 */
async function rejectProposal() {
    if (!currentProposalId) return;

    const reason = prompt('Please provide a reason for rejection (optional):');

    try {
        await api.rejectProposal(currentProposalId, reason || '');
        showToast('Proposal rejected', 'success');
        closeProposalModal();
        await loadProposals();
        await loadProposalStats();
    } catch (error) {
        handleApiError(error, 'rejecting proposal');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initProposals);
