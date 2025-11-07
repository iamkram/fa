// FA AI Assistant - Test Interface JavaScript

// Configuration
const API_BASE_URL = 'http://localhost:8000';

// State
let sessionId = generateSessionId();
let currentFaId = 'FA-001';
let isProcessing = false;

// Elements
const messagesContainer = document.getElementById('messages');
const queryInput = document.getElementById('queryInput');
const sendButton = document.getElementById('sendButton');
const faSelector = document.getElementById('faSelector');
const sessionIdDisplay = document.getElementById('sessionId');
const currentFaIdDisplay = document.getElementById('currentFaId');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

// Initialize
function init() {
    sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';
    currentFaIdDisplay.textContent = currentFaId;

    // Event listeners
    sendButton.addEventListener('click', handleSend);
    queryInput.addEventListener('keypress', handleKeyPress);
    faSelector.addEventListener('change', handleFaChange);

    // Example query listeners
    document.querySelectorAll('.example-query').forEach(el => {
        el.addEventListener('click', () => {
            queryInput.value = el.dataset.query;
            queryInput.focus();
        });
    });

    // Auto-resize textarea
    queryInput.addEventListener('input', () => {
        queryInput.style.height = 'auto';
        queryInput.style.height = queryInput.scrollHeight + 'px';
    });

    // Check server health
    checkServerHealth();
}

// Generate session ID
function generateSessionId() {
    return 'session-' + Math.random().toString(36).substring(2, 15);
}

// Check server health
async function checkServerHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            setStatus('connected', 'Connected');
        } else {
            setStatus('disconnected', 'Server Error');
        }
    } catch (error) {
        setStatus('disconnected', 'Disconnected');
        console.error('Health check failed:', error);
    }
}

// Set connection status
function setStatus(status, text) {
    statusDot.className = 'status-dot' + (status === 'disconnected' ? ' disconnected' : '');
    statusText.textContent = text;
}

// Handle FA change
function handleFaChange(e) {
    currentFaId = e.target.value;
    currentFaIdDisplay.textContent = currentFaId;

    // Create new session for new FA
    sessionId = generateSessionId();
    sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';

    addSystemMessage(`Switched to ${e.target.selectedOptions[0].text}`);
}

// Handle key press
function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
}

// Handle send
async function handleSend() {
    const query = queryInput.value.trim();

    if (!query || isProcessing) {
        return;
    }

    // Add user message
    addUserMessage(query);

    // Clear input
    queryInput.value = '';
    queryInput.style.height = 'auto';

    // Disable input
    isProcessing = true;
    sendButton.disabled = true;
    queryInput.disabled = true;

    // Show loading
    const loadingId = addLoadingMessage();

    try {
        // Send query to API
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                fa_id: currentFaId,
                session_id: sessionId,
                query_text: query,
                query_type: 'chat',
                context: {}
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const result = await response.json();

        // Remove loading message
        removeLoadingMessage(loadingId);

        // Add assistant response
        addAssistantMessage(result);

    } catch (error) {
        console.error('Query failed:', error);
        removeLoadingMessage(loadingId);
        addErrorMessage('Failed to get response. Please check that the server is running.');
        setStatus('disconnected', 'Error');
    } finally {
        isProcessing = false;
        sendButton.disabled = false;
        queryInput.disabled = false;
        queryInput.focus();
    }
}

// Add user message
function addUserMessage(text) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message user';
    messageEl.innerHTML = `
        <div class="message-avatar">👤</div>
        <div>
            <div class="message-content">${escapeHtml(text)}</div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

// Add assistant message
function addAssistantMessage(result) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';

    // Build metadata badges
    let metaBadges = '';

    if (result.processing_time_ms) {
        metaBadges += `<span class="meta-badge">${result.processing_time_ms}ms</span>`;
    }

    if (result.response_tier) {
        metaBadges += `<span class="meta-badge">${result.response_tier} tier</span>`;
    }

    if (result.guardrail_status) {
        const badgeClass = result.guardrail_status === 'passed' ? 'success' : 'warning';
        metaBadges += `<span class="meta-badge ${badgeClass}">${result.guardrail_status}</span>`;
    }

    if (result.pii_flags && result.pii_flags.length > 0) {
        metaBadges += `<span class="meta-badge warning">PII Detected</span>`;
    }

    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div>
            <div class="message-content">${formatResponse(result.response_text)}</div>
            ${metaBadges ? `<div class="message-meta">${metaBadges}</div>` : ''}
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

// Add system message
function addSystemMessage(text) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';
    messageEl.innerHTML = `
        <div class="message-avatar">ℹ️</div>
        <div>
            <div class="message-content" style="background: #eff6ff; color: #1e40af; border-color: #dbeafe;">
                ${escapeHtml(text)}
            </div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

// Add error message
function addErrorMessage(text) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';
    messageEl.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div>
            <div class="message-content" style="background: #fef2f2; color: #991b1b; border-color: #fecaca;">
                ${escapeHtml(text)}
            </div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

// Add loading message
function addLoadingMessage() {
    const loadingId = 'loading-' + Date.now();
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';
    messageEl.id = loadingId;
    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div>
            <div class="message-content">
                <div class="loading">
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                </div>
            </div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    return loadingId;
}

// Remove loading message
function removeLoadingMessage(loadingId) {
    const el = document.getElementById(loadingId);
    if (el) {
        el.remove();
    }
}

// Format response (basic markdown-like formatting)
function formatResponse(text) {
    if (!text) return '';

    // Escape HTML
    text = escapeHtml(text);

    // Convert line breaks
    text = text.replace(/\n/g, '<br>');

    // Bold
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');

    return text;
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Scroll to bottom
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
