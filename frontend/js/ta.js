// frontend/js/ta.js
// [UPDATED to handle new CV API response]

// Protect this page
protectPage();

// Global cache for TA's data
let taOfferings = [];
let studentRosters = {}; // Cache for student rosters, { offeringId: [students] }

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

            if (link.dataset.page === 'fix-attendance') {
                document.getElementById("fix-course-select").dispatchEvent(new Event('change'));
            }
        });
    });

    // Form Listeners
    document.getElementById("mark-attendance-form").addEventListener("submit", handleMarkAttendance);
    document.getElementById("fix-attendance-form").addEventListener("submit", handleFixAttendance);
    document.getElementById("fix-course-select").addEventListener("change", loadStudentsForFixForm);

    // Initial data load
    loadTaOfferings();
});

function showStatusMessage(message, type) {
    const statusBox = document.getElementById("status-message");
    statusBox.textContent = message;
    statusBox.style.backgroundColor = type === 'success' ? '#d4edda' : '#f8d7da';
    statusBox.style.color = type === 'success' ? '#155724' : '#721c24';
    statusBox.classList.remove("hidden");
    setTimeout(() => statusBox.classList.add("hidden"), 5000);
}

// --- Course & Roster Loading ---

async function loadTaOfferings() {
    const container = document.getElementById("assigned-courses-container");
    const markSelect = document.getElementById("ta-course-select");
    const fixSelect = document.getElementById("fix-course-select");

    showLoader(container);
    markSelect.innerHTML = `<option value="">-- Loading... --</option>`;
    fixSelect.innerHTML = `<option value="">-- Loading... --</option>`;

    try {
        const response = await apiFetch("/api/ta/courses"); // This endpoint returns offerings
        if (!response.ok) throw new Error(await response.text());
        taOfferings = await response.json();

        renderTaOfferings(taOfferings, container);
        populateCourseSelects(taOfferings, [markSelect, fixSelect]);

    } catch (error) {
        console.error("Failed to load TA offerings:", error);
        container.innerHTML = `<p style="color: red;">Error loading courses.</p>`;
        markSelect.innerHTML = `<option value="">-- Error --</option>`;
        fixSelect.innerHTML = `<option value="">-- Error --</option>`;
    }
}

function renderTaOfferings(offerings, container) {
    if (offerings.length === 0) {
        container.innerHTML = "<p>You are not assigned to any course offerings.</p>";
        return;
    }

    let listHtml = `<ul class="course-list">`;
    offerings.forEach(offering => {
        const courseName = offering.course_name || 'N/A';
        const courseCode = offering.course_code || 'N/A';
        const season = offering.season || 'N/A';
        const academicYear = offering.academic_year || 'N/A';
        const semester_text = offering.logical_semester ? `(Sem ${offering.logical_semester})` : '(Universal Elective)';

        listHtml += `
            <li class="course-item">
                <div class="course-info">
                    <h5>${courseName}</h5>
                    <span>${courseCode}</span>
                    <span>${academicYear} | ${season} ${semester_text}</span>
                </div>
                <button class="btn btn-roster" data-offering-id="${offering.offering_id}" style="width: auto; padding: 0.5rem 1rem;">View Roster</button>
            </li>
        `;
    });
    listHtml += `</ul>`;
    container.innerHTML = listHtml;

    document.querySelectorAll(".btn-roster").forEach(button => {
        button.addEventListener("click", handleViewRoster);
    });
}

function populateCourseSelects(offerings, selects) {
    let optionsHtml = `<option value="">-- Select an offering --</option>`;
    if (offerings.length > 0) {
        offerings.forEach(offering => {
            optionsHtml += `<option value="${offering.offering_id}">${offering.course_name} (${offering.academic_year} ${offering.season})</option>`;
        });
    }
    selects.forEach(select => select.innerHTML = optionsHtml);
}

async function handleViewRoster(e) {
    const offeringId = e.target.dataset.offeringId;
    const rosterContainer = document.getElementById("roster-container");
    showLoader(rosterContainer);

    try {
        const students = await getStudentRoster(offeringId);

        if (students.length === 0) {
            rosterContainer.innerHTML = "<p>No students are enrolled in this offering.</p>";
            return;
        }

        let tableHtml = `<table style="width: 100%;"><thead><tr><th>Name</th><th>Roll</th></tr></thead><tbody>`;
        students.forEach(s => {
            tableHtml += `<tr><td>${s.full_name}</td><td>${s.roll_number}</td></tr>`;
        });
        tableHtml += `</tbody></table>`;
        rosterContainer.innerHTML = tableHtml;

    } catch (error) {
        console.error("Failed to load roster:", error);
        rosterContainer.innerHTML = `<p style="color: red;">Error loading roster.</p>`;
    }
}

async function getStudentRoster(offeringId) {
    if (studentRosters[offeringId]) {
        return studentRosters[offeringId];
    }

    const response = await apiFetch(`/api/ta/offerings/${offeringId}/students`);
    if (!response.ok) throw new Error(await response.text());
    const students = await response.json();

    studentRosters[offeringId] = students;
    return students;
}

// --- Attendance Actions ---

//
// --- [THIS IS THE UPDATED FUNCTION] ---
//
async function handleMarkAttendance(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    const offeringId = document.getElementById("ta-course-select").value;
    const photo = document.getElementById("class-photo").files[0];

    // Find the new elements
    const resultsContainer = document.getElementById("attendance-results-container");
    const metricsContainer = document.getElementById("attendance-metrics");
    const unknownFacesContainer = document.getElementById("unknown-faces-container");
    const unknownFacesGrid = document.getElementById("unknown-faces-grid");

    // Clear old results
    resultsContainer.style.display = "none";
    metricsContainer.innerHTML = "";
    unknownFacesGrid.innerHTML = "";

    if (!offeringId || !photo) {
        showStatusMessage("Please select an offering and a photo.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Processing...";

    const formData = new FormData();
    formData.append("class_photo", photo);

    const endpoint = `/api/ta/attendance/mark?offering_id=${offeringId}`;

    try {
        const response = await apiFetch(endpoint, {
            method: "POST",
            body: formData
        });

        const data = await response.json(); // This is the new, rich response
        if (!response.ok) throw new Error(data.detail || "Failed to mark attendance.");

        // 1. Show the simple success message
        showStatusMessage(`Success: ${data.present_count} present, ${data.absent_count} absent.`, "success");
        form.reset();

        // 2. Populate and display the new results container
        resultsContainer.style.display = "block";

        // 3. Populate metrics
        const metrics = data.metrics || {};
        metricsContainer.innerHTML = `
            <p><strong>Total Faces Detected:</strong> ${metrics.total_faces_detected || 'N/A'}</p>
            <p><strong>Recognized Students:</strong> ${metrics.recognized_faces_count || 'N/A'}</p>
            <p><strong>Recognition Coverage:</strong> ${metrics.coverage ? (metrics.coverage * 100).toFixed(1) : 'N/A'}%</p>
            <p><strong>Model Used:</strong> ${metrics.model_used || 'N/A'}</p>
        `;

        // 4. Populate unknown faces
        const unknownFaces = data.unknown_faces || [];
        if (unknownFaces.length > 0) {
            unknownFacesContainer.style.display = "block";
            let facesHtml = "";
            unknownFaces.forEach(base64Image => {
                facesHtml += `<img src="data:image/jpeg;base64,${base64Image}" style="width: 80px; height: 80px; border-radius: 4px; object-fit: cover;" alt="Unrecognized face">`;
            });
            unknownFacesGrid.innerHTML = facesHtml;
        } else {
            unknownFacesContainer.style.display = "none";
        }

    } catch (error) {
        console.error("Mark attendance error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Mark Attendance";
    }
}

async function loadStudentsForFixForm(e) {
    const offeringId = e.target.value;
    const studentSelect = document.getElementById("fix-student-select");

    if (!offeringId) {
        studentSelect.innerHTML = `<option value="">-- Select a course first --</option>`;
        return;
    }

    studentSelect.innerHTML = `<option value="">-- Loading students... --</option>`;

    try {
        const students = await getStudentRoster(offeringId);
        let optionsHtml = `<option value="">-- Select a student --</option>`;
        students.forEach(s => {
            optionsHtml += `<option value="${s.student_id}">${s.full_name} (${s.roll_number})</option>`;
        });
        studentSelect.innerHTML = optionsHtml;
    } catch (error) {
        studentSelect.innerHTML = `<option value="">-- Error loading students --</option>`;
    }
}

async function handleFixAttendance(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");

    const fixData = {
        offering_id: document.getElementById("fix-course-select").value,
        student_id: document.getElementById("fix-student-select").value,
        date: document.getElementById("fix-date").value,
        status: document.getElementById("fix-status").value
    };

    if (!fixData.offering_id || !fixData.student_id || !fixData.date) {
        showStatusMessage("Please fill out all fields.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Updating...";

    try {
        const response = await apiFetch("/api/ta/attendance/fix", {
            method: "PUT",
            body: JSON.stringify(fixData)
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to update record.");

        showStatusMessage(data.message, "success");
        form.reset();
        document.getElementById("fix-student-select").innerHTML = `<option value="">-- Select a course first --</option>`;

    } catch (error) {
        console.error("Fix attendance error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Update Record";
    }
}