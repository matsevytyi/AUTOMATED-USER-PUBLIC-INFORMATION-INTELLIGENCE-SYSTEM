// Application State
const AppState = {
    currentUser: null,
    currentPage: 'home',
    searchHistory: [],
    currentReport: null
};

// Mock Data (simulating Flask backend responses)
const MockData = {
    users: [
        {
            email: "demo@profolio.com",
            password: "Demo123!",
            confirmed: true,
            name: "Demo User"
        }
    ],
    reports: [
        {
            report_id: "RPT-2024-001",
            user: "demo@profolio.com",
            query: "John Smith social media",
            generated_at: "2024-12-06T18:00:00Z",
            status: "completed",
            executive_summary: "Digital footprint analysis reveals moderate online exposure across 8 platforms with 3 high-risk information pieces requiring attention.",
            risk_distribution: {
                high: 3,
                medium: 7,
                low: 12
            },
            detailed_findings: [
                {
                    source: "LinkedIn",
                    category: "Professional",
                    info: "Current employment at TechCorp Inc.",
                    risk: "low",
                    timestamp: "2024-11-15",
                    url: "linkedin.com/in/johnsmith"
                },
                {
                    source: "Twitter",
                    category: "Social Media",
                    info: "Public tweets mentioning personal location",
                    risk: "medium",
                    timestamp: "2024-12-01",
                    url: "twitter.com/johnsmith123"
                },
                {
                    source: "Data Breach Database",
                    category: "Security",
                    info: "Email found in 2023 breach of ExampleSite",
                    risk: "high",
                    timestamp: "2023-08-15",
                    url: "N/A"
                },
                {
                    source: "Facebook",
                    category: "Social Media", 
                    info: "Public profile with family photos",
                    risk: "medium",
                    timestamp: "2024-10-20",
                    url: "facebook.com/john.smith"
                },
                {
                    source: "Public Records",
                    category: "Legal",
                    info: "Property ownership records",
                    risk: "low",
                    timestamp: "2024-01-10",
                    url: "N/A"
                }
            ],
            recommendations: [
                "Review privacy settings on social media accounts",
                "Consider changing passwords for accounts involved in data breaches",
                "Limit location sharing in social media posts",
                "Monitor credit reports for suspicious activity"
            ],
            source_distribution: {
                "Social Media": 8,
                "Professional Networks": 3,
                "Public Records": 4,
                "News/Articles": 2,
                "Data Breaches": 1,
                "Forums/Blogs": 4
            }
        }
    ]
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

// Authentication Functions
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

// Simulate API calls
function simulateAPICall(endpoint, data, delay = 1500) {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            try {
                switch (endpoint) {
                    case 'register':
                        // Check if user already exists
                        const existingUser = MockData.users.find(user => user.email === data.email);
                        if (existingUser) {
                            reject({ message: 'User with this email already exists' });
                        } else {
                            // Add new user
                            const newUser = {
                                email: data.email,
                                password: data.password,
                                name: data.name,
                                confirmed: false
                            };
                            MockData.users.push(newUser);
                            resolve({ message: 'Registration successful', user: newUser });
                        }
                        break;
                        
                    case 'login':
                        const user = MockData.users.find(u => u.email === data.email && u.password === data.password);
                        if (user) {
                            if (!user.confirmed) {
                                reject({ message: 'Please confirm your email address before logging in' });
                            } else {
                                resolve({ message: 'Login successful', user: user });
                            }
                        } else {
                            reject({ message: 'Invalid email or password' });
                        }
                        break;
                        
                    case 'confirm':
                        const userToConfirm = MockData.users.find(u => u.email === data.email);
                        if (userToConfirm) {
                            userToConfirm.confirmed = true;
                            resolve({ message: 'Email confirmed successfully', user: userToConfirm });
                        } else {
                            reject({ message: 'User not found' });
                        }
                        break;
                        
                    case 'search':
                        // Generate a new report based on the query
                        const reportId = 'RPT-' + Date.now();
                        const newReport = {
                            ...MockData.reports[0],
                            report_id: reportId,
                            query: data.query,
                            user: AppState.currentUser.email,
                            generated_at: new Date().toISOString()
                        };
                        resolve({ message: 'Search completed', report: newReport });
                        break;
                        
                    default:
                        reject({ message: 'Unknown endpoint' });
                }
            } catch (error) {
                reject({ message: 'Internal server error' });
            }
        }, delay);
    });
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
            
            try {
                const response = await simulateAPICall('register', formData);
                showNotification(response.message, 'success');
                
                // Store user for confirmation
                AppState.pendingUser = response.user;
                showPage('confirm');
            } catch (error) {
                showNotification(error.message, 'error');
            } finally {
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
                email: document.getElementById('login-email').value.trim(),
                password: document.getElementById('login-password').value
            };
            
            try {
                const response = await simulateAPICall('login', formData);
                AppState.currentUser = response.user;
                showNotification(response.message, 'success');
                showPage('dashboard');
            } catch (error) {
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitBtn, false);
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
                const response = await simulateAPICall('confirm', { email: AppState.pendingUser.email });
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
            
            try {
                const response = await simulateAPICall('search', { query: query }, 2000);
                
                // Add to search history
                AppState.searchHistory.unshift(response.report);
                
                // Display the report
                displayReport(response.report);
                
                // Update search history display
                loadSearchHistory();
                
                // Clear the form
                queryField.value = '';
                
                showNotification('Report generated successfully', 'success');
            } catch (error) {
                showNotification(error.message, 'error');
            } finally {
                setButtonLoading(submitBtn, false);
                hideLoading();
            }
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

// Make loadReport function global for onclick handlers
window.loadReport = loadReport;