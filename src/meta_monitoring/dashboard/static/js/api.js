/**
 * API Client for Meta-Monitoring Dashboard
 * Handles all API requests to the FastAPI backend
 */

const API_BASE_URL = '/api/meta-monitoring';

class ApiClient {
    /**
     * Make a GET request to the API
     */
    async get(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API GET error for ${endpoint}:`, error);
            throw error;
        }
    }

    /**
     * Make a POST request to the API
     */
    async post(endpoint, data = {}, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API POST error for ${endpoint}:`, error);
            throw error;
        }
    }

    /**
     * Make a PATCH request to the API
     */
    async patch(endpoint, data = {}, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API PATCH error for ${endpoint}:`, error);
            throw error;
        }
    }

    // Health & Status Endpoints

    /**
     * Get system health overview
     */
    async getHealth() {
        return this.get('/health');
    }

    /**
     * Get latest evaluation metrics
     */
    async getLatestMetrics() {
        return this.get('/metrics/latest');
    }

    // Alert Endpoints

    /**
     * Get all alerts with optional filtering
     */
    async getAlerts(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.get(`/alerts${queryString ? '?' + queryString : ''}`);
    }

    /**
     * Get alert statistics
     */
    async getAlertStats() {
        return this.get('/alerts/stats');
    }

    /**
     * Acknowledge an alert
     */
    async acknowledgeAlert(alertId) {
        return this.post(`/alerts/${alertId}/acknowledge`);
    }

    /**
     * Resolve an alert
     */
    async resolveAlert(alertId) {
        return this.post(`/alerts/${alertId}/resolve`);
    }

    // Proposal Endpoints

    /**
     * Get all proposals with optional filtering
     */
    async getProposals(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.get(`/proposals${queryString ? '?' + queryString : ''}`);
    }

    /**
     * Get proposal statistics
     */
    async getProposalStats() {
        return this.get('/proposals/stats');
    }

    /**
     * Get a specific proposal by ID
     */
    async getProposal(proposalId) {
        return this.get(`/proposals/${proposalId}`);
    }

    /**
     * Approve a proposal
     */
    async approveProposal(proposalId) {
        return this.post(`/proposals/${proposalId}/approve`);
    }

    /**
     * Reject a proposal
     */
    async rejectProposal(proposalId, reason = '') {
        return this.post(`/proposals/${proposalId}/reject`, { reason });
    }

    // Metrics & Trends Endpoints

    /**
     * Get metric trends over time
     */
    async getMetricTrends(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.get(`/metrics/trend${queryString ? '?' + queryString : ''}`);
    }

    // Manual Control Endpoints

    /**
     * Trigger manual evaluation
     */
    async triggerEvaluation() {
        return this.post('/evaluation/run');
    }

    /**
     * Trigger proposal generation for an alert
     */
    async triggerProposal(alertId) {
        return this.post(`/research/analyze-alert/${alertId}`);
    }

    /**
     * Trigger validation for a proposal
     */
    async triggerValidation(proposalId) {
        return this.post(`/validation/validate-proposal/${proposalId}`);
    }
}

// Export singleton instance
const api = new ApiClient();
