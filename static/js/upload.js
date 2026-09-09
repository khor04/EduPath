const pdfInput = document.getElementById("pdfUpload");
const dropZone = document.querySelector(".drop-zone");
const semesterPanel = document.querySelector(".semester-panel");

//handle file selection from button
pdfInput.addEventListener("change", function () {
    uploadPDF(this.files[0]);
});

//allow drag and drop file
dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropZone.classList.add("drag-active");
});

dropZone.addEventListener("dragleave", function () {
    dropZone.classList.remove("drag-active");
});

dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropZone.classList.remove("drag-active");

    const file = e.dataTransfer.files[0];
    uploadPDF(file);
});

document.getElementById("deleteBtn").addEventListener("click", function (e) {
    const hasTranscript = this.dataset.hasTranscript === "true";

    if (!hasTranscript) {
        e.stopPropagation();  // prevent modal from opening
        alert("No transcript data found to delete.");
        return;
    }

    // has transcript — let Bootstrap open the modal normally
    const modal = new bootstrap.Modal(
        document.getElementById("deleteTranscriptModal")
    );
    modal.show();
});

document.getElementById("confirmDeleteTranscriptBtn").addEventListener("click", function () {

    fetch("/delete-transcript-data", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken()
        }
    })
    .then(res => res.json())
    .then(data => {

        if (!data.success) {
            alert(data.message);
            return;
        }

        alert(data.message);

        window.location.reload();
    })
    .catch(err => {
        console.error(err);
        alert("Failed to delete transcript data.");
    });

});

//validate and send pdf file to backend
function uploadPDF(file) {
    if (!file) return;

    //check file type before sending to backend
    if (file.type !== "application/pdf") {
        alert("Only PDF files are supported.");
        return;
    }

    //store PDF file inside FormData for upload request
    const formData = new FormData();
    formData.append("pdf", file);


    fetch("/upload-transcript", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                alert(data.message);
                return;
            }
            //display extracted trnascript data in editable table
            renderExtractedData(data.semesters);
        })
        .catch(err => {
            alert("Error uploading transcript.");
            console.error(err);
        });
}

// Mirrors services/cgpa_services.py GRADE_POINTS — used only to
// derive a Grade Point when a manually added row leaves it blank,
// or to preview a semester's GPA before finalizing. The backend
// remains the source of truth when saving.
const GRADE_POINTS = {
    "A+": 4.00, "A": 4.00, "A-": 3.70,
    "B+": 3.30, "B": 3.00, "B-": 2.70,
    "C+": 2.30, "C": 2.00, "C-": 1.70,
    "D+": 1.30, "D": 1.00, "F": 0.00
};

function courseRowHtml(course) {
    const rowClass = course.needs_review ? ' class="needs-review"' : '';
    return `
        <tr${rowClass}>
            <td contenteditable="true">${escapeHtml(course.course_code)}</td>
            <td contenteditable="true">${escapeHtml(course.course_name)}</td>
            <td contenteditable="true">${escapeHtml(course.credits)}</td>
            <td contenteditable="true">${escapeHtml(course.grade)}</td>
            <td contenteditable="true">${escapeHtml(course.grade_point)}</td>
            <td class="row-actions"><button type="button" class="delete-row-btn" title="Remove this row">&times;</button></td>
        </tr>
    `;
}

// Falls back to credits * GRADE_POINTS[grade] when the typed grade
// point is missing/non-numeric, so an added row doesn't have to be
// hand-computed and the live GPA preview stays accurate for it.
function resolveGradePoint(grade, credits, typedValue) {
    const typed = (typedValue || "").trim();

    if (typed !== "" && !isNaN(Number(typed))) {
        return Number(typed);
    }

    const g = (grade || "").trim().toUpperCase();
    const c = Number(credits);

    if (g in GRADE_POINTS && !isNaN(c)) {
        return GRADE_POINTS[g] * c;
    }

    return NaN;
}

//recompute and display this semester's GPA from its current rows
function recalcSemesterGPA(detail) {
    let totalCredits = 0;
    let totalPoints = 0;

    detail.querySelectorAll("tbody tr").forEach(row => {
        const cells = row.querySelectorAll("td");
        const credits = Number(cells[2].innerText.trim());
        const grade = cells[3].innerText.trim();
        const gradePoint = resolveGradePoint(grade, credits, cells[4].innerText.trim());

        if (!isNaN(credits) && credits > 0 && !isNaN(gradePoint)) {
            totalCredits += credits;
            totalPoints += gradePoint;
        }
    });

    const gpa = totalCredits > 0 ? (totalPoints / totalCredits).toFixed(2) : "0.00";

    const summaryInfo = detail.querySelector(".summary-info");
    summaryInfo.innerHTML = summaryInfo.innerHTML.replace(/GPA:\s*[\d.]+/, `GPA: ${gpa}`);
}

//add/delete row buttons + live GPA recalculation on edit
document.getElementById("semesterPanel").addEventListener("click", function (e) {
    const deleteBtn = e.target.closest(".delete-row-btn");
    if (deleteBtn) {
        const detail = deleteBtn.closest("details");
        deleteBtn.closest("tr").remove();
        recalcSemesterGPA(detail);
        return;
    }

    const addBtn = e.target.closest(".add-row-btn");
    if (addBtn) {
        const detail = addBtn.closest("details");
        const tbody = detail.querySelector("tbody");
        tbody.insertAdjacentHTML("beforeend", courseRowHtml({
            course_code: "", course_name: "", credits: "", grade: "", grade_point: ""
        }));
    }
});

document.getElementById("semesterPanel").addEventListener("input", function (e) {
    const detail = e.target.closest("details");
    if (detail) recalcSemesterGPA(detail);
});

//display extracted data for verification
function renderExtractedData(semesters) {
    //show verification section only after transcript extraction
    document.getElementById("verificationSection").style.display = "block";

    const semesterPanel = document.getElementById("semesterPanel");
    //// Clear previous extracted result before showing new one
    semesterPanel.innerHTML = "";

    semesters.forEach((sem, index) => {
        let rows = "";

        //generate course rows that is editable
        sem.courses.forEach(course => {
            rows += courseRowHtml(course);
        });

        //generate semester section with GPA, CGPA and course table
        semesterPanel.innerHTML += `
    <details
        open
        data-semester-no="${sem.semester_no}"
        data-academic-session="${sem.academic_session}"
    >
        <summary>
            <strong>${sem.semester}</strong>
            <span class="summary-info">
                GPA: ${sem.gpa} | CGPA: ${sem.cgpa}
            </span>
        </summary>

        <table class="transcript-table">
            <thead>
                <tr>
                    <th>Course Code</th>
                    <th>Course Name</th>
                    <th>Credits</th>
                    <th>Grade</th>
                    <th>Grade Point</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
        <button type="button" class="add-row-btn">+ Add Course Row</button>
    </details>
`;
    });

    const hasIncompleteCourses = semesters.some(
        sem => sem.courses.some(course => course.needs_review)
    );

    if (hasIncompleteCourses) {
        alert(
            "Transcript extracted, but some course rows (highlighted in red) " +
            "could not be fully read. Please fill in the missing fields " +
            "before final submission."
        );
    } else {
        alert("Transcript extracted successfully. Please verify before final submission.");
    }
}

function toggleHistory(header) {
    const item = header.parentElement;
    item.classList.toggle("active");
}



//finalize verified data and save to database
document.getElementById("finalizeBtn").addEventListener("click", function () {
    const semesters = [];
    const errors = [];

    //select all details in semester panel
    document.querySelectorAll(".semester-panel details").forEach(detail => {
        const summaryText = detail.querySelector("strong").innerText;
        const semesterNo = detail.dataset.semesterNo;
        const academicSession = detail.dataset.academicSession;
        const summaryInfo = detail.querySelector(".summary-info").innerText;

        //\s* means with 0/multiple space;\d.+ mean one or more than number with decimal
        const gpaMatch = summaryInfo.match(/GPA:\s*([\d.]+)/);
        const cgpaMatch = summaryInfo.match(/CGPA:\s*([\d.]+)/);

        const courses = [];
        const seenCodes = new Set();

        //collect edited course data from table rows
        detail.querySelectorAll("tbody tr").forEach(row => {
            const cells = row.querySelectorAll("td");

            const course_code = cells[0].innerText.trim().toUpperCase();
            const course_name = cells[1].innerText.trim();
            const credits = cells[2].innerText.trim();
            const grade = cells[3].innerText.trim().toUpperCase();
            let grade_point = cells[4].innerText.trim();

            if (!course_code || !course_name || !credits || !grade) {
                errors.push(`${summaryText}: every course row needs a Course Code, Course Name, Credit Hour, and Grade (delete the row if it doesn't belong).`);
                return;
            }

            if (isNaN(Number(credits)) || Number(credits) <= 0) {
                errors.push(`${summaryText}: "${course_code}" has an invalid Credit Hour.`);
                return;
            }

            if (!(grade in GRADE_POINTS)) {
                errors.push(`${summaryText}: "${course_code}" has an unrecognized Grade "${grade}".`);
                return;
            }

            if (seenCodes.has(course_code)) {
                errors.push(`${summaryText}: duplicate course code "${course_code}".`);
                return;
            }
            seenCodes.add(course_code);

            // Grade Point isn't required from the user — derive it
            // from Grade x Credit Hour when left blank/invalid.
            if (grade_point === "" || isNaN(Number(grade_point))) {
                grade_point = (GRADE_POINTS[grade] * Number(credits)).toFixed(2);
            }

            courses.push({ course_code, course_name, credits, grade, grade_point });
        });

        const semesterCredits = courses.reduce((sum, c) => sum + Number(c.credits || 0), 0);

        //store one complete semester into the semesters list
        semesters.push({
            semester: summaryText,
            semester_no: Number(semesterNo),
            academic_session: academicSession,
            gpa: gpaMatch ? gpaMatch[1] : "",
            cgpa: cgpaMatch ? cgpaMatch[1] : "",
            //sum mean current total credit, c mean current course, calculate total credit hours for that sem
            credits: semesterCredits,
            courses: courses
        });
    });

    if (errors.length > 0) {
        alert(errors.join("\n"));
        return;
    }

    console.log(semesters);

    fetch("/save-transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ semesters })
    })
        .then(res => res.json())
        .then(data => {

            // ❗ HANDLE DUPLICATE FIRST
            if (data.status === "DUPLICATE") {
                alert("Duplicate transcript detected. No changes were saved.");
                return;
            }

            // ❗ HANDLE FAILURE
            if (!data.success) {
                alert(data.message);
                return;
            }

            let msg = "";

            if (data.saved.length > 0) {
                msg += "New semesters saved:\n" + data.saved.join(", ") + "\n";
            }

            if (data.updated.length > 0) {
                msg += "\nUpdated (appeal cases):\n" + data.updated.join(", ");
            }

            alert(msg || "Transcript processed successfully");
            location.reload();
        });
});


// function showWarning(missing) {
//     let text = "Missing semesters detected:\n";

//     missing.forEach(m => {
//         text += `Sem ${m.semester_no} ${m.session}\n`;
//     });

//     return confirm(text + "\nContinue?");
// }
