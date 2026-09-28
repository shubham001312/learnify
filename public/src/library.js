// Learnify — trainer library.
// Route: `/library`
//
// Everyone browses; only MASTER/SUPREME may add, edit or delete. An item is
// metadata plus either an uploaded file (private bucket, opened through a
// short-lived signed URL) or a YouTube reference. Follows the courses.js
// pattern: fetch with `api()`, unwrap with `ui.data()`, render with `ui.*`,
// bind through `ui.click(root, ...)` and return `{ destroy }` for timers.

import { api, apiForm, esc, toast } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { go, confirmAction, currentUser, openAppModal, closeAppModal } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';

const FILE_TYPES = ['RECORDED_LECTURE', 'PRESENTATION', 'STUDY_MATERIAL'];
const TYPE_LABEL = {
  RECORDED_LECTURE: 'Recorded lecture',
  PRESENTATION: 'Presentation',
  STUDY_MATERIAL: 'Study material',
};
const BUCKET = 'trainer-library';
const VIDEO_LIMIT = 100 * 1024 * 1024;
const DOC_LIMIT = 50 * 1024 * 1024;

// `filters` is module state so a re-render keeps the search intact, but every
// `render` — the entry point for a fresh visit to the route — resets it.
const filters = { q: '', type: '', subject: '', mine: false };
const view = { root: null, body: null, canAuthor: false, subjects: [], offs: [], toolbarOffs: [] };
let debounce = 0;
let seq = 0;    // stale-response guard for the list
let epoch = 0;  // stale-render guard: bumped by every render and by teardown

// The modal host (#app-modal-body) outlives the view, so its listeners are
// tracked explicitly and released on close and on route teardown.
const modal = { offs: [], stamp: 0 };

// ─── Page ──────────────────────────────────────────────────────────────────

export async function render(root, ctx) {
  const myEpoch = ++epoch;
  clearOffs();
  const user = currentUser() || ctx.user;
  const canAuthor = !!user && (user.role === 'MASTER' || user.role === 'SUPREME');

  filters.q = ''; filters.type = ''; filters.subject = ''; filters.mine = false;

  view.root = root;
  view.body = null;
  view.canAuthor = canAuthor;
  view.subjects = [];

  root.innerHTML = ui.head({
    title: 'Library',
    sub: canAuthor
      ? 'Your reusable lectures, decks and notes — file them once, reuse them anywhere.'
      : 'Recorded lectures, presentations and study material shared by your trainers.',
    actions: canAuthor ? '<button class="btn primary sm" data-add>+ Add item</button>' : '',
  }) + '<div data-body>' + ui.loading('library items') + '</div>';

  const body = root.querySelector('[data-body]');
  view.body = body;

  // Subject options come from the catalogue, not hardcoded.
  let subjects = [];
  try {
    const res = await api('/v1/subjects?limit=200');
    subjects = ui.data(res) || [];
  } catch (_) { subjects = []; }

  // The route changed (or this view was torn down) while we were waiting, so
  // painting now would clobber whatever replaced us. Return no `destroy` so
  // app.js keeps the handle of the module that actually owns the screen.
  if (epoch !== myEpoch) return;
  view.subjects = subjects;

  if (canAuthor) {
    view.offs.push(ui.click(root, '[data-add]', () => openCreate()));
    view.offs.push(ui.click(root, '[data-open]', (e, el) => openDetail(el.dataset.open)));
    view.offs.push(ui.on(root, '[data-open]', 'keydown', (e, el) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDetail(el.dataset.open);
      }
    }));
  }
  view.offs.push(ui.click(root, '[data-clear]', () => {
    filters.q = ''; filters.type = ''; filters.subject = ''; filters.mine = false;
    paintToolbar();
    load();
  }));
  view.offs.push(ui.click(root, '[data-retry]', (e) => { e.preventDefault(); load(); }));

  paintToolbar();
  load();

  return { destroy: teardown };
}

function teardown() {
  epoch += 1;   // any render still in flight must not paint after this
  seq += 1;     // ...and any list fetch still in flight must not resolve
  clearTimeout(debounce);
  clearOffs();
  clearToolbarOffs();
  closeModal();
}

function clearOffs() {
  view.offs.forEach((off) => { try { off(); } catch (_) { /* already unbound */ } });
  view.offs = [];
}

function clearToolbarOffs() {
  view.toolbarOffs.forEach((off) => { try { off(); } catch (_) { /* already unbound */ } });
  view.toolbarOffs = [];
}

// ─── Toolbar + list ────────────────────────────────────────────────────────

function paintToolbar() {
  const root = view.root;
  if (!root) return;
  clearToolbarOffs();
  const old = root.querySelector('.toolbar');
  if (old) old.remove();

  const bar = document.createElement('div');
  bar.className = 'toolbar';
  bar.innerHTML = `
    <div class="grow"><input type="search" name="q" placeholder="Search the library…"
      maxlength="80" value="${esc(filters.q)}" aria-label="Search the library"></div>
    <select name="type" aria-label="Filter by type">
      <option value="">All types</option>
      ${FILE_TYPES.map((t) => `<option value="${t}"${
        filters.type === t ? ' selected' : ''}>${esc(TYPE_LABEL[t])}</option>`).join('')}
    </select>
    <select name="subject" aria-label="Filter by subject">
      <option value="">All subjects</option>
      ${view.subjects.map((s) => `<option value="${esc(s.id)}"${
        filters.subject === s.id ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}
    </select>
    ${view.canAuthor ? `<button class="btn ghost sm${filters.mine ? ' active' : ''}" data-mine>
      Mine only</button>` : ''}
    <button class="btn primary sm" data-apply>Apply</button>`;

  root.insertBefore(bar, root.querySelector('[data-body]'));

  const sync = () => {
    filters.q = bar.querySelector('[name=q]').value.trim();
    filters.type = bar.querySelector('[name=type]').value;
    filters.subject = bar.querySelector('[name=subject]').value;
  };
  const apply = () => { clearTimeout(debounce); sync(); load(); };
  const toggleMine = () => {
    sync();
    filters.mine = !filters.mine;
    const btn = bar.querySelector('[data-mine]');
    if (btn) btn.classList.toggle('active', filters.mine);
    load();
  };

  view.toolbarOffs.push(ui.click(bar, '[data-apply]', apply));
  view.toolbarOffs.push(ui.click(bar, '[data-mine]', toggleMine));
  view.toolbarOffs.push(ui.on(bar, '[name=q]', 'input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(apply, 320);
  }));
  view.toolbarOffs.push(ui.on(bar, '[name=type]', 'change', apply));
  view.toolbarOffs.push(ui.on(bar, '[name=subject]', 'change', apply));
}

async function load() {
  const target = view.body;
  if (!target) return;
  const stamp = ++seq;
  target.innerHTML = ui.loading('library items');

  try {
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.type) params.set('file_type', filters.type);
    if (filters.subject) params.set('subject_id', filters.subject);
    if (filters.mine) params.set('mine', 'true');
    params.set('limit', '120');

    const res = await api('/v1/library?' + params.toString());
    if (stamp !== seq) return;
    const rows = ui.data(res) || [];
    target.innerHTML = rows.length
      ? `<div class="cc-grid three">${rows.map((r) => card(r)).join('')}</div>
         <p class="muted sm center mt">${rows.length} item${
           rows.length === 1 ? '' : 's'} shown</p>`
      : emptyState();
  } catch (err) {
    if (stamp !== seq) return;
    target.innerHTML = ui.errorBlock(err.message);
  }
}

function emptyState() {
  const filtered = filters.q || filters.type || filters.subject || filters.mine;
  if (!filtered) {
    const body = view.canAuthor
      ? 'Add the first recorded lecture, presentation or study material.'
      : 'Nothing has been shared here yet.';
    return `
      <div class="blank">
        <b>The library is empty</b>
        <p>${esc(body)}</p>
        ${view.canAuthor ? '<button class="btn primary sm" data-add>+ Add item</button>' : ''}
      </div>`;
  }
  return `
    <div class="blank">
      <b>No items match</b>
      <p>Try clearing the search or choosing a different type or subject.</p>
      <button class="btn ghost sm" data-clear>Clear filters</button>
    </div>`;
}

function card(it) {
  const desc = String(it.description || '');
  const openable = view.canAuthor;
  const label = TYPE_LABEL[it.file_type] || it.file_type || 'Item';
  return `
    <div class="cc-card lib-card${openable ? ' openable' : ''}"${
      openable ? ` data-open="${esc(it.id)}" role="button" tabindex="0"` : ''}>
      <div class="cc-card-head">
        ${it.file_type === 'RECORDED_LECTURE'
          ? `<span class="lib-play" aria-hidden="true">${iconSvg('play')}</span>` : ''}
        <span class="tag mute">${esc(label)}</span>
        ${it.has_youtube ? '<span class="tag info">YouTube</span>' : ''}
      </div>
      <h3>${esc(it.title)}</h3>
      <p>${esc(desc.slice(0, 150))}${desc.length > 150 ? '…' : ''}</p>
      <div class="card-foot">
        ${it.subject_name ? `<span class="role-tag">${esc(it.subject_name)}</span>` : ''}
        <span class="grow"></span>
        ${it.duration_seconds ? `<span class="sm muted">${esc(fmtDur(it.duration_seconds))}</span>` : ''}
        ${it.trainer_name ? `<span class="sm dim">${esc(it.trainer_name)}</span>` : ''}
      </div>
    </div>`;
}

function fmtDur(sec) {
  const s = Math.max(0, Number(sec) || 0);
  if (!s) return '';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

// ─── Modal plumbing ────────────────────────────────────────────────────────

function mountModal(html) {
  modal.offs.forEach((off) => { try { off(); } catch (_) { /* already unbound */ } });
  modal.offs = [];
  openAppModal(html);
  modal.stamp += 1;
  const card = document.getElementById('app-modal-card');
  if (card) card.classList.add('lib-wide');
  // The shell's own X and backdrop close bypass this module, so mirror them —
  // otherwise the wide card and the handlers below would outlive the modal.
  modal.offs.push(ui.on(document, '#app-modal [data-close]', 'click', () => closeModal()));
  modal.offs.push(ui.on(document, '#app-modal', 'click', (e) => {
    if (e.target && e.target.id === 'app-modal') closeModal();
  }));
  return document.getElementById('app-modal-body');
}

function closeModal() {
  modal.offs.forEach((off) => { try { off(); } catch (_) { /* already unbound */ } });
  modal.offs = [];
  modal.stamp += 1;
  const card = document.getElementById('app-modal-card');
  if (card) card.classList.remove('lib-wide');
  closeAppModal();
}

// ─── Item detail ───────────────────────────────────────────────────────────

async function openDetail(id) {
  mountModal(`<h3 class="modal-title">Library item</h3>${ui.loading('item')}`);
  const stamp = modal.stamp;

  try {
    const [iRes, sRes] = await Promise.all([
      api(`/v1/library/${encodeURIComponent(id)}`),
      api(`/v1/library/${encodeURIComponent(id)}/stats`).catch(() => null),
    ]);
    if (stamp !== modal.stamp) return;
    const item = ui.data(iRes);
    if (!item || !item.id) throw new Error('That library item could not be found.');
    const stats = sRes ? ui.data(sRes) : null;
    const body = mountModal(detailHtml(item, stats));
    paintDetailStars(body, stats);
    bindDetail(body, item);
  } catch (err) {
    if (stamp !== modal.stamp) return;
    const body = mountModal(`
      <h3 class="modal-title">Item unavailable</h3>
      <p class="modal-sub">${esc(err.message)}</p>
      <div class="row gap" style="justify-content:flex-end">
        <button class="btn ghost sm" data-cancel-detail>Close</button>
      </div>`);
    modal.offs.push(ui.click(body, '[data-cancel-detail]', () => closeModal()));
  }
}

function detailHtml(item, stats) {
  const label = TYPE_LABEL[item.file_type] || item.file_type || 'Item';
  const playable = !!(item.has_youtube || item.storage_path);
  const isVideo = item.file_type === 'RECORDED_LECTURE' && playable;
  const count = Number((stats && stats.count) || 0);

  return `
    <h3 class="modal-title">${esc(item.title)}</h3>
    <div class="wrap mb">
      <span class="tag mute">${esc(label)}</span>
      ${item.subject_name ? `<span class="tag info">${esc(item.subject_name)}</span>` : ''}
      ${item.has_youtube ? '<span class="tag mute">YouTube</span>' : ''}
    </div>
    <p class="page-sub" style="margin:0 0 12px">${
      esc(item.description || 'No description has been added yet.')}</p>

    <div class="lib-preview" data-preview-slot>
      ${isVideo
        ? '<button class="btn primary sm" data-preview>Preview video</button>'
        : item.storage_path
          ? '<button class="btn ghost sm" data-download>Open file</button>'
          : '<p class="sm muted">No file is attached to this item yet.</p>'}
    </div>

    ${ui.kv([
      ['Owner', item.trainer_name || ''],
      ['Designation', item.trainer_designation || ''],
      ['Subject', item.subject_name || ''],
      ['Duration', item.duration_seconds ? fmtDur(item.duration_seconds) : ''],
      ['Size', item.size_mb ? `${item.size_mb} MB` : ''],
      ['Format', item.mime || ''],
      ['Added', ui.fmtDate(item.created_at)],
    ])}

    <div class="lib-stats">
      <div class="lib-stats-head">
        <div data-detail-stars></div>
        <span class="sm muted">${count
          ? `${count} rating${count === 1 ? '' : 's'}`
          : 'No ratings yet'}</span>
      </div>
      ${recentList(stats)}
    </div>

    ${item.can_edit ? `
      <div class="row gap mt">
        <button class="btn primary sm" data-edit>Edit</button>
        <button class="btn ghost sm" data-del>Delete</button>
      </div>` : ''}`;
}

function recentList(stats) {
  const rows = ((stats && stats.recent) || [])
    .filter((r) => r && (r.comment || '').trim())
    .slice(0, 3);
  if (!rows.length) return '';
  return `<ul class="lib-recent">${rows.map((r) => `
    <li>
      <span class="sm muted">${esc(ui.relTime(r.created_at))} · ${
        esc(String(Number(r.rating) || 0))} / 5</span>
      <p>${esc(r.comment)}</p>
    </li>`).join('')}</ul>`;
}

function paintDetailStars(body, stats) {
  const el = body.querySelector('[data-detail-stars]');
  if (!el) return;
  ui.stars(el, { value: Number((stats && stats.average) || 0), id: 'lib-avg' });
  const box = el.querySelector('.stars');
  if (box) box.classList.add('readonly');
}

function bindDetail(body, item) {
  modal.offs.push(ui.click(body, '[data-preview]', () => {
    const slot = body.querySelector('[data-preview-slot]');
    if (slot) preview(item, slot);
  }));
  modal.offs.push(ui.click(body, '[data-download]', (e, btn) => downloadFile(item, body)));
  modal.offs.push(ui.click(body, '[data-edit]', () => openEdit(item)));
  modal.offs.push(ui.click(body, '[data-del]', async () => {
    const ok = await confirmAction(
      'Delete this library item?',
      'The item and its uploaded file are removed for everyone. This cannot be undone.',
      'Delete item');
    if (!ok) { openDetail(item.id); return; }
    try {
      await api(`/v1/library/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
      toast('Library item deleted.');
      closeModal();
      load();
    } catch (err) {
      toast(err.message, 'warn');
      openDetail(item.id);
    }
  }));
}

/** Signed URL -> <video> (or a YouTube embed when the item is linked). */
async function preview(item, slot) {
  slot.innerHTML = ui.loading('preview');
  if (item.youtube_id) {
    slot.innerHTML = `<iframe class="lib-video" title="Video preview" allowfullscreen
      src="https://www.youtube.com/embed/${
        esc(encodeURIComponent(String(item.youtube_id)))}"></iframe>`;
    return;
  }
  if (!item.storage_path) {
    slot.innerHTML = '<p class="sm muted">No video file is attached to this item.</p>';
    return;
  }
  try {
    const d = ui.data(await signUrl(item)) || {};
    if (!d.url) throw new Error('The video link could not be created.');
    slot.innerHTML = `<video class="lib-video" controls preload="metadata" src="${
      esc(d.url)}"></video>`;
  } catch (err) {
    slot.innerHTML = ui.errorBlock(err.message);
  }
}

async function downloadFile(item, body) {
  if (!item.storage_path) return;
  try {
    const d = ui.data(await signUrl(item)) || {};
    if (!d.url) throw new Error('The download link could not be created.');
    const w = window.open(d.url, '_blank', 'noopener');
    if (w) return;
    // Popup blocked — hand the user a link instead.
    const slot = body && body.querySelector('[data-preview-slot]');
    if (slot) {
      slot.innerHTML = `<a class="btn primary sm" href="${esc(d.url)}"
        target="_blank" rel="noopener">Open file</a>`;
    }
  } catch (err) {
    toast(err.message, 'warn');
  }
}

function signUrl(item) {
  const params = new URLSearchParams({
    path: item.storage_path,
    bucket: item.bucket || BUCKET,
    expires: '3600',
  });
  return api('/v1/library/files/sign?' + params.toString());
}

// ─── Create / edit ─────────────────────────────────────────────────────────

function openCreate() {
  const body = mountModal(formHtml({ item: null, subjects: view.subjects }));
  bindForm(body, null);
}

function openEdit(item) {
  const body = mountModal(formHtml({ item, subjects: view.subjects }));
  bindForm(body, item);
}

function formHtml({ item, subjects }) {
  const isEdit = !!item;
  const minutes = Math.round((Number(item && item.duration_seconds) || 0) / 60);
  return `
    <h3 class="modal-title">${isEdit ? 'Edit library item' : 'Add library item'}</h3>
    <p class="modal-sub">${isEdit
      ? 'Update how this item is described and filed.'
      : 'Share a recorded lecture, a presentation or study material.'}</p>
    <form class="lib-form" novalidate>
      ${isEdit ? '' : `
        <div class="seg">
          <button type="button" class="seg-btn active" data-mode="upload">Upload a file</button>
          <button type="button" class="seg-btn" data-mode="youtube">YouTube link</button>
        </div>`}

      <div class="field">
        <label for="lib-title">Title</label>
        <input id="lib-title" name="title" maxlength="200" required
          value="${esc(item ? item.title : '')}"
          placeholder="e.g. Heat engines — Lecture 4">
      </div>

      <div class="field">
        <label for="lib-desc">Description</label>
        <textarea id="lib-desc" name="description" rows="3" maxlength="2000"
          placeholder="One or two lines on what this covers.">${
            esc(item ? item.description : '')}</textarea>
      </div>

      <div class="lib-two">
        <div class="field">
          <label for="lib-type">Type</label>
          <select id="lib-type" name="file_type">
            ${FILE_TYPES.map((t) => `<option value="${t}"${
              (item ? item.file_type : 'RECORDED_LECTURE') === t ? ' selected' : ''}>${
              esc(TYPE_LABEL[t])}</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label for="lib-subject">Subject</label>
          <select id="lib-subject" name="subject_id">
            <option value="">No subject</option>
            ${subjects.map((s) => `<option value="${esc(s.id)}"${
              item && item.subject_id === s.id ? ' selected' : ''}>${
              esc(s.name)}</option>`).join('')}
          </select>
        </div>
      </div>

      <div class="field">
        <label for="lib-duration">Approx. duration (minutes)</label>
        <input id="lib-duration" name="duration" type="number" min="0" max="1440"
          step="1" value="${minutes || ''}" placeholder="0">
      </div>

      ${isEdit ? fileSummary(item) : `
        <div class="field" data-pane="upload">
          <label for="lib-file">File</label>
          <input id="lib-file" name="file" type="file"
            accept="video/*,.pdf,.doc,.docx,.ppt,.pptx,.xls,.png,.jpg,.jpeg,.webp,.txt">
          <p class="sm muted mt">Video up to 100 MB, other files up to 50 MB.</p>
        </div>
        <div class="field" data-pane="youtube" hidden>
          <label for="lib-yt">YouTube link</label>
          <input id="lib-yt" name="youtube_url" type="url"
            placeholder="https://www.youtube.com/watch?v=...">
        </div>`}

      <p class="auth-err" data-err></p>

      <div class="row gap mt lib-form-foot">
        <span class="grow"></span>
        <button type="button" class="btn ghost sm" data-cancel>Cancel</button>
        <button type="submit" class="btn primary sm" data-save>${
          isEdit ? 'Save changes' : 'Create item'}</button>
      </div>
    </form>`;
}

function fileSummary(item) {
  if (item.storage_path) {
    return `
      <div class="field">
        <label>Attached file</label>
        <p class="sm muted">${esc(item.mime || 'Uploaded file')}${
          item.size_mb ? ` · ${esc(String(item.size_mb))} MB` : ''}</p>
      </div>`;
  }
  if (item.has_youtube) {
    return `
      <div class="field">
        <label>Video</label>
        <p class="sm muted">Linked YouTube video</p>
      </div>`;
  }
  return `
    <div class="field">
      <label>Attached file</label>
      <p class="sm muted">No file is attached to this item yet.</p>
    </div>`;
}

function bindForm(body, item) {
  let mode = 'upload';

  const setMode = (next) => {
    mode = next;
    body.querySelectorAll('[data-mode]').forEach((b) =>
      b.classList.toggle('active', b.dataset.mode === next));
    const up = body.querySelector('[data-pane="upload"]');
    const yt = body.querySelector('[data-pane="youtube"]');
    if (up) up.hidden = next !== 'upload';
    if (yt) yt.hidden = next !== 'youtube';
    // A YouTube link is only valid on a recorded lecture.
    const ft = body.querySelector('[name=file_type]');
    if (ft && next === 'youtube') ft.value = 'RECORDED_LECTURE';
  };

  modal.offs.push(ui.click(body, '[data-mode]', (e, btn) => setMode(btn.dataset.mode)));
  modal.offs.push(ui.click(body, '[data-cancel]', () => {
    if (item) openDetail(item.id);
    else closeModal();
  }));
  modal.offs.push(ui.on(body, 'form', 'submit', (e, form) => {
    e.preventDefault();
    const btn = form.querySelector('[data-save]');
    const label = item ? 'Saving…' : (mode === 'youtube' ? 'Adding…' : 'Uploading…');
    ui.busy(btn, label, async () => {
      try {
        await save(form, item, mode);
      } catch (err) {
        ui.formError(form, err.message);
      }
    });
  }));
}

async function save(form, item, mode) {
  const v = ui.formValues(form);
  const title = String(v.title || '').trim();
  const description = String(v.description || '').trim();
  const file_type = String(v.file_type || 'RECORDED_LECTURE');
  const subject_id = String(v.subject_id || '');
  const minutes = Math.max(0, Math.min(1440, Number(v.duration) || 0));
  const duration_seconds = Math.round(minutes * 60);
  const youtube_url = String(v.youtube_url || '').trim();

  if (!title) throw new Error('Give this item a title.');

  if (item) {
    await api(`/v1/library/${encodeURIComponent(item.id)}`, {
      method: 'PUT',
      body: JSON.stringify({
        title, description, file_type, subject_id, youtube_url: '', duration_seconds,
      }),
    });
    toast('Library item updated.');
    closeModal();
    load();
    return;
  }

  if (mode === 'youtube') {
    if (!youtube_url) throw new Error('Paste a YouTube link.');
    if (file_type !== 'RECORDED_LECTURE') {
      throw new Error('YouTube links are only for recorded lectures.');
    }
    await api('/v1/library', {
      method: 'POST',
      body: JSON.stringify({
        title, description, file_type, subject_id, youtube_url, duration_seconds,
      }),
    });
    toast('Library item added.');
    closeModal();
    load();
    return;
  }

  const input = form.querySelector('[name=file]');
  const file = input && input.files ? input.files[0] : null;
  if (!file) throw new Error('Choose a file to upload.');
  const isVideo = String(file.type || '').indexOf('video/') === 0;
  if (file.size > (isVideo ? VIDEO_LIMIT : DOC_LIMIT)) {
    throw new Error(isVideo
      ? 'Video files are limited to 100 MB — paste a YouTube link for longer recordings.'
      : 'Documents are limited to 50 MB.');
  }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('bucket', BUCKET);
  fd.append('kind', file_type);
  const up = ui.data(await apiForm('/v1/library/upload', fd));
  if (!up || !up.storage_path) throw new Error('The upload did not finish — try again.');

  let created = null;
  try {
    const res = await api('/v1/library', {
      method: 'POST',
      body: JSON.stringify({
        title, description, file_type, subject_id, youtube_url: '', duration_seconds,
      }),
    });
    created = ui.data(res);
    if (!created || !created.id) throw new Error('The item could not be saved.');
    await api(`/v1/library/${encodeURIComponent(created.id)}/attach-file`, {
      method: 'POST',
      body: JSON.stringify({
        storage_path: up.storage_path,
        filename: up.filename,
        mime: up.mime,
        size_bytes: up.size_bytes,
      }),
    });
  } catch (err) {
    // Never leave an empty item or an orphaned object behind when the
    // metadata write fails — both cleanups are best effort.
    if (created && created.id) {
      api(`/v1/library/${encodeURIComponent(created.id)}`,
        { method: 'DELETE' }).catch(() => {});
    }
    api(`/v1/library/files?${
      new URLSearchParams({ path: up.storage_path, bucket: up.bucket || BUCKET })}`,
      { method: 'DELETE' }).catch(() => {});
    throw err;
  }

  toast('Library item added.');
  closeModal();
  load();
}
