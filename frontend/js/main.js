// API base URL - change this to your Flask server URL
const API_BASE_URL = 'http://localhost:5000/api';

// Global state management
const appState = {
    user: null,
    isLoggedIn: false,
    currentPage: 'home'
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Check if user is logged in (check localStorage)
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
        appState.user = JSON.parse(savedUser);
        appState.isLoggedIn = true;
        updateUI();
    }

    // Add event listeners
    setupEventListeners();
    
    console.log('AI Video Gallery initialized');
}

function setupEventListeners() {
    // Modal click outside to close
    window.addEventListener('click', function(event) {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });

    // Form submissions
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
}

// Modal functions
function showLogin() {
    document.getElementById('loginModal').style.display = 'block';
    document.getElementById('registerModal').style.display = 'none';
}

function showRegister() {
    document.getElementById('registerModal').style.display = 'block';
    document.getElementById('loginModal').style.display = 'none';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function showDemo() {
    alert('Demo feature coming soon! This will show a quick tour of the AI Video Gallery features.');
}

// Authentication functions
async function handleLogin(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const loginData = {
        email: formData.get('email') || event.target.querySelector('input[type="email"]').value,
        password: formData.get('password') || event.target.querySelector('input[type="password"]').value
    };

    try {
        showLoading('Logging in...');
        
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(loginData)
        });

        const result = await response.json();
        
        if (response.ok) {
            // Store user data
            appState.user = result.user;
            appState.isLoggedIn = true;
            localStorage.setItem('user', JSON.stringify(result.user));
            
            closeModal('loginModal');
            showSuccess('Login successful!');
            updateUI();
            
            // Redirect to dashboard
            window.location.href = 'dashboard.html';
        } else {
            showError(result.error || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError('Network error. Please try again.');
    } finally {
        hideLoading();
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const form = event.target;
    const password = form.querySelector('input[placeholder="Password"]').value;
    const confirmPassword = form.querySelector('input[placeholder="Confirm Password"]').value;
    
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }

    const registerData = {
        name: form.querySelector('input[placeholder="Full Name"]').value,
        email: form.querySelector('input[type="email"]').value,
        password: password
    };

    try {
        showLoading('Creating account...');
        
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(registerData)
        });

        const result = await response.json();
        
        if (response.ok) {
            closeModal('registerModal');
            showSuccess('Account created successfully! Please log in.');
            showLogin();
        } else {
            showError(result.error || 'Registration failed');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showError('Network error. Please try again.');
    } finally {
        hideLoading();
    }
}

function logout() {
    appState.user = null;
    appState.isLoggedIn = false;
    localStorage.removeItem('user');
    updateUI();
    window.location.href = 'index.html';
}

// UI update functions
function updateUI() {
    const navMenu = document.querySelector('.nav-menu');
    if (!navMenu) return;

    if (appState.isLoggedIn) {
        // Show logged-in navigation
        navMenu.innerHTML = `
            <a href="dashboard.html" class="nav-link">Dashboard</a>
            <a href="upload.html" class="nav-link">Upload</a>
            <a href="search.html" class="nav-link">Search</a>
            <a href="#" class="nav-link" onclick="logout()">Logout</a>
        `;
    } else {
        // Show logged-out navigation
        navMenu.innerHTML = `
            <a href="index.html" class="nav-link">Home</a>
            <a href="#" class="nav-link" onclick="showLogin()">Login</a>
            <a href="#" class="nav-link" onclick="showRegister()">Sign Up</a>
        `;
    }
}

// Utility functions for user feedback
function showLoading(message) {
    // Create or update loading indicator
    let loader = document.getElementById('loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'loader';
        loader.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            z-index: 3000;
            text-align: center;
        `;
        document.body.appendChild(loader);
    }
    loader.innerHTML = `
        <div style="margin-bottom: 1rem;">⏳</div>
        <div>${message}</div>
    `;
    loader.style.display = 'block';
}

function hideLoading() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'none';
    }
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 2rem;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 3000;
        animation: slideIn 0.3s ease;
        background-color: ${type === 'success' ? '#4caf50' : '#f44336'};
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style);