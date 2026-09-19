// Grade Tracker page. The server does all the grade maths (see
// services/grade_tracker_services.py); this file only renders the state
// it returns and sends the student's edits back. Every edit returns the
// fresh state, which replaces what's on screen.

let trackerState = initialState;

// Escapes for both text content and attribute values -- unlike
// escapeHtml() in csrf.js this also escapes quotes, needed because
// course/assessment names are typed by the student and land inside
// value="..." attributes.
function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// 73.2 -> "73.2", 75 -> "75", 76.84 -> "76.84"
function num(n) {
  return String(+Number(n).toFixed(2));
}

function showError(message) {
  document.getElementById("trackerError").textContent = message || "";
}

async function send(method, url, body) {
  showError("");

  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: body ? JSON.stringify(body) : undefined,
    });

    // 429 (rate limit) and 5xx come back as HTML, not JSON.
    const data = await response.json().catch(() => null);

    if (!data) {
      showError("Something went wrong. Please try again.");
      return false;
    }

    if (!data.success) {
      showError(data.message);
      // Redraw so a rejected inline edit snaps back to the saved value.
      render();
      return false;
    }

    trackerState = data.state;
    render();
    return true;
  } catch (e) {
    showError("Couldn't reach the server. Please check your connection.");
    return false;
  }
}

// ---------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------

function optionsHtml(grades, selected) {
  return grades
    .map(g => `<option value="${esc(g)}"${g === selected ? " selected" : ""}>${esc(g)}</option>`)
    .join("");
}

function renderOutlook(outlook) {
  const el = document.getElementById("trackerOutlook");

  if (!outlook) {
    el.innerHTML = "";
    return;
  }

  const current = outlook.current_cgpa !== null
    ? `<span class="outlook-was">now ${outlook.current_cgpa.toFixed(2)}</span>`
    : "";

  const excluded = outlook.courses_excluded > 0
    ? `<p class="tracker-note">${outlook.courses_excluded} course${outlook.courses_excluded > 1 ? "s" : ""} with no results yet ${outlook.courses_excluded > 1 ? "are" : "is"} not included.</p>`
    : "";

  el.innerHTML = `
    <div class="tracker-card outlook-card">
      <p class="card-label">SEMESTER OUTLOOK</p>
      <p class="outlook-lead">If every course finishes at its projected grade:</p>
      <div class="outlook-stats">
        <div><span class="stat-label">Semester GPA</span><strong>${outlook.semester_gpa.toFixed(2)}</strong></div>
        <div><span class="stat-label">Projected CGPA</span><strong>${outlook.projected_cgpa.toFixed(2)}</strong> ${current}</div>
      </div>
      ${excluded}
    </div>`;
}

function needHtml(course) {
  const need = course.need;
  if (!need) return "";

  const target = esc(course.target_grade);
  const remaining = num(course.remaining_weight);

  let where;
  if (course.pending_names.length === 1) {
    where = `in the ${esc(course.pending_names[0])} (the remaining ${remaining}%)`;
  } else {
    where = `across the remaining ${remaining}%`;
  }

  switch (need.status) {
    case "secured":
      return course.is_complete
        ? `<p class="need need-good">✅ You achieved <strong>${target}</strong>.</p>`
        : `<p class="need need-good">✅ <strong>${target}</strong> is already secured, whatever you score on the rest.</p>`;

    case "reachable":
      return `<p class="need">🎯 You need <strong>${num(need.percent)}%</strong> ${where} for <strong>${target}</strong>.</p>`;

    case "unreachable":
      return `<p class="need need-bad">⚠️ <strong>${target}</strong> is out of reach. The best you can get is <strong>${esc(need.best_grade)}</strong>, with full marks on the rest.</p>`;

    case "missed":
      return `<p class="need need-bad">Final grade <strong>${esc(need.final_grade)}</strong> — ${target} was not reached.</p>`;
  }
  return "";
}

function assessmentRowHtml(a) {
  const estimate = a.estimated
    ? `<span class="estimate-note" title="A letter grade is a range, so it is counted at the bottom of its band.">counted as ${num(a.counted_percent)}%</span>`
    : "";

  return `
    <tr data-assessment-id="${a.assessment_id}">
      <td><input class="cell-input" data-field="name" value="${esc(a.name)}" maxlength="100" aria-label="Assessment name"></td>
      <td class="num-col"><input class="cell-input weight-input" data-field="weight" type="number" min="0.5" max="100" step="any" value="${num(a.weight)}" aria-label="Weight in percent"> %</td>
      <td>
        <input class="cell-input" data-field="result" value="${esc(a.result || "")}" maxlength="20" placeholder="not received" aria-label="Result">
        ${estimate}
      </td>
      <td><button type="button" class="row-delete" data-action="delete-assessment" aria-label="Delete assessment">✕</button></td>
    </tr>`;
}

function courseHtml(course, grades) {
  const hasCurrent = course.current_performance !== null;

  const current = hasCurrent
    ? `${num(course.current_performance)}%`
    : "—";
  const completed = hasCurrent
    ? `${num(course.completed_weight)}% of the course marked`
    : "Enter a result to begin";

  const projectedLabel = course.is_complete ? "Final grade" : "Projected grade";
  const projectedNote = course.is_complete
    ? ""
    : (hasCurrent ? "if your current performance continues" : "");

  const estimateNote = course.has_estimate
    ? `<p class="tracker-note">Some results are letter grades. Each is counted at the bottom of its grade band, so the figures above are cautious.</p>`
    : "";

  const weightNote = Math.abs(course.declared_weight - 100) > 0.001
    ? `<p class="tracker-note warn">Your assessment weights add up to ${num(course.declared_weight)}%, not 100%. Add any missing assessment for a fuller picture.</p>`
    : "";

  const rows = course.assessments.map(assessmentRowHtml).join("");

  return `
    <div class="tracker-card course-card" data-course-id="${course.tracked_course_id}">
      <div class="course-head">
        <div>
          <h2>${esc(course.course_code)}${course.course_name ? " — " + esc(course.course_name) : ""}</h2>
          <p class="mini-text">${num(course.credit_hour)} credit hour${course.credit_hour === 1 ? "" : "s"}</p>
        </div>
        <div class="course-head-actions">
          <label class="target-label">Target
            <select class="target-select" data-action="change-target">${optionsHtml(grades, course.target_grade)}</select>
          </label>
          <button type="button" class="row-delete" data-action="delete-course" aria-label="Delete course">🗑</button>
        </div>
      </div>

      <div class="course-stats">
        <div class="stat">
          <span class="stat-label">Current performance</span>
          <strong>${current}</strong>
          <span class="stat-sub">${completed}</span>
        </div>
        <div class="stat">
          <span class="stat-label">${projectedLabel}</span>
          <strong>${course.projected_grade ? esc(course.projected_grade) : "—"}</strong>
          <span class="stat-sub">${projectedNote}</span>
        </div>
      </div>

      ${needHtml(course)}
      ${estimateNote}

      <table class="assessment-table">
        <thead><tr><th>Assessment</th><th>Weight</th><th>Result</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${course.assessments.length === 0 ? `<p class="tracker-note">Add your assessments below, e.g. Quiz 10%, Midterm 20%, Final Exam 50%.</p>` : ""}
      ${weightNote}

      <form class="add-assessment-form" data-action="add-assessment" autocomplete="off">
        <input type="text" name="name" maxlength="100" placeholder="Assessment (e.g. Midterm)" required aria-label="Assessment name">
        <input type="number" name="weight" min="0.5" max="100" step="any" placeholder="Weight %" required aria-label="Weight in percent">
        <input type="text" name="result" maxlength="20" placeholder="Result: 8/10, 75, 68%, A-" aria-label="Result (optional)">
        <button type="submit" class="tracker-btn secondary">+ Add</button>
      </form>
    </div>`;
}

function render() {
  const grades = trackerState.target_grades;
  const container = document.getElementById("trackerCourses");

  // Re-rendering replaces the inputs, so remember which one had focus
  // and put it back -- otherwise tabbing from one result to the next
  // (which is what saves the first) would lose the student's place.
  const active = document.activeElement;
  const focusKey = active && active.dataset && active.dataset.field
    ? {
        assessment: active.closest("tr")?.dataset.assessmentId,
        field: active.dataset.field,
      }
    : null;

  renderOutlook(trackerState.outlook);

  container.innerHTML = trackerState.courses.length
    ? trackerState.courses.map(c => courseHtml(c, grades)).join("")
    : `<p class="empty-message">No courses yet. Add your first course below to start tracking.</p>`;

  // Highlight the Grade Scale row(s) for the grades being aimed at.
  const targets = new Set(trackerState.courses.map(c => c.target_grade));
  document.querySelectorAll("#gradeScale tr[data-grade]").forEach(row => {
    row.classList.toggle("is-target", targets.has(row.dataset.grade));
  });

  if (focusKey && focusKey.assessment) {
    const el = container.querySelector(
      `tr[data-assessment-id="${focusKey.assessment}"] [data-field="${focusKey.field}"]`
    );
    if (el) el.focus();
  }
}

// ---------------------------------------------------------------
// Events (delegated: the cards are re-rendered after every edit)
// ---------------------------------------------------------------

const coursesEl = document.getElementById("trackerCourses");

function courseIdOf(el) {
  return el.closest(".course-card").dataset.courseId;
}

// Inline edits to an existing assessment save when the field changes.
coursesEl.addEventListener("change", (e) => {
  const el = e.target;

  if (el.dataset.action === "change-target") {
    send("PATCH", `/api/tracker/courses/${courseIdOf(el)}`, { target_grade: el.value });
    return;
  }

  if (el.dataset.field) {
    const id = el.closest("tr").dataset.assessmentId;
    send("PATCH", `/api/tracker/assessments/${id}`, { [el.dataset.field]: el.value });
  }
});

// Enter in an inline field commits it (change already fires on blur).
coursesEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.dataset.field) {
    e.target.blur();
  }
});

coursesEl.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;

  if (button.dataset.action === "delete-assessment") {
    const row = button.closest("tr");
    send("DELETE", `/api/tracker/assessments/${row.dataset.assessmentId}`);
  }

  if (button.dataset.action === "delete-course") {
    const card = button.closest(".course-card");
    const code = card.querySelector("h2").textContent;
    if (confirm(`Delete ${code} and all its results?`)) {
      send("DELETE", `/api/tracker/courses/${card.dataset.courseId}`);
    }
  }
});

coursesEl.addEventListener("submit", (e) => {
  const form = e.target.closest("[data-action='add-assessment']");
  if (!form) return;

  e.preventDefault();

  const body = {
    name: form.elements.name.value,
    weight: form.elements.weight.value,
  };
  // Leave the field out entirely when blank so it is stored as
  // "not received yet".
  if (form.elements.result.value.trim()) {
    body.result = form.elements.result.value;
  }

  send("POST", `/api/tracker/courses/${courseIdOf(form)}/assessments`, body);
});

document.getElementById("addCourseForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;

  const ok = await send("POST", "/api/tracker/courses", {
    course_code: form.elements.course_code.value,
    course_name: form.elements.course_name.value,
    credit_hour: form.elements.credit_hour.value,
    target_grade: form.elements.target_grade.value,
  });

  if (ok) {
    form.elements.course_code.value = "";
    form.elements.course_name.value = "";
  }
});

// csrf.js is loaded after this script in layout.html, so wait for
// the DOM before first use.
document.addEventListener("DOMContentLoaded", () => {
  const addTarget = document.getElementById("addCourseTarget");
  addTarget.innerHTML = optionsHtml(trackerState.target_grades, "A-");
  render();
});
