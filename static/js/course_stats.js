// Course Statistics card on the Peer Benchmarking page. The server decides
// what may be shown (consent, the minimum-students rule, first attempts --
// see services/course_stats_services.py) and which courses the student has
// taken; this file only fetches the list and filters it as the student types.
// Cells are built with textContent, never innerHTML, so course names can't
// inject markup.
(function () {
  const card = document.getElementById("courseStatsCard");
  if (!card) return;

  const search = document.getElementById("courseSearch");
  const scope = document.getElementById("courseScope");
  const statusFilter = document.getElementById("courseStatus");
  const message = document.getElementById("courseStatsMessage");
  const table = document.getElementById("courseStatsTable");
  const body = table.querySelector("tbody");

  const STATUS_LABELS = {
    taken: "Taken",
    in_progress: "In progress",
    not_taken: "Not taken yet",
  };

  let courses = [];
  let failed = false;

  function cell(text) {
    const td = document.createElement("td");
    td.textContent = String(text);
    return td;
  }

  function percent(value) {
    return `${Number(value).toFixed(1)}%`;
  }

  function statusCell(status) {
    const key = STATUS_LABELS[status] ? status : "not_taken";
    const td = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `course-status course-status--${key}`;
    badge.textContent = STATUS_LABELS[key];
    td.appendChild(badge);
    return td;
  }

  function row(course) {
    const tr = document.createElement("tr");

    const name = document.createElement("td");
    const code = document.createElement("strong");
    code.textContent = course.course_code;
    name.appendChild(code);
    if (course.course_name) {
      const sub = document.createElement("span");
      sub.className = "course-stats-name";
      sub.textContent = course.course_name;
      name.appendChild(sub);
    }
    tr.appendChild(name);

    tr.appendChild(cell(course.sample_size));
    tr.appendChild(cell(`${course.avg_grade} (${Number(course.avg_grade_point).toFixed(2)})`));
    tr.appendChild(cell(percent(course.fail_rate)));
    tr.appendChild(cell(percent(course.retake_rate)));
    tr.appendChild(statusCell(course.status));
    return tr;
  }

  function render() {
    body.replaceChildren();
    table.hidden = true;

    if (failed) {
      message.textContent = "Could not load course statistics. Please try again later.";
      return;
    }

    if (courses.length === 0) {
      message.textContent = scope.value === "faculty"
        ? "No course in your faculty has enough data from other students yet."
        : "No course in your programme has enough data from other students yet. Try students in my faculty.";
      return;
    }

    const query = search.value.trim().toLowerCase();
    const wanted = statusFilter.value;
    const shown = courses.filter((c) =>
      (wanted === "all" || (c.status || "not_taken") === wanted)
      && (!query
        || c.course_code.toLowerCase().includes(query)
        || (c.course_name || "").toLowerCase().includes(query))
    );

    if (shown.length === 0) {
      message.textContent = "No course matches your search or filter.";
      return;
    }

    message.textContent = `${shown.length} course${shown.length === 1 ? "" : "s"} shown`;
    shown.forEach((c) => body.appendChild(row(c)));
    table.hidden = false;
  }

  async function load() {
    message.textContent = "Loading…";
    table.hidden = true;

    try {
      const response = await fetch(
        `${card.dataset.url}?scope=${encodeURIComponent(scope.value)}`,
        { credentials: "same-origin", headers: { Accept: "application/json" } }
      );
      if (!response.ok) throw new Error(String(response.status));

      const data = await response.json();
      courses = data.courses || [];
      failed = false;
    } catch (err) {
      courses = [];
      failed = true;
    }

    render();
  }

  search.addEventListener("input", render);
  statusFilter.addEventListener("change", render);
  scope.addEventListener("change", load);
  load();
})();
