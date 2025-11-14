// frontend/js/student.js
// [FINAL: Corrected for 422 Error]

// Protect this page
protectPage();

// Global cache for semesters
let studentSemesters = [];

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("semester-filter").addEventListener("change", handleSemesterFilterChange);
    loadAllStudentData();
});

// --- Refactored Data Loading ---

async function loadCurrentCourses() {
    const container = document.getElementById("current-courses-container");
    try {
        showLoader(container);
        const currentCourses = await fetchCurrentCourses();
        renderCurrentCourses(currentCourses, container);
    } catch (error) {
        console.error("Failed to load current courses:", error);
        container.innerHTML = `<p style="color: #888;">No current courses found.</p>`;
    }
}

async function loadCurrentAttendance() {
    const container = document.getElementById("attendance-container");
    try {
        showLoader(container);
        const attendance = await fetchStudentAttendance();
        renderAttendance(attendance, container);
    } catch (error) {
        console.error("Failed to load attendance:", error);
        container.innerHTML = `<p style="color: #888;">Could not load attendance data.</p>`;
    }
}

async function loadCourseHistory(semester_id = null, gpaContainer, profileCGPA) {
    const gradesContainer = document.getElementById("grades-container");
    try {
        showLoader(gradesContainer);
        showLoader(gpaContainer);

        const grades = await fetchStudentGrades(semester_id);
        renderGrades(grades, gradesContainer);

        if (semester_id) {
            const gpaData = await fetchGpaData(semester_id);
            // Find the text for the selected option
            const semText = studentSemesters.find(s => s.semester_id === semester_id)?.season || "Semester";
            const semYear = studentSemesters.find(s => s.semester_id === semester_id)?.academic_year || "";
            renderGpaData(gpaData, gpaContainer, `${semText} ${semYear}`);
        } else {
            renderGpaData({ sgpa: null, cgpa_till_semester: profileCGPA }, gpaContainer);
        }
    } catch (error) {
        console.error("Failed to load grades:", error);
        gradesContainer.innerHTML = `<p style="color: #888;">Could not load grade data.</p>`;
        gpaContainer.innerHTML = `<p style="color: #888;">Could not load GPA data.</p>`;
    }
}

async function loadAvailableCourses() {
    const container = document.getElementById("recommendations-container");
    try {
        showLoader(container);
        const recommendations = await fetchCourseRecommendations();
        renderRecommendations(recommendations, container);
    } catch (error) {
        console.error("Failed to load recommendations:", error);
        container.innerHTML = `<p style="color: #888;">Course registration is not open or recommendations could not be loaded.</p>`;
    }
}

// --- Main loader ---
async function loadAllStudentData() {
    const profileContainer = document.getElementById("profile-widget-container");
    const gpaContainer = document.getElementById("gpa-display-container");

    // 1. Load Profile (Critical)
    let profileData;
    try {
        showLoader(profileContainer);
        profileData = await fetchStudentProfile();
        renderStudentProfile(profileData, profileContainer);
        document.getElementById("user-full-name").textContent = profileData.full_name;
    } catch (error) {
        console.error("Failed to load student profile:", error);
        profileContainer.innerHTML = `<p style="color: red;">Could not load profile. ${error.message}</p>`;
        return;
    }

    // 2. [NEW] Fetch the list of completed semesters
    try {
        studentSemesters = await fetchStudentSemesters();
        populateSemesterFilter(studentSemesters);
    } catch (error) {
        console.error("Failed to load semester filter:", error);
    }

    // 3. Load all other components in parallel
    Promise.all([
        loadCurrentCourses(),
        loadCurrentAttendance(),
        loadCourseHistory(null, gpaContainer, profileData.cgpa),
        loadAvailableCourses()
    ]);
}

// --- Event Handler ---
async function handleSemesterFilterChange(e) {
    const semester_id = e.target.value ? e.target.value : null; // This is now a UUID
    const gpaContainer = document.getElementById("gpa-display-container");

    const profile = await fetchStudentProfile();
    loadCourseHistory(semester_id, gpaContainer, profile.cgpa);
}


// --- Data Fetching Functions ---

async function fetchStudentProfile() {
    const response = await apiFetch("/api/student/profile");
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
}

async function fetchCourseRecommendations() {
    const response = await apiFetch("/api/student/courses/available");
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Could not fetch recommendations.");
    }
    return await response.json();
}

async function fetchStudentAttendance() {
    const response = await apiFetch("/api/student/attendance");
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
}

async function fetchStudentGrades(semester_id) {
    let endpoint = "/api/student/grades";
    if (semester_id) {
        endpoint += `?semester_id=${semester_id}`; // This is now a UUID
    }
    const response = await apiFetch(endpoint);
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Could not fetch grades.");
    }
    return await response.json();
}

async function fetchCurrentCourses() {
    const response = await apiFetch("/api/student/courses/current");
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
}

async function fetchGpaData(semester_id) {
    const response = await apiFetch(`/api/student/gpa?semester_id=${semester_id}`);
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
}

// [NEW] Fetches the list of completed semesters
async function fetchStudentSemesters() {
    const response = await apiFetch("/api/student/semesters/list");
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
}


// --- Data Rendering Functions ---

function renderStudentProfile(profile, container) {
    // ... (unchanged) ...
    const profilePic = profile.profile_picture_url || 'https://via.placeholder.com/80';
    const cgpa = profile.cgpa.toFixed(2);
    container.innerHTML = `... (same as before) ...`;
    container.innerHTML = `
        <div class="profile-widget">
            <img src="${profilePic}" alt="Profile Picture">
            <div class="profile-info">
                <h4>${profile.full_name}</h4>
                <p>${profile.roll_number} | ${profile.stream}</p>
                <p>${profile.email}</p>
            </div>
            <div class="profile-stats">
                <div class="stat">
                    <div class="stat-value" style="color: var(--primary-color);">${cgpa}</div>
                    <div class="stat-label">Overall CGPA</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${profile.current_semester}</div>
                    <div class="stat-label">Current Sem</div>
                </div>
            </div>
        </div>
    `;
}

function renderCurrentCourses(courses, container) {
    // ... (unchanged) ...
    if (!courses || courses.length === 0) {
        container.innerHTML = "<p>You are not enrolled in any courses this semester.</p>";
        return;
    }
    let listHtml = '<ul class="course-list">';
    for (const item of courses) {
        listHtml += `
            <li class="course-item">
                <div class="course-info">
                    <h5>${item.course_name} (${item.course_code})</h5>
                    <span style="font-size: 0.9rem; color: #6c757d;">
                        Prof: ${item.teacher.full_name}
                    </span>
                </div>
            </li>
        `;
    }
    listHtml += '</ul>';
    container.innerHTML = listHtml;
}

function renderAttendance(attendanceData, container) {
    // ... (unchanged) ...
    if (!attendanceData || attendanceData.length === 0) {
        container.innerHTML = "<p>No attendance data available for current courses.</p>";
        return;
    }
    let listHtml = '<ul class="course-list">';
    for (const item of attendanceData) {
        listHtml += `
            <li class="course-item">
                <div class="course-info">
                    <h5>${item.course_name}</h5>
                </div>
                <div class="course-score">
                    <div class="score ${item.attendance_percentage >= 75 ? 'high' : 'low'}">${item.attendance_percentage}%</div>
                </div>
            </li>
        `;
    }
    listHtml += '</ul>';
    container.innerHTML = listHtml;
}

function renderGrades(gradesData, container) {
    if (!gradesData || gradesData.length === 0) {
        container.innerHTML = "<p>No grades found for this selection.</p>";
        return;
    }
    let listHtml = '<ul class="course-list">';
    for (const item of gradesData) {
        listHtml += `
            <li class="course-item">
                <div class="course-info">
                    <h5>${item.course_name} (${item.course_code})</h5>
                    <span style="font-size: 0.9rem; color: #6c757d;">
                        ${item.academic_year} ${item.season} | Final Attendance: ${item.attendance_percentage}%
                    </span>
                </div>
                <div class="course-score">
                    <div class="stat-value" style="font-size: 1.5rem;">${item.grade}</div>
                </div>
            </li>
        `;
    }
    listHtml += '</ul>';
    container.innerHTML = listHtml;
}

// --- [THIS FUNCTION IS NOW FIXED] ---
// It populates the dropdown with UUIDs
function populateSemesterFilter(semesters) {
    const select = document.getElementById("semester-filter");

    // Clear old options (except the first "All")
    while (select.options.length > 1) {
        select.remove(1);
    }

    if (!semesters) return;

    // The 'semesters' variable is the result of our new API call
    semesters.forEach(sem => {
        const option = document.createElement("option");
        option.value = sem.semester_id; // <-- The UUID
        option.textContent = `${sem.academic_year} ${sem.season}`; // The text
        select.appendChild(option);
    });
}

function renderGpaData(gpaData, container, semesterText = null) {
    // ... (unchanged) ...
    let gpaHtml = "";
    if (semesterText) {
        gpaHtml = `
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div class="stat">
                    <div class="stat-value">${gpaData.sgpa.toFixed(2)}</div>
                    <div class="stat-label">${semesterText} SGPA</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${gpaData.cgpa_till_semester.toFixed(2)}</div>
                    <div class="stat-label">CGPA (Up to ${semesterText})</div>
                </div>
            </div>
        `;
    } else {
        gpaHtml = `
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div class="stat">
                    <div class="stat-value">${gpaData.cgpa_till_semester.toFixed(2)}</div>
                    <div class="stat-label">Overall CGPA</div>
                </div>
            </div>
        `;
    }
    container.innerHTML = gpaHtml;
}

function renderRecommendations(courses, container) {
    // ... (unchanged) ...
    if (!courses || courses.length === 0) {
        container.innerHTML = "<p>No new courses available for enrollment at this time.</p>";
        return;
    }
    let listHtml = '<ul class="course-list">';
    courses.sort((a, b) => (b.recommendation_score || 0) - (a.recommendation_score || 0));
    for (const course of courses) {
        const score = course.recommendation_score;
        let scoreClass = 'low';
        if (score >= 85) scoreClass = 'high';
        else if (score >= 70) scoreClass = 'medium';
        listHtml += `
            <li class="course-item">
                <div class="course-info">
                    <h5>${course.course_name}</h5>
                    <span>${course.course_code}</span>
                    <span>${course.domain || 'N/A'}</span>
                    <span>${course.credits} Credits</span>
                </div>
                <div class="course-score">
                    ${score !== null ? `
                        <div class="score ${scoreClass}">${score.toFixed(1)}%</div>
                        <div class="score-label">Match</div>
                    ` : `
                        <div class="score-label">N/A</div>
                    `}
                </div>
                <button class="btn btn-enroll" data-offering-id="${course.offering_id}">Enroll</button>
            </li>
        `;
    }
    listHtml += '</ul>';
    container.innerHTML = listHtml;
    container.querySelectorAll(".btn-enroll").forEach(button => {
        button.addEventListener("click", handleEnroll);
    });
}

async function handleEnroll(e) {
    // ... (unchanged) ...
    const button = e.target;
    const offeringId = button.dataset.offeringId;
    if (!confirm(`Are you sure you want to enroll in this course?`)) {
        return;
    }
    button.disabled = true;
    button.textContent = "Enrolling...";
    try {
        const response = await apiFetch("/api/student/enroll", {
            method: "POST",
            body: JSON.stringify({ offering_id: offeringId })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Enrollment failed.");
        }
        button.textContent = "Enrolled!";
        button.style.backgroundColor = "#28a745";
        loadCurrentCourses();
        loadCurrentAttendance();
        loadAvailableCourses();
    } catch (error) {
        console.error("Enrollment error:", error);
        alert(`Enrollment failed: ${error.message}`);
        button.disabled = false;
        button.textContent = "Enroll";
    }
}