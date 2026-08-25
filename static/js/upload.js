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
            "Content-Type": "application/json"
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
            const rowClass = course.needs_review ? ' class="needs-review"' : '';
            rows += `
                <tr${rowClass}>
                    <td contenteditable="true">${course.course_code}</td>
                    <td contenteditable="true">${course.course_name}</td>
                    <td contenteditable="true">${course.credits}</td>
                    <td contenteditable="true">${course.grade}</td>
                    <td contenteditable="true">${course.grade_point}</td>
                </tr>
            `;
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
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
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

        //collect edited course data from table rows
        detail.querySelectorAll("tbody tr").forEach(row => {
            const cells = row.querySelectorAll("td");

            courses.push({
                course_code: cells[0].innerText.trim(),
                course_name: cells[1].innerText.trim(),
                credits: cells[2].innerText.trim(),
                grade: cells[3].innerText.trim(),
                grade_point: cells[4].innerText.trim()
            });
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
    console.log(semesters);

    fetch("/save-transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
