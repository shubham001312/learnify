// LEARNIFY — the resumable five-step course wizard.
// Route: `/courses/{id}/edit` → `render(root, ctx)`
//
// The cursor lives on the server (`courses.draft_step`), so closing the tab
// on step 3 and coming back lands on step 3 again. Each step owns its own
// payload:
//
//   1  Basics     title, subject, level, description, hours  → PUT step1
//   2  Structure  modules and lessons: add, rename, reorder  → POST/PUT/DELETE
//   3  Content    body text, video source, attachments       → PUT slots/{sid}
//   4  Tests      link a questionnaire or an assessment      → PUT link-test
//   5  Review     checklist, outline preview, submit         → POST submit
//
// The handler returns `{ destroy }`: `st.dead` freezes every in-flight
// repaint, the delegated listeners are collected in `offs`, and the outline
// preview modal opened by this view is closed on the way out.

import { api, apiForm, esc, toast } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { go, confirmAction, currentUser, openAppModal, closeAppModal } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';
import { ART_KEYS, artSvg, artKeyFor, coverHtml } from './art.js?v=63';

const STEPS = [
  { n: 1, key: 's1', title: 'Basics', hint: 'Title, subject, level' },
  { n: 2, key: 's2', title: 'Structure', hint: 'Modules and lessons' },
  { n: 3, key: 's3', title: 'Content', hint: 'Video, reading or link' },
  { n: 4, key: 's4', title: 'Tests', hint: 'Practice or exam' },
  { n: 5, key: 's5', title: 'Review', hint: 'Check and submit' },
];

const LEVELS = ['Beginner', 'Intermediate', 'Advanced'];
const KINDS = [['VIDEO', 'Video'], ['READING', 'Reading'], ['LINK', 'Link'], ['TEST', 'Test']];
const KIND_ICON = { VIDEO: 'video', READING: 'file', LINK: 'link', TEST: 'quiz' };
const KIND_LABEL = { VIDEO: 'Video', READING: 'Reading', LINK: 'Link', TEST: 'Test' };
const TEST_TYPES = [['QUESTIONNAIRE', 'Practice set'], ['ASSESSMENT', 'Examination']];
const STATUS_LABEL = {
  DRAFT: 'Draft', IN_PROGRESS: 'In progress', PENDING_RELEASE: 'Pending release',
  PUBLISHED: 'Published', ARCHIVED: 'Archived',
};

// Captions for the artwork tiles. art.js keeps its own longer titles; the
// picker tiles need labels that survive a 120px column.
const ART_LABEL = {
  networks: 'Networks', code: 'Programming', database: 'Databases',
  os: 'Operating systems', web: 'Web development', ai: 'Artificial intelligence',
  security: 'Cyber security', embedded: 'Embedded systems', cloud: 'Cloud',
  software: 'Software engineering', math: 'Mathematics', physics: 'Physics',
  chemistry: 'Chemistry', biology: 'Biology', business: 'Business',
  communication: 'Communication',
};

const MB = 1024 * 1024;
const VIDEO_MB = 100;          // course-attachments bucket cap for video
const DOC_MB = 50;             // …and for documents
const VIDEO_TYPES = 'video/mp4,video/webm,video/quicktime,video/x-matroska';
const DOC_TYPES = 'video/*,application/pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,.xls,.xlsx';

const COVER_MB = 5;             // course-covers bucket cap for thumbnails
const COVER_MAX = 600;          // courses.cover_image_url is `text(600)`
// Checked in the browser before any round trip — mirrors the server's COVER_MIMES.
const COVER_RE = /^image\/(jpeg|png|webp|gif|svg\+xml)$/i;

// ─── Small shared helpers ──────────────────────────────────────────────────

function fmtSize(bytes) {
  const n = Number(bytes) || 0;
  if (n >= MB) return `${Math.round(n / MB * 10) / 10} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

function fileName(path) {
  const p = String(path || '');
  const seg = p.split('/').pop() || p;
  return seg.replace(/^[0-9a-f]{6,}_[0-9a-f]{12}_/i, '');
}

function statusLabel(status) {
  const s = String(status || '').toUpperCase();
  return STATUS_LABEL[s] || s.replace(/_/g, ' ').toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Only http(s) survives; everything else is treated as plain text. */
function safeUrl(raw) {
  const s = String(raw || '').trim();
  if (!s) return '';
  if (/^https?:\/\//i.test(s)) return s;
  if (/^\/\//.test(s)) return 'https:' + s;
  if (/^[\w.-]+\.[a-z]{2,}/i.test(s)) return 'https://' + s;
  return '';
}

function isVideoFile(file) {
  return /^video\//i.test(file.type || '') || /\.(mp4|webm|mov|mkv|m4v)$/i.test(file.name || '');
}

// ─── Handler ───────────────────────────────────────────────────────────────

export function render(root, ctx) {
  const id = String((ctx && ctx.params && ctx.params.id) || '');
  const user = (ctx && ctx.user) || currentUser() || {};

  const st = {
    id,
    user,
    dead: false,
    modal: false,
    loading: true,
    shellDirty: true,
    error: '',
    step: 1,
    maxStep: 1,
    complete: { s1: false, s2: false, s3: false, s4: false, s5: false },
    canSubmit: false,
    counts: {},
    course: null,
    modules: [],
    subjects: [],
    tests: { QUESTIONNAIRE: [], ASSESSMENT: [] },
    testsLoaded: false,
    testsBusy: false,
    testType: '',
    selSlot: '',
    detail: null,
    detailErr: '',
    detailFailed: '',
    detailBusy: false,
    attachments: [],
    pendingPath: '',
    uploading: false,
    cover: '',                  // the cover grammar value: '', 'art:<key>', 'https://…'
    coverErr: '',
    coverBusy: false,
    gen: 0,
  };
  const offs = [];

  const editable = () => {
    const c = st.course;
    return !!c && c.can_edit !== false
      && (c.status === 'DRAFT' || c.status === 'IN_PROGRESS');
  };

  const allSlots = () => {
    const out = [];
    for (const m of st.modules || []) {
      for (const s of (m.slots || [])) {
        out.push(Object.assign({}, s, { module_id: m.id, module_title: m.title }));
      }
    }
    return out;
  };

  const getSlot = (sid) => allSlots().find((s) => s.id === sid) || null;

  // ── Load ────────────────────────────────────────────────────────────────
  async function mount() {
    st.loading = true;
    paint();
    try {
      const [wRes, oRes, sRes] = await Promise.all([
        api(`/v1/courses/${id}/wizard`),
        api(`/v1/courses/${id}/outline`),
        api('/v1/subjects').catch(() => null),
      ]);
      if (st.dead) return;
      const w = ui.data(wRes) || {};
      st.course = w.course || null;
      // The picker rebuilds from this on every paint, so a reload lands on the
      // cover the trainer last saved (art:, an uploaded URL, or '' — all three).
      st.cover = String((w.course && w.course.cover_image_url) || '');
      st.coverErr = '';
      st.step = Math.max(1, Math.min(5, Number(w.step) || 1));
      st.maxStep = Math.max(1, Math.min(5, Number(w.max_step) || 1));
      st.complete = w.complete || st.complete;
      st.canSubmit = !!w.can_submit;
      st.counts = w.counts || {};
      const o = ui.data(oRes) || {};
      st.modules = o.modules || [];
      st.subjects = sRes ? (ui.data(sRes) || []) : [];
      st.loading = false;
      st.error = '';
      st.shellDirty = true;
      ensureSelection();
      paint();
    } catch (err) {
      if (st.dead) return;
      st.loading = false;
      st.error = err.message || 'The wizard could not be opened.';
      st.shellDirty = true;
      paint();
    }
  }

  /** Re-read the resume cursor + completion flags (never moves the user). */
  async function refreshState() {
    try {
      const res = await api(`/v1/courses/${id}/wizard`);
      const w = ui.data(res) || {};
      if (st.dead) return;
      const next = w.course || null;
      if (next && st.course && next.title !== st.course.title) st.shellDirty = true;
      if (next) st.course = next;
      st.complete = w.complete || st.complete;
      st.counts = w.counts || st.counts;
      st.canSubmit = !!w.can_submit;
      st.maxStep = Math.max(st.maxStep, Math.min(5, Number(w.max_step) || 1));
    } catch (_) { /* the wizard keeps working from the last known state */ }
  }

  /** Re-read the module → lesson tree after any structural change. */
  async function refreshOutline() {
    try {
      const res = await api(`/v1/courses/${id}/outline`);
      const o = ui.data(res) || {};
      if (st.dead) return;
      st.modules = o.modules || [];
      if (st.selSlot && !getSlot(st.selSlot)) st.selSlot = '';
      // The detail row may have changed with it — reload it on the next paint.
      clearDetail();
    } catch (_) { /* the previous tree stays on screen */ }
  }

  // ── Painting ────────────────────────────────────────────────────────────
  function paint() {
    if (st.dead) return;
    if (st.loading) {
      st.shellDirty = true;
      root.innerHTML = ui.loading('course wizard');
      return;
    }
    if (st.error) {
      st.shellDirty = true;
      root.innerHTML = errorScreen();
      return;
    }
    if (st.shellDirty || !root.querySelector('[data-main]')) {
      buildShell();
      st.shellDirty = false;
    }
    paintBanner();
    paintRail();
    paintMain();
    paintFoot();
  }

  function errorScreen() {
    return `
      <div class="crumbs"><a href="#/courses">&larr; All courses</a></div>
      ${ui.head({ title: 'Course wizard' })}
      <div class="blank">
        <b>The wizard could not open</b>
        <p>${esc(st.error)}</p>
        <div class="row gap wz-center">
          <button type="button" class="btn primary sm" data-retry>Try again</button>
          <a class="btn ghost sm" href="#/courses/${esc(id)}">Back to course</a>
        </div>
      </div>`;
  }

  function buildShell() {
    const c = st.course || {};
    root.innerHTML = `
      <div class="crumbs">
        <a href="#/courses">&larr; All courses</a> /
        <a href="#/courses/${esc(id)}">${esc(c.title || 'Course')}</a>
      </div>
      ${ui.head({
        title: 'Course wizard',
        sub: `${esc(c.title || '')}${c.subject_name ? ' &middot; ' + esc(c.subject_name) : ''}${
          user && user.name ? ' &middot; Editing as ' + esc(user.name) : ''}`,
        actions: `<span data-status>${ui.tag(c.status)}</span>
          <a class="btn ghost sm" href="#/courses/${esc(id)}">Course page</a>`,
      })}
      <div data-banner></div>
      <div class="wz-shell">
        <aside class="wz-rail"><div class="card wz-rail-card" data-rail></div></aside>
        <section class="wz-main" data-main></section>
      </div>
      <div class="wz-foot" data-foot></div>`;
  }

  function paintBanner() {
    const el = root.querySelector('[data-banner]');
    if (!el) return;
    if (editable()) { el.innerHTML = ''; return; }
    el.innerHTML = ui.note(
      `This course is <b>${esc(statusLabel(st.course && st.course.status))}</b>, so the wizard is read-only. `
      + 'Steps 1 to 4 can only change while a course is a draft or in progress.', 'warn');
  }

  function paintRail() {
    const el = root.querySelector('[data-rail]');
    if (!el) return;
    const done = STEPS.filter((s) => st.complete[s.key]).length;
    el.innerHTML = `
      <div class="card-head">
        <h3>Course wizard</h3>
        <span class="tag ${done === 5 ? 'ok' : 'info'}">${done} of 5</span>
      </div>
      ${ui.progressBar(Math.round((done / 5) * 100), `Step ${st.step} of 5`)}
      <ol class="wz-steps">
        ${STEPS.map(stepRow).join('')}
      </ol>
      <p class="wz-rail-note sm dim">${iconSvg('check')} Every step is saved on the server — close the tab and come back any time.</p>`;
  }

  function stepRow(s) {
    const cur = s.n === st.step;
    const ok = !!st.complete[s.key];
    return `
      <li>
        <button type="button" class="wz-step${cur ? ' is-current' : ''}${ok ? ' is-done' : ''}"
                data-step="${s.n}" ${cur ? 'aria-current="step"' : ''}>
          <span class="wz-step-n">${ok && !cur ? iconSvg('check') : s.n}</span>
          <span class="wz-step-txt"><b>${esc(s.title)}</b><small>${esc(s.hint)}</small></span>
          ${cur ? '<span class="wz-step-mark">Now</span>' : ''}
        </button>
      </li>`;
  }

  function paintMain() {
    const el = root.querySelector('[data-main]');
    if (!el) return;
    const html = st.step === 1 ? stepOne()
      : st.step === 2 ? stepTwo()
        : st.step === 3 ? stepThree()
          : st.step === 4 ? stepFour()
            : stepFive();
    el.innerHTML = html;
    if (st.step === 3) maybeLoadDetail();
    if (st.step === 4) ensureTests();
  }

  function paintFoot() {
    const el = root.querySelector('[data-foot]');
    if (!el) return;
    let right = '';
    if (st.step < 5) {
      const label = st.step === 1 ? 'Save and continue' : 'Next step';
      right = `<button type="button" class="btn primary" data-next ${
        st.step === 1 && !editable() ? 'disabled' : ''}>${label}</button>`;
    } else {
      right = st.course && (st.course.status === 'PENDING_RELEASE'
        || st.course.status === 'PUBLISHED')
        ? '<span class="sm dim">Submitted — this course is with Supreme.</span>'
        : `<button type="button" class="btn primary" data-submit ${
            st.canSubmit ? '' : 'disabled'}>Submit for release</button>`;
    }
    el.innerHTML = `
      <div class="wz-foot-in">
        <button type="button" class="btn ghost" data-prev ${
          st.step === 1 ? 'disabled' : ''}>${st.step === 5 ? 'Back' : 'Previous step'}</button>
        <span class="grow"></span>
        ${right}
      </div>`;
  }

  // ── Step navigation ─────────────────────────────────────────────────────
  async function gotoStep(n) {
    const target = Math.max(1, Math.min(5, Number(n) || 0));
    if (target === st.step) return;
    st.step = target;
    paint();
    try {
      await api(`/v1/courses/${id}/step/${target}`, { method: 'POST', body: '{}' });
    } catch (err) {
      if (!st.dead) toast(err.message, 'warn');
    }
  }

  async function next(btn) {
    if (st.step === 1) { await saveStep1(true, btn); return; }
    if (st.step >= 5) return;
    await gotoStep(st.step + 1);
  }

  /** Points steps 3 and 4 at a lesson that still exists (never repaints). */
  function ensureSelection() {
    const flat = allSlots();
    if (!flat.length) {
      st.selSlot = '';
      return;
    }
    if (!st.selSlot || !flat.some((s) => s.id === st.selSlot)) {
      st.selSlot = flat[0].id;
      const slot = getSlot(st.selSlot);
      st.testType = (slot && slot.linked_test_type) || '';
      clearDetail();
    }
  }

  function clearDetail() {
    st.detail = null;
    st.detailErr = '';
    st.detailFailed = '';
    st.attachments = [];
    st.pendingPath = '';
    st.detailBusy = false;
    st.gen += 1;                       // drop any load already in flight
  }

  function pickSlot(sid) {
    if (!sid || sid === st.selSlot) return;
    const slot = getSlot(sid);
    st.selSlot = sid;
    st.testType = (slot && slot.linked_test_type) || '';
    clearDetail();
    paintMain();
  }

  // ── Step 1 · Basics ─────────────────────────────────────────────────────
  function stepOne() {
    const c = st.course || {};
    const d = editable() ? '' : ' disabled';
    const level = String(c.level || 'Beginner');
    return `
      <div class="card wz-panel">
        <div class="card-head">
          <span class="wz-panel-ic">${iconSvg('edit')}</span>
          <div class="wz-panel-title">
            <h3>Course basics</h3>
            <p class="sm muted">What a trainee reads first. This step counts as
              complete once the title and either a description or a subject exist.</p>
          </div>
          <span class="grow"></span>
          <span class="tag ${st.complete.s1 ? 'ok' : 'warn'}">${
            st.complete.s1 ? 'Complete' : 'Needs work'}</span>
        </div>
        <form data-form="step1" novalidate>
          <div class="wz-grid">
            <div class="field wz-span2">
              <label for="wz-title">Course title</label>
              <input id="wz-title" name="title" maxlength="160" value="${esc(c.title || '')}"
                     placeholder="e.g. Structural Analysis for Site Engineers"${d}>
            </div>
            <div class="field">
              <label for="wz-subject">Subject</label>
              <select id="wz-subject" name="subject_id"${d}>
                <option value="">No subject yet</option>
                ${st.subjects.map((s) => `
                  <option value="${esc(s.id)}" ${c.subject_id === s.id ? 'selected' : ''}>${
                    esc(s.code ? `${s.code} — ${s.name}` : s.name)}</option>`).join('')}
              </select>
            </div>
            <div class="field">
              <label for="wz-level">Level</label>
              <select id="wz-level" name="level"${d}>
                ${LEVELS.map((l) => `<option ${level === l ? 'selected' : ''}>${l}</option>`).join('')}
              </select>
            </div>
            <div class="field">
              <label for="wz-hours">Estimated hours</label>
              <input id="wz-hours" name="duration_hours" type="number" min="0" max="1000"
                     step="0.5" value="${esc(String(c.duration_hours || 0))}"${d}>
            </div>
            ${coverField(d)}
            <div class="field wz-span2">
              <label for="wz-desc">Description</label>
              <textarea id="wz-desc" name="description" rows="5" maxlength="4000"
                        placeholder="What will a trainee be able to do after this course?"${
                          d}>${esc(c.description || '')}</textarea>
            </div>
          </div>
          <p class="wz-err" data-err></p>
          ${editable() ? `<div class="row gap wz-actions">
            <button type="button" class="btn ghost" data-save1>Save draft</button>
            <span class="grow"></span>
            <button type="submit" class="btn primary">Save and continue</button>
          </div>` : ''}
        </form>
      </div>`;
  }

  // ── Step 1 · thumbnail chooser ──────────────────────────────────────────
  /** The subject a `''` cover derives its artwork from. */
  function coverSubject() {
    const c = st.course || {};
    return { subject: c.subject_name || '', category: c.subject_category || '' };
  }

  /** Exactly the block the course card will draw for the current value. */
  function coverPreviewInner() {
    const s = coverSubject();
    return coverHtml(st.cover, { subject: s.subject, category: s.category })
      || '<p class="sm dim">No thumbnail</p>';
  }

  const isCoverUrl = (v) => /^https?:\/\/\S+$/i.test(String(v || '').trim());

  function setCoverErr(msg) {
    st.coverErr = String(msg || '');
    const box = root.querySelector('[data-cover-err]');
    if (box) box.textContent = st.coverErr;
  }

  /**
   * Apply a cover value without repainting the step — a repaint would drop
   * whatever else is half-typed in the form. Keeps the hidden input that feeds
   * `saveStep1`, the tile selection, the live preview and the link box in step
   * with `st.cover`, so revisiting step 1 always repopulates the same state.
   */
  function setCover(value) {
    if (!editable()) return;
    const next = String(value == null ? '' : value).trim().slice(0, COVER_MAX);
    st.cover = next;
    setCoverErr('');

    const form = root.querySelector('form[data-form="step1"]');
    const hid = form && form.querySelector('input[name="cover_image_url"]');
    if (hid) hid.value = next;

    root.querySelectorAll('[data-cover-art]').forEach((btn) => {
      const on = String(btn.dataset.coverArt || '') === next;
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-checked', on ? 'true' : 'false');
    });

    const prev = root.querySelector('[data-cover-prev]');
    if (prev) prev.innerHTML = coverPreviewInner();

    const file = root.querySelector('[data-cover-file]');
    const lab = file && file.closest('label');
    const txt = lab && lab.querySelector('[data-cover-file-label]');
    if (txt) txt.textContent = /^https?:\/\//i.test(next) ? 'Replace image' : 'Upload image';

    const link = root.querySelector('[data-cover-link]');
    if (link && link !== document.activeElement) {
      link.value = isCoverUrl(next) ? next : '';
    }
  }

  /** Step 1's "Course thumbnail" field: preview, upload/link tools, art grid. */
  function coverField(d) {
    const can = editable();
    const s = coverSubject();
    const defKey = artKeyFor(s.subject, s.category);
    const linkVal = isCoverUrl(st.cover) ? st.cover : '';
    return `
      <div class="field wz-span2 wz-cover">
        <label>Course thumbnail</label>
        <p class="sm dim">What trainees see on the course card — pick a cartoon
          artwork, upload your own picture, or paste a link.</p>
        <input type="hidden" id="wz-cover" name="cover_image_url" maxlength="${COVER_MAX}"
               value="${esc(st.cover)}">
        <div class="wz-cover-top">
          <div class="wz-cover-prev" data-cover-prev>${coverPreviewInner()}</div>
          <div class="wz-cover-tools">
            ${can ? `
              <label class="btn ghost sm wz-file">${iconSvg('upload')}<span
                data-cover-file-label>${
                  /^https?:\/\//i.test(st.cover) ? 'Replace image' : 'Upload image'
                }</span>
                <input type="file" data-cover-file accept="image/*" hidden></label>
              <p class="sm muted" data-cover-status></p>`
        : '<p class="sm dim">This course is read-only, so the thumbnail cannot be changed.</p>'}
            <label class="sm dim" for="wz-cover-link">Or paste an image link</label>
            <input id="wz-cover-link" data-cover-link type="url" maxlength="${COVER_MAX}"
                   placeholder="https://…" value="${esc(linkVal)}"${d}>
            <p class="sm dim">JPEG, PNG, WebP, GIF or SVG — up to ${COVER_MB} MB.</p>
          </div>
        </div>
        <div class="art-picker" role="radiogroup" aria-label="Course artwork">
          <button type="button" class="art-opt art-opt-def${st.cover ? '' : ' on'}"
                  data-cover-art="" role="radio" aria-checked="${st.cover ? 'false' : 'true'}"${
                    can ? '' : ' disabled'}>${artSvg(defKey)}
            <span class="art-opt-cap">Subject default</span>
          </button>
          ${ART_KEYS.map((k) => {
            const on = st.cover === `art:${k}`;
            return `<button type="button" class="art-opt${on ? ' on' : ''}"
                    data-cover-art="art:${k}" role="radio" aria-checked="${on}"${
                      can ? '' : ' disabled'}>${artSvg(k)}
              <span class="art-opt-cap">${esc(ART_LABEL[k] || k)}</span>
            </button>`;
          }).join('')}
        </div>
        <p class="wz-err" data-cover-err>${esc(st.coverErr)}</p>
      </div>`;
  }

  /**
   * Thumbnail upload. Type and size are checked here first, so a file the
   * server would reject never costs a round trip; a failed call leaves
   * `st.cover` (and therefore the preview and selection) exactly as it was.
   */
  async function uploadCover(input) {
    if (!editable() || st.coverBusy) return;
    const file = input && input.files && input.files[0];
    if (!file) return;
    if (!COVER_RE.test(String(file.type || ''))) {
      setCoverErr('That file is not an image — use JPEG, PNG, WebP, GIF or SVG.');
      input.value = '';
      return;
    }
    if (file.size > COVER_MB * MB) {
      setCoverErr(`That image is ${fmtSize(file.size)} — the limit is ${COVER_MB} MB.`);
      input.value = '';
      return;
    }

    st.coverBusy = true;
    const status = root.querySelector('[data-cover-status]');
    if (status) status.textContent = 'Uploading…';
    setCoverErr('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('bucket', 'course-covers');
      const res = await apiForm('/v1/library/upload', fd);
      const d = ui.data(res) || {};
      const url = String(d.public_url || '');
      if (!url) {
        // An envelope-level failure (success:false) carries the reason in error.
        const why = res && typeof res === 'object'
          && (res.error || res.detail || res.message);
        throw new Error(why || 'The upload did not return a public URL.');
      }
      if (url.length > COVER_MAX) {
        throw new Error('That image URL is too long to store as a thumbnail.');
      }
      if (st.dead) return;
      setCover(url);
      toast('Thumbnail uploaded — save this step to keep it.');
    } catch (err) {
      if (st.dead) return;
      setCoverErr(err.message || 'That image could not be uploaded.');
    } finally {
      st.coverBusy = false;
      if (!st.dead && status) status.textContent = '';
      input.value = '';
    }
  }

  /**
   * The optional "or paste a link" box. Returns false when it holds something
   * that would be rejected, so the save can stop and say why instead of
   * silently dropping the trainer's choice. An empty box never clears a pick.
   */
  function commitCoverLink(el) {
    if (!editable() || !el) return true;
    const raw = String(el.value || '').trim();
    if (!raw) return true;
    if (!isCoverUrl(raw)) {
      setCoverErr('Paste a full https:// link, or clear the box.');
      return false;
    }
    if (raw.length > COVER_MAX) {
      setCoverErr('That link is too long to store as a thumbnail.');
      return false;
    }
    setCover(raw);
    return true;
  }

  async function saveStep1(advance, btn) {
    const form = root.querySelector('form[data-form="step1"]');
    if (!form || !editable()) return;
    ui.formError(form, '');
    // Fold a link typed but not yet committed into st.cover before the values
    // are read, so the hidden input carries it into the payload.
    const link = form.querySelector('[data-cover-link]');
    if (!commitCoverLink(link)) {
      ui.formError(form, st.coverErr);
      return;
    }
    const v = ui.formValues(form);
    const title = String(v.title || '').trim();
    const description = String(v.description || '').trim();
    if (title.length < 3) {
      ui.formError(form, 'Give the course a title of at least 3 characters.');
      return;
    }
    const payload = {
      title,
      subject_id: String(v.subject_id || ''),
      level: String(v.level || 'Beginner'),
      description,
      duration_hours: Number(v.duration_hours) || 0,
      cover_image_url: String(v.cover_image_url || '').trim(),
    };
    const target = btn || form.querySelector('button[type="submit"]');
    await ui.busy(target, 'Saving…', async () => {
      try {
        await api(`/v1/courses/${id}/step1`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        if (st.dead) return;
        const soft = !payload.description && !payload.subject_id;
        toast(soft
          ? 'Saved — add a description or a subject to complete this step.'
          : 'Course details saved.');
        await refreshState();
        if (st.dead) return;
        if (advance) await gotoStep(2);
        else paint();
      } catch (err) {
        if (root.contains(form)) ui.formError(form, err.message);
        else toast(err.message, 'warn');
      }
    });
  }

  // ── Step 2 · Structure ──────────────────────────────────────────────────
  function stepTwo() {
    const mods = st.modules || [];
    const c = st.counts;
    return `
      <div class="card wz-panel">
        <div class="card-head">
          <span class="wz-panel-ic">${iconSvg('book')}</span>
          <div class="wz-panel-title">
            <h3>Modules and lessons</h3>
            <p class="sm muted">Modules are the sections a trainee sees in the
              outline. Each one holds its lessons, in the order you set here.</p>
          </div>
          <span class="grow"></span>
          <span class="tag ${st.complete.s2 ? 'ok' : 'warn'}">${st.complete.s2 ? 'Complete' : 'Needs work'}</span>
        </div>

        <div class="wz-counts">
          <span class="tag mute">${c.modules || 0} module${(c.modules || 0) === 1 ? '' : 's'}</span>
          <span class="tag mute">${c.slots || 0} lesson${(c.slots || 0) === 1 ? '' : 's'}</span>
          <span class="tag mute">${c.with_body || 0} reading${(c.with_body || 0) === 1 ? '' : 's'}</span>
        </div>

        ${mods.length
          ? `<div class="wz-mods">${mods.map(moduleCard).join('')}</div>`
          : `<div class="wz-empty">
               <span class="wz-empty-ic">${iconSvg('bookOpen')}</span>
               <b>No modules yet</b>
               <p class="sm muted">Add the first section below, then drop lessons into it.</p>
             </div>`}

        ${editable() ? `
          <form class="wz-add" data-add-mod novalidate>
            <input name="title" maxlength="160" placeholder="New module title"
                   aria-label="New module title">
            <input name="description" maxlength="1000"
                   placeholder="One line about this module (optional)"
                   aria-label="Module description">
            <button type="submit" class="btn primary sm">Add module</button>
            <p class="wz-err" data-err></p>
          </form>` : ''}
      </div>`;
  }

  function moduleCard(m, i) {
    const slots = m.slots || [];
    const can = editable();
    return `
      <article class="wz-mod" data-module="${esc(m.id)}">
        <div class="wz-mod-head">
          <span class="wz-mod-n">${i + 1}</span>
          ${can
            ? `<input class="wz-mod-title" data-title maxlength="160" value="${esc(m.title)}"
                      aria-label="Module title">`
            : `<b class="wz-mod-title">${esc(m.title)}</b>`}
          ${can ? `<div class="wz-mod-acts">
            <button type="button" class="btn ghost sm" data-mod-save data-id="${esc(m.id)}">Save</button>
            <button type="button" class="btn ghost sm" data-mod-up data-id="${esc(m.id)}" ${
              i === 0 ? 'disabled' : ''} aria-label="Move module up">&uarr;</button>
            <button type="button" class="btn ghost sm" data-mod-down data-id="${esc(m.id)}" ${
              i === st.modules.length - 1 ? 'disabled' : ''} aria-label="Move module down">&darr;</button>
            <button type="button" class="btn ghost sm" data-mod-del data-id="${esc(m.id)}">Delete</button>
          </div>` : ''}
        </div>
        ${m.description ? `<p class="wz-mod-desc sm muted">${esc(m.description)}</p>` : ''}
        ${slots.length
          ? `<ul class="wz-lessons">${slots.map((s) => lessonRow(s)).join('')}</ul>`
          : '<p class="wz-mod-empty sm dim">No lessons in this module yet.</p>'}
        ${can ? `
          <form class="wz-add wz-add-slot" data-add-slot="${esc(m.id)}" novalidate>
            <input name="title" maxlength="160" placeholder="New lesson title"
                   aria-label="New lesson title">
            <select name="kind" aria-label="Lesson type">
              ${KINDS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
            </select>
            <button type="submit" class="btn ghost sm">Add lesson</button>
            <p class="wz-err" data-err></p>
          </form>` : ''}
      </article>`;
  }

  function lessonRow(s) {
    const can = editable();
    return `
      <li class="wz-lesson" data-lesson="${esc(s.id)}">
        <span class="wz-kind">${iconSvg(KIND_ICON[s.kind] || 'file')}</span>
        ${can
          ? `<input class="wz-lesson-title" data-title maxlength="160" value="${esc(s.title)}"
                    aria-label="Lesson title">`
          : `<b class="wz-lesson-title">${esc(s.title)}</b>`}
        <span class="wz-lesson-tags">
          <span class="tag mute">${esc(KIND_LABEL[s.kind] || s.kind)}</span>
          ${s.has_video ? '<span class="tag ok">Video</span>' : ''}
          ${s.linked_test_id ? '<span class="tag info">Test</span>' : ''}
        </span>
        ${can ? `<div class="wz-lesson-acts">
          <button type="button" class="btn ghost sm" data-slot-save data-id="${esc(s.id)}">Save</button>
          <button type="button" class="btn ghost sm" data-slot-del data-id="${esc(s.id)}">Delete</button>
        </div>` : ''}
      </li>`;
  }

  async function addModule(form) {
    if (!form || !editable()) return;
    ui.formError(form, '');
    const v = ui.formValues(form);
    const title = String(v.title || '').trim();
    if (!title) { ui.formError(form, 'Name the module before adding it.'); return; }
    try {
      await api(`/v1/courses/${id}/modules`, {
        method: 'POST',
        body: JSON.stringify({ title, description: String(v.description || '').trim() }),
      });
      if (st.dead) return;
      toast('Module added.');
      form.reset();
      await refreshOutline();
      await refreshState();
      paint();
    } catch (err) {
      if (root.contains(form)) ui.formError(form, err.message);
      else toast(err.message, 'warn');
    }
  }

  async function addSlot(form) {
    if (!form || !editable()) return;
    ui.formError(form, '');
    const v = ui.formValues(form);
    const title = String(v.title || '').trim();
    if (!title) { ui.formError(form, 'Name the lesson before adding it.'); return; }
    try {
      await api(`/v1/courses/${id}/slots`, {
        method: 'POST',
        body: JSON.stringify({
          module_id: form.dataset.addSlot || '',
          title,
          kind: v.kind || 'VIDEO',
        }),
      });
      if (st.dead) return;
      toast('Lesson added.');
      form.reset();
      await refreshOutline();
      await refreshState();
      paint();
    } catch (err) {
      if (root.contains(form)) ui.formError(form, err.message);
      else toast(err.message, 'warn');
    }
  }

  async function saveModule(btn) {
    const box = btn.closest('[data-module]');
    const input = box && box.querySelector('[data-title]');
    const title = input ? String(input.value || '').trim() : '';
    if (!title) { toast('A module needs a title.', 'warn'); return; }
    const mid = btn.dataset.id;
    const mod = (st.modules || []).find((m) => m.id === mid);
    await ui.busy(btn, 'Saving…', async () => {
      try {
        await api(`/v1/courses/${id}/modules/${mid}`, {
          method: 'PUT',
          body: JSON.stringify({ title, description: (mod && mod.description) || '' }),
        });
        if (st.dead) return;
        toast('Module saved.');
        await refreshOutline();
        paint();
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  async function moveModule(btn, dir) {
    const ids = (st.modules || []).map((m) => m.id);
    const i = ids.indexOf(btn.dataset.id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ids.length) return;
    const order = ids.slice();
    const swap = order[i];
    order[i] = order[j];
    order[j] = swap;
    await ui.busy(btn, '', async () => {
      try {
        await api(`/v1/courses/${id}/modules-order`, {
          method: 'PUT',
          body: JSON.stringify({ order }),
        });
        if (st.dead) return;
        await refreshOutline();
        paint();
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  async function deleteModule(btn) {
    const mid = btn.dataset.id;
    const mod = (st.modules || []).find((m) => m.id === mid);
    if (!mod) return;
    const n = (mod.slots || []).length;
    const ok = await confirmAction(
      'Delete this module?',
      `“${mod.title}” and its ${n} lesson${n === 1 ? '' : 's'} will be removed. This cannot be undone.`,
      'Delete');
    if (!ok || st.dead) return;
    try {
      await api(`/v1/courses/${id}/modules/${mid}`, { method: 'DELETE' });
      if (st.dead) return;
      toast('Module deleted.');
      await refreshOutline();
      await refreshState();
      paint();
    } catch (err) {
      toast(err.message, 'warn');
    }
  }

  async function saveSlotTitle(btn) {
    const box = btn.closest('[data-lesson]');
    const input = box && box.querySelector('[data-title]');
    const title = input ? String(input.value || '').trim() : '';
    if (!title) { toast('A lesson needs a title.', 'warn'); return; }
    const sid = btn.dataset.id;
    const outlineRow = getSlot(sid);
    await ui.busy(btn, 'Saving…', async () => {
      try {
        // The outline only carries a summary — read the full row first so the
        // PUT never wipes the body text or the attached video.
        const dRes = await api(`/v1/courses/${id}/slots/${sid}`);
        const full = ui.data(dRes) || {};
        if (st.dead) return;
        await api(`/v1/courses/${id}/slots/${sid}`, {
          method: 'PUT',
          body: JSON.stringify({
            title,
            kind: full.kind || (outlineRow && outlineRow.kind) || 'VIDEO',
            body: full.body || '',
            duration_seconds: Number(full.duration_seconds) || 0,
            video_source: full.video_source || '',
            youtube_url: full.youtube_url || '',
            storage_path: full.storage_path || '',
          }),
        });
        if (st.dead) return;
        toast('Lesson saved.');
        await refreshOutline();
        paint();
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  async function deleteSlot(btn) {
    const sid = btn.dataset.id;
    const slot = getSlot(sid);
    const ok = await confirmAction(
      'Delete this lesson?',
      `“${slot ? slot.title : 'This lesson'}” will be removed from the course. This cannot be undone.`,
      'Delete');
    if (!ok || st.dead) return;
    try {
      await api(`/v1/courses/${id}/slots/${sid}`, { method: 'DELETE' });
      if (st.dead) return;
      toast('Lesson deleted.');
      await refreshOutline();
      await refreshState();
      paint();
    } catch (err) {
      toast(err.message, 'warn');
    }
  }

  // ── Step 3 · Content ────────────────────────────────────────────────────
  function stepThree() {
    if (!allSlots().length) {
      return emptyStep('No lessons to edit yet',
        'Add a module and a lesson in step 2, then come back to fill in the content.',
        2, 'Go to structure');
    }
    ensureSelection();
    if (!st.selSlot) return ui.loading('lesson');
    return `
      <div class="wz-content">
        ${pickList()}
        ${editorCard()}
      </div>`;
  }

  function pickList() {
    const flat = allSlots();
    return `
      <div class="card wz-pick">
        <div class="card-head">
          <h3>Lessons</h3>
          <span class="sm muted">${flat.length}</span>
        </div>
        <ul class="wz-pick-list">
          ${flat.map((s) => `
            <li>
              <button type="button" class="wz-pick-item${s.id === st.selSlot ? ' is-active' : ''}"
                      data-slot-pick data-id="${esc(s.id)}">
                <span class="wz-pick-ic">${iconSvg(KIND_ICON[s.kind] || 'file')}</span>
                <span class="wz-pick-txt">
                  <b>${esc(s.title)}</b>
                  <small>${esc(s.module_title || '')}</small>
                </span>
                ${s.has_video ? `<span class="wz-pick-mark">${iconSvg('check')}</span>` : ''}
              </button>
            </li>`).join('')}
        </ul>
        <p class="sm dim wz-pick-note">Choose a lesson, then edit it alongside.</p>
      </div>`;
  }

  function editorCard() {
    const slot = getSlot(st.selSlot);
    if (st.detailBusy || (!st.detail && !st.detailErr)) {
      return `<div class="card wz-editor">${ui.loading('lesson')}</div>`;
    }
    if (!st.detail && st.detailErr) {
      return `
        <div class="card wz-editor">
          ${ui.note(esc(st.detailErr), 'bad')}
          <button type="button" class="btn ghost sm" data-retry-slot>Try again</button>
        </div>`;
    }

    const d = st.detail;
    const kind = d.kind || (slot && slot.kind) || 'VIDEO';
    const src = d.video_source || '';
    const can = editable();
    const dis = can ? '' : ' disabled';
    const bodyLabel = kind === 'LINK' ? 'Destination URL'
      : kind === 'READING' ? 'Reading text'
        : kind === 'VIDEO' ? 'Lesson notes (optional)'
          : 'Instructions (optional)';
    const placeholder = kind === 'LINK'
      ? 'https://…'
      : kind === 'READING'
        ? 'Paste or write the reading. Blank lines start a new paragraph.'
        : 'Anything a trainee should keep in mind while watching.';

    return `
      <div class="card wz-editor">
        <div class="card-head">
          <span class="wz-panel-ic">${iconSvg(KIND_ICON[kind] || 'file')}</span>
          <div class="wz-panel-title">
            <h3>${esc(d.title || (slot && slot.title) || 'Lesson')}</h3>
            <p class="sm muted">${esc((slot && slot.module_title) || '')}</p>
          </div>
          <span class="grow"></span>
          ${ui.tone(KIND_LABEL[kind] || kind, 'mute')}
        </div>

        <form data-form="slot" novalidate>
          <div class="wz-grid">
            <div class="field">
              <label for="wz-kind">Lesson type</label>
              <select id="wz-kind" name="kind" data-kind${dis}>
                ${KINDS.map(([v, l]) => `<option value="${v}" ${kind === v ? 'selected' : ''}>${l}</option>`).join('')}
              </select>
            </div>
            ${kind === 'VIDEO' ? videoFields(d, src, dis) : ''}
            <div class="field wz-span2">
              <label for="wz-body">${esc(bodyLabel)}</label>
              <textarea id="wz-body" name="body" rows="8" placeholder="${esc(placeholder)}"${
                dis}>${esc(d.body || '')}</textarea>
            </div>
          </div>
          <p class="wz-err" data-err></p>
          ${can ? `<div class="row gap wz-actions">
            <button type="submit" class="btn primary" data-save-slot>Save lesson</button>
            <span class="grow"></span>
            <a class="btn ghost sm" href="#/learn/${esc(id)}/${esc(d.id || st.selSlot)}">Open lesson</a>
          </div>` : ''}
        </form>

        ${attBlock(can)}
      </div>`;
  }

  function videoFields(d, src, dis) {
    return `
      <div class="field">
        <label for="wz-vsrc">Video source</label>
        <select id="wz-vsrc" name="video_source" data-vsrc${dis}>
          <option value="" ${src === '' ? 'selected' : ''}>No video</option>
          <option value="YOUTUBE" ${src === 'YOUTUBE' ? 'selected' : ''}>YouTube link</option>
          <option value="UPLOAD" ${src === 'UPLOAD' ? 'selected' : ''}>Uploaded file</option>
        </select>
      </div>
      <div class="field">
        <label for="wz-dur">Duration (seconds)</label>
        <input id="wz-dur" name="duration_seconds" type="number" min="0" max="86400"
               value="${esc(String(d.duration_seconds || 0))}"${dis}>
      </div>
      <div class="field wz-span2" data-yt ${src === 'YOUTUBE' ? '' : 'hidden'}>
        <label for="wz-yt">YouTube URL</label>
        <input id="wz-yt" name="youtube_url" maxlength="400"
               placeholder="https://www.youtube.com/watch?v=…" value="${
                 esc(d.youtube_url || '')}"${dis}>
        <p class="sm dim">Paste a full watch URL — trainees get the privacy-enhanced player.</p>
      </div>
      <div class="field wz-span2" data-up ${src === 'UPLOAD' ? '' : 'hidden'}>
        <label>Uploaded video</label>
        ${uploadBlockInner()}
      </div>`;
  }

  function uploadBlockInner() {
    const path = st.pendingPath || (st.detail && st.detail.storage_path) || '';
    const can = editable();
    return `
      ${path
        ? `<div class="wz-file-row">${iconSvg('video')}<span>${esc(fileName(path))}</span>
             <span class="tag ${st.pendingPath ? 'warn' : 'ok'}">${
               st.pendingPath ? 'Unsaved' : 'Attached'}</span></div>`
        : '<p class="sm muted">No video uploaded yet.</p>'}
      <label class="wz-file btn ghost sm">${iconSvg('upload')}<span>${
        path ? 'Replace video' : 'Upload video'}</span>
        <input type="file" data-video accept="${VIDEO_TYPES}" ${can ? '' : 'disabled'} hidden></label>
      <p class="sm dim">Up to ${VIDEO_MB} MB. Larger files should be linked from YouTube instead.</p>
      <p class="sm muted" data-up-status></p>`;
  }

  function attBlock(can) {
    const n = st.attachments.length;
    return `
      <div class="wz-att-block">
        <div class="card-head">
          <h3>Attachments</h3>
          <span class="sm muted">${n}</span>
        </div>
        <ul class="wz-att-list" data-att-list>${attListInner()}</ul>
        ${can ? `
          <label class="wz-file btn ghost sm">${iconSvg('upload')}<span>Add file</span>
            <input type="file" data-att accept="${DOC_TYPES}" hidden></label>
          <p class="sm dim">Handouts and reference files — up to ${DOC_MB} MB for documents
            and ${VIDEO_MB} MB for video.</p>` : ''}
        <p class="sm muted" data-att-status></p>
      </div>`;
  }

  function attListInner() {
    if (!st.attachments.length) {
      return '<li class="wz-att-empty sm dim">No files attached yet.</li>';
    }
    const can = editable();
    return st.attachments.map((a) => `
      <li class="wz-att">
        <span class="wz-att-ic">${iconSvg('file')}</span>
        <span class="wz-att-t">${esc(a.filename)}
          <small>${esc(fmtSize(a.size_bytes))}</small></span>
        ${can ? `<button type="button" class="btn ghost sm" data-att-del data-id="${
          esc(a.id)}">Remove</button>` : ''}
      </li>`).join('');
  }

  function maybeLoadDetail() {
    if (!st.selSlot || st.detailBusy) return;
    if (st.detail && st.detail.id === st.selSlot) return;
    if (st.detailFailed === st.selSlot) return;
    loadDetail(st.selSlot);
  }

  function loadDetail(sid) {
    const gen = ++st.gen;
    st.detailBusy = true;
    st.detailErr = '';
    st.detail = null;
    st.attachments = [];
    st.pendingPath = '';
    paintMain();

    Promise.all([
      api(`/v1/courses/${id}/slots/${sid}`),
      api(`/v1/courses/${id}/slots/${sid}/attachments`).catch(() => null),
    ]).then(([dRes, aRes]) => {
      if (st.dead || gen !== st.gen) return;
      st.detail = ui.data(dRes) || null;
      st.attachments = aRes ? (ui.data(aRes) || []) : [];
      st.detailBusy = false;
      if (!st.detail) {
        st.detailFailed = sid;
        st.detailErr = 'That lesson could not be loaded.';
      }
      paintMain();
    }).catch((err) => {
      if (st.dead || gen !== st.gen) return;
      st.detailBusy = false;
      st.detail = null;
      st.detailFailed = sid;
      st.detailErr = err.message || 'That lesson could not be loaded.';
      paintMain();
    });
  }

  /** Keep what is already typed in the form when the editor repaints. */
  function syncDetail() {
    const form = root.querySelector('form[data-form="slot"]');
    if (!form || !st.detail) return;
    const v = ui.formValues(form);
    if (v.kind !== undefined) st.detail.kind = v.kind;
    if (v.body !== undefined) st.detail.body = v.body;
    if (v.video_source !== undefined) st.detail.video_source = v.video_source;
    if (v.youtube_url !== undefined) st.detail.youtube_url = v.youtube_url;
    if (v.duration_seconds !== undefined) {
      st.detail.duration_seconds = Number(v.duration_seconds) || 0;
    }
  }

  function toggleVideo(value) {
    const yt = root.querySelector('[data-yt]');
    const up = root.querySelector('[data-up]');
    if (yt) yt.hidden = value !== 'YOUTUBE';
    if (up) up.hidden = value !== 'UPLOAD';
  }

  async function uploadVideo(input) {
    if (st.uploading) return;
    const file = input && input.files && input.files[0];
    if (!file) return;
    if (!isVideoFile(file)) {
      toast('Pick a video file — MP4, WebM, MOV or MKV.', 'warn');
      input.value = '';
      return;
    }
    const cap = VIDEO_MB;
    if (file.size > cap * MB) {
      toast(`That video is ${fmtSize(file.size)} — the limit is ${cap} MB.`, 'warn');
      input.value = '';
      return;
    }

    st.uploading = true;
    const status = root.querySelector('[data-up-status]');
    if (status) status.textContent = 'Uploading — this can take a moment…';
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('bucket', 'course-attachments');
      const res = await apiForm('/v1/library/upload', fd);
      const d = ui.data(res) || {};
      if (!d.storage_path) throw new Error('The upload did not return a storage path.');
      if (st.dead) return;
      st.pendingPath = d.storage_path;
      if (st.detail) st.detail.storage_path = d.storage_path;
      const sel = root.querySelector('[data-vsrc]');
      if (sel) { sel.value = 'UPLOAD'; toggleVideo('UPLOAD'); }
      const box = root.querySelector('[data-up]');
      if (box) box.innerHTML = uploadBlockInner();
      toast('Video uploaded — save the lesson to attach it.');
    } catch (err) {
      toast(err.message, 'warn');
    } finally {
      st.uploading = false;
      if (!st.dead && status) status.textContent = '';
      input.value = '';
    }
  }

  async function uploadAttachment(input) {
    if (st.uploading) return;
    const file = input && input.files && input.files[0];
    if (!file || !st.selSlot) return;
    const video = isVideoFile(file);
    const cap = video ? VIDEO_MB : DOC_MB;
    if (file.size > cap * MB) {
      toast(`That file is ${fmtSize(file.size)} — the limit here is ${cap} MB.`, 'warn');
      input.value = '';
      return;
    }
    const sid = st.selSlot;
    st.uploading = true;
    const status = root.querySelector('[data-att-status]');
    if (status) status.textContent = 'Uploading…';
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('bucket', 'course-attachments');
      const up = ui.data(await apiForm('/v1/library/upload', fd)) || {};
      if (!up.storage_path) throw new Error('The upload did not return a storage path.');
      await api(`/v1/courses/${id}/slots/${sid}/attachments`, {
        method: 'POST',
        body: JSON.stringify({
          storage_path: up.storage_path,
          filename: up.filename || file.name,
          mime: up.mime || file.type || '',
          size_bytes: Number(up.size_bytes) || file.size,
          library_item_id: '',
        }),
      });
      const aRes = await api(`/v1/courses/${id}/slots/${sid}/attachments`);
      if (st.dead) return;
      st.attachments = ui.data(aRes) || [];
      const list = root.querySelector('[data-att-list]');
      if (list) list.innerHTML = attListInner();
      toast('Attachment added.');
    } catch (err) {
      toast(err.message, 'warn');
    } finally {
      st.uploading = false;
      if (!st.dead && status) status.textContent = '';
      input.value = '';
    }
  }

  async function deleteAttachment(btn) {
    const aid = btn.dataset.id;
    const file = st.attachments.find((a) => a.id === aid);
    const ok = await confirmAction(
      'Remove this attachment?',
      `“${file ? file.filename : 'This file'}” will be removed from the lesson.`,
      'Remove');
    if (!ok || st.dead) return;
    try {
      await api(`/v1/courses/${id}/attachments/${aid}`, { method: 'DELETE' });
      if (st.dead) return;
      st.attachments = st.attachments.filter((a) => a.id !== aid);
      const list = root.querySelector('[data-att-list]');
      if (list) list.innerHTML = attListInner();
      toast('Attachment removed.');
    } catch (err) {
      toast(err.message, 'warn');
    }
  }

  async function saveSlotContent(btn) {
    const form = root.querySelector('form[data-form="slot"]');
    const d = st.detail;
    if (!form || !d || !editable()) return;
    ui.formError(form, '');
    const v = ui.formValues(form);
    const sid = d.id || st.selSlot;
    const kind = String(v.kind || 'VIDEO');
    const body = String(v.body || '').trim();
    const finalSrc = kind === 'VIDEO' ? String(v.video_source || '') : String(d.video_source || '');
    const path = st.pendingPath || d.storage_path || '';
    const yt = String(v.youtube_url !== undefined ? v.youtube_url : (d.youtube_url || '')).trim();
    const dur = Math.max(0, Math.min(86400, Number(v.duration_seconds) || 0));

    if (kind === 'READING' && !body) {
      ui.formError(form, 'A reading needs its text before it can be saved.');
      return;
    }
    if (kind === 'LINK' && body && !safeUrl(body)) {
      ui.formError(form, 'That does not look like a full URL — start with https://.');
      return;
    }
    if (finalSrc === 'YOUTUBE' && !safeUrl(yt)) {
      ui.formError(form, 'Paste a full YouTube watch URL.');
      return;
    }
    if (finalSrc === 'UPLOAD' && !path) {
      ui.formError(form, 'Upload the video first, then save the lesson.');
      return;
    }

    const payload = {
      title: '',
      kind,
      body,
      duration_seconds: kind === 'VIDEO' ? dur : (Number(d.duration_seconds) || 0),
      video_source: finalSrc,
      youtube_url: finalSrc === 'YOUTUBE' ? yt : '',
      storage_path: finalSrc === 'UPLOAD' ? path : '',
    };

    const target = btn || form.querySelector('button[type="submit"]');
    await ui.busy(target, 'Saving…', async () => {
      try {
        await api(`/v1/courses/${id}/slots/${sid}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        if (st.dead) return;
        st.pendingPath = '';
        toast('Lesson saved.');
        await refreshOutline();
        await refreshState();
        if (st.dead) return;
        paint();
      } catch (err) {
        if (root.contains(form)) ui.formError(form, err.message);
        else toast(err.message, 'warn');
      }
    });
  }

  // ── Step 4 · Tests ──────────────────────────────────────────────────────
  function stepFour() {
    if (!allSlots().length) {
      return emptyStep('Nothing to link a test to yet',
        'Add a lesson in step 2 first — a questionnaire or examination hangs off a lesson.',
        2, 'Go to structure');
    }
    ensureSelection();
    if (!st.selSlot) return ui.loading('lessons');
    const slot = getSlot(st.selSlot);
    if (!slot) return ui.loading('lessons');
    return `
      <div class="wz-content">
        ${pickList()}
        ${linkPanel(slot)}
      </div>`;
  }

  function ensureTests() {
    if (st.testsLoaded || st.testsBusy) return;
    st.testsBusy = true;
    Promise.all([
      api('/v1/questionnaires?mine=1&limit=200').catch(() => null),
      api('/v1/assessments?mine=1&limit=200').catch(() => null),
    ]).then(([qRes, aRes]) => {
      st.tests.QUESTIONNAIRE = qRes ? (ui.data(qRes) || []) : [];
      st.tests.ASSESSMENT = aRes ? (ui.data(aRes) || []) : [];
      st.testsLoaded = true;
      st.testsBusy = false;
      if (!st.dead && st.step === 4) paintMain();
    }).catch(() => {
      st.testsBusy = false;
    });
  }

  function findTest(type, tid) {
    if (!type || !tid) return null;
    return (st.tests[type] || []).find((t) => t.id === tid) || null;
  }

  function typeLabel(type) {
    const hit = TEST_TYPES.find(([v]) => v === type);
    return hit ? hit[1] : 'Test';
  }

  function linkPanel(slot) {
    const type = st.testType || slot.linked_test_type || 'QUESTIONNAIRE';
    const list = st.tests[type] || [];
    const linkedId = slot.linked_test_id || '';
    const linked = findTest(slot.linked_test_type, linkedId);
    const can = editable();
    const dis = can ? '' : ' disabled';

    return `
      <div class="card wz-editor">
        <div class="card-head">
          <span class="wz-panel-ic">${iconSvg(slot.linked_test_type === 'ASSESSMENT' ? 'cert' : 'quiz')}</span>
          <div class="wz-panel-title">
            <h3>Link a test</h3>
            <p class="sm muted">${esc(slot.title)}${
              slot.module_title ? ' &middot; ' + esc(slot.module_title) : ''}</p>
          </div>
          <span class="grow"></span>
          <span class="tag ${linkedId ? 'ok' : 'warn'}">${linkedId ? 'Linked' : 'Not linked'}</span>
        </div>

        ${linkedId
          ? ui.note(`Currently linked: <b>${esc(
              linked ? linked.title : typeLabel(slot.linked_test_type))}</b> — ${
              esc(typeLabel(slot.linked_test_type))}.`)
          : ui.note('No test is linked to this lesson yet.', 'warn')}

        <form data-form="link" novalidate>
          <div class="wz-grid">
            <div class="field">
              <label for="wz-ttype">Test type</label>
              <select id="wz-ttype" name="test_type" data-test-type${dis}>
                ${TEST_TYPES.map(([v, l]) => `<option value="${v}" ${
                  v === type ? 'selected' : ''}>${l}</option>`).join('')}
              </select>
            </div>
            <div class="field wz-span2">
              <label for="wz-tid">Test</label>
              <select id="wz-tid" name="test_id"${dis}>
                <option value="">Choose a test…</option>
                ${list.map((t) => `<option value="${esc(t.id)}" ${
                  t.id === linkedId ? 'selected' : ''}>${esc(t.title)}${
                    t.status ? ` — ${esc(statusLabel(t.status))}` : ''}</option>`).join('')}
              </select>
              ${list.length ? '' : `<p class="sm dim">You have no ${
                type === 'ASSESSMENT' ? 'examinations' : 'practice sets'} yet —
                <a class="link" href="#/tests">create one in Tests</a>.</p>`}
            </div>
          </div>
          <p class="wz-err" data-err></p>
          ${can ? `<div class="row gap wz-actions">
            <button type="submit" class="btn primary" data-link>Link test</button>
            <span class="grow"></span>
            ${linkedId
              ? '<button type="button" class="btn ghost" data-unlink>Unlink</button>'
              : ''}
          </div>` : ''}
        </form>

        <p class="sm dim">Only tests you own can be linked here. Supreme may link any test.</p>
      </div>`;
  }

  async function linkTest(btn) {
    const form = root.querySelector('form[data-form="link"]');
    if (!form || !editable() || !st.selSlot) return;
    ui.formError(form, '');
    const v = ui.formValues(form);
    if (!v.test_id) { ui.formError(form, 'Choose a test to link.'); return; }
    await ui.busy(btn, 'Linking…', async () => {
      try {
        await api(`/v1/courses/${id}/slots/${st.selSlot}/link-test`, {
          method: 'PUT',
          body: JSON.stringify({
            linked_test_type: v.test_type || 'QUESTIONNAIRE',
            linked_test_id: v.test_id,
          }),
        });
        if (st.dead) return;
        toast('Test linked to this lesson.');
        await refreshOutline();
        await refreshState();
        if (st.dead) return;
        paint();
      } catch (err) {
        if (root.contains(form)) ui.formError(form, err.message);
        else toast(err.message, 'warn');
      }
    });
  }

  async function unlinkTest(btn) {
    if (!st.selSlot || !editable()) return;
    const ok = await confirmAction(
      'Unlink this test?',
      'Trainees will no longer be able to open a test from this lesson.',
      'Unlink');
    if (!ok || st.dead) return;
    await ui.busy(btn, 'Unlinking…', async () => {
      try {
        await api(`/v1/courses/${id}/slots/${st.selSlot}/link-test`, {
          method: 'PUT',
          body: JSON.stringify({ linked_test_type: '', linked_test_id: '' }),
        });
        if (st.dead) return;
        toast('Test unlinked.');
        await refreshOutline();
        await refreshState();
        if (st.dead) return;
        paint();
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  // ── Step 5 · Review ─────────────────────────────────────────────────────
  function stepFive() {
    const c = st.counts;
    const status = (st.course && st.course.status) || '';
    const submitted = status === 'PENDING_RELEASE' || status === 'PUBLISHED';

    return `
      <div class="card wz-panel">
        <div class="card-head">
          <span class="wz-panel-ic">${iconSvg('flag')}</span>
          <div class="wz-panel-title">
            <h3>Review and submit</h3>
            <p class="sm muted">A quick pass over the course before it goes to
              Supreme for release.</p>
          </div>
          <span class="grow"></span>
          ${ui.tag(status)}
        </div>

        <div class="wz-tiles">
          ${ui.tile({ icon: 'book', value: c.modules || 0, label: 'Modules' })}
          ${ui.tile({ icon: 'file', value: c.slots || 0, label: 'Lessons' })}
          ${ui.tile({ icon: 'video', value: c.with_video || 0, label: 'Videos' })}
          ${ui.tile({ icon: 'quiz', value: c.with_test || 0, label: 'Linked tests' })}
        </div>

        <ul class="wz-check">
          ${checkRow(st.complete.s1, 'Basics', 'Title plus a description or subject')}
          ${checkRow(st.complete.s2, 'Structure', `${c.modules || 0} module(s), ${c.slots || 0} lesson(s)`)}
          ${checkRow(st.complete.s3, 'Content', `${c.with_video || 0} video(s), ${c.with_body || 0} reading(s)`)}
          ${checkRow(st.complete.s4, 'Linked test', `${c.with_test || 0} lesson(s) with a test`)}
          ${checkRow(st.complete.s5, 'Submitted', 'Sent to Supreme for release')}
        </ul>

        ${st.complete.s1 && st.complete.s2 && st.complete.s3
          ? ui.note('The course meets the minimum bar: it has a module, a lesson and at least one video.')
          : ui.note('Add at least one module, one lesson and one video or reading before submitting.', 'warn')}

        ${submitted
          ? ui.note(`This course is <b>${esc(statusLabel(status))}</b>. Supreme reviews it and either
              releases it or sends it back for changes.`, 'warn')
          : ''}

        <div class="row gap wz-actions">
          <button type="button" class="btn ghost" data-preview>Preview outline</button>
          <span class="grow"></span>
          <a class="btn ghost" href="#/courses/${esc(id)}">Course page</a>
          ${!submitted
            ? `<button type="button" class="btn primary" data-submit ${
                st.canSubmit ? '' : 'disabled'}>Submit for release</button>`
            : ''}
        </div>
      </div>`;
  }

  function checkRow(ok, label, detail) {
    return `
      <li class="wz-check-row${ok ? ' is-ok' : ''}">
        <span class="wz-check-ic">${iconSvg(ok ? 'check' : 'clock')}</span>
        <span class="wz-check-txt">
          <b>${esc(label)}</b>
          <small>${esc(detail)}</small>
        </span>
        <span class="tag ${ok ? 'ok' : 'warn'}">${ok ? 'Done' : 'Pending'}</span>
      </li>`;
  }

  function previewOutline() {
    const mods = st.modules || [];
    const body = mods.length
      ? `<div class="wz-preview">${mods.map((m, i) => `
          <div class="wz-preview-mod">
            <div class="wz-preview-head">
              <span class="wz-mod-n">${i + 1}</span>
              <b>${esc(m.title)}</b>
              <span class="sm muted">${(m.slots || []).length} lesson${
                (m.slots || []).length === 1 ? '' : 's'}</span>
            </div>
            <ul class="wz-preview-slots">
              ${(m.slots || []).length
                ? m.slots.map((s) => `
                    <li>${iconSvg(KIND_ICON[s.kind] || 'file')}
                      <span>${esc(s.title)}</span>
                      ${s.linked_test_id ? '<span class="tag info">Test</span>' : ''}</li>`).join('')
                : '<li class="sm dim">No lessons yet.</li>'}
            </ul>
          </div>`).join('')}</div>`
      : '<p class="sm muted">This course has no modules yet.</p>';

    st.modal = true;
    openAppModal(`
      <h3 class="modal-title">Outline preview</h3>
      <p class="modal-sub">Exactly what a trainee sees in the course outline.</p>
      ${body}`);
  }

  async function submitCourse(btn) {
    if (!st.canSubmit || !editable()) return;
    const ok = await confirmAction(
      'Submit this course for release?',
      'Supreme reviews the course next. You can still view it here, and it can be sent back for changes.',
      'Submit');
    if (!ok || st.dead) return;
    await ui.busy(btn, 'Submitting…', async () => {
      try {
        await api(`/v1/courses/${id}/submit`, { method: 'POST', body: '{}' });
        if (st.dead) return;
        await refreshState();
        if (st.dead) return;
        paint();
        go(`/courses/${id}`);
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  // ── Shared bits ─────────────────────────────────────────────────────────
  function emptyStep(title, body, step, label) {
    return `
      <div class="card wz-panel">
        <div class="wz-empty">
          <span class="wz-empty-ic">${iconSvg('bookOpen')}</span>
          <b>${esc(title)}</b>
          <p class="sm muted">${esc(body)}</p>
          ${step ? `<button type="button" class="btn primary sm" data-step="${step}">${
            esc(label)}</button>` : ''}
        </div>
      </div>`;
  }

  // ── Delegated events (bound once, safe across repaints) ─────────────────
  offs.push(ui.on(root, '[data-retry]', 'click', (e) => { e.preventDefault(); mount(); }));
  offs.push(ui.click(root, '[data-retry-slot]', () => {
    st.detailFailed = '';
    st.detailErr = '';
    loadDetail(st.selSlot);
  }));
  offs.push(ui.click(root, '[data-step]', (e, btn) => gotoStep(btn.dataset.step)));
  offs.push(ui.click(root, '[data-prev]', () => gotoStep(st.step - 1)));
  offs.push(ui.click(root, '[data-next]', (e, btn) => next(btn)));
  offs.push(ui.click(root, '[data-submit]', (e, btn) => submitCourse(btn)));
  offs.push(ui.click(root, '[data-preview]', () => previewOutline()));

  // Step 1
  offs.push(ui.on(root, 'form[data-form="step1"]', 'submit', (e) => {
    e.preventDefault();
    saveStep1(true);
  }));
  offs.push(ui.click(root, '[data-save1]', (e, btn) => saveStep1(false, btn)));
  // Thumbnail chooser: artwork tiles, upload, and the optional link box.
  offs.push(ui.click(root, '[data-cover-art]', (e, btn) => setCover(btn.dataset.coverArt)));
  offs.push(ui.on(root, '[data-cover-file]', 'change', (e, el) => uploadCover(el)));
  offs.push(ui.on(root, '[data-cover-link]', 'input', (e, el) => {
    // Live preview while typing, but never rewrite the box being typed in.
    const raw = String(el.value || '').trim();
    if (raw && raw.length <= COVER_MAX && isCoverUrl(raw)) setCover(raw);
  }));
  offs.push(ui.on(root, '[data-cover-link]', 'change', (e, el) => commitCoverLink(el)));

  // Step 2
  offs.push(ui.on(root, 'form[data-add-mod]', 'submit', (e) => {
    e.preventDefault();
    addModule(e.target);
  }));
  offs.push(ui.on(root, 'form[data-add-slot]', 'submit', (e) => {
    e.preventDefault();
    addSlot(e.target);
  }));
  offs.push(ui.click(root, '[data-mod-save]', (e, btn) => saveModule(btn)));
  offs.push(ui.click(root, '[data-mod-up]', (e, btn) => moveModule(btn, -1)));
  offs.push(ui.click(root, '[data-mod-down]', (e, btn) => moveModule(btn, 1)));
  offs.push(ui.click(root, '[data-mod-del]', (e, btn) => deleteModule(btn)));
  offs.push(ui.click(root, '[data-slot-save]', (e, btn) => saveSlotTitle(btn)));
  offs.push(ui.click(root, '[data-slot-del]', (e, btn) => deleteSlot(btn)));

  // Step 3
  offs.push(ui.click(root, '[data-slot-pick]', (e, btn) => pickSlot(btn.dataset.id)));
  offs.push(ui.on(root, 'form[data-form="slot"]', 'submit', (e) => {
    e.preventDefault();
    saveSlotContent(e.target.querySelector('[data-save-slot]'));
  }));
  offs.push(ui.on(root, '[data-kind]', 'change', () => {
    syncDetail();
    paintMain();
  }));
  offs.push(ui.on(root, '[data-vsrc]', 'change', (e, el) => toggleVideo(el.value)));
  offs.push(ui.on(root, '[data-video]', 'change', (e, el) => uploadVideo(el)));
  offs.push(ui.on(root, '[data-att]', 'change', (e, el) => uploadAttachment(el)));
  offs.push(ui.click(root, '[data-att-del]', (e, btn) => deleteAttachment(btn)));

  // Step 4
  offs.push(ui.on(root, '[data-test-type]', 'change', (e, el) => {
    st.testType = el.value;
    paintMain();
  }));
  offs.push(ui.on(root, 'form[data-form="link"]', 'submit', (e) => {
    e.preventDefault();
    linkTest(e.target.querySelector('[data-link]'));
  }));
  offs.push(ui.click(root, '[data-unlink]', (e, btn) => unlinkTest(btn)));

  mount();

  return {
    destroy() {
      st.dead = true;
      st.gen += 1;
      offs.forEach((off) => off());
      if (st.modal) closeAppModal();
    },
  };
}
