// ================================
// Scroll-reveal for feature cards, steps, and the CTA banner.
// Bails out entirely under prefers-reduced-motion -- the matching
// CSS never sets an opacity/transform starting state in that case
// either, so this is a belt-and-suspenders skip, not the only guard.
// ================================
(function () {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!("IntersectionObserver" in window)) return;

  // Enables the CSS hidden-until-revealed starting state -- see the
  // comment above the matching @media block in landing.css for why
  // this has to happen in JS rather than unconditionally in CSS.
  // Guarded behind the IntersectionObserver check above so a browser
  // that can't reveal these elements never hides them to begin with.
  document.documentElement.classList.add("js-anim-ready");

  const staggeredGroups = [
    document.querySelectorAll(".feature-card"),
    document.querySelectorAll(".step-item"),
    document.querySelectorAll(".step-line"),
  ];

  staggeredGroups.forEach((group) => {
    group.forEach((el, index) => {
      el.style.transitionDelay = `${index * 90}ms`;
    });
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  document.querySelectorAll(".feature-card, .step-item, .step-line, .cta").forEach((el) => {
    observer.observe(el);
  });
})();
