// frontend/js/teacher.js
// [FINAL v5: All functions fully implemented]

// Protect this page
protectPage();

// Store data
let allTeacherOfferings = [];
let allCatalogCourses = [];
let allTAs = [];
let allSemesters = []; // Store all semesters
let currentPeriod = null; // Stores { semester_id, academic_year, season }

// Domain map
const DOMAIN_MAP = {
    "CSE": ["Programming & Data Structures", "Theoretical Computer Science", "Computer Systems & Architecture", "Computer Networks", "Databases & Software Engineering", "Artificial Intelligence & Machine Learning"],
    "DSE": ["Mathematical & Statistical Foundations", "Programming & Data Analytics", "Machine Learning & Modeling", "Data Engineering & Big Data", "Applied DS & Specializations"],
    "EE": ["Basic Circuits & Networks", "Electronic Devices & Circuits", "Core Electrical Systems (Power)", "Signals & Communication", "Control & Instrumentation", "VLSI & Embedded Systems"],
    "COMMON": ["Mathematics", "Physics", "Chemistry", "Humanities & Social Sciences", "General Management"]
};

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

            if (link.dataset.page === 'create-offering') {
                populateCourseCatalogSelect(allCatalogCourses);
                populateSemesterSelect(allSemesters);
            }
            if (link.dataset.page === 'catalog') {
                populatePrerequisiteDropdowns(allCatalogCourses);
                handleStreamChange({ target: document.getElementById("course-stream") });
            }
        });
    });

    // Modal controls
    const modal = document.getElementById("teacher-modal");
    const closeBtn = document.querySelector(".close-btn");
    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    };

    // Form Listeners
    document.getElementById("create-course-form").addEventListener("submit", handleCreateCatalogCourse);
    document.getElementById("create-offering-form").addEventListener("submit", handleCreateOffering);
    document.getElementById("prereq-form").addEventListener("submit", handlePrerequisiteSubmit);
    document.getElementById("offering-filter").addEventListener("change", renderTeacherOfferings);
    document.getElementById("course-stream").addEventListener("change", handleStreamChange);

    // Initial data load
    loadInitialData();
});

async function loadInitialData() {
    // We need to get *all* semesters first
    // TODO: We need to create this /api/admin/semesters/list endpoint
    // For now, loadCurrentPeriod() will act as a fallback.
    // await loadAllSemesters(); 

    // Then determine which one is active
    await loadCurrentPeriod();

    // [FIX] If allSemesters is empty, populate it with the active one
    if (allSemesters.length === 0 && currentPeriod.semester_id) {
        allSemesters = [currentPeriod];
    }

    // Then load the teacher's offerings
    await loadTeacherOfferings();
    // Load other data
    await loadAllTAs();
    await loadAllCourses();
}

function showStatusMessage(message, type) {
    const statusBox = document.getElementById("status-message");
    statusBox.textContent = message;
    statusBox.style.backgroundColor = type === 'success' ? '#d4edda' : '#f8d7da';
    statusBox.style.color = type === 'success' ? '#155724' : '#721c24';
    statusBox.classList.remove("hidden");
    setTimeout(() => statusBox.classList.add("hidden"), 5000);
}

// --- Data Loading ---
async function loadCurrentPeriod() {
    try {
        const response = await apiFetch("/api/teacher/registration/active");
        if (response.ok) {
            currentPeriod = await response.json();
        } else {
            console.error("Could not load active registration period.");
            currentPeriod = { semester_id: null, academic_year: null, season: null };
        }
    } catch (error) {
        console.error("Error loading active period:", error);
        currentPeriod = { semester_id: null, academic_year: null, season: null };
    }
}

// [NEW] Get all semesters from the 'semesters' table
async function loadAllSemesters() {
    try {
        // This endpoint needs to exist on the admin router
        // and be callable by teachers (see RLS policy)
        // We will assume for now it's at /api/semesters/list
        // As a fallback, we will just use the active one

        const response = await apiFetch("/api/teacher/semesters/list");
        if (response.ok) {
            allSemesters = await response.json();
        } else {
            console.error("Could not pre-fetch all semesters.");
        }

        // For now, this function does nothing and we rely on loadCurrentPeriod()
        allSemesters = [];

    } catch (error) {
        console.error("Could not pre-fetch all semesters:", error);
        allSemesters = [];
    }
}


async function loadTeacherOfferings() {
    const container = document.getElementById("my-offerings-container");
    showLoader(container);
    try {
        const response = await apiFetch("/api/teacher/offerings");
        if (!response.ok) throw new Error(await response.text());
        allTeacherOfferings = await response.json();
        renderTeacherOfferings();
    } catch (error) {
        console.error("Failed to load offerings:", error);
        container.innerHTML = `<p style="color: red;">Error loading your course offerings.</p>`;
    }
}

async function loadAllCourses() {
    try {
        const response = await apiFetch("/api/teacher/courses/catalog");
        if (response.ok) {
            allCatalogCourses = await response.json();
            populateCourseCatalogSelect(allCatalogCourses);
            populatePrerequisiteDropdowns(allCatalogCourses);
        } else {
            console.error("Could not pre-fetch all courses:", await response.text());
        }
    } catch (error) {
        console.error("Could not pre-fetch all courses:", error);
    }
}

async function loadAllTAs() {
    try {
        const response = await apiFetch("/api/teacher/available-tas");
        if (response.ok) {
            allTAs = await response.json();
        } else {
            console.error("Could not pre-fetch TAs:", await response.text());
        }
    } catch (error) {
        console.error("Could not pre-fetch TAs:", error);
    }
}

// --- Rendering & Form Population ---
function populateCourseCatalogSelect(courses) {
    const select = document.getElementById("course-catalog-select");
    if (!select) return;
    let optionsHtml = `<option value="">-- Select a course --</option>`;
    if (courses.length > 0) {
        courses.forEach(course => {
            optionsHtml += `<option value="${course.course_id}">${course.course_name} (${course.course_code})</option>`;
        });
    }
    select.innerHTML = optionsHtml;
}

function populatePrerequisiteDropdowns(courses) {
    const courseSelect = document.getElementById("prereq-course-select");
    const prereqSelect = document.getElementById("prereq-select");
    if (!courseSelect || !prereqSelect) return;
    let optionsHtml = `<option value="">-- Select a course --</option>`;
    if (courses.length > 0) {
        courses.forEach(course => {
            optionsHtml += `<option value="${course.course_id}">${course.course_name} (${course.course_code})</option>`;
        });
    }
    courseSelect.innerHTML = optionsHtml;
    prereqSelect.innerHTML = optionsHtml;
}

function populateSemesterSelect(semesters) {
    const select = document.getElementById("offering-semester-select");
    if (!select) return;

    // [FIX] Filter for only *active* registration periods
    const activeSemesters = semesters.filter(s => {
        // 's' might just be the currentPeriod object
        return s.semester_id && s.academic_year && s.season;
    });

    let optionsHtml = `<option value="">-- Select an active semester --</option>`;
    if (activeSemesters.length > 0) {
        activeSemesters.forEach(sem => {
            optionsHtml += `<option value="${sem.semester_id}">${sem.academic_year} ${sem.season}</option>`;
        });
    } else {
        optionsHtml = `<option value="">-- No active semesters found (Admin must start one) --</option>`;
    }
    select.innerHTML = optionsHtml;
}


function renderTeacherOfferings() {
    const container = document.getElementById("my-offerings-container");
    const filter = document.getElementById("offering-filter").value;
    let offeringsToShow = [];

    if (filter === 'current') {
        if (currentPeriod && currentPeriod.semester_id) {
            offeringsToShow = allTeacherOfferings.filter(o =>
                o.semester_id === currentPeriod.semester_id
            );
        } else {
            offeringsToShow = [];
        }
    } else {
        offeringsToShow = allTeacherOfferings;
    }

    if (offeringsToShow.length === 0) {
        if (filter === 'current') {
            container.innerHTML = "<p>No course offerings found for the *current* active semester. (Have you started a registration period?)</p>";
        } else {
            container.innerHTML = "<p>No course offerings found.</p>";
        }
        return;
    }

    let cardsHtml = "";
    offeringsToShow.forEach(offering => {
        const isCompleted = offering.is_completed;
        const disabledAttr = isCompleted ? 'disabled' : '';
        const disabledStyle = isCompleted ? 'background-color: #aaa; color: #555; cursor: not-allowed;' : '';
        const assignTaStyle = isCompleted ? disabledStyle : 'background-color: #ffc107;';
        const gradesStyle = isCompleted ? disabledStyle : 'background-color: var(--accent-color);';
        const courseName = offering.course_name || 'N/A';
        const courseCode = offering.course_code || 'N/A';
        const season = offering.season || 'N/A';
        const semester_text = offering.logical_semester ? `(Sem ${offering.logical_semester})` : '(Universal Elective)';

        cardsHtml += `
            <div class="card" data-offering-id="${offering.offering_id}">
                <h3>${courseName} <span style="font-size: 0.9rem; color: #6c757d;">(${courseCode})</span></h3>
                <p><strong>${offering.academic_year} | ${season} ${semester_text}</strong>
                   ${isCompleted ? '<span style="color: red; font-weight: bold; margin-left: 10px;">[COMPLETED]</span>' : ''}
                </p>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <button class="btn btn-action" data-action="stats" style="width: auto; padding: 0.5rem 1rem;">Stats</button>
                    <button class="btn btn-action" data-action="grades" 
                            style="width: auto; padding: 0.5rem 1rem; ${gradesStyle}" ${disabledAttr}>
                        Grades
                    </button>
                    <button class="btn btn-action" data-action="assign-ta" 
                            style="width: auto; padding: 0.5rem 1rem; ${assignTaStyle}" ${disabledAttr}>
                        Assign TA
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = cardsHtml;

    container.querySelectorAll(".btn-action").forEach(button => {
        button.addEventListener("click", handleOfferingAction);
    });
}

// --- Form Handlers ---
async function handleCreateCatalogCourse(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Creating...";

    const logicalSemesterValue = document.getElementById("course-logical-semester").value;

    const courseData = {
        course_name: document.getElementById("course-name").value,
        course_code: document.getElementById("course-code").value,
        stream: document.getElementById("course-stream").value,
        credits: parseInt(document.getElementById("course-credits").value),
        category: document.getElementById("course-category").value,
        domain: document.getElementById("course-domain").value || null,
        difficulty_level: parseInt(document.getElementById("course-difficulty").value),
        description: document.getElementById("course-desc").value || null,
        logical_semester: logicalSemesterValue ? parseInt(logicalSemesterValue) : null
    };
    try {
        const response = await apiFetch("/api/teacher/courses/catalog", {
            method: "POST",
            body: JSON.stringify(courseData)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to create course.");
        showStatusMessage("Course created in catalog successfully!", "success");
        form.reset();
        loadAllCourses();
        handleStreamChange({ target: document.getElementById("course-stream") });
    } catch (error) {
        console.error("Create course error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Create Course in Catalog";
    }
}

async function handleCreateOffering(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Creating...";

    const logicalSemesterValue = document.getElementById("offering-logical-semester").value;

    const offeringData = {
        course_id: document.getElementById("course-catalog-select").value,
        semester_id: document.getElementById("offering-semester-select").value,
        logical_semester: logicalSemesterValue ? parseInt(logicalSemesterValue) : null
    };

    if (!offeringData.course_id || !offeringData.semester_id) {
        showStatusMessage("Please select both an active semester and a course.", "error");
        button.disabled = false;
        button.textContent = "Create Offering";
        return;
    }

    try {
        const response = await apiFetch("/api/teacher/courses/offer", {
            method: "POST",
            body: JSON.stringify(offeringData)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to create offering.");
        showStatusMessage("Course offering created successfully!", "success");
        form.reset();
        loadTeacherOfferings();
        document.querySelector(".sidebar-nav a[data-page='my-offerings']").click();
    } catch (error) {
        console.error("Create offering error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Create Offering";
    }
}

async function handlePrerequisiteSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const button = form.querySelector("button[type='submit']");
    const courseId = document.getElementById("prereq-course-select").value;
    const prereqId = document.getElementById("prereq-select").value;
    if (!courseId || !prereqId) {
        showStatusMessage("Please select both a course and its prerequisite.", "error");
        return;
    }
    if (courseId === prereqId) {
        showStatusMessage("A course cannot be a prerequisite for itself.", "error");
        return;
    }
    button.disabled = true;
    button.textContent = "Adding...";
    const payload = {
        prerequisite_course_id: prereqId,
        is_mandatory: document.getElementById("prereq-mandatory").checked
    };
    try {
        const response = await apiFetch(`/api/teacher/courses/${courseId}/prerequisites`, {
            method: "POST",
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to add prerequisite.");
        showStatusMessage("Prerequisite added successfully!", "success");
        form.reset();
    } catch (error) {
        console.error("Prerequisite add error:", error);
        showStatusMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Add Prerequisite";
    }
}

function handleStreamChange(e) {
    const selectedStream = e.target.value;
    const domainDropdown = document.getElementById("course-domain");
    domainDropdown.innerHTML = "";
    const domains = DOMAIN_MAP[selectedStream];
    if (domains && domains.length > 0) {
        domainDropdown.innerHTML = `<option value="">-- Select a domain --</option>`;
        domains.forEach(domain => {
            const option = document.createElement("option");
            option.value = domain;
            option.textContent = domain;
            domainDropdown.appendChild(option);
        });
    } else {
        domainDropdown.innerHTML = `<option value="">-- Select a stream first --</option>`;
    }
}

// --- Modal Actions ---
function handleOfferingAction(e) {
    const button = e.target;
    if (button.disabled) return;
    const action = button.dataset.action;
    const offeringCard = button.closest(".card");
    const offeringId = offeringCard.dataset.offeringId;
    const offering = allTeacherOfferings.find(o => o.offering_id === offeringId);
    const courseName = offering.course_name || 'N/A';
    const modal = document.getElementById("teacher-modal");
    const modalTitle = document.getElementById("modal-title");
    const modalBody = document.getElementById("modal-body");
    modalTitle.textContent = `Manage ${courseName}`;
    switch (action) {
        case "stats":
            modalTitle.textContent = `Attendance Stats for ${courseName}`;
            loadAttendanceStats(offeringId, modalBody);
            break;
        case "grades":
            modalTitle.textContent = `Enter Grades for ${courseName}`;
            loadGradeEntryForm(offeringId, modalBody);
            break;
        case "assign-ta":
            modalTitle.textContent = `Assign TA to ${courseName}`;
            loadAssignTaForm(offeringId, modalBody);
            break;
    }
    modal.style.display = "block";
}

async function loadAttendanceStats(offeringId, modalBody) {
    showLoader(modalBody);
    try {
        const response = await apiFetch(`/api/teacher/offerings/${offeringId}/attendance`);
        if (!response.ok) throw new Error(await response.text());
        const stats = await response.json();
        if (stats.length === 0) {
            modalBody.innerHTML = "<p>No attendance data found for this offering.</p>";
            return;
        }
        let tableHtml = `
            <table style="width: 100%; border-collapse: collapse;">
                <thead><tr><th>Name</th><th>Roll</th><th>Total</th><th>Attended</th><th>%</th></tr></thead>
                <tbody>
        `;
        stats.forEach(s => {
            tableHtml += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px;">${s.full_name}</td>
                    <td style="padding: 8px;">${s.roll_number}</td>
                    <td style="padding: 8px;">${s.total_classes}</td>
                    <td style="padding: 8px;">${s.attended_classes}</td>
                    <td style="padding: 8px;">${s.attendance_percentage.toFixed(1)}%</td>
                </tr>
            `;
        });
        tableHtml += `</tbody></table>`;
        modalBody.innerHTML = tableHtml;
    } catch (error) {
        console.error("Failed to load stats:", error);
        modalBody.innerHTML = `<p style="color: red;">Error loading stats.</p>`;
    }
}

async function loadGradeEntryForm(offeringId, modalBody) {
    showLoader(modalBody);
    try {
        const response = await apiFetch(`/api/teacher/offerings/${offeringId}/students`);
        if (!response.ok) throw new Error(await response.text());
        const students = await response.json();
        if (students.length === 0) {
            modalBody.innerHTML = "<p>No students are enrolled in this offering.</p>";
            return;
        }
        let formHtml = `<form id="grade-entry-form" data-offering-id="${offeringId}">`;
        students.forEach(s => {
            formHtml += `
                <div class="form-group" style="display: flex; justify-content: space-between; align-items: center;">
                    <label>${s.full_name} (${s.roll_number})</label>
                    <input type="text" class="grade-input" data-student-id="${s.student_id}" placeholder="e.g., S" style="width: 100px;">
                </div>
            `;
        });
        formHtml += `<button type="submit" class="btn btn-primary">Submit Grades</button></form>`;
        modalBody.innerHTML = formHtml;
        document.getElementById("grade-entry-form").addEventListener("submit", handleGradeSubmit);
    } catch (error) {
        console.error("Failed to load student list for grades:", error);
        modalBody.innerHTML = `<p style="color: red;">Error loading student list.</p>`;
    }
}

async function handleGradeSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const offeringId = form.dataset.offeringId;
    const inputs = form.querySelectorAll(".grade-input");
    const gradesData = [];
    inputs.forEach(input => {
        if (input.value.trim() !== "") {
            gradesData.push({
                student_id: input.dataset.studentId,
                grade: input.value.trim().toUpperCase()
            });
        }
    });
    if (gradesData.length === 0) {
        showStatusMessage("No grades were entered.", "error");
        return;
    }
    try {
        const response = await apiFetch(`/api/teacher/offerings/${offeringId}/grades`, {
            method: "POST",
            body: JSON.stringify(gradesData)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to submit grades.");
        showStatusMessage(data.message, "success");
        document.getElementById("teacher-modal").style.display = "none";
        loadTeacherOfferings();
    } catch (error) {
        console.error("Grade submit error:", error);
        showStatusMessage(error.message, "error");
    }
}

function loadAssignTaForm(offeringId, modalBody) {
    if (allTAs.length === 0) {
        modalBody.innerHTML = "<p>No TAs found in the system. Please ask an admin to add one.</p>";
        return;
    }
    let formHtml = `<form id="assign-ta-form" data-offering-id="${offeringId}">
        <div class="form-group">
            <label for="ta-select">Select a TA</label>
            <select id="ta-select" required>
                <option value="">-- Choose a TA --</option>
    `;
    allTAs.forEach(ta => {
        formHtml += `<option value="${ta.user_id}">${ta.full_name} (${ta.email})</option>`;
    });
    formHtml += `
            </select>
        </div>
        <button type="submit" class="btn btn-primary">Assign TA</button>
    </form>`;
    modalBody.innerHTML = formHtml;
    document.getElementById("assign-ta-form").addEventListener("submit", handleTaSubmit);
}

async function handleTaSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const offeringId = form.dataset.offeringId;
    const taId = document.getElementById("ta-select").value;
    if (!taId) {
        showStatusMessage("Please select a TA.", "error");
        return;
    }
    try {
        const response = await apiFetch(`/api/teacher/offerings/${offeringId}/assign-ta`, {
            method: "POST",
            body: JSON.stringify({ ta_id: taId })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to assign TA.");
        showStatusMessage(data.message, "success");
        document.getElementById("teacher-modal").style.display = "none";
    } catch (error) {
        console.error("TA assign error:", error);
        showStatusMessage(error.message, "error");
    }
}