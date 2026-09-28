// Learnify — the home feed.
// Route: `/feed`
//
// Four post types published by Supreme: Notification · Announcement ·
// Achievement · New Content. `embed()` lets a role dashboard drop the same feed
// into its own page without re-implementing any of it.

import { api, esc, toast, el } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { currentUser, openAppModal, closeAppModal, confirmAction } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';

export const POST_TYPES = ['NOTIFICATION', 'ANNOUNCEMENT', 'ACHIEVEMENT', 'NEW_CONTENT'];

const META = {
  NOTIFICATION: { label: 'Notification', icon: 'bell', tone: 'info' },
  ANNOUNCEMENT: { label: 'Announcement', icon: 'megaphone', tone: 'warn' },
  ACHIEVEMENT: { label: 'Achievement', icon: 'trophy', tone: 'ok' },
  NEW_CONTENT: { label: 'New content', icon: 'bookOpen', tone: 'ok' },
};

const state = { type: '', q: '' };
let debounce = 0;

// ─── Full page ──────────────────────────────────────────────────────────────

export async function render(root, ctx) {
  const user = currentUser();
  const isSupreme = user && user.role === 'SUPREME';

  root.innerHTML = ui.head({
    title: 'Home feed',
    sub: isSupreme
      ? 'Everything the organisation sees, in one place. You publish these.'
      : 'Notifications, announcements, achievements and new content — newest first.',
    actions: isSupreme
      ? `<button class="btn ghost sm" data-manage>Drafts</button>
         <button class="btn primary sm" data-new>+ New post</button>`
      : '',
  })
    + '<div data-filters></div>'
    + `<div data-list>${ui.loading('feed')}</div>`;

  if (isSupreme) {
    ui.click(root, '[data-new]', () => openComposer(null));
    ui.click(root, '[data-manage]', () => openManage(root));
  }

  buildFilters(root.querySelector('[data-filters]'), isSupreme);
  const paint = () => load(root.querySelector('[data-list]'), { limit: 60 });
  paint();

  return { destroy: () => clearTimeout(debounce) };
}

function buildFilters(host, isSupreme) {
  host.innerHTML = `
    <div class="toolbar">
      <div class="grow"><input type="search" name="q" placeholder="Search the feed…"
        value="${esc(state.q)}" aria-label="Search the feed"></div>
      <select name="type" aria-label="Filter by post type">
        <option value="">All types</option>
        ${POST_TYPES.map((t) => `<option value="${t}"${
          state.type === t ? ' selected' : ''}>${META[t].label}</option>`).join('')}
      </select>
    </div>`;

  const apply = () => {
    state.q = host.querySelector('[name=q]').value.trim();
    state.type = host.querySelector('[name=type]').value;
    const list = host.parentElement.querySelector('[data-list]');
    if (list) load(list, { limit: 60 });
  };

  host.querySelector('[name=q]').addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(apply, 320);
  });
  host.querySelector('[name=type]').addEventListener('change', apply);
}

// ─── Shared renderer (also used by the role dashboards) ────────────────────

/**
 * Load the caller's feed into `host`. Returns a promise resolving to a
 * cleanup function, so an embedding dashboard can tear down on re-render.
 */
export async function embed(host, opts = {}) {
  host.innerHTML = ui.loading('updates');
  try {
    const items = await fetchPosts(opts);
    host.innerHTML = items.length
      ? items.map((p) => card(p, opts.manage && currentUser().role === 'SUPREME')).join('')
      : ui.blank({
          title: 'Nothing new yet',
          body: 'When an administrator posts something for your role it lands here.',
        });
    if (opts.manage && currentUser().role === 'SUPREME') bindCards(host);
    return () => {};
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
    return () => {};
  }
}

async function fetchPosts(opts) {
  const p = new URLSearchParams();
  if (state.type) p.set('post_type', state.type);
  if (state.q) p.set('q', state.q);
  if (opts.limit) p.set('limit', String(opts.limit));
  if (opts.all) {
    const res = await api('/v1/feed/all/manage?' + p.toString());
    return ui.data(res) || [];
  }
  const res = await api('/v1/feed?' + p.toString());
  return ui.data(res) || [];
}

async function load(target, opts) {
  target.innerHTML = ui.loading('updates');
  try {
    const items = await fetchPosts(opts);
    const supreme = currentUser().role === 'SUPREME';
    target.innerHTML = items.length
      ? items.map((p) => card(p, supreme)).join('')
      : ui.blank({
          title: state.q || state.type ? 'Nothing matches' : 'Nothing new yet',
          body: state.q || state.type
            ? 'Try a different search or clear the type filter.'
            : 'When an administrator posts something for your role it lands here.',
        });
    if (supreme) bindCards(target);
  } catch (err) {
    target.innerHTML = ui.errorBlock(err.message);
  }
}

export function card(p, canManage = false) {
  const meta = META[p.type] || META.NOTIFICATION;
  const isDraft = p.published === false;
  return `
    <article class="post${p.pinned ? ' pinned' : ''}${isDraft ? ' draft' : ''}" data-post="${esc(p.id)}">
      <div class="post-head">
        <span class="post-ico tone-${meta.tone}">${iconSvg(meta.icon)}</span>
        <div class="post-meta">
          <span class="tag ${meta.tone}">${esc(meta.label)}</span>
          ${p.pinned ? '<span class="tag warn">Pinned</span>' : ''}
          ${isDraft ? '<span class="tag mute">Draft</span>' : ''}
          <time class="sm muted">${esc(ui.relTime(p.published_at || p.created_at))}</time>
        </div>
        ${canManage ? `
          <div class="post-actions">
            <button class="icon-btn" data-act="pin" title="${p.pinned ? 'Unpin' : 'Pin'}">
              ${iconSvg('flag')}</button>
            <button class="icon-btn" data-act="edit" title="Edit">${iconSvg('edit')}</button>
            <button class="icon-btn" data-act="del" title="Delete">${iconSvg('trash')}</button>
          </div>` : ''}
      </div>
      <h3 class="post-title">${esc(p.title)}</h3>
      ${p.body ? `<p class="post-body">${esc(p.body)}</p>` : ''}
      ${p.image_url ? `<img class="post-img" src="${esc(p.image_url)}" alt="" loading="lazy">` : ''}
      ${p.link ? `<a class="link" href="${esc(p.link)}" target="_blank" rel="noopener">
        ${esc(p.link)} &rarr;</a>` : ''}
      ${canManage && Array.isArray(p.target_roles) && p.target_roles.length < 3
        ? `<p class="sm muted">Audience: ${p.target_roles.map(esc).join(', ')}</p>` : ''}
    </article>`;
}

function bindCards(host) {
  ui.click(host, '[data-post] [data-act]', async (e, btn) => {
    e.preventDefault();
    const id = btn.closest('[data-post]').dataset.post;
    const act = btn.dataset.act;
    if (act === 'pin') {
      try {
        await api(`/v1/feed/${id}/pin`, { method: 'POST', body: '{}' });
        refresh(host);
      } catch (err) { toast(err.message, 'warn'); }
    } else if (act === 'edit') {
      try {
        const row = ui.data(await api(`/v1/feed/${id}`));
        openComposer(row, host);
      } catch (err) { toast(err.message, 'warn'); }
    } else if (act === 'del') {
      const ok = await confirmAction('Delete this post?',
        'It disappears from everyone\'s feed immediately.', 'Delete');
      if (!ok) return;
      try {
        await api(`/v1/feed/${id}`, { method: 'DELETE' });
        toast('Post deleted.');
        refresh(host);
      } catch (err) { toast(err.message, 'warn'); }
    }
  });
}

function refresh(host) {
  const page = host.closest('.stage') && host.hasAttribute('data-list');
  if (page) load(host, { limit: 60 });
  else load(host, { limit: 40 });
}

// ─── Composer ───────────────────────────────────────────────────────────────

function openComposer(existing, host) {
  const roles = (existing && existing.target_roles) || ['SUPREME', 'MASTER', 'ALPHA'];
  openAppModal(`
    <h3 class="modal-title">${existing ? 'Edit post' : 'New post'}</h3>
    <p class="modal-sub">Visible to the roles you tick. Published posts hit the feed at once.</p>
    <form id="post-form" class="stack" novalidate>
      <div class="field">
        <label for="p-type">Type</label>
        <select id="p-type" name="type">
          ${POST_TYPES.map((t) => `<option value="${t}"${
            existing && existing.type === t ? ' selected' : ''}>${META[t].label}</option>`).join('')}
        </select>
      </div>
      <div class="field">
        <label for="p-title">Title</label>
        <input id="p-title" name="title" maxlength="200" required
               value="${esc((existing && existing.title) || '')}"
               placeholder="e.g. Results day timetable">
      </div>
      <div class="field">
        <label for="p-body">Body</label>
        <textarea id="p-body" name="body" rows="4" maxlength="4000"
                  placeholder="Keep it short and factual.">${esc((existing && existing.body) || '')}</textarea>
      </div>
      <div class="field">
        <label for="p-link">Link (optional)</label>
        <input id="p-link" name="link" value="${esc((existing && existing.link) || '')}"
               placeholder="https://…">
      </div>
      <div class="field">
        <label>Audience</label>
        <div class="wrap">
          ${['ALPHA', 'MASTER', 'SUPREME'].map((r) => `
            <label class="chk"><input type="checkbox" name="role_${r}"
              ${roles.includes(r) ? 'checked' : ''}> ${r}</label>`).join('')}
        </div>
      </div>
      <div class="wrap">
        <label class="chk"><input type="checkbox" name="pinned"
          ${existing && existing.pinned ? 'checked' : ''}> Pinned</label>
        <label class="chk"><input type="checkbox" name="published"
          ${!existing || existing.published !== false ? 'checked' : ''}> Published</label>
      </div>
      <div class="auth-err" data-err role="alert"></div>
      <div class="row gap" style="justify-content:flex-end">
        <button type="button" class="btn ghost sm" data-cancel>Cancel</button>
        <button type="submit" class="btn primary sm">${existing ? 'Save changes' : 'Publish'}</button>
      </div>
    </form>`);

  const body = el('app-modal-body');
  const form = body.querySelector('#post-form');
  body.querySelector('[data-cancel]').addEventListener('click', closeAppModal);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const errBox = body.querySelector('[data-err]');
    errBox.textContent = '';

    const title = form.title.value.trim();
    if (!title) { errBox.textContent = 'A title is required.'; return; }

    const target = ['ALPHA', 'MASTER', 'SUPREME']
      .filter((r) => form.querySelector(`[name=role_${r}]`).checked);
    if (!target.length) { errBox.textContent = 'Pick at least one audience.'; return; }

    const payload = {
      type: form.type.value,
      title,
      body: form.body.value.trim(),
      link: form.link.value.trim(),
      target_roles: target,
      pinned: form.pinned.checked,
      published: form.published.checked,
    };

    try {
      if (existing) await api(`/v1/feed/${existing.id}`, { method: 'PUT', body: JSON.stringify(payload) });
      else await api('/v1/feed', { method: 'POST', body: JSON.stringify(payload) });
      closeAppModal();
      toast(existing ? 'Post updated.' : (payload.published ? 'Published.' : 'Saved as a draft.'));
      if (host) refresh(host);
      else window.dispatchEvent(new HashChangeEvent('hashchange'));
    } catch (err) {
      errBox.textContent = err.message;
    }
  });
}

async function openManage(root) {
  const host = root.querySelector('[data-list]');
  host.innerHTML = ui.loading('all posts');
  try {
    const rows = ui.data(await api('/v1/feed/all/manage?limit=200')) || [];
    host.innerHTML = ui.head({
      title: 'All posts',
      sub: 'Including drafts you have not published yet.',
      actions: '<button class="btn ghost sm" data-back>Back to feed</button>',
    }) + (rows.length
      ? `<div class="stack">${rows.map((p) => card(p, true)).join('')}</div>`
      : ui.blank({ title: 'No posts yet', body: 'Create one with the button above.' }));
    ui.click(host, '[data-back]', () => load(host, { limit: 60 }));
    bindCards(host);
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}
