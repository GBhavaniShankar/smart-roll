// frontend/js/main.js

// --- Global Configuration ---

const API_BASE_URL = "http://localhost:8000"; // Your FastAPI server URL

// --- Utility Functions ---

/**
 * A wrapper for the native fetch API to automatically include the
 * JWT access token in the headers for all API requests.
 */
async function apiFetch(endpoint, options = {}) {
    let accessToken = localStorage.getItem("access_token");

    if (!accessToken) {
        console.error("No access token found. Redirecting to login.");
        redirectToLogin();
        return;
    }

    const defaultHeaders = {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`
    };

    if (options.body instanceof FormData) {
        delete defaultHeaders["Content-Type"];
    }

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers,
        },
    };

    let response = await fetch(`${API_BASE_URL}${endpoint}`, config);

    if (response.status === 401 || response.status === 403) {
        console.error("Authorization error. Logging out.");
        logout(); // This will call the function in auth.js
        return;
    }

    return response;
}

/**
 * Redirects the user to the login page.
 */
function redirectToLogin() {
    if (!window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
        window.location.href = "index.html";
    }
}

/**
 * Checks for auth tokens and redirects to login if not found.
 */
function protectPage() {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
        redirectToLogin();
    }
}

/**
 * Injects a simple loader into a container.
 */
function showLoader(container) {
    container.innerHTML = `
        <div class="loader-container">
            <div class="loader"></div>
        </div>
    `;
}