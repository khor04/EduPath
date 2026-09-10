// Mobile nav drawer: the sidebar slides in from the left on small screens
// (see layout.css's max-width:768px block) instead of sitting inline like
// on desktop. Loads on every page via layout.html, so it has to no-op
// cleanly on pages where these elements don't exist.
document.addEventListener("DOMContentLoaded", function () {
  const menuToggleBtn = document.getElementById("menuToggleBtn");
  const sidebar = document.querySelector(".sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");

  if (!menuToggleBtn || !sidebar || !backdrop) return;

  function openMenu() {
    sidebar.classList.add("open");
    backdrop.classList.add("visible");
    menuToggleBtn.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("visible");
    menuToggleBtn.setAttribute("aria-expanded", "false");
  }

  menuToggleBtn.addEventListener("click", function () {
    if (sidebar.classList.contains("open")) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  backdrop.addEventListener("click", closeMenu);

  // Picking a destination should close the drawer too, not leave it open
  // over the newly-loaded page.
  sidebar.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", closeMenu);
  });
});
