
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
  document.getElementById("gpaHistogram");

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
const meanCtx =
  document.getElementById("meanChart");

const meanChart = new Chart(meanCtx, {

  type: "doughnut",

  data: {

    datasets: [{

      data: [
        semesterData["Semester 1"].mean,
        4 - semesterData["Semester 1"].mean
      ],

      backgroundColor: [
        "#b292d6",
        "#6f8bd8"
      ],

      borderWidth: 0

    }]
  },

  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "70%",
    plugins: {
      legend: { display: false }
    }
  }

});
const trendCtx =
  document.getElementById("semesterTrend");

new Chart(trendCtx, {

  type: "line",

  data: {

    labels: trendData.labels,

    datasets: [

      {
        label: "Your GPA",
        data: trendData.student,
        borderColor: "#168bd1",
        tension: 0.3
      },

      {
        label: "Department Average",
        data: trendData.department,
        borderColor: "#999",
        borderDash: [5, 5],
        tension: 0.3
      }

    ]
  }

});

semesterSelector.addEventListener("change", () => {
  const selected = semesterSelector.value;
  const sem = semesterData[selected];

  updateHistogram(selected);

  meanChart.data.datasets[0].data = [
    sem.mean,
    4 - sem.mean
  ];
  meanChart.update();

  document.getElementById("departmentMeanValue").textContent =
    sem.mean.toFixed(2);

  document.getElementById("benchmarkInsight").textContent =
    sem.insight;
});