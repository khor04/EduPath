// Radar Chart
const radarCtx = document.getElementById("skillRadar");

const radarChart = new Chart(radarCtx, {
  type: "radar",
  data: {
    labels: [
      "Programming",
      "Data Analytics",
      "AI",
      "System Design",
      "Mathematics"
    ],
    datasets: [{
      label: "Skill Score",
      data: [85, 72, 68, 62, 55],
      backgroundColor: "rgba(22, 139, 209, 0.18)",
      borderColor: "#168bd1",
      pointBackgroundColor: "#168bd1",
      pointRadius: 5,
    }]
  },
  options: {
  layout: {
    padding: 10
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

infoIcon.addEventListener("click", () => {
    matchGuide.classList.toggle("hidden");
});

// Feedback selection
const ratingButtons = document.querySelectorAll(".rating-btn");

ratingButtons.forEach(button => {
  button.addEventListener("click", () => {
    ratingButtons.forEach(btn => btn.classList.remove("active"));
    button.classList.add("active");
  });
});