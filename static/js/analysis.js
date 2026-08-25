document.getElementById("currentCGPA").innerText = currentCGPA;
document.getElementById("currentCredits").innerText = currentCredits;

//latest gpa extraction
let latestGPA = 0;
latestGPA = gpaValues[gpaValues.length - 1];

// GPA Trend Chart
document.addEventListener("DOMContentLoaded", function () {

  const canvas = document.getElementById("gpaTrendChart");

  if (!canvas) {
    console.error("❌ GPA chart canvas NOT found in DOM");
    return;
  }

  const ctx = canvas.getContext("2d");

  if (!ctx) {
    console.error("❌ Cannot get 2D context");
    return;
  }

  if (!gpaLabels?.length || !gpaValues?.length) {
    console.warn("⚠️ No data for chart");
    return;
  }

  new Chart(ctx, {
    type: "line",
    data: {
      labels: gpaLabels,
      datasets: [{
        label: "GPA",
        data: gpaValues,
        pointBackgroundColor: "#7776B3",
        borderColor: "#7776B3",
        tension: 0.35
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (context) {
              return `GPA: ${context.raw}`;
            }
          }
        }
      },
      elements: {
        point: { radius: 5, hoverRadius: 8 }
      },
      layout: {
        padding: { top: 20 }
      },
      scales: {
        y: { beginAtZero: true, max: 4.5 }
      }
    }
  });
});

let latestRequiredGPA = 0;
let latestStatus = "";
let hasCalculated = false;

// Keep each slider and its paired number input in sync, in both
// directions, so a student can either drag or type an exact value
// (a slider alone can't reliably hit precise values like 3.67).
const targetCGPASlider = document.getElementById("targetCGPA");
const targetCGPANumber = document.getElementById("targetCGPANumber");
const remainingCreditsSlider = document.getElementById("remainingCredits");
const remainingCreditsNumber = document.getElementById("remainingCreditsNumber");

targetCGPASlider.addEventListener("input", function () {
  targetCGPANumber.value = parseFloat(this.value).toFixed(2);
});

targetCGPANumber.addEventListener("input", function () {
  let value = parseFloat(this.value);
  if (isNaN(value)) return;
  value = Math.min(4.00, Math.max(0.00, value));
  targetCGPASlider.value = value;
});

remainingCreditsSlider.addEventListener("input", function () {
  remainingCreditsNumber.value = this.value;
  updateCreditsBalance();
});

remainingCreditsNumber.addEventListener("input", function () {
  let value = parseInt(this.value);
  if (isNaN(value)) return;
  value = Math.min(128, Math.max(0, value));
  remainingCreditsSlider.value = value;
  updateCreditsBalance();
});

// Projection formula
function projectCGPA(currentCGPA, currentCredits, remainingCredits, assumedGPA) {
  const totalCredits = currentCredits + remainingCredits;
  const projected =
    ((currentCGPA * currentCredits) + (assumedGPA * remainingCredits)) / totalCredits;

  return projected.toFixed(2);
}

// Required GPA formula
function calculateRequiredGPA(targetCGPA, currentCGPA, currentCredits, remainingCredits) {
  const totalCredits = currentCredits + remainingCredits;

  const requiredGPA =
    ((targetCGPA * totalCredits) - (currentCGPA * currentCredits)) / remainingCredits;

  return requiredGPA;
}

// ==========================================================
// Worst-case decline estimate
//
// Uses the student's FULL semester-to-semester GPA history —
// not just the latest transition — so one anomalous semester
// doesn't single-handedly dominate the estimate:
//   - Volatility = population standard deviation of GPA changes,
//     bounded to [0.20, 0.50].
//   - Trend = average GPA change, nudging the decline down for
//     an improving trend (some "protection") or up for a
//     declining one, capped at ±0.15 either way.
// With fewer than 3 semesters there isn't enough history to
// compute a meaningful trend/volatility, so this falls back to
// simpler, still-bounded heuristics.
// ==========================================================
function computeWorstCaseDecline(gpaHistory) {
  const n = gpaHistory.length;

  // 0-1 semesters: no deltas at all — use the flat safety floor.
  if (n < 2) {
    return 0.20;
  }

  const deltas = [];
  for (let i = 1; i < n; i++) {
    deltas.push(gpaHistory[i] - gpaHistory[i - 1]);
  }

  // Exactly 2 semesters: a single delta isn't enough to separate
  // "trend" from "volatility" — treat its magnitude as the
  // decline signal directly, still bounded to [0.20, 0.50].
  if (deltas.length === 1) {
    return Math.min(Math.max(Math.abs(deltas[0]), 0.20), 0.50);
  }

  // 3+ semesters: combine historical volatility and overall trend.
  const meanDelta = deltas.reduce((sum, d) => sum + d, 0) / deltas.length;

  const variance =
    deltas.reduce((sum, d) => sum + Math.pow(d - meanDelta, 2), 0) / deltas.length;
  const stdDev = Math.sqrt(variance);

  const baseDecline = Math.min(Math.max(stdDev, 0.20), 0.50);
  const trendAdjustment = Math.min(Math.abs(meanDelta) * 0.5, 0.15);

  if (meanDelta > 0) {
    // Improving trend gives some protection — reduces the decline.
    return Math.max(baseDecline - trendAdjustment, 0.20);
  } else if (meanDelta < 0) {
    // Declining trend makes the scenario more conservative.
    return baseDecline + trendAdjustment;
  }

  return baseDecline;
}

function setPredictionError(message) {
  document.getElementById("predictionError").innerText = message || "";
}

// Main calculation
function calculatePrediction() {

  const targetCGPA = parseFloat(document.getElementById("targetCGPA").value);
  const remainingCredits = parseInt(document.getElementById("remainingCredits").value);

  if (targetCGPA <= 0) {
    setPredictionError("Please set a target CGPA greater than 0.");
    document.getElementById("predictionOutput").style.display = "none";
    return;
  }

  if (remainingCredits <= 0) {
    setPredictionError("Please enter remaining credits greater than 0.");
    document.getElementById("predictionOutput").style.display = "none";
    return;
  }

  setPredictionError("");
  document.getElementById("predictionOutput").style.display = "block";
  document.getElementById("aiPlanCard").style.display = "block";

  const requiredGPA = calculateRequiredGPA(
    targetCGPA,
    currentCGPA,
    currentCredits,
    remainingCredits
  );

  const roundedRequiredGPA = Number(requiredGPA.toFixed(2));
  latestRequiredGPA = roundedRequiredGPA;
  hasCalculated = true;

  //assume future gpa = 4.00 across the remaining semester
  const bestCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, 4.0);

  // Realistic/Worst case both need a GPA history (latestGPA) to
  // work from. A student with no transcript uploaded yet has none
  // (gpaValues is empty, so latestGPA is undefined) — show that
  // plainly instead of letting it silently compute to NaN.
  const hasGpaHistory = gpaValues && gpaValues.length > 0;

  let realisticCase = "No transcript data found";
  let worstCase = "No transcript data found";

  if (hasGpaHistory) {
    //assume future gpa = latest gpa
    realisticCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, latestGPA);

    // Estimated worst-case GPA, based on the student's full
    // history (volatility + trend), not just the last semester.
    const decline = computeWorstCaseDecline(gpaValues);
    const worstGPA = Math.max(0.0, Math.min(4.0, latestGPA - decline));

    worstCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, worstGPA);
  }

  document.getElementById("bestCase").innerText = bestCase;
  document.getElementById("realisticCase").innerText = realisticCase;
  document.getElementById("worstCase").innerText = worstCase;

  const resultStatus = document.getElementById("resultStatus");
  const resultMessage = document.getElementById("resultMessage");
  const bestPossibleText = document.getElementById("bestPossibleText");
  const resultBox = document.getElementById("resultBox");

  if (roundedRequiredGPA > 4.005) {
    latestStatus = "Not Achievable";
    resultStatus.innerText = "NOT ACHIEVABLE!";
    resultStatus.style.color = "red";

    resultMessage.innerHTML =
      `Required GPA of <b>${roundedRequiredGPA.toFixed(2)}</b> exceeds maximum possible GPA (4.00).`;

    bestPossibleText.innerHTML =
      `Best possible CGPA you may achieve is <b>${bestCase}</b>, assuming 4.00 for all remaining ${remainingCredits} credits.`;

    resultBox.style.background = "#fff8bd";

  } else if (roundedRequiredGPA < 0) {
    latestStatus = "Already Achievable";
    resultStatus.innerText = "ALREADY ACHIEVABLE!";
    resultStatus.style.color = "green";

    resultMessage.innerHTML =
      `Your current CGPA is already above the target CGPA.`;

    bestPossibleText.innerHTML =
      `Maintaining your current performance gives a projected CGPA of <b>${realisticCase}</b>.`;

    resultBox.style.background = "#d9ffd4";

  } else {
    latestStatus = "Achievable";
    resultStatus.innerText = "ACHIEVABLE";
    resultStatus.style.color = "green";

    resultMessage.innerHTML =
      `Required average GPA: <b>${roundedRequiredGPA.toFixed(2)}</b> for the remaining ${remainingCredits} credits.`;
    bestPossibleText.innerHTML =
      `Best possible CGPA you may achieve is <b>${bestCase}</b>.`;

    resultBox.style.background = "#d9ffd4";
  }
}

document.addEventListener("input", function (e) {

  if (e.target.classList.contains("semester-credit")) {
    updateCreditsBalance();
  }

});

// SAVE TARGET CGPA PLAN
document.getElementById("saveTargetBtn").addEventListener("click", function () {

  // Prevent saving before calculation. Uses an explicit flag
  // rather than checking latestRequiredGPA === 0, since a
  // required GPA of exactly 0.00 is itself a valid, reachable
  // calculated result (e.g. current CGPA already meets the
  // target) — that shouldn't be mistaken for "hasn't calculated".
  if (!hasCalculated) {
    setPredictionError("Please calculate prediction before saving.");
    return;
  }

  if (latestRequiredGPA > 4.005) {
    setPredictionError("Target CGPA plan cannot be saved because the goal is not achievable.");
    return;
  }

  setPredictionError("");

  const targetCGPA = parseFloat(
    document.getElementById("targetCGPA").value
  );

  const remainingCredits = parseInt(
    document.getElementById("remainingCredits").value
  );

  fetch("/save-target-cgpa", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      target_cgpa: targetCGPA,
      required_gpa: latestRequiredGPA,
      remaining_credits: remainingCredits,
    })
  })
    .then(res => res.json())
    .then(data => {
      alert(data.message);
    })
    .catch(err => {
      console.error(err);
      alert("Failed to save target CGPA plan.");
    });

});

// Reset
function resetPrediction() {
  document.getElementById("predictionOutput").style.display = "none";
  setPredictionError("");

  document.getElementById("targetCGPA").value = 0;
  document.getElementById("remainingCredits").value = 0;

  document.getElementById("targetCGPANumber").value = "0.00";
  document.getElementById("remainingCreditsNumber").value = "0";

  document.getElementById("bestCase").innerText = "-";
  document.getElementById("realisticCase").innerText = "-";
  document.getElementById("worstCase").innerText = "-";

  document.getElementById("resultStatus").innerText = "-";

  document.getElementById("resultMessage").innerText =
    "Adjust the sliders and click Calculate to generate prediction.";

  document.getElementById("bestPossibleText").innerText = "";

  document.getElementById("resultBox").style.background = "#f5f5f5";

  // Reset temporary prediction variables
  latestRequiredGPA = 0;
  latestStatus = "";
  hasCalculated = false;

  updateCreditsBalance();
}

// Set default slider display values on page load
document.getElementById("targetCGPANumber").value = "0.00";
document.getElementById("remainingCreditsNumber").value = "0";
document.getElementById("predictionOutput").style.display = "none";

function updateCreditsBalance() {

  const sliderCredits = parseInt(
    document.getElementById("remainingCredits").value
  ) || 0;

  let allocatedCredits = 0;

  document.querySelectorAll(".semester-credit").forEach(input => {
    allocatedCredits += parseInt(input.value) || 0;
  });

  const balance = sliderCredits - allocatedCredits;

  const balanceElement =
    document.getElementById("creditsBalance");

  balanceElement.innerText =
    `Allocated: ${allocatedCredits}/${sliderCredits}`;

  if (balance < 0) {
    balanceElement.style.color = "red";
  }
  else if (balance > 0) {
    balanceElement.style.color = "orange";
  }
  else {
    balanceElement.style.color = "green";
  }
}

//gemini
// Track how many semesters already completed
const completedSems = semesterHistory.length; // already available from Flask

// Add Semester button
document.getElementById("addSemesterBtn").addEventListener("click", function () {

  const row = document.createElement("div");
  row.classList.add("semester-input-row");

  row.innerHTML = `
  <label class="sem-label"></label>
  <input type="number" class="semester-credit" min="1" value="17">
  <button type="button"
    onclick="this.parentElement.remove();
             updateSemesterLabels();
             updateCreditsBalance();">
    ✕
  </button>
`;

  document.getElementById("semesterInputs").appendChild(row);

  updateSemesterLabels();
  updateCreditsBalance();
});

document.addEventListener("DOMContentLoaded", function () {
  updateSemesterLabels();
  updateCreditsBalance();
});

function updateSemesterLabels() {
  const labels = document.querySelectorAll(".sem-label");

  const base = completedSems; // from Flask

  labels.forEach((label, index) => {
    label.innerText = `Semester ${base + index + 1}`;
  });
}

// generateAIPlan with correct sem numbering
async function generateAIPlan() {
  if (latestRequiredGPA <= 0) {
    alert("Please calculate prediction first.");
    return;
  }

  const sliderCredits =
    parseInt(document.getElementById("remainingCredits").value) || 0;

  let allocatedCredits = 0;

  document.querySelectorAll(".semester-credit").forEach(input => {
    allocatedCredits += parseInt(input.value) || 0;
  });

  if (allocatedCredits !== sliderCredits) {

    alert(
      `Semester credits (${allocatedCredits}) must equal Remaining Credits (${sliderCredits}).`
    );

    return;
  }

  const remainingSemesters = [];

  document.querySelectorAll(".semester-credit").forEach((input, index) => {
    remainingSemesters.push({
      sem: completedSems + index + 1,  // ← correct offset
      credits: parseInt(input.value) || 0
    });
  });

  // Validate all credits filled
  const hasEmpty = remainingSemesters.some(s => s.credits <= 0);
  if (hasEmpty) {
    alert("Please fill in credits for all semesters.");
    return;
  }

  // Show loading state
  document.getElementById("aiResultSection").style.display = "none";
  const btn = document.querySelector(".ai-button-row button");
  btn.innerText = "Generating...";
  btn.disabled = true;
  //sending data to AI Planner
  try {
    const response = await fetch("/generate-ai-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        currentCGPA: currentCGPA,
        currentCredits: currentCredits,
        targetCGPA: parseFloat(document.getElementById("targetCGPA").value),
        requiredGPA: latestRequiredGPA,
        history: semesterHistory,
        remainingSemesters: remainingSemesters,
        latestGPA: latestGPA
      })
    });

    const result = await response.json();
    renderAIResult(result);

  } catch (err) {
    alert("Failed to generate AI plan. Please try again.");
    console.error(err);

  } finally {
    btn.innerText = "Generate AI Plan";
    btn.disabled = false;
  }
}


// ==========================
// Meaning Maps
// ==========================
const trendMeanings = {
  "Improving": "GPA consistently rising across semesters.",
  "Slightly Improving": "GPA showing small but steady upward movement.",
  "Stable": "GPA remaining consistent with no clear direction.",
  "Volatile": "GPA fluctuating significantly between semesters.",
  "Slightly Declining": "GPA showing small but steady downward movement.",
  "Declining": "GPA consistently dropping across semesters.",
};

const feasibilityMeanings = {
  "Achievable": "Required GPA is close to your current performance.",
  "Challenging": "Moderate improvement is needed to reach your target CGPA.",
  "Very Challenging": "Significant improvement is required in remaining semesters.",
  "Impossible": "Required GPA exceeds the maximum possible GPA (4.00)"
};

// ==========================
// Helper Functions
// ==========================
function getTrendMeaning(trend) {
  return trendMeanings[trend] || "";
}

function getFeasibilityMeaning(feasibility) {
  return feasibilityMeanings[feasibility] || "";
}

// ==========================
// Main Render Function
// ==========================
function renderAIResult(data) {
document.getElementById("aiResultSection").style.display = "block";
  // Safety check
  if (!data || !Array.isArray(data.semesters)) {
    alert(data?.message || "Invalid AI response");
    console.error(data);
    return;
  }

  // ==========================
  // Trend + Feasibility Text
  // ==========================
  document.getElementById("trendResult").textContent = data.trend || "—";
  document.getElementById("trendMeaning").textContent = getTrendMeaning(data.trend);

  document.getElementById("feasibilityResult").textContent = data.feasibility || "—";
  document.getElementById("feasibilityMeaning").textContent = getFeasibilityMeaning(data.feasibility);


  document.getElementById("trendInfoIcon")
  .addEventListener("click", () => {

    document.getElementById("feasibilityGuide")
      .classList.add("hidden");

    document.getElementById("trendGuide")
      .classList.toggle("hidden");
});

document.getElementById("feasibilityInfoIcon")
  .addEventListener("click", () => {

    document.getElementById("trendGuide")
      .classList.add("hidden");

    document.getElementById("feasibilityGuide")
      .classList.toggle("hidden");
});

  // ==========================
  // Optional Tooltip (hover info)
  // ==========================
  document.getElementById("trendPill").title =
    getTrendMeaning(data.trend);

  document.getElementById("feasibilityPill").title =
    getFeasibilityMeaning(data.feasibility);

  // ==========================
  // Update trend styling
  // ==========================
  const trendPill = document.getElementById("trendPill");

  trendPill.classList.remove(
    "trend-improving",
    "trend-slightly-improving",
    "trend-stable",
    "trend-volatile",
    "trend-slightly-declining",
    "trend-declining"
  );

  switch ((data.trend || "").toLowerCase()) {
    case "improving":
      trendPill.classList.add("trend-improving");
      break;

    case "slightly improving":
      trendPill.classList.add("trend-slightly-improving");
      break;

    case "stable":
      trendPill.classList.add("trend-stable");
      break;

    case "volatile":
      trendPill.classList.add("trend-volatile");
      break;

    case "slightly declining":
      trendPill.classList.add("trend-slightly-declining");
      break;

    case "declining":
      trendPill.classList.add("trend-declining");
      break;

    default:
      trendPill.classList.add("trend-stable");
  }

  // ==========================
  // Update feasibility styling
  // ==========================
  const feasibilityPill = document.getElementById("feasibilityPill");

  feasibilityPill.classList.remove(
    "feasible-success",
    "feasible-warning",
    "feasible-danger",
    "feasible-neutral"
  );

  switch ((data.feasibility || "").toLowerCase()) {

    case "achievable":
      feasibilityPill.classList.add("feasible-success");
      break;

    case "challenging":
      feasibilityPill.classList.add("feasible-warning");
      break;

    case "very challenging":
      feasibilityPill.classList.add("feasible-danger");
      break;

    case "impossible":
      feasibilityPill.classList.add("feasible-danger");
      break;

    default:
      feasibilityPill.classList.add("feasible-neutral");
  }

  // ==========================
  // Semester Plan Table
  // ==========================
  const tbody = document.getElementById("semesterPlanTable");
  tbody.innerHTML = "";

  tbody.innerHTML = data.semesters.map(sem => `
    <tr>
      <td>Semester ${sem.sem}</td>
      <td>${sem.credits}</td>
      <td>${sem.minimumGPARequired}</td>
    </tr>
  `).join("");


  const adviceElement = document.getElementById("adviceText");

  console.log("data =", data);
  console.log("data.advice =", data.advice);
  console.log("type =", typeof data.advice);
  let advice = data.advice;
  if (Array.isArray(data.advice)) {
    console.log("reached b");
    adviceElement.innerHTML = advice.join("<br><br>");
    console.log("reached c");
  }
  else if (typeof advice === "string") {
    const points = advice
      .split("•")
      .map(p => p.trim())
      .filter(p => p.length > 0);

    adviceElement.innerHTML = points
      .map(p => "• " + p)
      .join("<br><br>");
    console.log("reached d");
  } else {
    adviceElement.textContent = "No advice available";
  }

}

// ==========================================================
// Per-Course CGPA Simulator
// ==========================================================

const GRADE_OPTIONS = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"];

let userCourses = [];
let simRowCounter = 0;

async function loadUserCourses() {
  const retakeBtn = document.getElementById("addRetakeBtn");
  retakeBtn.disabled = true;

  try {
    const response = await fetch("/api/my-courses");
    userCourses = await response.json();
  } catch (err) {
    console.error("Failed to load courses for simulator:", err);
    userCourses = [];
  }

  retakeBtn.disabled = userCourses.length === 0;
}

function buildGradeSelect() {
  const options = GRADE_OPTIONS
    .map(g => `<option value="${g}">${g}</option>`)
    .join("");
  return `<select class="sim-grade-select">${options}</select>`;
}

function updateCourseSimVisibility() {
  const hasRows = document.getElementById("courseSimBody").children.length > 0;

  document.getElementById("courseSimTable").style.display = hasRows ? "table" : "none";
  document.getElementById("courseSimEmptyMsg").style.display = hasRows ? "none" : "block";

  if (!hasRows) {
    document.getElementById("courseSimResult").style.display = "none";
  }
}

function addRetakeRow() {
  if (!userCourses.length) {
    document.getElementById("courseSimError").innerText =
      "You don't have any completed courses to retake yet.";
    return;
  }

  document.getElementById("courseSimError").innerText = "";

  const row = document.createElement("tr");
  row.id = `sim-row-${simRowCounter++}`;
  row.dataset.type = "retake";

  const courseOptions = userCourses
    .map(c =>
      `<option value="${c.course_id}" data-credits="${c.credit_hour}">` +
      `${c.course_code} - ${c.course_name} (current: ${c.grade})</option>`
    )
    .join("");

  row.innerHTML = `
    <td><select class="sim-course-select">${courseOptions}</select></td>
    <td class="sim-credits-display">${userCourses[0].credit_hour}</td>
    <td>${buildGradeSelect()}</td>
    <td><button type="button" class="sim-remove-btn">✕</button></td>
  `;

  document.getElementById("courseSimBody").appendChild(row);
  updateCourseSimVisibility();
  recomputeSimulation();
}

function addFutureRow() {
  const row = document.createElement("tr");
  row.id = `sim-row-${simRowCounter++}`;
  row.dataset.type = "future";

  row.innerHTML = `
    <td><input type="text" class="sim-course-label" placeholder="Course name (optional)"></td>
    <td><input type="number" class="sim-credits-input" min="1" step="1" value="3"></td>
    <td>${buildGradeSelect()}</td>
    <td><button type="button" class="sim-remove-btn">✕</button></td>
  `;

  document.getElementById("courseSimBody").appendChild(row);
  updateCourseSimVisibility();
  recomputeSimulation();
}

function collectSimEntries() {
  const entries = [];
  const rows = document.getElementById("courseSimBody").children;

  for (const row of rows) {
    const grade = row.querySelector(".sim-grade-select").value;

    if (row.dataset.type === "retake") {
      const courseSelect = row.querySelector(".sim-course-select");

      entries.push({
        type: "retake",
        course_id: parseInt(courseSelect.value),
        grade: grade
      });

    } else {
      const credits = parseFloat(
        row.querySelector(".sim-credits-input").value
      ) || 0;

      entries.push({
        type: "future",
        credits: credits,
        grade: grade
      });
    }
  }

  return entries;
}

async function recomputeSimulation() {
  const entries = collectSimEntries();

  if (entries.length === 0) {
    document.getElementById("courseSimResult").style.display = "none";
    return;
  }

  try {
    const response = await fetch("/api/simulate-cgpa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries })
    });

    const data = await response.json();

    if (!data.success) {
      document.getElementById("courseSimError").innerText =
        data.message || "Unable to simulate.";
      document.getElementById("courseSimResult").style.display = "none";
      return;
    }

    document.getElementById("courseSimError").innerText = "";
    document.getElementById("courseSimResult").style.display = "block";
    document.getElementById("courseSimCurrentCGPA").innerText =
      data.current_cgpa.toFixed(2);
    document.getElementById("courseSimProjectedCGPA").innerText =
      data.projected_cgpa.toFixed(2);

    const change = data.change;
    const changeEl = document.getElementById("courseSimChange");
    const sign = change > 0 ? "+" : "";

    changeEl.innerText = `${sign}${change.toFixed(2)}`;
    changeEl.style.color =
      change > 0 ? "#1c8a4c" : (change < 0 ? "#c0392b" : "#444");

  } catch (err) {
    console.error("simulate-cgpa error:", err);
    document.getElementById("courseSimError").innerText =
      "Failed to simulate CGPA. Please try again.";
  }
}

// Event delegation on the table body, since rows are added
// dynamically — one listener handles grade/course changes and
// row removal for every row, present or future.
document.getElementById("courseSimBody").addEventListener("change", function (e) {

  if (e.target.classList.contains("sim-course-select")) {
    const row = e.target.closest("tr");
    const selectedOption = e.target.selectedOptions[0];
    row.querySelector(".sim-credits-display").innerText =
      selectedOption ? selectedOption.dataset.credits : "-";
  }

  recomputeSimulation();
});

document.getElementById("courseSimBody").addEventListener("input", function (e) {
  if (e.target.classList.contains("sim-credits-input")) {
    recomputeSimulation();
  }
});

document.getElementById("courseSimBody").addEventListener("click", function (e) {
  if (e.target.classList.contains("sim-remove-btn")) {
    e.target.closest("tr").remove();
    updateCourseSimVisibility();
    recomputeSimulation();
  }
});

document.getElementById("addRetakeBtn").addEventListener("click", addRetakeRow);
document.getElementById("addFutureBtn").addEventListener("click", addFutureRow);

document.getElementById("clearAllSimBtn").addEventListener("click", function () {
  document.getElementById("courseSimBody").innerHTML = "";
  document.getElementById("courseSimError").innerText = "";
  updateCourseSimVisibility();
});

loadUserCourses();
