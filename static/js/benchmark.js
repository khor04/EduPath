const semesterSelector = document.getElementById("semesterSelector");

// ================================
// Chart instances (global-safe)
// ================================
let histogramChart = null;
let meanChart = null;
let trendChart = null;

// ================================
// Utility functions
// ================================
function getHistogramColors(userIndex) {
  return Array(8)
    .fill("#c7d6ef")
    .map((color, index) =>
      index === userIndex ? "#4c78c8" : color
    );
}

// ================================
// INIT HISTOGRAM CHART
// ================================
// ================================
// "YOU'RE HERE" LABEL PLUGIN
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
    const y = bar.y - 10; // slightly above the bar top

    ctx.save();
    ctx.font = "bold 12px sans-serif";
    ctx.fillStyle = "#4c78c8";
    ctx.textAlign = "center";
    ctx.fillText("You're here", x, y);

    // small arrow pointing down at the bar
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

function initHistogram() {
  const ctx = document.getElementById("gpaHistogram");

  histogramChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: [
        "[2.4,2.6)",
        "[2.6,2.8)",
        "[2.8,3.0)",
        "[3.0,3.2)",
        "[3.2,3.4)",
        "[3.4,3.6)",
        "[3.6,3.8)",
        "[3.8,4.0]"
      ],
      datasets: [{
        data: [],
        backgroundColor: []
      }]
    },
    options: {
      responsive: true,
      layout: {
        padding: {
          top: 24 // extra headroom so the label doesn't clip at the top of the canvas
        }
      },
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0 }
        }
      }
    },
    plugins: [youAreHerePlugin]
  });
}

// ================================
// INIT MEAN CHART
// ================================
function initMeanChart() {
  const ctx = document.getElementById("meanChart");

  meanChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [0, 4]
      }]
    },
    options: {
      cutout: "70%",
      plugins: {
        legend: {
          display: false
        }
      }
    }
  });
}

// ================================
// LOAD BENCHMARK DATA
// ================================

// ================================
// Motivation message
// ================================
const messagesAbove = [
  "Great work — keep up this momentum.",
  "Consistency like this pays off over time.",
  "You're building strong habits this semester."
];

const messagesEqual = [
  "You're right on pace with your cohort — solid, steady footing.",
  "You're tracking exactly with the department average.",
  "Right in step with your peers this semester."
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

  let pool;
  let styleClass;

  if (performanceBand === "above") {
    pool = messagesAbove;
    styleClass = "above";
  } else if (performanceBand === "equal") {
    pool = messagesEqual;
    styleClass = "equal";
  } else {
    // "slightly_below" and "below" share the same tone
    pool = messagesBelow;
    styleClass = "below";
  }

  el.textContent = pickMessage(pool);
  el.classList.remove("above", "equal", "below");
  el.classList.add(styleClass);
}

async function loadBenchmark() {
  try {
    const value = semesterSelector.value || "";
    const parts = value.split("|");

    const session = (parts[0] || "").trim();
    const semester = parseInt(parts[1]);

    if (!session || isNaN(semester)) {
      console.error("Invalid semester selection");
      return;
    }

    const response = await fetch(
      `/api/benchmark-data?session=${session}&semester=${semester}`
    );

    const data = await response.json();

    if (data.error) {
      document.getElementById("benchmarkInsight").textContent =
        "Not enough peer data available for this semester yet.";
      document.getElementById("sampleSize").textContent = data.sample_size ?? 0;
      document.getElementById("departmentMeanValue").textContent = "-";

      const el = document.getElementById("motivationMessage");
      el.textContent = "";
      el.classList.remove("above", "below");

      histogramChart.data.userIndex = null;
      histogramChart.data.datasets[0].data = [];
      histogramChart.data.datasets[0].backgroundColor = getHistogramColors(-1);
      histogramChart.update();

      meanChart.data.datasets[0].data = [0, 4];
      meanChart.update();

      return;
    }

    setMotivationMessage(data.performance_band);

    // ================================
    // Update UI text
    // ================================
    document.getElementById("sampleSize").textContent = data.sample_size ?? 0;

    document.getElementById("departmentMeanValue").textContent =
      (data.mean ?? 0).toFixed(2);

    document.getElementById("benchmarkInsight").textContent =
      data.insight ?? "-";


    // ================================
    // Histogram update
    // ================================
    const userIndex = data.user_bin_index ?? 0;
    histogramChart.data.userIndex = userIndex;
    histogramChart.data.datasets[0].data = data.histogram || [];
    histogramChart.data.datasets[0].backgroundColor =
      getHistogramColors(userIndex);

    histogramChart.update();

    // ================================
    // Mean chart update
    // ================================
    meanChart.data.datasets[0].data = [
      data.mean || 0,
      Math.max(0, 4 - (data.mean || 0))
    ];

    meanChart.update();

  } catch (err) {
    console.error("loadBenchmark error:", err);
  }
}

// ================================
// LOAD TREND CHART
// ================================
async function loadTrend() {

  try {
    const response = await fetch("/api/benchmark-trend");
    const data = await response.json();

    if (!data.labels || !data.student) {
      console.error("Invalid trend data");
      return;
    }

    document.getElementById("trendInsight").textContent =
      data.trend_insight ?? "-";

    // destroy old chart (IMPORTANT FIX)
    if (trendChart) {
      trendChart.destroy();
    }

    trendChart = new Chart(
      document.getElementById("semesterTrend"),
      {
        type: "line",
        data: {
          labels: data.labels,
          datasets: [
            {
              label: "Your GPA",
              data: data.student,
              borderColor: "#168bd1",
              tension: 0.3
            },
            {
              label: "Cohort Average",
              data: data.cohort,
              borderColor: "#999",
              borderDash: [5, 5],
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true
            }
          },
          layout: {
            padding: { top: 20 }
          },
          scales: {
            y: { beginAtZero: true, max: 4.5 }
          }
        }
      }
    );

  } catch (err) {
    console.error("loadTrend error:", err);
  }
}

// ================================
// EVENT LISTENER
// ================================
window.addEventListener("DOMContentLoaded", () => {
  if (semesterSelector) {
    semesterSelector.selectedIndex = 0;
    semesterSelector.addEventListener("change", loadBenchmark); // <-- add this
  }

  initHistogram();
  initMeanChart();

  loadBenchmark();
  loadTrend();
});