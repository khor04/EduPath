document.getElementById("currentCGPA").innerText = currentCGPA.toFixed(2);
document.getElementById("currentCredits").innerText = currentCredits;

//latest gpa extraction
let latestGPA = 0;
latestGPA = gpaValues[gpaValues.length - 1];

//recent trend calculation (gpa change between last two semester)
let recentTrend = 0;
if (gpaValues.length >= 2) {
  recentTrend =
    gpaValues[gpaValues.length - 1] -
    gpaValues[gpaValues.length - 2];
}
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
      scales: {
        y: { beginAtZero: true, suggestedMax: 4.1 }
      }
    }
  });
});

let latestRequiredGPA = 0;
let latestStatus = "";

// Update slider values live
document.getElementById("targetCGPA").addEventListener("input", function () {
  document.getElementById("targetValue").innerText = parseFloat(this.value).toFixed(2);
});

document.getElementById("remainingCredits").addEventListener("input", function () {
  document.getElementById("creditValue").innerText = this.value;
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

// Main calculation
function calculatePrediction() {
  console.log(recentTrend);

  document.getElementById("predictionOutput").style.display = "block";
  document.getElementById("aiPlanCard").style.display = "block";
  const targetCGPA = parseFloat(document.getElementById("targetCGPA").value);
  const remainingCredits = parseInt(document.getElementById("remainingCredits").value);

  if (remainingCredits <= 0) {
    alert("Please enter remaining credits greater than 0.");
    document.getElementById("predictionOutput").style.display = "none";
    return;
  }

  const requiredGPA = calculateRequiredGPA(
    targetCGPA,
    currentCGPA,
    currentCredits,
    remainingCredits
  );

  const roundedRequiredGPA = Number(requiredGPA.toFixed(2));
  latestRequiredGPA = roundedRequiredGPA;
//assume future gpa = 4.00 across the remaining semester
  const bestCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, 4.0);
//assume future gpa = latest gpa
  const realisticCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, latestGPA);
//assume future GPA drops from latest gpa
  let worstGPA = latestGPA - Math.max(Math.abs(recentTrend), 0.20);
  worstGPA = Math.max(0.0, worstGPA);

  const worstCase = projectCGPA(currentCGPA, currentCredits, remainingCredits, worstGPA);

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

  // Prevent saving before calculation
  if (latestRequiredGPA === 0) {
    alert("Please calculate prediction before saving.");
    return;
  }

  if (latestRequiredGPA > 4.005) {
    alert("Target CGPA plan cannot be saved because the goal is not achievable.");
    return;
  }

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
      status: latestStatus
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

  document.getElementById("targetCGPA").value = 0;
  document.getElementById("remainingCredits").value = 0;

  document.getElementById("targetValue").innerText = "0.00";
  document.getElementById("creditValue").innerText = "0";

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

  updateCreditsBalance();
}

// Set default slider display values on page load
document.getElementById("targetValue").innerText = "0.00";
document.getElementById("creditValue").innerText = "0";
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

//render output
function renderAIResult(data) {

  if (!data || !data.semesters) {
    alert(data.message || "Invalid AI response");
    console.error(data);
    return;
  }

  document.getElementById("aiResultSection").style.display = "block";
  document.getElementById("trendResult").innerText = data.trend || "-";
  const feasibilityText = document.getElementById("feasibilityResult");
  const feasibilityPill = document.getElementById("feasibilityPill");
  feasibilityText.innerText = data.feasibility || "-";

  // Remove old classes
  feasibilityPill.classList.remove(
    "feasible-success",
    "feasible-warning",
    "feasible-danger",
    "feasible-neutral"
  );

  const trendPill = document.getElementById("trendPill");
  trendPill.classList.remove(
    "trend-improving",
    "trend-stable",
    "trend-declining"
  );

  switch ((data.trend || "").toLowerCase()) {
    case "improving":
      trendPill.classList.add("trend-improving");
      break;
    case "declining":
      trendPill.classList.add("trend-declining");
      break;
    default:
      trendPill.classList.add("trend-stable");
  }

  // Add new class
  switch ((data.feasibility || "").toLowerCase()) {

    case "achievable":
      feasibilityPill.classList.add("feasible-success");
      break;

    case "challenging":
      feasibilityPill.classList.add("feasible-warning");
      break;

    case "impossible":
      feasibilityPill.classList.add("feasible-danger");
      break;

    default:
      feasibilityPill.classList.add("feasible-neutral");
  }
  const tbody = document.getElementById("semesterPlanTable");
  tbody.innerHTML = "";


  if (!Array.isArray(data.semesters)) {
    console.error("Invalid semesters format", data);
    return;
  }
  let rows = "";

  data.semesters.forEach(sem => {
    rows += `
    <tr>
      <td>Semester ${sem.sem}</td>
      <td>${sem.credits}</td>
      <td>${sem.minimumGPARequired}</td>
    </tr>
  `;
  });

  tbody.innerHTML = rows;

  const adviceElement = document.getElementById("adviceText");
  console.log(data);
  console.log(data.advice);
  console.log(typeof data.advice);
  console.log("reached A");

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
