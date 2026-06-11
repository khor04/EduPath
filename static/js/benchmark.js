// GPA Histogram
const histogramCtx = document.getElementById("gpaHistogram");


const userPositionPlugin = {
  id: "userPositionLabel",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);

    const userIndex = 6; // CGPA 3.78 belongs to [3.6,3.8)
    const bar = meta.data[userIndex];

    if (!bar) return;

    const labelWidth = 95;
    const labelHeight = 30;
    const labelX = bar.x - labelWidth / 2;
    const labelY = bar.y - 45;

    ctx.save();

    // black label box
    ctx.fillStyle = "#111";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    // white text
    ctx.fillStyle = "#fff";
    ctx.font = "bold 10px Arial";
    ctx.textAlign = "center";
    ctx.fillText("YOUR POSITION", bar.x, labelY + 12);
    ctx.fillText("CGPA 3.78", bar.x, labelY + 24);

    ctx.restore();
  }
};

new Chart(histogramCtx, {
  type: "bar",
  data: {
    labels: ["[2.4,2.6)", "[2.6,2.8)", "[2.8,3.0)", "[3.0,3.2)", "[3.2,3.4)", "[3.4,3.6)", "[3.6,3.8)", "[3.8,4.0]"],
    datasets: [{
      label: "Number of Students",
      data: [1, 1, 2, 1, 4, 2, 3, 5],
      backgroundColor: [
        "#c7d6ef",
        "#c7d6ef",
        "#c7d6ef",
        "#c7d6ef",
        "#c7d6ef",
        "#c7d6ef",
        "#4c78c8",
        "#c7d6ef"
      ]
    }]
  },
  options: {
    plugins: {
      legend: { display: false }
    },
    scales: {
      y: { beginAtZero: true },
      x: { title: { display: true, text: "CGPA" } }
    }
  },
  plugins: [userPositionPlugin]
});

// Semester Trend
const trendCtx = document.getElementById("semesterTrend");

new Chart(trendCtx, {
  type: "line",
  data: {
    labels: ["Semester 1", "Semester 2", "Semester 3"],
    datasets: [
      {
        label: "Your CGPA",
        data: [2.8, 3.15, 3.35],
        borderColor: "#168bd1",
        tension: 0.3
      },
      {
        label: "Peer Average",
        data: [2.75, 3.05, 3.12],
        borderColor: "#999",
        borderDash: [5, 5],
        tension: 0.3
      }
    ]
  },
  options: {
  layout: {
    padding: {
      top: 45
    }
  },
  plugins: {
    legend: { display: false }
  },
  scales: {
    y: { beginAtZero: true },
    x: { title: { display: true, text: "CGPA" } }
  }
}
});




// Mean doughnut
const meanCtx = document.getElementById("meanChart");

new Chart(meanCtx, {
  type: "doughnut",
  data: {
    datasets: [{
      data: [3.67, 0.33],
      backgroundColor: ["#b292d6", "#6f8bd8"],
      borderWidth: 0
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "70%",
    plugins: {
      legend: { display: false },
      tooltip: { enabled: false }
    }
  }
});