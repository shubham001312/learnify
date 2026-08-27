const KEY = "learnify_notifs";

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (_) { return []; }
}
function save(arr) {
  try { localStorage.setItem(KEY, JSON.stringify(arr)); } catch (_) {}
}

export function addNotification(text) {
  const arr = load();
  arr.unshift({ id: Date.now(), text, time: new Date().toISOString(), read: false });
  if (arr.length > 25) arr.length = 25;
  save(arr);
  renderBell();
}

function unreadCount() {
  return load().filter((n) => !n.read).length;
}

export function renderBell() {
  const badge = document.getElementById("notif-badge");
  if (!badge) return;
  const c = unreadCount();
  badge.style.display = c ? "flex" : "none";
  badge.textContent = c;
}

export function renderPanel() {
  const list = document.getElementById("notif-list");
  if (!list) return;
  const arr = load();
  if (!arr.length) {
    list.innerHTML = '<div class="notif-empty">No notifications yet</div>';
    return;
  }
  list.innerHTML = arr
    .map(
      (n) =>
        '<div class="notif-item ' + (n.read ? "read" : "") + '">' +
        '<div class="notif-dot"></div><div class="notif-text">' + esc(n.text) + "</div></div>"
    )
    .join("");
}

export function togglePanel() {
  const p = document.getElementById("notif-panel");
  if (!p) return;
  const open = p.classList.toggle("open");
  if (open) {
    const arr = load();
    arr.forEach((n) => (n.read = true));
    save(arr);
    renderBell();
    renderPanel();
  }
}

export function initNotifications() {
  const bell = document.querySelector('.icon-btn[title="Notifications"]');
  if (bell) bell.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePanel();
  });
  document.addEventListener("click", (e) => {
    const p = document.getElementById("notif-panel");
    if (!p || !p.classList.contains("open")) return;
    const t = e.target;
    if (p.contains(t)) return;
    if (t.closest && t.closest('.icon-btn[title="Notifications"]')) return;
    p.classList.remove("open");
  });

  if (!localStorage.getItem("learnify_notifs_seeded")) {
    save([
      { id: Date.now() + 1, text: "Welcome to Learnify! 🎉 Explore colleges & ask Veda.", time: new Date().toISOString(), read: false },
      { id: Date.now() + 2, text: "3 new scholarships match your profile — check Career.", time: new Date().toISOString(), read: false },
    ]);
    try { localStorage.setItem("learnify_notifs_seeded", "1"); } catch (_) {}
  }
  renderBell();
  renderPanel();
}
