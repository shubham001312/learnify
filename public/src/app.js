// Learnify — SPA shell and hash router.
//
// One mount point (#view). Every route dynamically imports a feature module and
// calls its handler with (root, params). Views get `ctx` from here so they never
// have to re-read auth state or build navigation themselves.

import { api, el, esc, getUser, setUser, getToken, clearToken, clearUser, toast }
  from './utils.js?v=63';
import { iconSvg } from './icons.js?v=63';
import { logout } from './auth.js?v=63';

export const V = 'v=63';

export const ROLE_LABEL = {
  ALPHA: 'Trainee (ALPHA)',
  MASTER: 'Trainer (MASTER)',
  SUPREME: 'Administrator (SUPREME)',
};

const ROLE_BY_PATH = { alpha: 'ALPHA', master: 'MASTER', supreme: 'SUPREME' };

// What an account still awaiting approval may open: the waiting screen and
// its own profile, where a name, department or password can be corrected
// while it waits. Everything else is refused by the server anyway.
const PENDING_OK = /^\/(pending|profile)$/;

// ─── Route table ────────────────────────────────────────────────────────────
// `file` is the module name; `$role` resolves at render time to the signed-in
// user's dashboard. `pub` routes work signed-out; everything else is guarded.
const ROUTES = [
  // Public
  { re: /^\/$/, file: 'landing', fn: 'home', pub: true },
  { re: /^\/(?<role>alpha|master|supreme)$/, file: 'landing', fn: 'role', pub: true },
  { re: /^\/(?<role>alpha|master|supreme)\/(?<mode>login|signup)$/,
    file: 'auth_pages', fn: 'auth', pub: true },

  // Signed-in
  { re: /^\/home$/, file: '$role', fn: 'render' },
  // Reachable by every account, including one still awaiting approval.
  { re: /^\/pending$/, file: 'pending', fn: 'render' },
  { re: /^\/feed$/, file: 'feed', fn: 'render' },
  { re: /^\/courses$/, file: 'courses', fn: 'list' },
  { re: /^\/courses\/(?<id>[\w-]+)$/, file: 'courses', fn: 'detail' },
  { re: /^\/courses\/(?<id>[\w-]+)\/edit$/, file: 'course_wizard', fn: 'render',
    roles: ['MASTER', 'SUPREME'] },
  { re: /^\/learn\/(?<id>[\w-]+)(?:\/(?<slot>[\w-]+))?$/, file: 'player', fn: 'course' },

  { re: /^\/tests$/, file: 'question_builder', fn: 'list' },
  { re: /^\/tests\/(?<kind>[qa])\/(?<id>[\w-]+)$/, file: 'question_builder', fn: 'detail' },
  { re: /^\/tests\/(?<kind>[qa])\/(?<id>[\w-]+)\/edit$/, file: 'question_builder', fn: 'edit',
    roles: ['MASTER', 'SUPREME'] },
  { re: /^\/drafts$/, file: 'question_builder', fn: 'drafts', roles: ['MASTER', 'SUPREME'] },
  { re: /^\/take\/(?<kind>[qa])\/(?<id>[\w-]+)$/, file: 'player', fn: 'attempt' },

  { re: /^\/reports$/, file: 'report', fn: 'list' },
  { re: /^\/reports\/(?<id>[\w-]+)$/, file: 'report', fn: 'detail' },
  { re: /^\/library$/, file: 'library', fn: 'render' },
  { re: /^\/competency(?:\/(?<subject>[\w-]+))?$/, file: 'competency', fn: 'render' },
  { re: /^\/feedback\/(?<kind>course|content)\/(?<id>[\w-]+)$/, file: 'feedback', fn: 'render' },
  { re: /^\/profile$/, file: 'profile', fn: 'render' },
  { re: /^\/notifications$/, file: 'notifications', fn: 'render' },

  { re: /^\/admin(?:\/(?<page>[\w-]+))?$/, file: 'supreme', fn: 'render',
    roles: ['SUPREME'] },
  { re: /^\/trainers\/(?<subject>[\w-]+)$/, file: 'competency', fn: 'rank' },
];

// ─── Navigation ─────────────────────────────────────────────────────────────
const NAV = {
  ALPHA: [
    { href: '#/home', label: 'Home', icon: 'target' },
    { href: '#/courses', label: 'Courses', icon: 'book' },
    { href: '#/tests', label: 'Tests', icon: 'quiz' },
    { href: '#/reports', label: 'Reports', icon: 'chart' },
    { href: '#/library', label: 'Library', icon: 'graduation' },
  ],
  MASTER: [
    { href: '#/home', label: 'Home', icon: 'target' },
    { href: '#/courses', label: 'Courses', icon: 'book' },
    { href: '#/tests', label: 'Tests', icon: 'quiz' },
    { href: '#/drafts', label: 'AI drafts', icon: 'sparkles' },
    { href: '#/library', label: 'Library', icon: 'graduation' },
  ],
  SUPREME: [
    { href: '#/home', label: 'Home', icon: 'target' },
    { href: '#/admin/content', label: 'Content', icon: 'shield' },
    { href: '#/admin/users', label: 'Users', icon: 'briefcase' },
    { href: '#/feed', label: 'Feed', icon: 'megaphone' },
    { href: '#/admin/audit', label: 'Audit', icon: 'chart' },
  ],
};

// Extra desktop-only links; the dock stays at five items.
const TOP_EXTRA = {
  ALPHA: [{ href: '#/feed', label: 'Feed', icon: 'megaphone' },
          { href: '#/competency', label: 'Trainers', icon: 'award' }],
  MASTER: [{ href: '#/feed', label: 'Feed', icon: 'megaphone' },
           { href: '#/competency', label: 'Competency', icon: 'award' }],
  SUPREME: [{ href: '#/reports', label: 'Reports', icon: 'chart' },
            { href: '#/competency', label: 'Competency', icon: 'award' }],
};

// ─── View lifecycle ─────────────────────────────────────────────────────────
let active = null;   // { destroy } from the currently mounted module

function teardown() {
  if (active && typeof active.destroy === 'function') {
    try { active.destroy(); } catch (_) { /* view cleanup must never block */ }
  }
  active = null;
}

export function go(path) {
  const next = '#' + (path.startsWith('/') ? path : '/' + path);
  if (location.hash === next) render();
  else location.hash = next;
}

export function currentPath() {
  const h = location.hash || '#/';
  return h.slice(1).split('?')[0] || '/';
}

/** Signed-in user, refreshed from the API when the cached copy is stale. */
export function currentUser() {
  return getUser();
}

export function refreshUser() {
  return api('/auth/me')
    .then((d) => { if (d && d.user) { setUser(d.user); paintChrome(); } return d.user; })
    .catch(() => { clearToken(); clearUser(); paintChrome(); return null; });
}

export function signOut() {
  logout();
  toast('Signed out.');
  go('/');
}

// ─── Modal helper (shared by views for confirms and quick forms) ────────────
export function openAppModal(html) {
  const body = el('app-modal-body');
  if (body) body.innerHTML = html;
  el('app-modal')?.classList.add('open');
}

export function closeAppModal() {
  el('app-modal')?.classList.remove('open');
}

/** Promise-based confirm. Resolves true when the user accepts. */
export function confirmAction(title, message, okLabel = 'Confirm') {
  return new Promise((resolve) => {
    openAppModal(`
      <h3 class="modal-title">${esc(title)}</h3>
      <p class="modal-sub">${esc(message)}</p>
      <div class="row gap" style="margin-top:16px;justify-content:flex-end">
        <button class="btn ghost sm" data-act="cancel">Cancel</button>
        <button class="btn primary sm" data-act="ok">${esc(okLabel)}</button>
      </div>`);
    const done = (v) => { closeAppModal(); resolve(v); };
    el('app-modal-body')?.querySelector('[data-act="ok"]')
      ?.addEventListener('click', () => done(true));
    el('app-modal-body')?.querySelector('[data-act="cancel"]')
      ?.addEventListener('click', () => done(false));
  });
}

// ─── Chrome (top bar, dock, footer) ─────────────────────────────────────────
function paintChrome() {
  const user = getUser();
  const path = currentPath();
  const isPublic = path === '/' || /^\/(alpha|master|supreme)(\/(login|signup))?$/.test(path);

  el('btn-signin').hidden = !!user;
  el('top-avatar').hidden = !user;
  el('btn-signout').hidden = !user;
  el('btn-notif').hidden = !user;

  // Footer belongs to the public pages — the app gets that screen space back.
  el('site-foot').hidden = !isPublic;

  const dock = el('tabbar');
  const top = el('top-nav');
  if (!user) {
    dock.hidden = true;
    top.innerHTML = '';
    return;
  }

  const items = NAV[user.role] || NAV.ALPHA;
  // An unapproved account has nowhere to navigate to yet — the dock and the
  // top links would only lead to the guard bouncing them back here.
  const waiting = user.status === 'PENDING';
  dock.hidden = waiting;
  if (waiting) {
    top.innerHTML = '';
    paintActive(path);
    return;
  }
  dock.innerHTML = items.map((it) => `
    <button class="tbtn" data-go="${it.href}">${iconSvg(it.icon)}<span>${esc(it.label)}</span></button>
  `).join('');
  dock.querySelectorAll('[data-go]').forEach((b) =>
    b.addEventListener('click', () => go(b.dataset.go.slice(1))));

  const all = items.concat(TOP_EXTRA[user.role] || []);
  top.innerHTML = all.map((it) =>
    `<a class="top-link" href="${it.href}">${esc(it.label)}</a>`).join('');

  paintActive(path);
}

function paintActive(path) {
  const cur = '#/' + path.replace(/^\//, '');
  document.querySelectorAll('#tabbar .tbtn').forEach((b) => {
    const href = b.dataset.go || '';
    b.classList.toggle('active', href === cur || (href !== '#/home' && cur.startsWith(href)));
  });
  document.querySelectorAll('#top-nav .top-link').forEach((a) =>
    a.classList.toggle('active', a.getAttribute('href') === cur));
}

// ─── Notifications ──────────────────────────────────────────────────────────
function initNotifications() {
  el('btn-notif')?.addEventListener('click', async (e) => {
    e.stopPropagation();
    const panel = el('notif-panel');
    if (panel.classList.contains('open')) { panel.classList.remove('open'); return; }
    panel.classList.add('open');
    const list = el('notif-list');
    list.innerHTML = '<div class="empty-state">Loading…</div>';
    try {
      const d = await api('/v1/notifications/my?limit=30');
      // This endpoint returns `{items:[...]}` bare (no success envelope), so
      // unwrap every shape it might arrive in before testing for emptiness.
      const rows = (d && Array.isArray(d.items) && d.items)
        || (d && d.data && d.data.items)
        || (Array.isArray(d) ? d : []);
      if (!rows.length) { list.innerHTML = '<div class="empty-state">No notifications yet.</div>'; return; }
      list.innerHTML = rows.map((n) => `
        <div class="notif-item${n.read ? '' : ' unread'}">
          <b>${esc(n.title)}</b>
          <p>${esc(n.message || '')}</p>
          ${n.link ? `<a href="#${esc(String(n.link).replace(/^#/, ''))}" data-close-panel>Open</a>` : ''}
        </div>`).join('');
      list.querySelectorAll('[data-close-panel]').forEach((a) =>
        a.addEventListener('click', () => panel.classList.remove('open')));
      api('/v1/notifications/mark-all-read', { method: 'POST' }).then(syncBadge).catch(() => {});
    } catch (_) {
      list.innerHTML = '<div class="empty-state">Could not load notifications.</div>';
    }
  });

  document.addEventListener('click', (e) => {
    const panel = el('notif-panel');
    if (panel && panel.classList.contains('open') && !panel.contains(e.target)
        && !el('btn-notif').contains(e.target)) panel.classList.remove('open');
  });

  syncBadge();
}

// Sign-out lives in the chrome (next to the avatar) and again on the profile
// page — both are static markup bound exactly once at boot, so re-painting the
// top bar can never stack a second handler on the same button.
function initSignOut() {
  const btn = el('btn-signout');
  if (btn) btn.addEventListener('click', (e) => { e.stopPropagation(); signOut(); });
  document.querySelectorAll('[data-signout]').forEach(bindSignOut);
}

/** Wire up any sign-out control a view has just rendered. */
export function bindSignOut(node) {
  if (node && !node.dataset.bound) {
    node.dataset.bound = '1';
    node.addEventListener('click', (e) => { e.preventDefault(); signOut(); });
  }
}

export function syncBadge() {
  if (!getUser()) return;
  api('/v1/notifications/unread-count')
    .then((d) => {
      // `{count: n}` bare — tolerate the envelope too in case it changes.
      const n = Number((d && d.count) ?? (d && d.data && d.data.count)
        ?? (d && d.data) ?? 0);
      const b = el('notif-badge');
      if (!b) return;
      b.textContent = String(n);
      b.style.display = n > 0 ? '' : 'none';
    })
    .catch(() => {});
}
setInterval(syncBadge, 60000);

// ─── Router ─────────────────────────────────────────────────────────────────
function match(path) {
  for (const r of ROUTES) {
    const m = r.re.exec(path);
    if (m) return { route: r, params: (m && m.groups) || {} };
  }
  return null;
}

/** Where to send a signed-out (or wrongly-roled) visitor for this route. */
function landingFor(path, user) {
  const pub = match(path);
  if (pub && pub.route.pub) return null;
  const m = /^\/(alpha|master|supreme)(\/(login|signup))?/.exec(path);
  const role = m ? ROLE_BY_PATH[m[1]] : (user && user.role) || 'ALPHA';
  const dest = (role || 'ALPHA').toLowerCase();
  if (m && m[2]) return null;                     // already on an auth page
  return `/${dest}/login`;
}

async function render() {
  const path = currentPath();
  const user = getUser();
  const hit = match(path);

  if (!hit) { renderNotFound(); return; }

  // Role guard for authed routes.
  if (!hit.route.pub) {
    if (!user) { go(landingFor(path, null)); return; }
    if (hit.route.roles && !hit.route.roles.includes(user.role)) {
      toast('You do not have access to that page.', 'warn');
      go('/home');
      return;
    }
    // An unapproved account gets the waiting screen and nothing else. The
    // server refuses these calls too — this only stops the app from painting
    // a dashboard that is about to light up with errors.
    if (user.status === 'PENDING' && !PENDING_OK.test(path)) {
      go('/pending');
      return;
    }
  }

  const file = hit.route.file === '$role'
    ? String(user ? user.role : 'ALPHA').toLowerCase()
    : hit.route.file;

  paintChrome();
  teardown();

  const root = el('view');
  root.innerHTML = '<div class="empty-state">Loading…</div>';
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });

  let mod;
  try {
    mod = await import(`./${file}.js?${V}`);
  } catch (err) {
    console.error('route module failed to load:', file, err);
    root.innerHTML = `<div class="empty-state">
      <b>This page could not be loaded.</b>
      <p>The module "${esc(file)}" is missing or failed to compile.</p>
      <p><a href="#/">Back to home</a></p></div>`;
    return;
  }

  const ctx = { path, params: hit.params, user: getUser(), route: hit.route };

  try {
    const out = await mod[hit.route.fn](root, ctx);
    if (out && typeof out.destroy === 'function') active = out;
  } catch (err) {
    console.error('route render failed:', file, err);
    root.innerHTML = `<div class="empty-state">
      <b>Something went wrong.</b>
      <p>${esc(err && err.message ? err.message : 'Unexpected error.')}</p>
      <p><a href="#/home">Back to home</a></p></div>`;
  }

  paintActive(path);
}

function renderNotFound() {
  teardown();
  el('view').innerHTML = `
    <div class="empty-state">
      <b>Page not found</b>
      <p>The address you followed does not exist.</p>
      <p><a href="#/">Back to home</a></p>
    </div>`;
}

// ─── Boot ───────────────────────────────────────────────────────────────────
async function boot() {
  document.querySelectorAll('[data-close]').forEach((b) =>
    b.addEventListener('click', closeAppModal));
  el('app-modal')?.addEventListener('click', (e) => {
    if (e.target === el('app-modal')) closeAppModal();
  });

  initNotifications();
  initSignOut();

  // Restore the session before the first paint so the guard sees a real role.
  if (getToken()) {
    try {
      const d = await api('/auth/me');
      if (d && d.user) setUser(d.user);
      else { clearToken(); clearUser(); }
    } catch (_) { clearToken(); clearUser(); }
  }

  window.addEventListener('hashchange', render);
  await render();
}

boot();
