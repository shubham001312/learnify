// Learnify — the notifications inbox.
// Route: `/notifications`
//
// The top-nav bell opens a 30-item panel; this is the full list with the
// read/unread controls the panel deliberately leaves out. Writes are
// individual (`PATCH …/read`) so reading one item does not silently clear
// every other unread one the way `mark-all-read` would.

import { api, esc, toast } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { syncBadge, confirmAction } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';

// Server sends `type`; nothing outside this file needs to know the mapping.
const TYPE_META = {
  SYSTEM: { icon: 'bell', tone: 'info', label: 'System' },
  ACHIEVEMENT: { icon: 'trophy', tone: 'ok', label: 'Achievement' },
  RELEASE: { icon: 'send', tone: 'warn', label: 'Release' },
  FEEDBACK: { icon: 'message', tone: 'info', label: 'Feedback' },
  WARNING: { icon: 'ban', tone: 'bad', label: 'Warning' },
};

const state = { filter: 'all', items: [] };

export async function render(root, ctx) {
  root.innerHTML = ui.head({
    title: 'Notifications',
    sub: 'Everything the portal has told you, newest first.',
    actions: '<button class="btn ghost sm" data-all-read>Mark all read</button>',
  })
    + `<div class="pillbar">
        <button data-filter="all" class="active">All</button>
        <button data-filter="unread">Unread</button>
        <span class="pillbar-gap"></span>
        <span data-count class="sm muted"></span>
      </div>`
    + `<div data-body class="stack">${ui.loading('notifications')}</div>`;

  ui.click(root, '[data-filter]', (e, btn) => {
    state.filter = btn.dataset.filter;
    root.querySelectorAll('[data-filter]').forEach((b) =>
      b.classList.toggle('active', b.dataset.filter === state.filter));
    paint(root.querySelector('[data-body]'));
  });

  ui.click(root, '[data-all-read]', async (e, btn) => {
    const unread = state.items.filter((n) => !n.read).length;
    if (!unread) { toast('Nothing unread.'); return; }
    const ok = await confirmAction('Mark everything read?',
      `${unread} notification${unread === 1 ? '' : 's'} will be cleared.`, 'Mark all read');
    if (!ok) return;
    try {
      await ui.busy(btn, 'Marking…', async () => {
        await api('/v1/notifications/mark-all-read', { method: 'POST', body: '{}' });
        state.items = state.items.map((n) => ({ ...n, read: true }));
        paint(root.querySelector('[data-body]'));
        syncBadge();
        toast('All marked as read.');
      });
    } catch (err) { toast(err.message, 'warn'); }
  });

  await load(root);
  return { destroy: () => {} };
}

async function load(root) {
  const host = root.querySelector('[data-body]');
  host.innerHTML = ui.loading('notifications');
  try {
    // Returned bare as `{items:[…}` — no success envelope on this route.
    const res = await api('/v1/notifications/my?limit=200');
    const items = (res && Array.isArray(res.items) && res.items)
      || (res && res.data && res.data.items)
      || (Array.isArray(res) ? res : []);
    state.items = items;
    paint(host);
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function paint(host) {
  const shown = state.filter === 'unread'
    ? state.items.filter((n) => !n.read) : state.items;
  const unread = state.items.filter((n) => !n.read).length;

  const counter = document.querySelector('[data-count]');
  if (counter) {
    counter.textContent = unread
      ? `${unread} unread of ${state.items.length}`
      : `${state.items.length} total`;
  }

  if (!shown.length) {
    host.innerHTML = ui.blank({
      title: state.filter === 'unread' ? 'You are all caught up' : 'No notifications',
      body: state.filter === 'unread'
        ? 'Nothing is waiting on you.'
        : 'Course releases, certificates and account notices land here.',
      action: 'Open the feed',
      actionHref: '#/feed',
    });
    return;
  }

  host.innerHTML = shown.map(row).join('');

  ui.click(host, '[data-read]', async (e, btn) => {
    const id = btn.closest('[data-id]').dataset.id;
    try {
      await ui.busy(btn, '…', async () => {
        await api(`/v1/notifications/${encodeURIComponent(id)}/read`,
          { method: 'PATCH' });
        state.items = state.items.map((n) => (n.id === id ? { ...n, read: true } : n));
        paint(host);
        syncBadge();
      });
    } catch (err) { toast(err.message, 'warn'); }
  });
}

function row(n) {
  const meta = TYPE_META[n.type] || TYPE_META.SYSTEM;
  // Portal paths become hash routes; a full address is opened as-is. The
  // composer accepts both, so honour both here rather than prefixing an
  // `https://` with `#`.
  const raw = n.link ? String(n.link) : '';
  const href = /^https?:\/\//i.test(raw) ? raw : '#' + raw.replace(/^#/, '');
  return `
    <div class="notif-row${n.read ? '' : ' is-unread'}" data-id="${esc(n.id)}">
      <span class="notif-ico">${iconSvg(meta.icon)}</span>
      <div class="notif-main">
        <div class="row gap">
          <b>${esc(n.title)}</b>
          ${n.read ? '' : '<span class="tag info">New</span>'}
        </div>
        ${n.message ? `<p>${esc(n.message)}</p>` : ''}
        <div class="sm muted">${esc(ui.relTime(n.created_at))}
          <span class="tag mute">${esc(meta.label)}</span></div>
      </div>
      <div class="notif-side">
        ${href ? `<a class="btn ghost sm" href="${esc(href)}">Open</a>` : ''}
        ${n.read ? '' : '<button class="btn ghost sm" data-read>Mark read</button>'}
      </div>
    </div>`;
}
