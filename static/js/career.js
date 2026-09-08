// Radar Chart
const radarCtx = document.getElementById("skillRadar");

const radarChart = new Chart(radarCtx, {
  type: "radar",
  data: {
    labels: careerRadarLabels,
    datasets: [{
      label: "Skill Score",
      data: careerRadarValues,
      backgroundColor: "rgba(22, 139, 209, 0.18)",
      borderColor: "#168bd1",
      pointBackgroundColor: "#168bd1",
      pointRadius: 5,
    }]
  },
  options: {
  layout: {
    padding: {
      top: 30,
      bottom: 30,
      left: 50,
      right: 50
    }
  },
  interaction: {
    mode: "nearest",
    intersect: false
  },
  elements: {
    point: {
      radius: 6,
      hoverRadius: 9,
      hitRadius: 10
    }
  },
  plugins: {
    legend: { display: false }
  },
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: {
        stepSize: 25
      },
      pointLabels: {
        font: {
          size: 11
        }
      }
    }
  }
}
});

function showSkillDetail(skill) {

  // hide all detail cards
  document.querySelectorAll(".strength-detail").forEach(el => {
    el.classList.add("hidden");
  });

  // remove active from all buttons
  document.querySelectorAll(".strength-buttons button").forEach(btn => {
    btn.classList.remove("active");
  });

  // show selected detail
  const skillId = skill.replace(/\s/g, "");
  const target = document.getElementById(skillId);

  if (target) {
    target.classList.remove("hidden");
  }

  // 🔥 highlight clicked button
  document.querySelectorAll(".strength-buttons button").forEach(btn => {
    if (btn.innerText === skill) {
      btn.classList.add("active");
    }
  });
}

// Area for Improvement dropdown
document.querySelectorAll(".growth-top").forEach(item => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".growth-detail").forEach(d => {
      if (d !== item.parentElement.querySelector(".growth-detail")) {
        d.classList.add("hidden");
      }
    });

    document.querySelectorAll(".toggle-icon").forEach(i => {
      if (i !== item.querySelector(".toggle-icon")) {
        i.classList.remove("rotate");
      }
    });

    const detail = item.parentElement.querySelector(".growth-detail");
    const icon = item.querySelector(".toggle-icon");

    detail.classList.toggle("hidden");
    icon.classList.toggle("rotate");
  });
});

const infoIcon = document.querySelector(".info-icon");
const matchGuide = document.querySelector(".match-guide");

if (infoIcon) {
  infoIcon.addEventListener("click", () => {
      matchGuide.classList.toggle("hidden");
  });
}

// Snapshot just the career pathways section (grid of cards) as a PNG,
// hiding our own download icon first so it doesn't appear in the image.
function downloadCareerSectionAsPng() {
  const section = document.getElementById("careerSection");
  const btn = document.getElementById("careerPngBtn");
  if (!section) return;

  btn.style.visibility = "hidden";

  html2canvas(section, { backgroundColor: "#ffffff", scale: 2 })
    .then(canvas => {
      const link = document.createElement("a");
      link.download = "career_recommendations.png";
      link.href = canvas.toDataURL("image/png");
      link.click();
    })
    .finally(() => {
      btn.style.visibility = "visible";
    });
}

function toggleCareerDescription(descId) {
  const target = document.getElementById(descId);
  if (target) {
    target.classList.toggle("hidden");
  }
}

// Per-career feedback
function toggleAllCareerFeedback() {
  const intro = document.getElementById("careerFeedbackIntro");
  if (intro) {
    intro.classList.toggle("hidden");
  }
  document.querySelectorAll(".career-feedback").forEach(el => {
    el.classList.toggle("hidden");
  });
}

function submitCareerFeedback(careerId, rating) {
  const container = document.getElementById(`feedback-${careerId}`);
  if (!container) return;

  fetch(`/career/feedback/${careerId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify({ rating: rating }),
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        container.innerHTML = '<p class="career-feedback-thanks">Thank you for your feedback!</p>';
      } else {
        console.error("Feedback submission failed:", data.error);
      }
    })
    .catch(error => console.error("Feedback submission failed:", error));
}