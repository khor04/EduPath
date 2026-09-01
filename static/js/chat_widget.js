// ================================
// EduPath AI floating chat widget
// ================================
(function () {
  const STORAGE_KEY = "edupath_chat_history";
  const MAX_HISTORY_TURNS = 10;

  const toggleBtn = document.getElementById("chatToggleBtn");
  const closeBtn = document.getElementById("chatCloseBtn");
  const panel = document.getElementById("chatPanel");
  const messagesEl = document.getElementById("chatMessages");
  const greetingEl = document.querySelector(".chat-greeting");
  const suggestionsEl = document.getElementById("chatSuggestions");
  const errorEl = document.getElementById("chatError");
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSendBtn");

  if (!toggleBtn || !panel) return;

  // sessionStorage, not a DB table -- survives navigating between
  // pages within one visit, clears on tab close/logout. See the
  // conversation history discussion: this is deliberately just
  // conversational context, never treated as an authoritative source
  // of student facts (that's the backend's job, from real data).
  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory(history) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
      // sessionStorage unavailable (private mode, quota, etc.) --
      // the widget still works, it just won't persist across pages.
    }
  }

  // Escapes real HTML first, THEN converts markdown-ish syntax to
  // tags -- in that order specifically, so anything Gemini echoes
  // back (or that arrived via a manipulated response) can never
  // inject real markup. Only bold/italic/bulleted/numbered lists are
  // handled -- enough to make Gemini's normal output style readable
  // without pulling in a full markdown library for a narrow use case.
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function inlineFormat(line) {
    return line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  }

  function renderMarkdownLite(text) {
    const lines = escapeHtml(text).split("\n");
    const parts = [];
    let listItems = [];
    let listTag = null;

    function flushList() {
      if (listItems.length) {
        parts.push(`<${listTag}>${listItems.map((i) => `<li>${i}</li>`).join("")}</${listTag}>`);
        listItems = [];
        listTag = null;
      }
    }

    lines.forEach((rawLine) => {
      const line = rawLine.trim();
      const bullet = line.match(/^[-*]\s+(.*)/);
      const numbered = line.match(/^\d+[.)]\s+(.*)/);

      if (bullet) {
        if (listTag !== "ul") { flushList(); listTag = "ul"; }
        listItems.push(inlineFormat(bullet[1]));
      } else if (numbered) {
        if (listTag !== "ol") { flushList(); listTag = "ol"; }
        listItems.push(inlineFormat(numbered[1]));
      } else {
        flushList();
        if (line) parts.push(`<p>${inlineFormat(line)}</p>`);
      }
    });
    flushList();

    return parts.join("");
  }

  function renderMessage(role, text, link) {
    const el = document.createElement("div");
    el.className = `chat-message ${role}`;

    if (role === "assistant") {
      el.innerHTML = renderMarkdownLite(text);
    } else {
      el.textContent = text;
    }

    if (link) {
      const a = document.createElement("a");
      a.href = link.url;
      a.className = "chat-message-link";
      a.textContent = link.label + " →";
      el.appendChild(document.createElement("br"));
      el.appendChild(a);
    }

    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function renderHistory(history) {
    if (history.length === 0) return;
    if (greetingEl) greetingEl.style.display = "none";
    history.forEach((turn) => renderMessage(turn.role === "user" ? "user" : "assistant", turn.text, turn.link));
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
  }

  function clearError() {
    errorEl.classList.add("hidden");
    errorEl.textContent = "";
  }

  async function loadSuggestions() {
    if (!suggestionsEl) return;
    try {
      const res = await fetch("/api/chat/suggestions");
      const data = await res.json();
      (data.suggestions || []).forEach((question) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chat-suggestion-chip";
        chip.textContent = question;
        chip.addEventListener("click", () => sendMessage(question));
        suggestionsEl.appendChild(chip);
      });
    } catch (e) {
      // Suggestions are a nicety, not core functionality -- fail quietly.
    }
  }

  async function sendMessage(message) {
    if (!message.trim()) return;

    clearError();
    if (greetingEl) greetingEl.style.display = "none";

    const history = loadHistory();
    renderMessage("user", message);

    const loadingEl = document.createElement("div");
    loadingEl.className = "chat-message loading";
    loadingEl.textContent = "Thinking...";
    messagesEl.appendChild(loadingEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: history.slice(-MAX_HISTORY_TURNS)
        })
      });

      const data = await res.json();
      loadingEl.remove();

      if (!res.ok || !data.success) {
        showError(data.message || "Something went wrong. Please try again.");
        return;
      }

      renderMessage("assistant", data.response, data.link);

      history.push({ role: "user", text: message });
      history.push({ role: "assistant", text: data.response, link: data.link || undefined });
      saveHistory(history.slice(-MAX_HISTORY_TURNS * 2));

    } catch (e) {
      loadingEl.remove();
      showError("Couldn't reach EduPath AI. Check your connection and try again.");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // The "Ask EduPath AI" bubble only makes sense while there's no
  // active session -- once the panel is open, it visually replaces
  // the bubble's spot instead of floating above a now-redundant
  // label. Tied to the panel's current open/closed state, not a
  // one-time "seen it before" flag -- closing the panel brings the
  // bubble back.
  function syncToggleAppearance() {
    const isOpen = !panel.classList.contains("hidden");
    toggleBtn.classList.toggle("compact", isOpen);
  }

  toggleBtn.addEventListener("click", () => {
    panel.classList.toggle("hidden");
    syncToggleAppearance();
    if (!panel.classList.contains("hidden")) {
      input.focus();
    }
  });

  closeBtn.addEventListener("click", () => {
    panel.classList.add("hidden");
    syncToggleAppearance();
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value);
  });

  renderHistory(loadHistory());
  loadSuggestions();
})();
