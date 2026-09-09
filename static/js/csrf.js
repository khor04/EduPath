function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

// Escapes text before it's interpolated into an innerHTML template
// literal -- required anywhere the value could originate from a PDF/
// OCR-extracted transcript field or an AI-generated response, neither
// of which is safe to trust as literal HTML. Uses the browser's own
// textContent -> innerHTML round-trip rather than a hand-rolled regex.
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
