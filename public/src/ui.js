// Learnify — shared view toolkit.
//
// Every feature module composes its screen from these helpers so the portal
// reads as one product rather than twelve. Nothing here talks to the API;
// modules fetch their own data and hand plain objects to these renderers.
//
//   import * as ui from './ui.js?v=64';
//   root.innerHTML = ui.page({ title, sub, actions, body });
//
// Route handlers receive (root, ctx) from app.js and may return { destroy }.

import { esc, qs } from './utils.js?v=64';
import { iconSvg } from './icons.js?v=64';

// ─── Page scaffolding ───────────────────────────────────────────────────────

/** Full page: head + body, in one string. */
export function page({ title, sub, actions = '', crumbs = '', body = '' }) {
  return crumbs + head({ title, sub, actions }) + body;
}

/** Title row with optional action buttons. */
export function head({ title, sub = '', actions = '' }) {
  return `
    <div class="page-head">
      <div>
        <h1 class="page-title">${esc(title)}</h1>
        ${sub ? `<p class="page-sub">${sub}</p>` : ''}
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ''}
    </div>`;
}

/** Standard "nothing here yet" block with an optional call to action. */
export function blank({ title, body = '', action = '', actionHref = '' }) {
  return `
    <div class="blank">
      <b>${esc(title)}</b>
      ${body ? `<p>${body}</p>` : ''}
      ${action ? `<a class="btn primary sm" href="${esc(actionHref)}">${esc(action)}</a>` : ''}
    </div>`;
}

export function loading(what = '') {
  return `<div class="empty-state">Loading${what ? ' ' + esc(what) : ''}…</div>`;
}

export function errorBlock(message) {
  return `
    <div class="blank">
      <b>Could not load this</b>
      <p>${esc(message || 'Something went wrong while fetching this page.')}</p>
      <p><a href="#" data-retry>Try again</a></p>
    </div>`;
}

export function sectionTitle(text) {
  return `<h2 class="section-title">${esc(text)}</h2>`;
}

export function note(html, tone = '') {
  return `<div class="note${tone ? ' ' + tone : ''}">${html}</div>`;
}

// ─── Status vocabulary ──────────────────────────────────────────────────────

const TONE = {
  DRAFT: 'mute', PENDING: 'warn', PENDING_RELEASE: 'warn', PUBLISHED: 'ok',
  RELEASED: 'ok',
  ACTIVE: 'ok', APPROVED: 'ok', REJECTED: 'bad', ARCHIVED: 'mute',
  CLOSED: 'mute', RETIRED: 'mute', IN_PROGRESS: 'info', SUBMITTED: 'info',
  OPEN: 'ok', UPCOMING: 'info', EXPIRED: 'mute', VOID: 'bad', FAILED: 'bad',
  PASSED: 'ok', COMPLETED: 'ok', SUSPENDED: 'bad', BANNED: 'bad',
  INACTIVE: 'mute', ENROLLED: 'info', WAITLIST: 'warn',
};

const LABEL = {
  PENDING: 'Pending approval', PENDING_RELEASE: 'Pending release',
  IN_PROGRESS: 'In progress',
  SUBMITTED: 'Submitted', EXPIRED: 'Expired', PUBLISHED: 'Published',
};

export function tag(status) {
  const s = String(status || '').toUpperCase();
  if (!s) return '';
  const label = LABEL[s] || s.replace(/_/g, ' ').toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return `<span class="tag ${TONE[s] || 'mute'}">${esc(label)}</span>`;
}

export function tone(text, tone) {
  return `<span class="tag ${tone}">${esc(text)}</span>`;
}

// ─── Small pieces ───────────────────────────────────────────────────────────

export function initials(name) {
  const parts = String(name || '?').trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0] || '').join('').toUpperCase() || '?';
}

/** Person block: avatar initials, name, secondary line. */
export function who(name, sub = '', cls = '') {
  return `
    <div class="who ${cls}">
      <div class="ini">${esc(initials(name))}</div>
      <div class="nm">
        <b>${esc(name || 'Unknown')}</b>
        ${sub ? `<small>${esc(sub)}</small>` : ''}
      </div>
    </div>`;
}

export function tile({ icon = '', value, label, hint = '', href = '' }) {
  const inner = `
    ${icon ? `<span class="ico">${iconSvg(icon)}</span>` : ''}
    <b>${esc(String(value))}</b>
    <span>${esc(label)}</span>
    ${hint ? `<small>${esc(hint)}</small>` : ''}`;
  return href
    ? `<a class="stat-tile" href="${esc(href)}" style="text-decoration:none">${inner}</a>`
    : `<div class="stat-tile">${inner}</div>`;
}

export function progressBar(pct, label = '') {
  const n = Math.max(0, Math.min(100, Number(pct) || 0));
  return `
    <div class="progress-row">
      <div class="progress-bar"><div class="progress-fill" style="width:${n}%"></div></div>
      <span class="progress-label">${esc(label || Math.round(n) + '%')}</span>
    </div>`;
}

export function kv(items) {
  return `<div class="kv">${items
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `<div class="k"><span>${esc(k)}</span><b>${esc(v)}</b></div>`)
    .join('')}</div>`;
}

export function pillbar(items, active) {
  return `<div class="pillbar">${items
    .map((it) => `<button data-pill="${esc(it.key)}"${
      it.key === active ? ' class="active"' : ''}>${esc(it.label)}${
      it.count !== undefined ? ` (${it.count})` : ''}</button>`)
    .join('')}</div>`;
}

export function table(cols, rows, rowKey = 'id') {
  if (!rows || !rows.length) return '';
  return `
    <div class="tbl-wrap"><table class="tbl">
      <thead><tr>${cols.map((c) => `<th>${esc(c.label)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr${
        r[rowKey] ? ` data-row="${esc(r[rowKey])}"` : ''
      }>${cols.map((c) => `<td data-l="${esc(c.label)}">${
        typeof c.get === 'function' ? (c.get(r) ?? '') : esc(c.get ?? '')
      }</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
}

// ─── Dates ──────────────────────────────────────────────────────────────────

export function fmtDate(s, { withTime = false, short = false } = {}) {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d)) return String(s);
  const date = d.toLocaleDateString('en-GB', short
    ? { day: '2-digit', month: 'short' }
    : { day: '2-digit', month: 'short', year: 'numeric' });
  if (!withTime) return date;
  return `${date}, ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`;
}

export function relTime(s) {
  if (!s) return '—';
  const then = new Date(s).getTime();
  if (isNaN(then)) return String(s);
  const diff = Math.round((Date.now() - then) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} d ago`;
  return fmtDate(s);
}

export function countdown(iso) {
  if (!iso) return '';
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms)) return '';
  if (ms <= 0) return 'closed';
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  if (d >= 1) return `${d}d ${Math.floor((s % 86400) / 3600)}h left`;
  const h = Math.floor(s / 3600);
  if (h >= 1) return `${h}h ${Math.floor((s % 3600) / 60)}m left`;
  return `${Math.floor(s / 60)}m left`;
}

export function fmtHours(n) {
  const v = Number(n) || 0;
  return v >= 1 ? `${(Math.round(v * 10) / 10)} h` : `${Math.round(v * 60)} min`;
}

export function fmtNum(n) {
  const v = Number(n) || 0;
  if (v >= 1000) return (Math.round(v / 100) / 10) + 'k';
  return String(v);
}

export function pct(n, digits = 1) {
  const v = Number(n);
  if (!isFinite(v)) return '—';
  return `${Math.round(v * 10 ** digits) / 10 ** digits}%`;
}

// ─── Event delegation ───────────────────────────────────────────────────────
// Views are re-rendered wholesale, so listeners are bound through the container
// rather than to individual nodes that are about to be replaced. Because the
// container outlives its contents, re-binding the same (selector, event) pair
// on the same element REPLACES the previous handler instead of stacking a
// second one — otherwise a list that re-renders five times would fire its
// action five times. The returned function unbinds explicitly.

const DELEGATED = new WeakMap();

/** Bind `handler` for `selector`, scoped to `root` (returns off()). */
export function on(root, selector, event, handler) {
  const key = event + '\u0000' + selector;
  let map = DELEGATED.get(root);
  if (!map) { map = new Map(); DELEGATED.set(root, map); }

  const previous = map.get(key);
  if (previous) root.removeEventListener(event, previous);

  const fn = (e) => {
    const target = e.target.closest(selector);
    if (target && root.contains(target)) handler(e, target);
  };
  map.set(key, fn);
  root.addEventListener(event, fn);

  return () => {
    root.removeEventListener(event, fn);
    if (map.get(key) === fn) map.delete(key);
  };
}

/** Convenience for the most common case. */
export function click(root, selector, handler) {
  return on(root, selector, 'click', handler);
}

/** Enable an element, run async work, then restore it (double-submit guard). */
export async function busy(btn, label, work) {
  if (!btn) return work();
  const html = btn.innerHTML;
  btn.disabled = true;
  if (label) btn.textContent = label;
  try {
    return await work();
  } finally {
    btn.disabled = false;
    btn.innerHTML = html;
  }
}

// ─── Star rating ────────────────────────────────────────────────────────────

/** Five tappable stars. `onPick(stars)` fires on selection. */
export function stars(root, { value = 0, onPick = null, id = 'star' } = {}) {
  const n = Math.round(Number(value) || 0);
  root.innerHTML = `
    <div class="stars" role="radiogroup" aria-label="Rating out of five">
      ${[1, 2, 3, 4, 5].map((i) => `
        <button type="button" class="star${i <= n ? ' on' : ''}" data-star="${i}"
                role="radio" aria-checked="${i === n}"
                aria-label="${i} star${i > 1 ? 's' : ''}"
                id="${id}-${i}">&#9733;</button>`).join('')}
      <span class="star-val">${n ? n + ' / 5' : 'Not rated'}</span>
    </div>`;
  if (onPick) {
    click(root, '.star', (e, btn) => {
      const v = Number(btn.dataset.star);
      root.querySelectorAll('.star').forEach((s, i) => {
        s.classList.toggle('on', i < v);
        s.setAttribute('aria-checked', String(i + 1 === v));
      });
      const lbl = root.querySelector('.star-val');
      if (lbl) lbl.textContent = `${v} / 5`;
      onPick(v);
    });
  }
  return n;
}

// ─── Misc ───────────────────────────────────────────────────────────────────

/** Read `<select name>` / `<input name>` values from a form into a plain object. */
export function formValues(form) {
  const out = {};
  if (!form) return out;
  form.querySelectorAll('[name]').forEach((f) => {
    if (f.type === 'checkbox') out[f.name] = f.checked;
    else out[f.name] = f.value;
  });
  return out;
}

/** Show an inline form error next to the submit button. */
export function formError(form, message) {
  const box = form && form.querySelector('[data-err]');
  if (box) box.textContent = message || '';
}

export function escapeHtml(s) { return esc(s); }

export function query(params) { return qs(params); }

/** Strip the API envelope: `{success,data,error}` -> `data` (null on failure). */
export function data(res) {
  if (res && typeof res === 'object' && 'success' in res) return res.success ? res.data : null;
  return res;
}

export function meta(res) {
  return (res && res.meta) || {};
}
