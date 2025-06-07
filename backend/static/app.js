// Application State
const AppState = {
    currentUser: null,
    jwt: null,
    currentPage: 'home',
    searchHistory: [],
    currentReport: null,
    pendingUser: null
};


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
    }
}

function updateNavigation() {
    const loginBtn = document.getElementById('nav-login-btn');
    const registerBtn = document.getElementById('nav-register-btn');
    const logoutBtn = document.getElementById('nav-logout-btn');
    
    if (AppState.currentUser) {
        if (loginBtn) loginBtn.classList.add('hidden');
        if (registerBtn) registerBtn.classList.add('hidden');
        if (logoutBtn) logoutBtn.classList.remove('hidden');
    } else {
        if (loginBtn) loginBtn.classList.remove('hidden');
        if (registerBtn) registerBtn.classList.remove('hidden');
        if (logoutBtn) logoutBtn.classList.add('hidden');
    }
}

// Main authentication functions

async function registerUser(formData) {
    const response = await fetch('/api/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });
    return await response.json();
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

async function confirmEmail(email) {
    const response = await fetch('/api/confirm', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email })
    });
    return await response.json();
}

async function searchReport(query) {
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + AppState.jwt
        },
        body: JSON.stringify({ query })
    });
    return await response.json();
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


// Authentication Util Functions
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function validatePassword(password) {
    // At least 8 characters, one uppercase, one lowercase, one number, one special character
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
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
    
    const name = nameField.value.trim();
    const email = emailField.value.trim();
    const password = passwordField.value;
    const confirmPassword = confirmPasswordField.value;
    
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

function validateLoginForm() {
    const emailField = document.getElementById('login-email');
    const passwordField = document.getElementById('login-password');
    
    if (!emailField || !passwordField) {
        return false;
    }
    
    const email = emailField.value.trim();
    const password = passwordField.value;
    
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

function loadReport(reportId) {
    const report = AppState.searchHistory.find(r => r.report_id === reportId);
    if (report) {
        displayReport(report);
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
    
    if (highRiskCount) highRiskCount.textContent = report.risk_distribution.high;
    if (mediumRiskCount) mediumRiskCount.textContent = report.risk_distribution.medium;
    if (lowRiskCount) lowRiskCount.textContent = report.risk_distribution.low;
    
    // Update detailed findings
    const findingsList = document.getElementById('findings-list');
    if (findingsList) {
        findingsList.innerHTML = report.detailed_findings.map(finding => `
            <div class="finding-item risk-${finding.risk}">
                <div class="finding-header">
                    <div class="finding-source">${finding.source}</div>
                    <div class="finding-category">${finding.category}</div>
                </div>
                <div class="finding-info">${finding.info}</div>
                <div class="finding-meta">
                    <div class="finding-timestamp">Found: ${new Date(finding.timestamp).toLocaleDateString()}</div>
                    ${finding.url !== 'N/A' ? `<a href="https://${finding.url}" target="_blank" class="finding-url">${finding.url}</a>` : '<span class="finding-url">Source not public</span>'}
                </div>
            </div>
        `).join('');
    }
    
    // Update recommendations
    const recommendationsList = document.getElementById('recommendations-list');
    if (recommendationsList) {
        recommendationsList.innerHTML = report.recommendations.map(rec => `
            <div class="recommendation-item">${rec}</div>
        `).join('');
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
    AppState.searchHistory = [];
    AppState.currentReport = null;
    
    // Hide report section
    const reportSection = document.getElementById('report-section');
    if (reportSection) {
        reportSection.classList.add('hidden');
    }
    
    showNotification('Logged out successfully', 'info');
    showPage('home');
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Ensure loading overlay is hidden on page load
    hideLoading();
    
    // Navigation event listeners
    const navLoginBtn = document.getElementById('nav-login-btn');
    const navRegisterBtn = document.getElementById('nav-register-btn');
    const navLogoutBtn = document.getElementById('nav-logout-btn');
    const heroLoginBtn = document.getElementById('hero-login-btn');
    const heroRegisterBtn = document.getElementById('hero-register-btn');
    const authLoginLink = document.getElementById('auth-login-link');
    const authRegisterLink = document.getElementById('auth-register-link');
    
    if (navLoginBtn) navLoginBtn.addEventListener('click', () => showPage('login'));
    if (navRegisterBtn) navRegisterBtn.addEventListener('click', () => showPage('register'));
    if (navLogoutBtn) navLogoutBtn.addEventListener('click', logout);
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
                name: document.getElementById('register-name').value.trim(),
                email: document.getElementById('register-email').value.trim(),
                password: document.getElementById('register-password').value
            };
            
            const response = await registerUser(formData);
            if (response.success) {
                AppState.pendingUser = { email: formData.email };
                showNotification(response.message, 'success');
                showPage('confirm');
            } else {
                showNotification(response.message, 'error');
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
                email: document.getElementById('login-email').value.trim(),
                password: document.getElementById('login-password').value
            };
            
            const response = await loginUser(formData);
            if (response.success) {
                showNotification(response.message, 'success');
                showPage('dashboard');
                await reloadSearchHistory();
            } else {
                showNotification(response.message, 'error');
            }
        });
    }
    
    // Email confirmation simulation
    const simulateConfirmBtn = document.getElementById('simulate-confirm-btn');
    if (simulateConfirmBtn) {
        simulateConfirmBtn.addEventListener('click', async function() {
            if (!AppState.pendingUser) {
                showNotification('No pending confirmation found', 'error');
                return;
            }
            
            setButtonLoading(this, true);
            
            try {

                const response = await fetch('/api/confirm', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email: AppState.pendingUser.email })
                }).then(res => res.json());

                AppState.currentUser = response.user;
                AppState.pendingUser = null;

                showNotification(response.message, 'success');
                showPage('dashboard');

            } catch (error) {
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(this, false);
            }
        });
    }
    
    // Search form
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const queryField = document.getElementById('search-query');
            if (!queryField) return;
            
            const query = queryField.value.trim();
            if (!query) {
                showNotification('Please enter a search query', 'error');
                return;
            }
            
            const submitBtn = document.getElementById('search-submit-btn');
            setButtonLoading(submitBtn, true);
            showLoading();

            const response = await searchReport(query);

            if (response.success) {
                AppState.searchHistory.unshift(response.report);
                displayReport(response.report);
                loadSearchHistory();
                showNotification('Report generated successfully', 'success');
            } else {
                showNotification(response.message, 'error');
            }
            
            // try {

            //     const response = await fetch('/api/search', {
            //         method: 'POST',
            //         headers: {
            //             'Content-Type': 'application/json',
            //             'Authorization': 'Bearer ' + AppState.jwt  // JWT from login
            //         },
            //         body: JSON.stringify({ query: query })
            //     }).then(res => res.json());

                
            //     // Add to search history
            //     AppState.searchHistory.unshift(response.report);
                
            //     // Display the report
            //     displayReport(response.report);
                
            //     // Update search history display
            //     loadSearchHistory();
                
            //     // Clear the form
            //     queryField.value = '';
                
            //     showNotification('Report generated successfully', 'success');
            // } catch (error) {
            //     showNotification(error.message, 'error');
            // } finally {
            //     setButtonLoading(submitBtn, false);
            //     hideLoading();
            // }
        });
    }
    
    // Profile button
    const profileBtn = document.getElementById('profile-btn');
    if (profileBtn) {
        profileBtn.addEventListener('click', function() {
            showNotification('Profile management coming soon', 'info');
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
    
    // Clear form errors on input
    const formInputs = document.querySelectorAll('.form-control');
    formInputs.forEach(input => {
        input.addEventListener('input', function() {
            clearFormError(this.id);
        });
    });
    
    // Initialize the application
    updateNavigation();
});

async function reloadSearchHistory() {
    const response = await getHistory();
    if (response.success) {
        // For each history item, get the report details
        const reports = [];
        for (const hist of response.history) {
            const rep = await getReport(hist.report_id);
            if (rep.success) reports.push(rep.report);
        }
        AppState.searchHistory = reports;
        loadSearchHistory();
    }
}


// Make loadReport function global for onclick handlers
window.loadReport = loadReport;