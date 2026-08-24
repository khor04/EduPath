// ================================
// GPA Trend Chart (unchanged)
// ================================
const gpaCtx = document.getElementById("dashboardGpaTrend");

if (gpaCtx) {
  new Chart(gpaCtx, {
    type: "line",
    data: {
      labels: dashboardGpaLabels,
      datasets: [{
        label: "GPA",
        data: dashboardGpaValues,
        borderColor: "#7776B3",
        backgroundColor: "#7776B3",
        pointBackgroundColor: "#7776B3",
        pointRadius: 5,
        tension: 0.35
      }]
    },
    options: {
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          callbacks: {
            label: (context) => `GPA: ${context.raw}`
          }
        }
      },
      elements: {
        point: { radius: 5, hoverRadius: 8, hitRadius: 20 }
      },
      scales: {
        y: { beginAtZero: true, suggestedMax: 4.1 }
      }
    }
  });
}

// ================================
// Histogram utilities (same as benchmark.js)
// ================================
function getHistogramColors(userIndex) {
  return Array(8)
    .fill("#c7d6ef")
    .map((color, index) => (index === userIndex ? "#4c78c8" : color));
}

function getUserIndex(userGPA) {
  if (!userGPA || isNaN(userGPA)) return 0;
  return Math.max(0, Math.min(Math.floor((userGPA - 2.4) / 0.2), 7));
}

// ================================
// "You're here" plugin (same as benchmark.js)
// ================================
const youAreHerePlugin = {
  id: "youAreHerePlugin",
  afterDatasetsDraw(chart) {
    const userIndex = chart.data.userIndex;
    if (userIndex === undefined || userIndex === null) return;

    const meta = chart.getDatasetMeta(0);
    const bar = meta.data[userIndex];
    if (!bar) return;

    const { ctx } = chart;
    const x = bar.x;
    const y = bar.y - 10;

    ctx.save();
    ctx.font = "bold 12px sans-serif";
    ctx.fillStyle = "#4c78c8";
    ctx.textAlign = "center";
    ctx.fillText("You're here", x, y);

    ctx.beginPath();
    ctx.moveTo(x - 4, y + 4);
    ctx.lineTo(x + 4, y + 4);
    ctx.lineTo(x, y + 10);
    ctx.closePath();
    ctx.fillStyle = "#4c78c8";
    ctx.fill();
    ctx.restore();
  }
};

// ================================
// Motivation message (same pools as benchmark.js)
// ================================
const messagesAbove = [
  "Great work — keep up this momentum.",
  "Consistency like this pays off over time.",
  "You're building strong habits this semester."
];

const messagesBelow = [
  "Consistent effort across semesters can turn this around.",
  "Progress often isn't linear — stay focused on your own growth.",
  "Focus on progress rather than comparison."
];

function pickMessage(pool) {
  return pool[Math.floor(Math.random() * pool.length)];
}

function setMotivationMessage(performanceBand) {
  const el = document.getElementById("motivationMessage");
  if (!el) return;
  const isAbove = performanceBand === "above";
  el.textContent = isAbove ? pickMessage(messagesAbove) : pickMessage(messagesBelow);
  el.classList.remove("above", "below");
  el.classList.add(isAbove ? "above" : "below");
}

// ================================
// Histogram chart init
// ================================
const semesterSelector = document.getElementById("semesterSelector");
const histogramCtx = document.getElementById("dashboardHistogram");
let histogramChart = null;

if (histogramCtx) {
  histogramChart = new Chart(histogramCtx, {
    type: "bar",
    data: {
      labels: [
        "[2.4,2.6)", "[2.6,2.8)", "[2.8,3.0)", "[3.0,3.2)",
        "[3.2,3.4)", "[3.4,3.6)", "[3.6,3.8)", "[3.8,4.0]"
      ],
      datasets: [{ data: [], backgroundColor: [] }]
    },
    options: {
      responsive: true,
      layout: { padding: { top: 24 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => {
              const userIndex = histogramChart.data.userIndex;
              let text = `${context.label}: ${context.raw} students`;
              if (context.dataIndex === userIndex) text += " (You're here)";
              return text;
            }
          }
        }
      },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } }
      }
    },
    plugins: [youAreHerePlugin]
  });
}

// ================================
// Fetch real benchmark data from the same API used on benchmarking page
// ================================
async function loadDashboardBenchmark() {
  if (!semesterSelector || !histogramChart) return;

  try {
    const value = semesterSelector.value || "";
    const [session, semesterStr] = value.split("|");
    const semester = parseInt(semesterStr);

    if (!session || isNaN(semester)) return;

    const response = await fetch(
      `/api/benchmark-data?session=${session}&semester=${semester}`
    );
    const data = await response.json();

    if (data.error) {
      document.getElementById("benchmarkInsight").textContent =
        "Not enough peer data available for this semester yet.";
      document.getElementById("dashboardSampleSize").textContent =
        `Based on anonymized data (${data.sample_size ?? 0} student${data.sample_size === 1 ? "" : "s"} so far)`;

      const el = document.getElementById("motivationMessage");
      el.textContent = "";
      el.classList.remove("above", "below");

      histogramChart.data.userIndex = null;
      histogramChart.data.datasets[0].data = [];
      histogramChart.data.datasets[0].backgroundColor = getHistogramColors(-1);
      histogramChart.update();
      return;
    }

    document.getElementById("dashboardSampleSize").textContent =
      `Based on anonymized data from ${data.sample_size} students in your cohort (including you)`;

    document.getElementById("benchmarkInsight").textContent = data.insight ?? "-";
    setMotivationMessage(data.performance_band);

    const userIndex = getUserIndex(data.user_gpa);
    histogramChart.data.userIndex = userIndex;
    histogramChart.data.datasets[0].data = data.histogram || [];
    histogramChart.data.datasets[0].backgroundColor = getHistogramColors(userIndex);
    histogramChart.update();

  } catch (err) {
    console.error("loadDashboardBenchmark error:", err);
  }
}

if (semesterSelector) {
  semesterSelector.selectedIndex = 0;
  semesterSelector.addEventListener("change", loadDashboardBenchmark);
  loadDashboardBenchmark();
}