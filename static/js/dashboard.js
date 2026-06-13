// GPA Trend Chart
const gpaCtx = document.getElementById("dashboardGpaTrend");

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
    interaction: {
      mode: "nearest",
      intersect: false
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        enabled: true,
        callbacks: {
          label: function(context) {
            return `GPA: ${context.raw}`;
          }
        }
      }
    },
    elements: {
      point: {
        radius: 5,
        hoverRadius: 8,
        hitRadius: 20
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        suggestedMax: 4.1
      }
    }
  }
});

const semesterData = {

  "Semester 1": {
    histogram: [1, 1, 2, 1, 4, 2, 3, 5],
    mean: 3.25,
    userGPA: 3.78,
    insight: "You performed above the department average in Semester 1."
  },

  "Semester 2": {
    histogram: [0, 2, 2, 3, 3, 4, 4, 2],
    mean: 3.40,
    userGPA: 3.92,
    insight: "You ranked among the stronger performers in Semester 2."
  },

  "Semester 3": {
    histogram: [1, 1, 1, 2, 4, 5, 3, 3],
    mean: 3.55,
    userGPA: 4.00,
    insight: "Your GPA was significantly above the department average."
  }
};

const trendData = {
  labels: ["Semester 1", "Semester 2", "Semester 3"],
  student: [3.78, 3.92, 4.00],
  department: [3.25, 3.40, 3.55]
};


const semesterSelector =
  document.getElementById("semesterSelector");

Object.keys(semesterData).forEach(sem => {

  const option = document.createElement("option");
  option.value = sem;
  option.textContent = sem;

  semesterSelector.appendChild(option);

});

function getHistogramColors(userIndex) {

  return Array(8)
    .fill("#c7d6ef")
    .map((color, index) =>
      index === userIndex
        ? "#4c78c8"
        : color
    );
}

function getUserIndex(userGPA) {
  return Math.min(Math.floor((userGPA - 2.4) / 0.2), 7);
}
const histogramCtx =
  document.getElementById("dashboardHistogram");

const histogramChart = new Chart(histogramCtx, {
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
      data: semesterData["Semester 1"].histogram,
      backgroundColor: getHistogramColors(
        getUserIndex(semesterData["Semester 1"].userGPA)
      )
    }]
  },
  options: {
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function (context) {
            const sem = semesterData[semesterSelector.value];
            const userIndex = getUserIndex(sem.userGPA);

            let text = `${context.label}: ${context.raw} students`;

            if (context.dataIndex === userIndex) {
              text += " (You're here)";
            }

            return text;
          }
        }
      }
    }
  }
});

function updateHistogram(semName) {
  const sem = semesterData[semName];
  const userIndex = getUserIndex(sem.userGPA);

  histogramChart.data.datasets[0].data = sem.histogram;

  histogramChart.data.datasets[0].backgroundColor =
    getHistogramColors(userIndex);

  histogramChart.update();
}

semesterSelector.addEventListener("change", () => {
  const selected = semesterSelector.value;
  const sem = semesterData[selected];

  updateHistogram(selected);

  document.getElementById("benchmarkInsight").textContent =
    sem.insight;
});