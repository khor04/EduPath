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



// User position label plugin for histogram
const dashboardUserPositionPlugin = {
  id: "dashboardUserPositionLabel",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);

    const userIndex = 6; // CGPA 3.78 belongs to [3.6,3.8)
    const bar = meta.data[userIndex];

    if (!bar) return;

    const labelWidth = 80;
    const labelHeight = 26;
    const labelX = bar.x - labelWidth / 2;
    const labelY = bar.y - 40;

    ctx.save();

    ctx.fillStyle = "#111";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    ctx.fillStyle = "#fff";
    ctx.font = "bold 9px Arial";
    ctx.textAlign = "center";
    ctx.fillText("YOUR POSITION", bar.x, labelY + 11);
    ctx.fillText(`CGPA ${dashboardLatestCGPA.toFixed(2)}`, bar.x, labelY + 22); 

    ctx.restore();
  }
};


// GPA Histogram
const histogramCtx = document.getElementById("dashboardHistogram");

new Chart(histogramCtx, {
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
  responsive: true,
  maintainAspectRatio: false,

  interaction: {
    mode: "index",
    intersect: false
  },

  layout: {
    padding: {
      top: 45
    }
  },

  plugins: {
    legend: { display: false },
    tooltip: {
      enabled: true,
      callbacks: {
        label: function(context) {
          return `Students: ${context.raw}`;
        }
      }
    }
  },

  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: "Number of Students"
      }
    },
    x: {
      title: {
        display: true,
        text: "CGPA"
      }
    }
  }
},
  plugins: [dashboardUserPositionPlugin]
});