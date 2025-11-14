document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    const logoutButton = document.getElementById("logout-button");

    if (loginForm) {
        loginForm.addEventListener("submit", handleLogin);
    }

    if (logoutButton) {
        logoutButton.addEventListener("click", logout);
    }
});

/**
 * Handles the login form submission.
 * [UPDATED] to show clean error messages.
 */
async function handleLogin(e) {
    e.preventDefault();
    const errorMessage = document.getElementById("error-message");
    const loginButton = document.getElementById("login-button");

    errorMessage.classList.add("hidden");
    loginButton.disabled = true;
    loginButton.textContent = "Logging in...";

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                username: email,
                password: password,
            }),
        });

        // Get the JSON response body, whether it's an error or success
        const data = await response.json();

        if (!response.ok) {
            // If response is not OK (e.g., 401, 500), 
            // throw the clean 'detail' message from the backend.
            throw new Error(data.detail || "An unknown error occurred.");
        }

        // --- Success ---
        // If we are here, response was OK (200)
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("user_role", data.user_role);

        redirectToDashboard(data.user_role);

    } catch (error) {
        // --- [FIXED] ---
        // This 'error' is now the 'data.detail' message we threw
        // (e.g., "Invalid email or password.")
        console.error("Login error:", error.message);
        errorMessage.textContent = error.message; // This will be a clean string
        errorMessage.classList.remove("hidden");
        loginButton.disabled = false;
        loginButton.textContent = "Login";
    }
}

/**
 * Redirects the user to the appropriate dashboard based on their role.
 * @param {string} role - The user's role ('admin', 'teacher', 'student', 'ta')
 */
function redirectToDashboard(role) {
    switch (role) {
        case "admin":
            window.location.href = "dashboard_admin.html";
            break;
        case "teacher":
            window.location.href = "dashboard_teacher.html";
            break;
        case "student":
            window.location.href = "dashboard_student.html";
            break;
        case "ta":
            window.location.href = "dashboard_ta.html";
            break;
        default:
            console.error("Unknown user role:", role);
            window.location.href = "index.html"; // Back to login
    }
}

/**
 * Logs the user out by clearing localStorage and redirecting to login.
 */
function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_role");

    redirectToLogin();
}