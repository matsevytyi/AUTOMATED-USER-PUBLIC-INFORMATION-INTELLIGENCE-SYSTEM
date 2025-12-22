// Application State
const AppState = {
    currentUser: null,
    jwt: null,
    currentPage: 'home',
    searchHistory: [],
    currentReport: null
};

// Chat state
AppState.chat = {
    activeSessionId: null,
    reportId: null,
    selectedPieces: []
};

function openChatPanel(reportId, preselectPieceId) {
    AppState.chat.reportId = reportId;
    AppState.chat.activeSessionId = null;
    AppState.chat.selectedPieces = [];
    if (preselectPieceId) AppState.chat.selectedPieces.push(preselectPieceId);
    document.getElementById('chat-panel').classList.remove('hidden');
    document.getElementById('chat-report-title').textContent = `Report Chat - ${reportId}`;
    updateSelectedPiecesUI();
    // clear messages
    const msgs = document.getElementById('chat-messages'); if (msgs) msgs.innerHTML = '';
}

// ensure opening chat also creates/returns the single session for this report
async function openChatPanelAndLoad(reportId, preselectPieceId) {
    openChatPanel(reportId, preselectPieceId);
    document.body.classList.add('chat-open');
    const session = await createChatSessionForReport(reportId);
    if (session && session.id) {
        AppState.chat.activeSessionId = session.id;
        document.getElementById('chat-session-meta').textContent = `Session: ${session.id}`;
        await loadSessionMessages(session.id);
    }
}

function closeChatPanel() {
    document.getElementById('chat-panel').classList.add('hidden');
    document.body.classList.remove('chat-open');
}

function updateSelectedPiecesUI() {
    const el = document.getElementById('chat-selected-pieces');
    if (!el) return;
    if (!AppState.chat.selectedPieces || AppState.chat.selectedPieces.length === 0) {
        el.style.display = 'none';
        el.innerHTML = '';
        return;
    }
    el.style.display = 'block';
    // show human-friendly names from DOM if available
    const labels = AppState.chat.selectedPieces.map(id => {
        const node = document.querySelector(`[data-piece-id="${id}"]`);
        const name = node ? node.getAttribute('data-piece-name') || id : id;
        return `<span class="chip">${name}</span>`;
    });
    el.innerHTML = '<strong>Selected datapieces:</strong> ' + labels.join(' ');
}

async function createChatSessionForReport(reportId, title = null, save_history = true) {
    try {
        const res = await fetch('/api/chat/report/' + encodeURIComponent(reportId) + '/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + AppState.jwt },
            body: JSON.stringify({ title, save_history })
        });
        const data = await res.json();
        if (data.success && data.session) {
            AppState.chat.activeSessionId = data.session.id;
            document.getElementById('chat-session-meta').textContent = `Session: ${data.session.id}`;
            return data.session;
        } else {
            showNotification(data.message || 'Failed to create session', 'error');
            return null;
        }
    } catch (e) {
        console.error('create session failed', e);
        showNotification('Create session failed', 'error');
        return null;
    }
}

async function loadSessionMessages(sessionId) {
    try {
        const res = await fetch('/api/chat/sessions/' + sessionId + '/messages', {
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        const data = await res.json();
        if (data.success) {
            const msgs = data.messages || [];
            const container = document.getElementById('chat-messages');
            container.innerHTML = '';
            msgs.forEach(m => appendMessageToChatDOM(m.sender, m.content));
            container.scrollTop = container.scrollHeight;
        }
    } catch (e) {
        console.error('load messages failed', e);
    }
}

function appendMessageToChatDOM(sender, content) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const el = document.createElement('div');
    el.className = 'chat-bubble ' + (sender === 'user' ? 'chat-user' : 'chat-assistant');
    // If assistant returned HTML-like content, sanitize and render it; otherwise render plain text
    try {
        if (sender === 'assistant' && typeof content === 'string' && /<[a-z][\s\S]*>/i.test(content)) {
            el.innerHTML = sanitizeAllowedHtml(content);
        } else {
            el.textContent = content;
        }
    } catch (e) {
        el.textContent = content;
    }
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
}

// Lightweight HTML sanitizer: allow a small set of tags and safe attributes (href on <a> with http(s)).
function sanitizeAllowedHtml(html) {
    if (!html) return '';
    const parser = new DOMParser();
    const doc = parser.parseFromString('<div>' + html + '</div>', 'text/html');
    const container = doc.body.firstChild;

    const allowedTags = new Set(['STRONG','B','EM','I','A','CODE','UL','OL','LI','P','BR']);

    const walk = (node) => {
        const children = Array.from(node.childNodes);
        for (const child of children) {
            if (child.nodeType === Node.ELEMENT_NODE) {
                if (!allowedTags.has(child.tagName)) {
                    // replace element with its text content
                    const txt = document.createTextNode(child.textContent);
                    node.replaceChild(txt, child);
                    continue;
                }

                // sanitize attributes: only allow href on <a>
                const attrs = Array.from(child.attributes).map(a => a.name);
                for (const a of attrs) {
                    if (child.tagName === 'A' && a === 'href') {
                        const href = child.getAttribute('href') || '';
                        try {
                            const u = new URL(href, window.location.href);
                            if (u.protocol !== 'http:' && u.protocol !== 'https:') {
                                child.removeAttribute('href');
                            } else {
                                child.setAttribute('target', '_blank');
                                child.setAttribute('rel', 'noopener noreferrer');
                            }
                        } catch (e) {
                            child.removeAttribute('href');
                        }
                    } else {
                        child.removeAttribute(a);
                    }
                }

                walk(child);
            } else if (child.nodeType === Node.TEXT_NODE) {
                // ok
            } else {
                node.removeChild(child);
            }
        }
    };

    walk(container);
    return container.innerHTML;
}

// Truncate text to a maximum length, adding an ellipsis if truncated
function truncateText(text, maxLen = 100) {
    try {
        if (!text) return '';
        const s = String(text);
        if (s.length <= maxLen) return s;
        return s.slice(0, maxLen) + '…';
    } catch (e) {
        return text;
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const text = DOMPurify.sanitize(input.value.trim());
    if (!text) return;
    // ensure session
    if (!AppState.chat.activeSessionId) {
        const session = await createChatSessionForReport(AppState.chat.reportId);
        if (!session) return;
    }

    // gather scope and piece ids
    const scope = document.getElementById('chat-scope')?.value || 'report';
    const body = { message: text, scope: scope, datapiece_ids: AppState.chat.selectedPieces.map(id => Number(id)) };

    appendMessageToChatDOM('user', text);
    input.value = '';

    try {
        const res = await fetch('/api/chat/sessions/' + AppState.chat.activeSessionId + '/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + AppState.jwt },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.success) {
            appendMessageToChatDOM('assistant', data.assistant || '(no reply)');
        } else {
            appendMessageToChatDOM('assistant', data.message || 'Failed to get reply');
        }
    } catch (e) {
        console.error('send chat failed', e);
        appendMessageToChatDOM('assistant', 'Request failed');
    }
}


// Utility Functions
function showNotification(message, type = 'info') {
    const toast = document.getElementById('notification-toast');
    const messageEl = document.getElementById('notification-message');
    
    messageEl.textContent = message;
    toast.className = `notification-toast ${type}`;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 5000);
}

function showLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
    }
}

function hideLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }
}

function setButtonLoading(button, loading) {
    if (!button) return;
    
    if (loading) {
        button.classList.add('loading');
        button.disabled = true;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

function showFormError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorEl = document.getElementById(fieldId + '-error');
    
    if (field) field.classList.add('error');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.add('show');
    }
}

function clearFormError(fieldId) {
    const field = document.getElementById(fieldId);
    const errorEl = document.getElementById(fieldId + '-error');
    
    if (field) field.classList.remove('error');
    if (errorEl) errorEl.classList.remove('show');
}

function clearAllFormErrors(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const errors = form.querySelectorAll('.form-error');
    const fields = form.querySelectorAll('.form-control');
    
    errors.forEach(error => error.classList.remove('show'));
    fields.forEach(field => field.classList.remove('error'));
}

// Page Navigation
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show target page
    const targetPage = document.getElementById(pageId + '-page');
    if (targetPage) {
        targetPage.classList.add('active');
        AppState.currentPage = pageId;
    }
    
    // Update navigation
    updateNavigation();
    
    // Page-specific initialization
    if (pageId === 'dashboard') {
        initializeDashboard();
    } else if (pageId === 'admin-dashboard') {
        initializeAdminDashboard();
    }
}

function updateNavigation() {
    const loginBtn = document.getElementById('nav-login-btn');
    const registerBtn = document.getElementById('nav-register-btn');
    const logoutBtn = document.getElementById('nav-logout-btn');
    const dashboardBtn = document.getElementById('nav-dashboard-btn');
    
    if (AppState.currentUser) {
        if (loginBtn) loginBtn.classList.add('hidden');
        if (registerBtn) registerBtn.classList.add('hidden');
        if (logoutBtn) logoutBtn.classList.remove('hidden');
        // Hide dashboard button for admins

        const navbar = document.getElementById('general-navbar');

        if (navbar) {
            if (AppState.currentUser.is_admin) {
                navbar.classList.add('hidden');
            } else {
                navbar.classList.remove('hidden');
            }
        }
    } else {
        if (loginBtn) loginBtn.classList.remove('hidden');
        if (registerBtn) registerBtn.classList.remove('hidden');
        if (logoutBtn) logoutBtn.classList.add('hidden');
        if (dashboardBtn) dashboardBtn.classList.add('hidden');
    }

    if (AppState.currentPage === 'dashboard') {
        if (dashboardBtn) dashboardBtn.classList.add('hidden');
    } else {
        if (dashboardBtn && AppState.currentUser) dashboardBtn.classList.remove('hidden');
    }
}

// POST functions

async function registerUser(formData) {
    const response = await fetch('/api/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });
    const data = await response.json();
    if (data.success) {
        AppState.currentUser = data.user;
        AppState.jwt = data.access_token;
    }
    return data;
}

async function loginUser(formData) {
    const response = await fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });
    const data = await response.json();
    if (data.success) {
        AppState.currentUser = data.user;
        AppState.jwt = data.access_token;
    }
    return data;
}

async function searchReport(query, generalSearch, facebookSearch) {
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + AppState.jwt
        },
        body: JSON.stringify({ query, general_search: generalSearch, facebook_search: facebookSearch })
    });
    return response.json();
}

async function getHistory() {
    const response = await fetch('/api/history', {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + AppState.jwt
        }
    });
    return await response.json();
}

async function getReport(reportId) {
    const response = await fetch(`/api/report/${reportId}`, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + AppState.jwt
        }
    });
    return await response.json();
}

async function changePassword(formData) {
    try {
        const response = await fetch('/api/profile/password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + (AppState.jwt || '')
            },
            body: JSON.stringify(formData)
        });
        const data = await response.json();
        return data;
    } catch (err) {
        console.error('changePassword: request failed', err);
        return { success: false, message: 'Request failed' };
    }
}


// Authentication Util Functions
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function validatePassword(password) {
    // At least 8 characters, one uppercase, one lowercase, one number, one special character
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&.])[A-Za-z\d@$!%*?&.]{8,}$/;
    return passwordRegex.test(password);
}

function validateRegistrationForm() {
    const nameField = document.getElementById('register-name');
    const emailField = document.getElementById('register-email');
    const passwordField = document.getElementById('register-password');
    const confirmPasswordField = document.getElementById('register-confirm-password');
    
    if (!nameField || !emailField || !passwordField || !confirmPasswordField) {
        return false;
    }
    
    const name = DOMPurify.sanitize(nameField.value.trim());
    const email = DOMPurify.sanitize(emailField.value.trim());
    const password = DOMPurify.sanitize(passwordField.value);
    const confirmPassword = DOMPurify.sanitize(confirmPasswordField.value);
    
    let isValid = true;
    
    clearAllFormErrors('register-form');
    
    if (!name) {
        showFormError('register-name', 'Full name is required');
        isValid = false;
    }
    
    if (!email) {
        showFormError('register-email', 'Email is required');
        isValid = false;
    } else if (!validateEmail(email)) {
        showFormError('register-email', 'Please enter a valid email address');
        isValid = false;
    }
    
    if (!password) {
        showFormError('register-password', 'Password is required');
        isValid = false;
    } else if (!validatePassword(password)) {
        showFormError('register-password', 'Password must meet complexity requirements');
        isValid = false;
    }
    
    if (!confirmPassword) {
        showFormError('register-confirm-password', 'Please confirm your password');
        isValid = false;
    } else if (password !== confirmPassword) {
        showFormError('register-confirm-password', 'Passwords do not match');
        isValid = false;
    }
    
    return isValid;
}

function validatePasswordChangeForm() {
    const current_password_field = document.getElementById('current-password');
    const new_password_field = document.getElementById('new-password');
    const confirm_new_password_field = document.getElementById('confirm-password');
    
    if (!current_password_field || !new_password_field || !confirm_new_password_field) {
        return false;
    }
    
    const current_password = DOMPurify.sanitize(current_password_field.value);
    const new_password = DOMPurify.sanitize(new_password_field.value);
    const confirm_new_password = DOMPurify.sanitize(confirm_new_password_field.value);
    
    let isValid = true;

    if (!current_password) {
        showFormError('current-password', 'Current password is required');
        isValid = false;
    }
    
    if (!new_password) {
        showFormError('new-password', 'New password is required');
        isValid = false;
    } else if (!validatePassword(new_password)) {
        showFormError('new-password', 'Password must meet complexity requirements');
        isValid = false;
    } else if (current_password === new_password) {
        showFormError('new-password', 'New password cannot be the same as the current password');
        isValid = false;
    }
    
    if (!confirm_new_password) {
        showFormError('confirm-password', 'Please confirm your password');
        isValid = false;
    } else if (new_password !== confirm_new_password) {
        showFormError('confirm-password', 'Passwords do not match');
        isValid = false;
    }
    
    return isValid;
}

// THEME HANDLING
function applyTheme(theme) {
    // theme: 'light' | 'dark' | 'device'
    try {
        if (!theme) theme = 'device';
        document.documentElement.setAttribute('data-color-scheme', theme);
        // persist locally: if logged in, store per-user; otherwise store global guest theme
        try {
            if (AppState && AppState.currentUser && AppState.currentUser.email) {
                localStorage.setItem('theme:' + AppState.currentUser.email, theme);
            } else {
                localStorage.setItem('theme', theme);
            }
        } catch (e) {}
        // update radio inputs state
        const radios = document.querySelectorAll('input[name="theme"]');
        radios.forEach(r => { r.checked = (r.value === theme); });
    } catch (e) {
        console.warn('Failed to apply theme', e);
    }
}

async function persistThemeToServer(theme) {
    // Try to save preference server-side if logged in; ignore errors
    try {
        if (!AppState || !AppState.jwt) return;
        await fetch('/api/profile/theme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + AppState.jwt
            },
            body: JSON.stringify({ theme })
        });
    } catch (e) {
        // ignore
    }
}

function initThemeControls() {
    // set from localStorage first, fallback to 'device'
    let saved = 'device';
    try {
        // if logged in and have per-user theme, prefer that
        if (AppState && AppState.currentUser && AppState.currentUser.email) {
            const userKey = 'theme:' + AppState.currentUser.email;
            const ut = localStorage.getItem(userKey);
            if (ut) {
                saved = ut;
            } else {
                const t = localStorage.getItem('theme'); if (t) saved = t;
            }
        } else {
            const t = localStorage.getItem('theme'); if (t) saved = t;
        }
    } catch (e) {}
    applyTheme(saved);

    // wire radio inputs
    const radios = document.querySelectorAll('input[name="theme"]');
    radios.forEach(r => {
        r.addEventListener('change', async function() {
            if (!this.checked) return;
            const t = this.value;
            applyTheme(t);
            // attempt to persist
            persistThemeToServer(t);
        });
    });
}

// Fetch full profile for logged-in user (includes theme)
async function fetchProfile() {
    try {
        const res = await fetch('/api/profile', {
            method: 'GET',
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        return await res.json();
    } catch (e) {
        return null;
    }
}

function validateLoginForm() {
    const emailField = document.getElementById('login-email');
    const passwordField = document.getElementById('login-password');
    
    if (!emailField || !passwordField) {
        return false;
    }
    
    const email = DOMPurify.sanitize(emailField.value.trim());
    const password = DOMPurify.sanitize(passwordField.value);
    
    let isValid = true;
    
    clearAllFormErrors('login-form');
    
    if (!email) {
        showFormError('login-email', 'Email is required');
        isValid = false;
    } else if (!validateEmail(email)) {
        showFormError('login-email', 'Please enter a valid email address');
        isValid = false;
    }
    
    if (!password) {
        showFormError('login-password', 'Password is required');
        isValid = false;
    }
    
    return isValid;
}

// Dashboard Functions
function initializeDashboard() {
    if (AppState.currentUser) {
        const userNameEl = document.getElementById('user-name');
        if (userNameEl) {
            userNameEl.textContent = AppState.currentUser.name;
        }
        loadSearchHistory();
    }
}

function initializeAdminDashboard() {
    if (AppState.currentUser) {
        const userNameEl = document.getElementById('admin-user-name');
        if (userNameEl) {
            userNameEl.textContent = AppState.currentUser.name;
        }
        loadAdminStats();
        loadPotentialMisusers();
        loadSuspendedUsers();
        loadDocuments();
        initializeDocumentUpload();
    }
}

function loadSearchHistory() {
    const historyContainer = document.getElementById('search-history');
    if (!historyContainer) return;
    
    if (AppState.searchHistory.length === 0) {
        historyContainer.innerHTML = '<p class="empty-state">No searches yet. Create your first report above.</p>';
        return;
    }
    
    historyContainer.innerHTML = AppState.searchHistory.map(item => `
        <div class="history-item" onclick="loadReport('${item.report_id}')">
            <div class="history-item-header">
                <div class="history-item-query">${item.query}</div>
                <div class="history-item-date">${new Date(item.generated_at).toLocaleDateString()}</div>
            </div>
            <div class="history-item-summary">Report ID: ${item.report_id}</div>
        </div>
    `).join('');
}

async function loadReport(reportId) {
    let report = AppState.searchHistory.find(r => r.report_id === reportId);
    if (report) {
        // Check if it's a full report (has detailed_findings)
        if (report.detailed_findings) {
            displayReport(report);
        } else {
            // Load full report
            const fullReport = await getReport(reportId);
            if (fullReport.success) {
                // Update in searchHistory
                const index = AppState.searchHistory.findIndex(r => r.report_id === reportId);
                if (index !== -1) {
                    AppState.searchHistory[index] = fullReport.report;
                }
                displayReport(fullReport.report);
            } else {
                showNotification('Failed to load report', 'error');
            }
        }
    }
}

function displayReport(report) {
    AppState.currentReport = report;
    
    // Update report header
    const reportTitle = document.getElementById('report-title');
    const reportId = document.getElementById('report-id');
    
    if (reportTitle) reportTitle.textContent = `Digital Footprint Report - ${report.query}`;
    if (reportId) reportId.textContent = report.report_id;
    
    // Update executive summary
    const executiveSummary = document.getElementById('executive-summary');
    if (executiveSummary) executiveSummary.textContent = report.executive_summary;
    
    // Update risk distribution
    const highRiskCount = document.getElementById('high-risk-count');
    const mediumRiskCount = document.getElementById('medium-risk-count');
    const lowRiskCount = document.getElementById('low-risk-count');

    const riskDist = report.risk_distribution || {};
    
    if (highRiskCount) highRiskCount.textContent = riskDist.high || 0;
    if (mediumRiskCount) mediumRiskCount.textContent = riskDist.medium || 0;
    if (lowRiskCount) lowRiskCount.textContent = riskDist.low || 0;
    
    // Update detailed findings
    const findingsList = document.getElementById('findings-list');
    if (findingsList) {
        // sort findings by risk: high -> medium -> low, then by recency
        const findings = Array.isArray(report.detailed_findings) ? report.detailed_findings.slice() : [];
        const riskOrder = { 'high': 3, 'medium': 2, 'low': 1 };
        findings.sort((a, b) => {
            const ra = (a.risk || '').toString().toLowerCase();
            const rb = (b.risk || '').toString().toLowerCase();
            const va = riskOrder[ra] || 0;
            const vb = riskOrder[rb] || 0;
            if (va !== vb) return vb - va; // higher risk first
            // fallback: newer first
            const ta = new Date(a.timestamp || 0).getTime();
            const tb = new Date(b.timestamp || 0).getTime();
            return tb - ta;
        });

        findingsList.innerHTML = findings.map(finding => {
            const linkHtml = (finding.url && finding.url !== 'N/A')
                ? `<a href="${finding.url}" target="_blank" class="finding-url" title="${finding.url}">${truncateText(finding.url, 100)}</a>`
                : '<span class="finding-url">Source not public</span>';

            return `
            <div class="finding-item risk-${finding.risk}" data-piece-id="${finding.id}" data-piece-name="${finding.info}">
                <div class="finding-header">
                    <div class="finding-source">${finding.source}</div>
                    <div class="finding-category">${finding.category}</div>
                </div>
                <div class="finding-info">${finding.info}</div>
                <div class="finding-meta">
                    <div class="finding-timestamp">Found: ${new Date(finding.timestamp).toLocaleDateString()}</div>
                    ${linkHtml}
                    <button class="btn-inline-ask btn btn--outline" data-piece-id="${finding.id}" style="margin-left:8px;">Ask</button>
                </div>
            </div>
        `;
        }).join('');
    }

    // Update recommendations
    const recommendationsList = document.getElementById('recommendations-list');
    if (recommendationsList) {
        const recs = report.recommendations || [];
        
        if (recs.length === 0) {
            recommendationsList.innerHTML = '<div class="empty-state">No recommendations available.</div>';
        } else {
            recommendationsList.innerHTML = recs.map(rec => `
                <div class="recommendation-item">${rec}</div>
            `).join('');
        }
    }
    
    // Update source distribution
    const sourceDistribution = document.getElementById('source-distribution');
    if (sourceDistribution) {
        sourceDistribution.innerHTML = Object.entries(report.source_distribution).map(([source, count]) => `
            <div class="source-item">
                <div class="source-name">${source}</div>
                <div class="source-count">${count}</div>
            </div>
        `).join('');
    }
    
    // Show report section
    const reportSection = document.getElementById('report-section');
    if (reportSection) {
        reportSection.classList.remove('hidden');
        
        // Scroll to report
        reportSection.scrollIntoView({ behavior: 'smooth' });
    }
}

function logout() {
    AppState.currentUser = null;
    AppState.jwt = null;
    AppState.searchHistory = [];
    AppState.currentReport = null;
    // Hide report section
    const reportSection = document.getElementById('report-section');
    if (reportSection) {
        reportSection.classList.add('hidden');
    }
    
    // Clear form fields
    const formsToClear = ['register-form', 'login-form', 'search-form', 'update-password-form'];
    formsToClear.forEach(formId => {
        const form = document.getElementById(formId);
        if (form) form.reset();
    });
    const fieldsToClear = ['fb-login', 'fb-password', 'cookies-json'];
    fieldsToClear.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) field.value = '';
    });
    
    showNotification('Logged out successfully', 'info');
    showPage('home');
    // restore guest/global theme (do not keep previous user's theme applied)
    try {
        const guestTheme = localStorage.getItem('theme') || 'device';
        applyTheme(guestTheme);
    } catch (e) {}
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Ensure loading overlay is hidden on page load
    hideLoading();
    
    // Navigation event listeners
    const navLoginBtn = document.getElementById('nav-login-btn');
    const navRegisterBtn = document.getElementById('nav-register-btn');
    const navLogoutBtn = document.getElementById('nav-logout-btn');
    const navDashboardBtn = document.getElementById('nav-dashboard-btn');
    const heroLoginBtn = document.getElementById('hero-login-btn');
    const heroRegisterBtn = document.getElementById('hero-register-btn');
    const authLoginLink = document.getElementById('auth-login-link');
    const authRegisterLink = document.getElementById('auth-register-link');
    
    if (navLoginBtn) navLoginBtn.addEventListener('click', () => showPage('login'));
    if (navRegisterBtn) navRegisterBtn.addEventListener('click', () => showPage('register'));
    if (navLogoutBtn) navLogoutBtn.addEventListener('click', logout);
    if (navDashboardBtn) navDashboardBtn.addEventListener('click', () => showPage('dashboard'));
    if (heroLoginBtn) heroLoginBtn.addEventListener('click', () => showPage('login'));
    if (heroRegisterBtn) heroRegisterBtn.addEventListener('click', () => showPage('register'));
    
    if (authLoginLink) {
        authLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            showPage('login');
        });
    }
    
    if (authRegisterLink) {
        authRegisterLink.addEventListener('click', (e) => {
            e.preventDefault();
            showPage('register');
        });
    }
    
    // Registration form
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!validateRegistrationForm()) {
                return;
            }
            
            const submitBtn = document.getElementById('register-submit-btn');
            setButtonLoading(submitBtn, true);
            
            const formData = {
                name: DOMPurify.sanitize(document.getElementById('register-name').value.trim()),
                email: DOMPurify.sanitize(document.getElementById('register-email').value.trim()),
                password: DOMPurify.sanitize(document.getElementById('register-password').value)
            };
            
            const response = await registerUser(formData);
            if (response.success) {
                setButtonLoading(submitBtn, false);
                showNotification(response.message, 'success');
                try {
                    const profileRes = await fetchProfile();
                    if (profileRes && profileRes.success && profileRes.profile) {
                        AppState.currentUser = Object.assign(AppState.currentUser || {}, profileRes.profile);
                        // choose theme: server preference > per-user localStorage > guest localStorage > device
                        const serverTheme = profileRes.profile.theme;
                        const localUserTheme = localStorage.getItem('theme:' + profileRes.profile.email);
                        // Preference order: server-saved > per-user local > device default
                        const chosen = serverTheme || localUserTheme || 'device';
                        applyTheme(chosen);
                    }
                } catch (e) {
                }
                showPage('dashboard');
                await reloadSearchHistory();
                // update FB cookies status for logged-in user
                getFacebookCookiesStatus();
                // Clear register fields
                document.getElementById('register-email').value = '';
                document.getElementById('register-password').value = '';
                document.getElementById('register-name').value = '';
            } else {
                showNotification(response.message, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }
    
    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!validateLoginForm()) {
                return;
            }
            
            const submitBtn = document.getElementById('login-submit-btn');
            setButtonLoading(submitBtn, true);
            
            const formData = {
                email: DOMPurify.sanitize(document.getElementById('login-email').value.trim()),
                password: DOMPurify.sanitize(document.getElementById('login-password').value)
            };
            
            const response = await loginUser(formData);
            if (response.success) {
                setButtonLoading(submitBtn, false);
                showNotification(response.message, 'success');
                try {
                    const profileRes = await fetchProfile();
                    if (profileRes && profileRes.success && profileRes.profile) {
                        AppState.currentUser = Object.assign(AppState.currentUser || {}, profileRes.profile);
                        // choose theme: server preference > per-user localStorage > guest localStorage > device
                        const serverTheme = profileRes.profile.theme;
                        const localUserTheme = localStorage.getItem('theme:' + profileRes.profile.email);
                        // Preference order: server-saved > per-user local > device default
                        const chosen = serverTheme || localUserTheme || 'device';
                        applyTheme(chosen);
                    }
                } catch (e) {
                }

                // Check if admin and redirect accordingly
                if (AppState.currentUser && AppState.currentUser.is_admin) {
                    showPage('admin-dashboard');
                } else {
                    showPage('dashboard');
                }
                await reloadSearchHistory();
                // update FB cookies status for logged-in user
                getFacebookCookiesStatus();
                // Clear login fields
                document.getElementById('login-email').value = '';
                document.getElementById('login-password').value = '';
            } else {
                showNotification(response.message, 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }

    const passwordUpdateForm = document.getElementById('update-password-form');
    if (passwordUpdateForm) {
        passwordUpdateForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!validatePasswordChangeForm()) {
                return;
            }
            
            const submitBtn = document.getElementById('update-password-btn');
            setButtonLoading(submitBtn, true);
            
            const formData = {
                current_password: DOMPurify.sanitize(document.getElementById('current-password').value.trim()),
                new_password: DOMPurify.sanitize(document.getElementById('new-password').value.trim())
            };
            
            const response = await changePassword(formData);
            if (response.success) {
                setButtonLoading(submitBtn, false);
                showNotification(response.message || 'Password changed successfully', 'success');
                showPage('dashboard');
                // Clear password fields
                document.getElementById('current-password').value = '';
                document.getElementById('new-password').value = '';
                document.getElementById('confirm-password').value = '';
            } else {
                showNotification(response.message ? ('Try Again! ' + response.message) : 'Failed to change password', 'error');
                setButtonLoading(submitBtn, false);
            }
        });
    }
    
    // Search form
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const queryField = document.getElementById('search-query')
            if (!queryField) return;
            
            const query = DOMPurify.sanitize(queryField.value.trim());
            if (!query) {
                showNotification('Please enter a search query', 'error');
                return;
            }
            
            const generalSearch = document.getElementById('general-search').checked;
            const facebookSearch = document.getElementById('facebook-search').checked;
            
            if (!generalSearch && !facebookSearch) {
                showNotification('Please select at least one search option', 'error');
                return;
            }
            
            const submitBtn = document.getElementById('search-submit-btn');
            setButtonLoading(submitBtn, true);
            showLoading();

            try {

                const response = await searchReport(query, generalSearch, facebookSearch);

                if (response.success) {
                    AppState.searchHistory.unshift(response.report);
                    displayReport(response.report);
                    loadSearchHistory();
                    showNotification('Report generated successfully', 'success');
                    // Clear the search query field
                    queryField.value = '';

                } else {
                    showNotification(response.message, 'error');
                }

            } catch (error) {
                showNotification(error.message, 'error');
            } finally {
                hideLoading();
                setButtonLoading(submitBtn, false);

            }
            
            
        });
    }
    
    // Profile button
    const profileBtn = document.getElementById('profile-btn');
    if (profileBtn) {
        // profileBtn.addEventListener('click', function() {
        //     showNotification('Profile management coming soon', 'info');
        // });

        profileBtn.addEventListener("click", function() {
            // Switch to the Settings main view
            showPage('profile');
        });
    }

    // Profile
    document.querySelectorAll('.profile-tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const sectionID = 'profile-' + btn.dataset.section;
            const section = document.getElementById(sectionID);
            if(section) section.scrollIntoView({behavior: 'smooth', block: 'start'});
        });
    });

    // cookies
    document.getElementById('paste-cookies-btn').addEventListener('click', function() {
        const textarea = document.getElementById('cookies-json');
        const status = document.getElementById('facebook-cookies-status');
        try {
            const cookiesObj = JSON.parse(DOMPurify.sanitize(textarea.value));
            postFacebookCookies(cookiesObj);
        } catch (err) {
            status.textContent = "Invalid JSON format";
            status.style.color = "var(--color-error)";
        }
    });

    document.getElementById('save-cookies-btn').addEventListener('click', function() {
        const status = document.getElementById('facebook-cookies-status');
        // Read all input fields
        const c_user = DOMPurify.sanitize(document.getElementById('cookie-c-user').value.trim());
        const xs    = DOMPurify.sanitize(document.getElementById('cookie-xs').value.trim());
        const datr  = DOMPurify.sanitize(document.getElementById('cookie-datr').value.trim());
        const fr    = DOMPurify.sanitize(document.getElementById('cookie-fr').value.trim());
        const sb  = DOMPurify.sanitize(document.getElementById('cookie-sb').value.trim());

        // Build cookies object (only add fields if non-empty)
        let cookiesObj = {};
        if (c_user) cookiesObj.c_user = c_user;
        if (xs)     cookiesObj.xs     = xs;
        if (datr)   cookiesObj.datr   = datr;
        if (fr)     cookiesObj.fr     = fr;
        if (sb)   cookiesObj.sb   = sb;

        postFacebookCookies(cookiesObj);
    });

    // Facebook credentials login (uses server endpoint that invokes Selenium)
    const fbLoginBtn = document.getElementById('facebook-login-btn');
    const fbTestBtn = document.getElementById('facebook-test-login-btn');
    if (fbLoginBtn) {
        fbLoginBtn.addEventListener('click', async function() {
            const status = document.getElementById('facebook-cookies-status');
            if (!AppState || !AppState.jwt) {
                showNotification('Please sign in to your account first', 'error');
                return;
            }

            const login = DOMPurify.sanitize(document.getElementById('fb-login')?.value.trim());
            const password = DOMPurify.sanitize(document.getElementById('fb-password')?.value || '');
            const headless = !!document.getElementById('fb-headless')?.checked;

            if (!login || !password) {
                if (status) { status.textContent = 'Please enter Facebook login and password'; status.style.color = 'var(--color-error)'; }
                return;
            }

            setButtonLoading(fbLoginBtn, true);
            try {
                const res = await fetch('/api/profile/facebook/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + AppState.jwt
                    },
                    body: JSON.stringify({ login, password, headless })
                });
                const data = await res.json();
                if (data.success) {
                    showNotification(data.message || 'Facebook login successful; cookies saved', 'success');
                    if (status) { status.textContent = 'Cookies saved and valid'; status.style.color = 'var(--color-success)'; }
                    // refresh status and redirect shortly so user sees notification
                    await getFacebookCookiesStatus();
                    setTimeout(() => showPage('dashboard'), 500);
                    // Clear Facebook login fields
                    document.getElementById('fb-login').textContent = '';
                    document.getElementById('fb-password').textContent = '';
                } else {
                    const msg = data.message || data.error || 'Login failed';
                    showNotification(msg, 'error');
                    if (status) { status.textContent = msg; status.style.color = 'var(--color-error)'; }
                }
            } catch (e) {
                console.error('FB login request failed', e);
                showNotification('Request failed', 'error');
                if (status) { status.textContent = 'Request failed'; status.style.color = 'var(--color-error)'; }
            } finally {
                setButtonLoading(fbLoginBtn, false);
                // Clear password field for safety
                try { document.getElementById('fb-password').textContent = ''; } catch (e) {}
            }
        });
    }

    if (fbTestBtn) {
        // Ensure button is enabled and attach a robust handler
        try { fbTestBtn.disabled = false; } catch (e) {}
        fbTestBtn.addEventListener('click', async function() {
            const statusEl = document.getElementById('facebook-cookies-status');
            if (!AppState || !AppState.jwt) {
                showNotification('Please sign in to your account first', 'error');
                if (statusEl) { statusEl.textContent = 'Not signed in'; statusEl.style.color = 'var(--color-error)'; }
                return;
            }

            const loginInput = document.getElementById('fb-login');
            const passInput = document.getElementById('fb-password');
            const headlessInput = document.getElementById('fb-headless');
            const login = loginInput ? loginInput.textContent.trim() : '';
            const password = passInput ? passInput.textContent : '';
            const headless = headlessInput ? !!headlessInput.checked : false;

            if (!login || !password) {
                showNotification('Enter login and password to test', 'error');
                if (statusEl) { statusEl.textContent = 'Enter login and password'; statusEl.style.color = 'var(--color-error)'; }
                return;
            }

            setButtonLoading(fbTestBtn, true);
            try {
                const res = await fetch('/api/profile/facebook/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + AppState.jwt
                    },
                    body: JSON.stringify({ login, password, headless })
                });

                let data = null;
                try { data = await res.json(); } catch (e) { data = null; }

                if (res.ok && data && data.success) {
                    showNotification(data.message || 'Test login succeeded and cookies saved', 'success');
                    if (statusEl) { statusEl.textContent = 'Cookies saved and valid'; statusEl.style.color = 'var(--color-success)'; }
                    await getFacebookCookiesStatus();
                } else {
                    const msg = (data && (data.message || data.error)) || `Test failed (status ${res.status})`;
                    showNotification(msg, 'error');
                    if (statusEl) { statusEl.textContent = msg; statusEl.style.color = 'var(--color-error)'; }
                }
            } catch (e) {
                console.error('FB test request failed', e);
                showNotification('Request failed', 'error');
                if (statusEl) { statusEl.textContent = 'Request failed'; statusEl.style.color = 'var(--color-error)'; }
            } finally {
                setButtonLoading(fbTestBtn, false);
                try { if (document.getElementById('fb-password')) document.getElementById('fb-password').value = ''; } catch (e) {}
            }
        });
    }

    // Facebook OAuth button: open popup to start OAuth flow. We include JWT in state query param.
    const fbOauthBtn = document.getElementById('facebook-oauth-btn');
    if (fbOauthBtn) {
        fbOauthBtn.disabled = false;
        fbOauthBtn.addEventListener('click', function() {
            const token = AppState && AppState.jwt ? AppState.jwt : '';
            const oauthUrl = '/api/auth/facebook/start' + (token ? ('?state=' + encodeURIComponent(token)) : '');
            const w = window.open(oauthUrl, 'fb_oauth', 'width=600,height=700');
            if (!w) {
                showNotification('Popup blocked — please allow popups for this site', 'error');
                return;
            }
        });
    }

    // Listen for messages from OAuth popup
    window.addEventListener('message', function(ev) {
        try {
            if (!ev.data || ev.data.type !== 'facebook-oauth') return;
            const payload = ev.data.payload || {};
            if (payload.success) {
                showNotification('Facebook linked successfully', 'success');
                // refresh cookies/status
                getFacebookCookiesStatus();
                // optionally redirect to dashboard
                setTimeout(() => showPage('dashboard'), 600);
            } else {
                showNotification(payload.message || 'Facebook auth failed', 'error');
            }
        } catch (e) {
            console.warn('Invalid oauth message', e);
        }
    });

    // Save interface preferences (theme/compact/notifications)
    const saveInterfaceBtn = document.getElementById('save-interface-btn');
    if (saveInterfaceBtn) {
        saveInterfaceBtn.addEventListener('click', async function() {
            // read theme
            const themeInput = document.querySelector('input[name="theme"]:checked');
            const theme = themeInput ? themeInput.value : 'device';

            // apply locally and persist per-user
            applyTheme(theme);
            await persistThemeToServer(theme);

            // optional: persist compact/notifications locally per-user
            try {
                const compact = document.getElementById('compact-view')?.checked;
                const notif = document.getElementById('notifications-enabled')?.checked;
                if (AppState && AppState.currentUser && AppState.currentUser.email) {
                    const key = 'prefs:' + AppState.currentUser.email;
                    localStorage.setItem(key, JSON.stringify({ compact: !!compact, notifications: !!notif }));
                } else {
                    localStorage.setItem('prefs:guest', JSON.stringify({ compact: !!compact, notifications: !!notif }));
                }
            } catch (e) {}

            // redirect to dashboard after saving
            showNotification('Interface preferences saved', 'success');
            setTimeout(() => showPage('dashboard'), 500);
        });
    }

    
    // Notification close button
    const notificationClose = document.getElementById('notification-close');
    if (notificationClose) {
        notificationClose.addEventListener('click', function() {
            const toast = document.getElementById('notification-toast');
            if (toast) toast.classList.add('hidden');
        });
    }
    
    // Loading close button
    const loadingCloseBtn = document.getElementById('loading-close-btn');
    if (loadingCloseBtn) {
        loadingCloseBtn.addEventListener('click', function() {
            hideLoading();
            // Reset search button loading
            const submitBtn = document.getElementById('search-submit-btn');
            if (submitBtn) setButtonLoading(submitBtn, false);
        });
    }
    
    // Clear form errors on input
    const formInputs = document.querySelectorAll('.form-control');
    formInputs.forEach(input => {
        input.addEventListener('input', function() {
            clearFormError(this.id);
        });
    });
    
    // Initialize the application
    updateNavigation();
    // setup theme controls and apply saved theme
    initThemeControls();
    // update FB cookies status (if logged in)
    getFacebookCookiesStatus();

    // Chat panel listeners
    const chatCloseBtn = document.getElementById('chat-close-btn');
    if (chatCloseBtn) chatCloseBtn.addEventListener('click', () => closeChatPanel());

    const chatSendBtn = document.getElementById('chat-send-btn');
    if (chatSendBtn) chatSendBtn.addEventListener('click', sendChatMessage);

    // Delegate inline Ask button clicks from findings list
    const findingsContainer = document.getElementById('findings-list');
    if (findingsContainer) {
        findingsContainer.addEventListener('click', function(e) {
            const btn = e.target.closest('.btn-inline-ask');
            if (!btn) return;
            const pieceId = btn.getAttribute('data-piece-id');
            // open chat panel, create/get session and load messages
            const reportId = document.getElementById('report-id')?.textContent || AppState.chat.reportId;
            openChatPanelAndLoad(reportId, pieceId).then(() => {
                try { document.getElementById('chat-input').focus(); } catch (e) {}
            });
        });
    }

    // Admin dashboard listeners
    const adminLogoutBtn = document.getElementById('admin-logout-btn');
    if (adminLogoutBtn) adminLogoutBtn.addEventListener('click', logout);

    const adminReloadBtn = document.getElementById('admin-reload-btn');
    if (adminReloadBtn) adminReloadBtn.addEventListener('click', () => {
        loadAdminStats();
        loadPotentialMisusers();
        loadSuspendedUsers();
        loadDocuments();
        showNotification('Dashboard reloaded', 'info');
    });

    const misuserModalClose = document.getElementById('misuser-modal-close');
    if (misuserModalClose) misuserModalClose.addEventListener('click', () => {
        document.getElementById('misuser-modal').classList.add('hidden');
    });

    const suspendModalClose = document.getElementById('suspend-modal-close');
    if (suspendModalClose) suspendModalClose.addEventListener('click', () => {
        document.getElementById('suspend-modal').classList.add('hidden');
    });

    const suspendUserBtn = document.getElementById('suspend-user-btn');
    if (suspendUserBtn) suspendUserBtn.addEventListener('click', () => {
        document.getElementById('suspend-modal').classList.remove('hidden');
    });

    const confirmSuspendBtn = document.getElementById('confirm-suspend-btn');
    if (confirmSuspendBtn) confirmSuspendBtn.addEventListener('click', async () => {
        const userId = document.getElementById('misuser-modal').dataset.userId;
        const reason = DOMPurify.sanitize(document.getElementById('suspend-reason').value.trim());
        console.log('Suspension reason:', reason);
        if (!reason) {
            showNotification('Please provide a reason for suspension', 'error');
            return;
        }
        await suspendUser(userId, reason);
        document.getElementById('suspend-modal').classList.add('hidden');
    });

    const cancelSuspendBtn = document.getElementById('cancel-suspend-btn');
    if (cancelSuspendBtn) cancelSuspendBtn.addEventListener('click', () => {
        document.getElementById('suspend-modal').classList.add('hidden');
    });

    const reactivateUserBtn = document.getElementById('reactivate-user-btn');
    if (reactivateUserBtn) reactivateUserBtn.addEventListener('click', async () => {
        const userId = document.getElementById('misuser-modal').dataset.userId;
        await reactivateUser(userId);
    });

    const backToDashboardBtn = document.getElementById('back-to-dashboard-btn');
    if (backToDashboardBtn) backToDashboardBtn.addEventListener('click', () => {
        document.getElementById('misuser-modal').classList.add('hidden');
    });
});

async function reloadSearchHistory() {
    const response = await getHistory();
    if (response.success) {
        // Load only the first report fully, keep others as summaries
        AppState.searchHistory = response.history;
        if (response.history.length > 0) {
            const firstReport = await getReport(response.history[0].report_id);
            if (firstReport.success) {
                // Replace the first item with full report
                AppState.searchHistory[0] = firstReport.report;
            }
        }
        loadSearchHistory();
    }
}

// Post cookies.json to backend
async function postFacebookCookies(cookiesObj) {
    const status = document.getElementById('facebook-cookies-status');
    try {
        // Must contain at least c_user and xs
        if (!cookiesObj.c_user || !cookiesObj.xs) {
            status.textContent = "Missing required c_user or xs field";
            status.style.color = "var(--color-error)";
            return;
        }
        const res = await fetch("/api/profile/facebook/cookies", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": AppState && AppState.jwt ? ("Bearer " + AppState.jwt) : "",
            },
            body: JSON.stringify({ cookies_json: JSON.stringify(cookiesObj) })
        });
        const data = await res.json();
        if (data.success) {
                status.textContent = "Cookies saved!";
                status.style.color = "var(--color-success)";
                // Refresh status badge
                await getFacebookCookiesStatus();
                // Show toast and redirect after a short delay so user sees the notification
                showNotification('Cookies saved!', 'success');
                setTimeout(() => showPage('dashboard'), 500);
        } else {
            status.textContent = data.error || "Failed to save cookies";
            status.style.color = "var(--color-error)";
        }
    } catch (e) {
        status.textContent = "Request failed";
        status.style.color = "var(--color-error)";
    }
}

// Fetch Facebook cookies status from backend and update UI
async function getFacebookCookiesStatus() {
    const fbStatusSpan = document.getElementById('fb-status-text');
    const statusEl = document.getElementById('facebook-cookies-status');

    if (!AppState || !AppState.jwt) {
        if (fbStatusSpan) fbStatusSpan.textContent = 'Not signed in';
        if (statusEl) {
            statusEl.textContent = 'Sign in to manage cookies';
            statusEl.style.color = 'var(--color-error)';
        }
        return;
    }

    try {
        const res = await fetch('/api/profile/facebook/cookies', {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + AppState.jwt
            }
        });
        const data = await res.json();
        if (data.has_cookies) {
            if (data.is_expired) {
                if (fbStatusSpan) fbStatusSpan.textContent = 'Saved (expired)';
                if (statusEl) { statusEl.textContent = 'Cookies present but expired'; statusEl.style.color = 'orange'; }
            } else {
                if (fbStatusSpan) fbStatusSpan.textContent = 'Saved (valid)';
                if (statusEl) { statusEl.textContent = 'Cookies saved and valid'; statusEl.style.color = 'var(--color-success)'; }
            }
        } else {
            if (fbStatusSpan) fbStatusSpan.textContent = 'Not configured';
            if (statusEl) { statusEl.textContent = 'No cookies saved'; statusEl.style.color = 'var(--color-error)'; }
        }
    } catch (e) {
        if (fbStatusSpan) fbStatusSpan.textContent = 'Status unknown';
        if (statusEl) { statusEl.textContent = 'Failed to fetch status'; statusEl.style.color = 'var(--color-error)'; }
    }
}



// Make loadReport function global for onclick handlers
window.loadReport = loadReport;

// Export report function
async function exportReport(format) {
    const reportId = document.getElementById('report-id').textContent;
    if (!reportId) {
        showNotification('No report loaded', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/reports/${reportId}/export?format=${format}`, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + AppState.jwt
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            showNotification(errorData.message || 'Export failed', 'error');
            return;
        }

        // Create download link
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${reportId}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification(`Report exported as ${format.toUpperCase()}`, 'success');
    } catch (e) {
        console.error('Export error:', e);
        showNotification('Export failed', 'error');
    }
}

// ADMIN FUNCTIONS

async function loadAdminStats() {
    console.log('[DEBUG] Loading admin stats...');
    try {
        const response = await fetch('/api/admin/stats', {
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        const data = await response.json();
        console.log('[DEBUG] Admin stats response:', data);
        if (data.success) {
            displayAdminStats(data.stats);
        } else {
            showNotification(data.message || 'Failed to load statistics', 'error');
        }
    } catch (e) {
        console.error('Load admin stats error:', e);
        showNotification('Failed to load statistics', 'error');
    }
}

function displayAdminStats(stats) {
    console.log('[DEBUG] Displaying admin stats:', stats);
    document.getElementById('active-users').textContent = stats.active_users || 0;
    document.getElementById('active-sessions').textContent = stats.active_sessions || 0;
    document.getElementById('acquisition-velocity').textContent = stats.acquisition_velocity ? stats.acquisition_velocity.toFixed(2) : 0;
    document.getElementById('weekly-reports').textContent = stats.weekly_reports || 0;
    document.getElementById('weekly-chats').textContent = stats.weekly_chats || 0;
    document.getElementById('apdex-score').textContent = stats.apdex_score ? stats.apdex_score.toFixed(3) : 0;
    document.getElementById('misuse-index').textContent = stats.misuse_index ? stats.misuse_index.toFixed(3) : 0;
}

async function loadPotentialMisusers() {
    try {
        const response = await fetch('/api/admin/misusers', {
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        const data = await response.json();
        if (data.success) {
            displayMisusers(data.misusers);
        } else {
            showNotification(data.message || 'Failed to load misusers', 'error');
        }
    } catch (e) {
        console.error('Load misusers error:', e);
        showNotification('Failed to load misusers', 'error');
    }
}

function displayMisusers(misusers) {
    const container = document.getElementById('misusers-list');
    if (misusers.length === 0) {
        container.innerHTML = '<p class="empty-state">No potential misusers detected</p>';
        return;
    }

    const html = misusers.map(misuser => `
        <div class="misuser-item card" data-user-id="${misuser.user_id}">
            <div class="card__body">
                <div class="flex items-center justify-between">
                    <div>
                        <h4>${misuser.name || 'Unknown'}</h4>
                        <p class="small-text">${misuser.email}</p>
                        <p class="small-text">Misuse Score: ${misuser.misuse_score.toFixed(3)}</p>
                        <p class="small-text">Recent Searches: ${misuser.recent_searches_count}</p>
                    </div>
                    <button class="btn btn--outline view-misuser-btn" data-user-id="${misuser.user_id}">View Details</button>
                </div>
            </div>
        </div>
    `).join('');
    container.innerHTML = html;

    // Add event listeners
    document.querySelectorAll('.view-misuser-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const userId = e.target.dataset.userId;
            showMisuserModal(userId);
        });
    });
}

async function showMisuserModal(userId) {
    try {
        // Get user info
        const userResponse = await fetch(`/api/admin/user/${userId}/requests`, {
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        const userData = await userResponse.json();
        
        if (userData.success) {
            // For now, we'll need to get user details separately or store them
            // Let's assume we have the misuser data from the list
            const misuserCard = document.querySelector(`[data-user-id="${userId}"]`);
            const name = misuserCard.querySelector('h4').textContent;
            const email = misuserCard.querySelector('.small-text').textContent.split('\n')[0];
            const score = misuserCard.querySelectorAll('.small-text')[1].textContent.split(': ')[1];
            
            document.getElementById('misuser-email').textContent = email;
            document.getElementById('misuser-name').textContent = name;
            document.getElementById('misuser-score').textContent = score;
            
            // Display requests
            const requestsHtml = userData.requests.map(req => `
                <div class="request-item">
                    <strong>${req.type.toUpperCase()}:</strong> ${req.query}
                    <br><small>${new Date(req.timestamp).toLocaleString()}</small>
                </div>
            `).join('');
            document.getElementById('misuser-requests').innerHTML = requestsHtml || '<p>No recent requests</p>';
            
            // Set user ID on modal for later use
            document.getElementById('misuser-modal').dataset.userId = userId;
            document.getElementById('suspend-user-email').textContent = email;
            
            document.getElementById('misuser-modal').classList.remove('hidden');
        } else {
            showNotification(userData.message || 'Failed to load user details', 'error');
        }
    } catch (e) {
        console.error('Show misuser modal error:', e);
        showNotification('Failed to load user details', 'error');
    }
}

async function suspendUser(userId, reason) {
    try {
        const response = await fetch(`/api/admin/user/${userId}/suspend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + AppState.jwt
            },
            body: JSON.stringify({ reason })
        });
        const data = await response.json();
        if (data.success) {
            showNotification('User suspended successfully', 'success');
            document.getElementById('misuser-modal').classList.add('hidden');
            loadPotentialMisusers(); // Refresh list
            loadSuspendedUsers();
        } else {
            showNotification(data.message || 'Failed to suspend user', 'error');
        }
    } catch (e) {
        console.error('Suspend user error:', e);
        showNotification('Failed to suspend user', 'error');
    }
}

async function reactivateUser(userId) {
    try {
        const response = await fetch(`/api/admin/user/${userId}/reactivate`, {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + AppState.jwt
            },
            body: JSON.stringify({})
        });
        const data = await response.json();
        if (data.success) {
            showNotification('User reactivated successfully', 'success');
            document.getElementById('misuser-modal').classList.add('hidden');
            loadPotentialMisusers(); // Refresh list
        } else {
            showNotification(data.message || 'Failed to reactivate user', 'error');
        }
    } catch (e) {
        console.error('Reactivate user error:', e);
        showNotification('Failed to reactivate user', 'error');
    }
}

async function loadSuspendedUsers() {
    console.log('[DEBUG] Loading suspended users...');
    try {
        const response = await fetch('/api/admin/suspended', {
            headers: { 'Authorization': 'Bearer ' + AppState.jwt }
        });
        const data = await response.json();
        if (data.success) {
            displaySuspendedUsers(data.suspended_users);
        } else {
            showNotification(data.message || 'Failed to load suspended users', 'error');
        }
    } catch (e) {
        console.error('Load suspended users error:', e);
        showNotification('Failed to load suspended users', 'error');
    }
}

function displaySuspendedUsers(suspendedUsers) {
    const container = document.getElementById('suspended-list');
    if (suspendedUsers.length === 0) {
        container.innerHTML = '<p class="empty-state">No suspended users</p>';
        return;
    }

    const html = suspendedUsers.map(user => `
        <div class="suspended-user-item card" data-user-id="${user.user_id}">
            <div class="card__body">
                <div class="flex items-center justify-between">
                    <div>
                        <h4>${user.name || 'Unknown'}</h4>
                        <p class="small-text">${user.email}</p>
                        <p class="small-text">Suspended: ${new Date(user.suspended_at).toLocaleDateString()}</p>
                        <p class="small-text">Created: ${new Date(user.created_at).toLocaleDateString()}</p>
                    </div>
                    <button class="btn btn--success reactivate-user-btn" data-user-id="${user.user_id}">Reactivate</button>
                </div>
            </div>
        </div>
    `).join('');
    container.innerHTML = html;

    // Add event listeners
    document.querySelectorAll('.reactivate-user-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const userId = e.target.dataset.userId;
            reactivateSuspendedUser(userId);
        });
    });
}

async function reactivateSuspendedUser(userId) {
    try {
        const response = await fetch(`/api/admin/user/${userId}/reactivate`, {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + AppState.jwt
            },
            body: JSON.stringify({})
        });
        const data = await response.json();
        if (data.success) {
            showNotification('User reactivated successfully', 'success');
            loadSuspendedUsers(); // Refresh list
            loadPotentialMisusers();
        } else {
            showNotification(data.message || 'Failed to reactivate user', 'error');
        }
    } catch (e) {
        console.error('Reactivate suspended user error:', e);
        showNotification('Failed to reactivate user', 'error');
    }
}

//  KNOWLEDGE BASE MANAGEMENT

async function loadDocuments() {
    const documentsList = document.getElementById('documents-list');
    if (!documentsList) return;
    
    try {
        const response = await fetch('/api/admin/documents', {
            headers: {
                'Authorization': `Bearer ${AppState.jwt}`
            }
        });
        const data = await response.json();
        
        if (data.success) {
            if (data.documents.length === 0) {
                documentsList.innerHTML = '<p class="empty-state">No documents in knowledge base.</p>';
            } else {
                documentsList.innerHTML = data.documents.map(doc => `
                    <div class="document-item" style="display: flex; justify-content: space-between; align-items: center; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; margin-bottom: 8px;">
                        <span>${doc.filename}</span>
                        <div>
                            <button class="btn btn--outline btn--sm" onclick="downloadDocument('${doc.filename}')">Download</button>
                            <button class="btn btn--danger btn--sm" onclick="removeDocument('${doc.filename}')">Remove</button>
                        </div>
                    </div>
                `).join('');
            }
        } else {
            documentsList.innerHTML = '<p class="empty-state">Failed to load documents.</p>';
        }
    } catch (e) {
        console.error('Load documents error:', e);
        documentsList.innerHTML = '<p class="empty-state">Failed to load documents.</p>';
    }
}

function initializeDocumentUpload() {
    const uploadBtn = document.getElementById('upload-document-btn');
    const fileInput = document.getElementById('document-file');
    
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', async () => {
            const file = fileInput.files[0];
            if (!file) {
                showNotification('Please select a file to upload', 'error');
                return;
            }
            
            setButtonLoading(uploadBtn, true);
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/api/admin/documents/upload', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${AppState.jwt}`
                    },
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (data.status === 'conflicts_detected') {
                        // Handle conflicts - for now, just show message
                        showNotification('Document uploaded but conflicts detected. Processing with existing version.', 'warning');
                        loadDocuments();
                    } else {
                        showNotification(data.message, 'success');
                        loadDocuments();
                    }
                    fileInput.value = '';
                } else {
                    showNotification(data.message || 'Upload failed', 'error');
                }
            } catch (e) {
                console.error('Upload document error:', e);
                showNotification('Upload failed', 'error');
            } finally {
                setButtonLoading(uploadBtn, false);
            }
        });
    }
}

async function downloadDocument(filename) {
    try {
        const response = await fetch(`/api/admin/documents/${filename}/download`, {
            headers: {
                'Authorization': `Bearer ${AppState.jwt}`
            }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            showNotification('Download failed', 'error');
        }
    } catch (e) {
        console.error('Download document error:', e);
        showNotification('Download failed', 'error');
    }
}

async function removeDocument(filename) {
    if (!confirm(`Are you sure you want to remove "${filename}" from the knowledge base?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/documents/${filename}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${AppState.jwt}`
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message, 'success');
            loadDocuments();
        } else {
            showNotification(data.message || 'Removal failed', 'error');
        }
    } catch (e) {
        console.error('Remove document error:', e);
        showNotification('Removal failed', 'error');
    }
}