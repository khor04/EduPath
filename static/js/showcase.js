// ================================
// "See EduPath in action" carousel on the landing page.
//
// Two audiences (student / staff), each with its own set of slides.
// One slide is shown at a time: the arrows step through the slides of
// the audience currently selected, and the dots jump straight to one.
//
// Slides are plain markup in landing.html and the first one ships with
// .is-active already on it, so if this script never runs the section
// still shows that feature and its screenshot -- only the arrows, tabs
// and dots go inert.
// ================================
(function () {
  const section = document.querySelector(".showcase");
  if (!section) return;

  const tabs = Array.from(section.querySelectorAll(".showcase-tab"));
  const slides = Array.from(section.querySelectorAll(".showcase-slide"));
  const dotsBox = section.querySelector(".showcase-dots");
  const prevBtn = section.querySelector(".showcase-arrow--prev");
  const nextBtn = section.querySelector(".showcase-arrow--next");
  const counter = section.querySelector(".showcase-counter");
  // Register button: students only. Signing up always creates a student
  // account -- staff access is granted by the administrator.
  const registerCta = section.querySelector(".showcase-cta");
  if (!tabs.length || !slides.length) return;

  let audience = tabs[0].dataset.audience;
  let index = 0;

  const current = () => slides.filter((s) => s.dataset.audience === audience);

  function render() {
    const group = current();
    index = Math.max(0, Math.min(index, group.length - 1));

    slides.forEach((slide) => {
      const active = slide.dataset.audience === audience && group.indexOf(slide) === index;
      slide.classList.toggle("is-active", active);
    });

    tabs.forEach((tab) => {
      const on = tab.dataset.audience === audience;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });

    // Dots are rebuilt per audience: the two tabs have different slide counts.
    dotsBox.innerHTML = "";
    group.forEach((slide, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "showcase-dot" + (i === index ? " is-active" : "");
      dot.setAttribute("aria-label", `Show ${slide.dataset.title}`);
      dot.setAttribute("aria-current", i === index ? "true" : "false");
      dot.addEventListener("click", () => {
        index = i;
        render();
      });
      dotsBox.appendChild(dot);
    });

    counter.textContent = `${index + 1} / ${group.length}`;

    if (registerCta) registerCta.hidden = audience !== "student";

    // The arrows wrap around, so they are only ever dead when there is a
    // single slide to sit on.
    const many = group.length > 1;
    prevBtn.disabled = !many;
    nextBtn.disabled = !many;
  }

  function step(delta) {
    const group = current();
    index = (index + delta + group.length) % group.length;
    render();
  }

  prevBtn.addEventListener("click", () => step(-1));
  nextBtn.addEventListener("click", () => step(1));

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.dataset.audience === audience) return;
      audience = tab.dataset.audience;
      index = 0;   // a new audience starts at its first feature
      render();
    });
  });

  // Left/right arrow keys move between slides once the carousel has focus.
  section.querySelector(".showcase-viewport").addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { step(-1); }
    else if (e.key === "ArrowRight") { step(1); }
  });

  render();
})();
