/**
 * Utility functions for the Meta-Monitoring Dashboard
 */

/**
 * Format a timestamp to a readable date/time string
 */
function formatDateTime(timestamp) {
    if (!timestamp) return '--';

    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // If less than 1 minute ago, show "Just now"
    if (diff < 60000) {
        return 'Just now';
    }

    // If less than 1 hour ago, show "X minutes ago"
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    }

    // If less than 24 hours ago, show "X hours ago"
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    }

    // Otherwise, show formatted date/time
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format a timestamp to just the time component
 */
function formatTime(timestamp) {
    if (!timestamp) return '--:--';

    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * Format a number as a percentage
 */
function formatPercent(value, decimals = 1) {
    if (value === null || value === undefined) return '--%';
    return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a duration in milliseconds to a readable string
 */
function formatDuration(ms) {
    if (!ms) return '-- ms';

    if (ms < 1000) {
        return `${Math.round(ms)} ms`;
    }

    if (ms < 60000) {
        return `${(ms / 1000).toFixed(1)} sec`;
    }

    const minutes = Math.floor(ms / 60000);
    const seconds = Math.round((ms % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
}

/**
 * Get CSS class for status badge
 */
function getStatusClass(status) {
    const statusMap = {
        'healthy': 'healthy',
        'degraded': 'degraded',
        'critical': 'critical',
        'warning': 'degraded'
    };
    return statusMap[status?.toLowerCase()] || 'degraded';
}

/**
 * Get CSS class for severity badge
 */
function getSeverityClass(severity) {
    const severityMap = {
        'critical': 'critical',
        'high': 'high',
        'medium': 'medium',
        'low': 'low'
    };
    return severityMap[severity?.toLowerCase()] || 'medium';
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Update the "last updated" timestamp in the header
 */
function updateLastUpdatedTime() {
    const element = document.getElementById('last-updated-time');
    if (element) {
        element.textContent = formatTime(new Date());
    }
}

/**
 * Create an HTML element with classes and content
 */
function createElement(tag, classes = [], content = '') {
    const element = document.createElement(tag);
    if (classes.length > 0) {
        element.className = classes.join(' ');
    }
    if (content) {
        element.textContent = content;
    }
    return element;
}

/**
 * Safely set element text content
 */
function setTextContent(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
}

/**
 * Safely set element HTML content
 */
function setHTMLContent(elementId, html) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = html;
    }
}

/**
 * Handle API errors gracefully
 */
function handleApiError(error, context = 'loading data') {
    console.error(`Error ${context}:`, error);
    showToast(`Failed ${context}. Please try again.`, 'error', 5000);
}

/**
 * Debounce function calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Get color for metric value based on thresholds
 */
function getMetricColor(value, thresholds) {
    if (!thresholds) return 'inherit';

    if (value >= thresholds.good) return 'var(--success)';
    if (value >= thresholds.warning) return 'var(--warning)';
    return 'var(--error)';
}

/**
 * Truncate text with ellipsis
 */
function truncate(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
}
