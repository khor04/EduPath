// "Save as image" for the admin analysis pages (Performance Trends, Course
// Difficulty). Same approach as the student Career page: html2canvas snapshots
// one section and the browser downloads it as a PNG.
//
// The section is captured exactly as the page rendered it, so the image can
// never show anything the admin could not already see -- small-group hiding
// ("<5", "Withheld") is baked into the page before this runs.
//
// The section holds a hidden .export-header (title, filters, date). It only
// appears in the snapshot, where onclone switches on the "exporting" class,
// so a saved image explains itself once it is out of the site.
function saveAdminSectionAsPng(sectionId, filename) {
  const section = document.getElementById(sectionId);
  if (!section || typeof html2canvas === "undefined") return;

  const today = new Date();
  const dateLabel = today.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  const isoDate = today.toISOString().slice(0, 10);

  html2canvas(section, {
    backgroundColor: "#ffffff",
    scale: 2,
    // Lay the snapshot out at desktop width whatever the screen size, so a
    // phone doesn't produce a squashed image with a clipped table.
    windowWidth: 1200,
    // The download button is screen-only.
    ignoreElements: el => el.classList && el.classList.contains("admin-png-btn"),
    onclone: clonedDoc => {
      const clonedSection = clonedDoc.getElementById(sectionId);
      clonedSection.classList.add("exporting");
      clonedSection.querySelectorAll(".export-date").forEach(el => {
        el.textContent = dateLabel;
      });
    }
  }).then(canvas => {
    const link = document.createElement("a");
    link.download = `${filename}_${isoDate}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  });
}
