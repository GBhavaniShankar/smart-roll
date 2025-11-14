// frontend/js/admin.js
// Protect this page
protectPage();

document.addEventListener("DOMContentLoaded", () => {
    // Page navigation
    const navLinks = document.querySelectorAll(".sidebar-nav a");
    const pages = document.querySelectorAll(".page-content");
    const headerTitle = document.getElementById("header-title");
    
    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const pageId = `page-${link.dataset.page}`;
            pages.forEach(page => page.classList.add("hidden"));
            document.getElementById(pageId).classList.remove("hidden");
            navLinks.forEach(nav => nav.classList.remove("active"));
            link.classList.add("active");
            headerTitle.textContent = link.textContent;
            if (link.dataset.page === 'users') {
                loadUsers();
            }
        });
    });
    
    // Form Listeners
    document.getElementById("add-student-form").addEventListener("submit", handleAddNewStudent);
    document.getElementById("add-teacher-form").addEventListener("submit", handleAddNewTeacher);
    document.getElementById("registration-form").addEventListener("submit", handleStartRegistration);
    document.getElementById("stop-registration-btn").addEventListener("click", handleStopRegistration);
    document.getElementById("user-filter").addEventListener("change", loadUsers);
    document.getElementById("advance-semester-btn").addEventListener("click", handleAdvanceSemester);

    // Initial load
    loadUsers();
});

function showStatusMessage(message, type) {
    const statusBox = document.getElementById("status-message");
    statusBox.textContent = message;
    statusBox.style.backgroundColor = type === 'success' ? '#d4edda' : '#f8d7da';
    statusBox.style.color = type === 'success' ? '#155724' : '#721c24';
    statusBox.classList.remove("hidden");
    setTimeout(() => statusBox.classList.add("hidden"), 5000);
}

// --- User Management ---
async function loadUsers() {
    const container = document.getElementById("user-list-container");
    const roleFilter = document.getElementById("user-filter").value;
    showLoader(container);
    let endpoint = "/api/admin/users";
    if (roleFilter) {
        endpoint += `?role=${roleFilter}`;
    }
    try {
        const response = await apiFetch(endpoint);
        if (!response.ok) throw new Error(await response.text());
        const users = await response.json();
        renderUsers(users, container);
    } catch (error) {
        console.error("Failed to load users:", error);
        container.innerHTML = `<p style="color: red;">Error loading users.</p>`;
    }
}

function renderUsers(users, container) {
    if (users.length === 0) {
        container.innerHTML = "<p>No users found.</p>";
        return;
    }
    let tableHtml = `
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 2px solid var(--primary-color);">
                    <th style="padding: 0.5rem; text-align: left;">Name</th>
                    <th style="padding: 0.5rem; text-align: left;">Email</th>
                    <th style="padding: 0.5rem; text-align: left;">Role</th>
                    <th style="padding: 0.5rem; text-align: left;">Actions</th>
                </tr>
            </thead>
            <tbody>
    `;
    users.forEach(user => {
        let actionsHtml = '';
        if (user.role === 'student') {
            actionsHtml = `
                <button class="btn btn-promote-ta" data-user-id="${user.user_id}" 
                        style="background-color: #ffc107; color: #333; padding: 0.25rem 0.5rem; width: auto; font-size: 0.8rem;">
                    Promote to TA
                </button>
            `;
        } else if (user.role === 'ta') {
            actionsHtml = `<span style="color: #007bff; font-weight: 600;">Is a TA</span>`;
        }
        tableHtml += `
            <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 0.5rem;">${user.full_name}</td>
                <td style="padding: 0.5rem;">${user.email}</td>
                <td style="padding: 0.5rem;">${user.role}</td>
                <td style="padding: 0.5rem;">
                    <button class="btn btn-delete" data-user-id="${user.user_id}" 
                            style="background-color: #dc3545; color: white; padding: 0.25rem 0.5rem; width: auto; font-size: 0.8rem; margin-right: 5px;">
                        Delete
                    </button>
                    ${actionsHtml}
                </td>
            </tr>
        `;
    });
    tableHtml += `</tbody></table>`;
    container.innerHTML = tableHtml;
    document.querySelectorAll(".btn-delete").forEach(button => {
        button.addEventListener("click", handleDeleteUser);
    });
    document.querySelectorAll(".btn-promote-ta").forEach(button => {
        button.addEventListener("click", handlePromoteToTA);
    });
}

async function handlePromoteToTA(e) {
    const button = e.target;
    const userId = button.dataset.userId;
    if (!confirm(`Are you sure you want to promote this student to a TA?`)) {
        return;
    }
    button.disabled = true;
    button.textContent = "Promoting...";
    try {
        const response = await apiFetch(`/api/admin/promote-to-ta/${userId}`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Failed to promote user.");
        }
        showStatusMessage("User promoted to TA successfully.", "success");
        loadUsers();
    } catch (error) {
        console.error("Promote user error:", error);
        showStatusMessage(error.message, "error");
        button.disabled = false;
        button.textContent = "Promote to TA";
    }
}

async function handleDeleteUser(e) {
    const userId = e.target.dataset.userId;
    if (!confirm(`Are you sure you want to delete user ${userId}? This action cannot be undone.`)) {
        return;
    }
    try {
        const response = await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Failed to delete user.");
        }
        showStatusMessage("User deleted successfully.", "success");
        loadUsers();
    } catch (error) {
        console.error("Delete user error:", error);
        showStatusMessage(error.message, "error");
    }
}

async function handleAddNewStudent(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Adding...";
    const formDataForApi = new FormData();
    formDataForApi.append("profile_picture", document.getElementById("student-photo").files[0]);
    formDataForApi.append("full_name", document.getElementById("student-name").value);
    formDataForApi.append("email", document.getElementById("student-email").value);
    formDataForApi.append("password", document.getElementById("student-password").value);
    formDataForApi.append("roll_number", document.getElementById("student-roll").value);
    formDataForApi.append("stream", document.getElementById("student-stream").value);
    const cgpa = document.getElementById("student-cgpa").value;
    if(cgpa) formDataForApi.append("cgpa", cgpa);
    try {
        const response = await apiFetch("/api/admin/students", {
            method: "POST",
            body: formDataForApi,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to add student.");
        showStatusMessage("Student added successfully!", "success");
        form.reset();
        loadUsers();
    } catch (error) {
        console.error("Add student error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Add Student";
    }
}

async function handleAddNewTeacher(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Adding...";
    const teacherData = {
        full_name: document.getElementById("teacher-name").value,
        email: document.getElementById("teacher-email").value,
        password: document.getElementById("teacher-password").value,
        employee_id: document.getElementById("teacher-id").value,
        department: document.getElementById("teacher-dept").value,
        specialization: document.getElementById("teacher-spec").value || null
    };
    try {
        const response = await apiFetch("/api/admin/teachers", {
            method: "POST",
            body: JSON.stringify(teacherData)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to add teacher.");
        showStatusMessage("Teacher added successfully!", "success");
        form.reset();
        loadUsers();
    } catch (error) {
        console.error("Add teacher error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Add Teacher";
    }
}

// --- Registration Management ---
async function handleStartRegistration(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Starting...";

    const localStartDate = document.getElementById("reg-start").value;
    const localEndDate = document.getElementById("reg-end").value;

    // [UPDATED] Send the correct data
    const registrationData = {
        academic_year: document.getElementById("reg-year").value,
        season: document.getElementById("reg-season").value,
        registration_start_date: new Date(localStartDate).toISOString(),
        registration_end_date: new Date(localEndDate).toISOString(),
        // We no longer send semester
    };
    
    try {
        const response = await apiFetch("/api/admin/registration/start", {
            method: "POST",
            body: JSON.stringify(registrationData)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to start registration.");
        showStatusMessage("Registration period started successfully!", "success");
        form.reset();
    } catch (error) {
        console.error("Start registration error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Start Registration";
    }
}

async function handleStopRegistration() {
    if (!confirm("Are you sure you want to stop all active registration periods?")) {
        return;
    }
    const button = document.getElementById("stop-registration-btn");
    button.disabled = true;
    button.textContent = "Stopping...";
     try {
        const response = await apiFetch("/api/admin/registration/stop", { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to stop registration.");
        showStatusMessage(data.message, "success");
    } catch (error) {
        console.error("Stop registration error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Stop All Active Periods";
    }
}

async function handleAdvanceSemester() {
    if (!confirm("ARE YOU SURE?\n\nThis will advance the semester for ALL students and cannot be undone.")) {
        return;
    }
    const button = document.getElementById("advance-semester-btn");
    button.disabled = true;
    button.textContent = "Advancing...";
     try {
        const response = await apiFetch("/api/admin/semester/advance", { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to advance semester.");
        showStatusMessage(data.message, "success");
    } catch (error) {
        console.error("Advance semester error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Advance All Students to Next Semester";
    }
}