// Learnify — content player and test runner.
// Routes: `/learn/{id}` · `/learn/{id}/{slotId}` · `/take/{kind}/{id}`
//
// Two handlers live here and share nothing but the toolkit:
//   * `course`  — the unified two-pane player: outline rail on the left, the
//                 current lesson (video / reading / link / test + attachments)
//                 on the right, with the 90% watch rule and resumable position.
//   * `attempt` — the timed MCQ runner. `kind === 'q'` is practice with a
//                 deadline, `kind === 'a'` is the formal examination whose pass
//                 issues a certificate.
//
// Both return `{ destroy }`: the player holds a progress throttle and native
// media listeners, the runner holds a countdown and an autosave interval.

import { api, esc, toast } from './utils.js?v=62';
import * as ui from './ui.js?v=62';
import { go, confirmAction, currentUser } from './app.js?v=62';
import { iconSvg } from './icons.js?v=62';

const KIND_ICON = { VIDEO: 'video', READING: 'file', LINK: 'link', TEST: 'quiz' };
const KIND_LABEL = { VIDEO: 'Video', READING: 'Reading', LINK: 'Link', TEST: 'Test' };
const MB = 1024 * 1024;

// ─── Small shared helpers ──────────────────────────────────────────────────

function flatten(modules) {
  const out = [];
  for (const m of modules || []) {
    for (const s of m.slots || []) out.push(Object.assign({}, s, { module_id: m.id }));
  }
  return out;
}

function fmtClock(ms) {
  const t = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function fmtSize(bytes) {
  const n = Number(bytes) || 0;
  if (n >= MB) return `${Math.round(n / MB * 10) / 10} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

/** Only http(s) survives; anything else is shown as plain text instead. */
function safeUrl(raw) {
  const s = String(raw || '').trim();
  if (!s) return '';
  if (/^https?:\/\//i.test(s)) return s;
  if (/^\/\//.test(s)) return 'https:' + s;
  if (/^[\w.-]+\.[a-z]{2,}/i.test(s)) return 'https://' + s;
  return '';
}

/** Escaped paragraphs — server text never becomes markup. */
function paragraphs(text) {
  return String(text || '')
    .split(/\n{2,}/)
    .filter((p) => p.trim())
    .map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`)
    .join('');
}

function triggerDownload(url) {
  const a = document.createElement('a');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ─── 1 · Course player ─────────────────────────────────────────────────────

export async function course(root, ctx) {
  const cid = ctx.params.id;
  const user = ctx.user || currentUser();
  const isTrainee = !user || user.role === 'ALPHA';

  root.innerHTML = ui.loading('course');

  let course, outline, participation;
  try {
    const [cRes, oRes, pRes] = await Promise.all([
      api(`/v1/courses/${cid}`),
      api(`/v1/courses/${cid}/outline`),
      api(`/v1/participation/course/${cid}`).catch(() => null),
    ]);
    course = ui.data(cRes);
    outline = ui.data(oRes);
    participation = pRes ? ui.data(pRes) : null;
    if (!course || !outline) throw new Error('Course not found.');
  } catch (err) {
    root.innerHTML = ui.head({ title: 'Course' })
      + ui.blank({ title: 'Course unavailable', body: esc(err.message) });
    return {};
  }

  const st = {
    cid,
    isTrainee,
    course,
    modules: outline.modules || [],
    counts: outline.counts || {},
    progress: participation,
    slotId: ctx.params.slot || '',
    flat: flatten(outline.modules),
    collapsed: new Set(),
    detail: null,
    detailSlot: '',
    attachments: [],
    slotProg: null,
    videoUrl: '',
    videoError: '',
    gen: 0,
    media: null,
    throttle: 0,
    lastPost: 0,
    lastPos: 0,
    watchAccum: 0,
    completedOnce: false,
    dead: false,
  };
  const offs = [];

  // Nothing to play yet → say so instead of pointing at an empty URL.
  if (!st.flat.length) {
    root.innerHTML = `
      <div class="crumbs"><a href="#/courses">&larr; All courses</a> / <a href="#/courses/${esc(cid)}">${esc(course.title)}</a></div>`
      + ui.head({ title: course.title, sub: esc(course.trainer_name || '') })
      + ui.blank({
          title: 'No lessons yet',
          body: 'This course has no published lessons. Check back once the trainer adds content.',
          action: 'Course page',
          actionHref: `#/courses/${cid}`,
        });
    return {};
  }

  // `/learn/{id}` with no slot → land on the first lesson.
  if (!st.slotId) {
    go(`/learn/${cid}/${st.flat[0].id}`);
    return {};
  }

  const current = () => st.flat.find((s) => s.id === st.slotId) || null;
  const isDone = (sid) => !!(st.progress && st.progress.slots
    && st.progress.slots[sid] && st.progress.slots[sid].completed);

  root.innerHTML = `
    <div class="crumbs">
      <a href="#/courses">&larr; All courses</a> /
      <a href="#/courses/${esc(cid)}">${esc(course.title)}</a>
    </div>
    ${ui.head({
      title: course.title,
      sub: `${esc(course.trainer_name || 'Independent trainer')}${
        course.subject_name ? ' &middot; ' + esc(course.subject_name) : ''}`,
      actions: `<a class="btn ghost sm" href="#/courses/${esc(cid)}">Course page</a>`,
    })}
    <div class="ply-shell">
      <aside class="ply-rail" data-rail></aside>
      <section class="ply-main" data-main></section>
    </div>`;

  const railEl = root.querySelector('[data-rail]');
  const mainEl = root.querySelector('[data-main]');

  // ── Outline rail ─────────────────────────────────────────────────────────
  function paintRail() {
    const total = st.flat.length;
    const done = st.flat.filter((s) => isDone(s.id)).length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    railEl.innerHTML = `
      <div class="card ply-rail-card">
        <div class="card-head">
          <h3>Course outline</h3>
          <span class="tag ${done === total ? 'ok' : 'info'}">${done}/${total}</span>
        </div>
        ${ui.progressBar(pct, `${done} of ${total} lessons`)}
        <div class="ply-mods">
          ${st.modules.length
            ? st.modules.map(modHtml).join('')
            : '<p class="sm muted">No modules yet.</p>'}
        </div>
      </div>`;
  }

  function modHtml(m) {
    const slots = m.slots || [];
    const open = !st.collapsed.has(m.id);
    const done = slots.filter((s) => isDone(s.id)).length;
    return `
      <div class="ply-mod${open ? ' open' : ''}">
        <button type="button" class="ply-mod-head" data-mod="${esc(m.id)}"
                aria-expanded="${open}">
          <span class="ply-chev">${open ? '&#9662;' : '&#9656;'}</span>
          <b>${esc(m.title)}</b>
          <span class="grow"></span>
          <span class="sm muted">${done}/${slots.length}</span>
        </button>
        ${open ? (slots.length
          ? `<ul class="ply-slots">${slots.map(slotRow).join('')}</ul>`
          : '<p class="sm muted ply-empty">No lessons in this module yet.</p>') : ''}
      </div>`;
  }

  function slotRow(s) {
    const active = s.id === st.slotId;
    const done = isDone(s.id);
    return `
      <li><a class="ply-slot${active ? ' is-active' : ''}${done ? ' is-done' : ''}"
             href="#/learn/${esc(cid)}/${esc(s.id)}">
        <span class="ply-tick">${done ? iconSvg('check') : iconSvg(KIND_ICON[s.kind] || 'file')}</span>
        <span class="ply-slot-t">${esc(s.title)}</span>
        ${s.linked_test_id ? `<span class="ply-test" title="Linked test">${iconSvg('quiz')}</span>` : ''}
      </a></li>`;
  }

  // ── Current lesson ───────────────────────────────────────────────────────
  async function paintMain() {
    const slot = current();
    if (!slot) {
      mainEl.innerHTML = ui.blank({
        title: 'Lesson not found',
        body: 'That lesson is no longer part of this course.',
        action: 'Course page',
        actionHref: `#/courses/${cid}`,
      });
      return;
    }

    clearMedia();
    const gen = ++st.gen;
    st.detail = null;
    st.detailSlot = slot.id;
    st.attachments = [];
    st.slotProg = null;
    st.videoUrl = '';
    st.videoError = '';
    st.completedOnce = isDone(slot.id);
    st.watchAccum = 0;
    st.lastPos = 0;
    st.lastPost = 0;
    mainEl.innerHTML = ui.loading('lesson');

    try {
      const [dRes, aRes, pRes] = await Promise.all([
        api(`/v1/courses/${cid}/slots/${slot.id}`).catch(() => null),
        api(`/v1/courses/${cid}/slots/${slot.id}/attachments`).catch(() => null),
        api(`/v1/participation/slot/${slot.id}`).catch(() => null),
      ]);
      if (st.dead || gen !== st.gen) return;
      st.detail = dRes ? ui.data(dRes) : null;
      st.attachments = aRes ? (ui.data(aRes) || []) : [];
      st.slotProg = pRes ? ui.data(pRes) : null;
      if (st.slotProg && st.slotProg.completed) st.completedOnce = true;

      // Uploaded video needs a signed URL before it can be rendered.
      const detail = st.detail;
      const source = (detail && detail.video_source) || slot.video_source;
      if (slot.kind === 'VIDEO' && source === 'UPLOAD') {
        const path = detail && detail.storage_path;
        if (!path) {
          st.videoError = 'This lesson has no uploaded video attached yet.';
        } else {
          try {
            const sRes = await api(`/v1/library/files/sign?path=${encodeURIComponent(path)}&bucket=course-attachments&expires=3600`);
            const d = ui.data(sRes) || {};
            st.videoUrl = d.url || '';
            if (!st.videoError && !st.videoUrl) st.videoError = 'The video could not be signed for playback.';
          } catch (err) {
            st.videoError = err.message;
          }
        }
      }
      if (st.dead || gen !== st.gen) return;

      mainEl.innerHTML = slotHtml(slot);
      wireMedia(slot);
      updateStatus();
    } catch (err) {
      if (st.dead || gen !== st.gen) return;
      mainEl.innerHTML = ui.errorBlock(err.message);
    }
  }

  function slotHtml(slot) {
    return `
      <article class="card ply-lesson">
        <div class="card-head ply-lesson-head">
          <span class="ply-kind">${iconSvg(KIND_ICON[slot.kind] || 'file')}</span>
          <div class="ply-lesson-title">
            <span class="sm muted">${esc(slot.module_title || '')}</span>
            <h3>${esc(slot.title)}</h3>
          </div>
          <span data-slot-status></span>
        </div>
        <div data-slot-body>${slotBody(slot)}</div>
        ${attachHtml()}
        <div class="card-foot ply-foot" data-slot-foot></div>
      </article>`;
  }

  function slotBody(slot) {
    const detail = st.detail || {};
    const parts = [];

    if (slot.kind === 'VIDEO') parts.push(videoHtml(slot, detail));
    else if (slot.kind === 'READING') parts.push(readHtml(detail));
    else if (slot.kind === 'LINK') parts.push(linkHtml(detail));
    else if (slot.kind === 'TEST') parts.push(testCard(slot));

    // Reading notes travel with a video slot too.
    if (slot.kind === 'VIDEO' && (detail.body || '').trim()) {
      parts.push(`
        <div class="ply-notes">
          <div class="card-head"><h3>Lesson notes</h3></div>
          ${paragraphs(detail.body)}
        </div>`);
    }

    // A linked test can sit on any kind of lesson.
    if (slot.kind !== 'TEST' && slot.linked_test_id) parts.push(testCard(slot));
    if (!parts.length) {
      parts.push(ui.note('This lesson has no content yet.'));
    }
    return parts.join('');
  }

  function videoHtml(slot, detail) {
    const source = detail.video_source || slot.video_source || '';
    if (source === 'YOUTUBE') {
      const yt = detail.youtube_id || '';
      if (!yt) return ui.note('This YouTube lesson is not configured yet.', 'warn');
      return `
        <div class="ply-media">
          <iframe src="https://www.youtube-nocookie.com/embed/${esc(yt)}"
                  title="${esc(slot.title)}" frameborder="0"
                  allow="accelerometer; encrypted-media; picture-in-picture; encrypted-media"
                  allowfullscreen></iframe>
        </div>
        <div class="row gap sm muted ply-media-note">
          ${iconSvg('play')}<span>Watch time on YouTube cannot be tracked — use
          <b>Mark complete</b> when you have finished watching.</span>
        </div>`;
    }
    if (source === 'UPLOAD') {
      if (st.videoError) return ui.note(esc(st.videoError), 'warn');
      if (!st.videoUrl) return ui.loading('video');
      const dur = Math.round((detail.duration_seconds || slot.duration_seconds || 0));
      return `
        <div class="ply-media">
          <video data-media controls playsinline preload="metadata"
                 src="${esc(st.videoUrl)}"></video>
        </div>
        <div class="row gap sm muted ply-media-note">
          ${iconSvg('clock')}<span>Progress saves every few seconds${
            dur ? ` &middot; ${Math.round(dur / 60)} min lesson` : ''}. Complete at
            90% watched.</span>
        </div>`;
    }
    return ui.note('No video has been attached to this lesson yet.', 'warn');
  }

  function readHtml(detail) {
    const body = (detail.body || '').trim();
    if (!body) {
      return ui.note(
        st.detail === null
          ? 'This reading could not be loaded.'
          : 'This reading has no text yet.', 'warn');
    }
    return `<div class="ply-read">${paragraphs(body)}</div>`;
  }

  function linkHtml(detail) {
    const raw = (detail.body || '').trim();
    const url = safeUrl(raw);
    if (!raw) return ui.note('No link has been added to this lesson yet.', 'warn');
    return `
      <div class="ply-link">
        <span class="ply-link-ic">${iconSvg('link')}</span>
        <div class="ply-link-body">
          <b>External resource</b>
          <p class="sm muted">${esc(raw)}</p>
        </div>
        ${url
          ? `<a class="btn primary sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open link</a>`
          : '<span class="tag warn">Invalid URL</span>'}
      </div>`;
  }

  function testCard(slot) {
    const type = slot.linked_test_type || '';
    const id = slot.linked_test_id || '';
    if (!id) {
      return slot.kind === 'TEST'
        ? ui.note('No test is linked to this lesson yet.', 'warn')
        : '';
    }
    const isExam = type === 'ASSESSMENT';
    return `
      <div class="ply-linked${isExam ? ' is-exam' : ''}">
        <span class="ply-linked-ic">${iconSvg(isExam ? 'cert' : 'quiz')}</span>
        <div class="ply-linked-body">
          <b>${isExam ? 'Examination' : 'Practice set'}</b>
          <p class="sm muted">${isExam
            ? 'Timed and formal — passing issues a certificate.'
            : 'Practice with a deadline. No certificate is issued.'}</p>
        </div>
        <a class="btn primary sm" href="#/take/${isExam ? 'a' : 'q'}/${esc(id)}">Open test</a>
      </div>`;
  }

  function attachHtml() {
    const list = st.attachments;
    if (!list.length) return '';
    return `
      <div class="ply-att">
        <div class="card-head"><h3>Attachments</h3>
          <span class="sm muted">${list.length}</span></div>
        <ul class="ply-att-list">
          ${list.map((a) => `
            <li>
              <span class="ply-att-ic">${iconSvg('file')}</span>
              <span class="ply-att-t">${esc(a.filename)}
                <small>${esc(fmtSize(a.size_bytes))}</small></span>
              <button type="button" class="btn ghost sm" data-dl="${esc(a.id)}">Download</button>
            </li>`).join('')}
        </ul>
      </div>`;
  }

  // Status chip + footer are re-painted without touching the media element.
  function updateStatus() {
    const slot = current();
    if (!slot) return;
    const done = isDone(slot.id);
    const prog = st.slotProg;
    const statusEl = mainEl.querySelector('[data-slot-status]');
    const footEl = mainEl.querySelector('[data-slot-foot]');
    if (statusEl) {
      statusEl.innerHTML = `${done ? ui.tone('Completed', 'ok') : ui.tone(KIND_LABEL[slot.kind] || 'Lesson', 'mute')}${
        !done && prog && Number(prog.progress_pct) > 0
          ? ` <span class="sm muted">${Math.round(prog.progress_pct)}% watched</span>` : ''}`;
    }
    if (footEl) footEl.innerHTML = footHtml(slot);
  }

  function footHtml(slot) {
    const i = st.flat.findIndex((s) => s.id === slot.id);
    const prev = i > 0 ? st.flat[i - 1] : null;
    const next = i >= 0 && i < st.flat.length - 1 ? st.flat[i + 1] : null;
    const done = isDone(slot.id);
    const tracked = slot.kind === 'VIDEO' && st.detail
      && st.detail.video_source === 'UPLOAD';
    const pct = st.slotProg ? Math.round(Number(st.slotProg.progress_pct) || 0) : 0;

    let note = '';
    if (!done && tracked && pct < 90) {
      note = ui.note(
        `Watch at least <b>90%</b> of this video before marking it complete — you are at <b>${pct}%</b>.`,
        'warn');
    }

    return `
      <button type="button" class="btn ghost sm" data-prev
        ${prev ? '' : 'disabled'}>&larr; Previous</button>
      <span class="grow"></span>
      ${done
        ? '<span class="sm dim">Lesson complete</span>'
        : (st.isTrainee
          ? `<button type="button" class="btn primary sm" data-complete>Mark complete</button>`
          : '<span class="sm dim">Preview mode — progress is not recorded</span>')}
      <button type="button" class="btn ghost sm" data-next
        ${next ? '' : 'disabled'}>Next &rarr;</button>
      ${note ? `<div class="ply-foot-note">${note}</div>` : ''}`;
  }

  const goSlot = (delta) => {
    const i = st.flat.findIndex((s) => s.id === st.slotId);
    const target = st.flat[i + delta];
    if (target) go(`/learn/${cid}/${target.id}`);
  };

  // ── Playback tracking (90% rule) ─────────────────────────────────────────
  function clearMedia() {
    if (st.throttle) { clearInterval(st.throttle); st.throttle = 0; }
    if (st.media) {
      for (const pair of st.media.handlers) {
        st.media.el.removeEventListener(pair[0], pair[1]);
      }
      st.media = null;
    }
  }

  function wireMedia(slot) {
    const el = mainEl.querySelector('video[data-media]');
    if (!el) return;

    const onTime = () => {
      const pos = el.currentTime || 0;
      const delta = pos - st.lastPos;
      if (delta > 0 && delta < 5) st.watchAccum += delta;   // ignore scrubbing
      st.lastPos = pos;
      const dur = el.duration || 0;
      if (dur && pos / dur >= 0.9) completeFromVideo(slot, el, dur);
    };
    const onEnded = () => { st.lastPos = el.currentTime || 0; completeFromVideo(slot, el, el.duration || 0); };
    const onPause = () => { flushProgress(el, true); };

    el.addEventListener('timeupdate', onTime);
    el.addEventListener('ended', onEnded);
    el.addEventListener('pause', onPause);
    st.media = { el, handlers: [['timeupdate', onTime], ['ended', onEnded], ['pause', onPause]] };

    // Resume where the trainee left off.
    const resume = st.slotProg ? Number(st.slotProg.resume_from) || 0 : 0;
    if (resume > 3) {
      const seek = () => {
        try {
          const dur = el.duration || resume + 30;
          el.currentTime = Math.min(resume, Math.max(0, dur - 5));
        } catch (_) { /* metadata not ready — ignore */ }
      };
      if (el.readyState >= 1) seek();
      else el.addEventListener('loadedmetadata', seek, { once: true });
    }

    st.throttle = setInterval(() => flushProgress(el, false), 10000);
  }

  function flushProgress(el, force) {
    const slot = current();
    if (!slot || st.dead) return;
    const dur = Math.round(el.duration || st.detail && st.detail.duration_seconds
      || (st.slotProg && st.slotProg.duration_seconds) || 0);
    const pos = Math.round(el.currentTime || 0);
    if (!dur) return;

    if (pos / dur >= 0.9 || el.ended) { completeFromVideo(slot, el, dur); return; }
    if (!force && Date.now() - st.lastPost < 10000) return;
    if (force && !pos) return;

    st.lastPost = Date.now();
    const delta = Math.min(3600, Math.max(0, Math.floor(st.watchAccum)));
    st.watchAccum = 0;
    api('/v1/participation/progress', {
      method: 'POST',
      body: JSON.stringify({
        slot_id: slot.id,
        position_seconds: Math.min(86400, pos),
        duration_seconds: Math.min(86400, dur),
        watched_delta: delta,
      }),
    }).then(() => { if (st.slotProg) st.slotProg.last_position_seconds = pos; })
      .catch(() => { /* a dropped heartbeat never breaks playback */ });
  }

  function completeFromVideo(slot, el, dur) {
    if (st.completedOnce || st.dead) return;
    st.completedOnce = true;
    if (st.throttle) { clearInterval(st.throttle); st.throttle = 0; }
    flushProgress(el, true);
    api('/v1/participation/complete', {
      method: 'POST',
      body: JSON.stringify({ slot_id: slot.id }),
    }).then(() => {
      if (st.dead) return;
      toast('Slot completed');
      refreshProgress().then(() => { if (!st.dead) { paintRail(); updateStatus(); } });
      syncEnrollment();
    }).catch((err) => {
      st.completedOnce = false;
      if (!st.dead) toast(err.message, 'warn');
    });
  }

  async function markComplete(btn) {
    const slot = current();
    if (!slot) return;
    await ui.busy(btn, 'Saving…', async () => {
      try {
        const tracked = slot.kind === 'VIDEO' && st.detail
          && st.detail.video_source === 'UPLOAD';
        if (!tracked) {
          // No watch clock on readings, links and YouTube — record a finished
          // pass so the 90% bar the server enforces is satisfied honestly.
          await api('/v1/participation/progress', {
            method: 'POST',
            body: JSON.stringify({
              slot_id: slot.id, position_seconds: 100,
              duration_seconds: 100, watched_delta: 0,
            }),
          });
        }
        const res = await api('/v1/participation/complete', {
          method: 'POST',
          body: JSON.stringify({ slot_id: slot.id }),
        });
        const d = ui.data(res) || {};
        st.completedOnce = true;
        if (st.slotProg) { st.slotProg.completed = true; st.slotProg.progress_pct = 100; }
        toast(d.course_complete ? 'Course completed — well done.' : 'Slot completed');
        await refreshProgress();
        if (d.course_complete) syncEnrollment();
        if (!st.dead) { paintRail(); updateStatus(); }
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  async function refreshProgress() {
    try {
      const res = await api(`/v1/participation/course/${cid}`);
      if (!st.dead) st.progress = ui.data(res);
    } catch (_) { /* keep the previous ticks */ }
  }

  function syncEnrollment() {
    api(`/v1/participation/enrollment/${cid}/sync`, { method: 'POST', body: '{}' })
      .catch(() => { /* only trainees have an enrollment */ });
  }

  async function download(btn) {
    const id = btn.dataset.dl;
    const file = st.attachments.find((a) => a.id === id);
    if (!file) return;
    await ui.busy(btn, 'Opening…', async () => {
      try {
        const res = await api(`/v1/library/files/sign?path=${encodeURIComponent(file.storage_path)}&bucket=course-attachments&expires=3600`);
        const d = ui.data(res) || {};
        if (!d.url) throw new Error('This file could not be opened.');
        triggerDownload(d.url);
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  // ── Delegated events (bound once, safe across repaints) ──────────────────
  offs.push(ui.click(root, '[data-mod]', (e, btn) => {
    const id = btn.dataset.mod;
    if (st.collapsed.has(id)) st.collapsed.delete(id);
    else st.collapsed.add(id);
    paintRail();
  }));
  offs.push(ui.click(root, '[data-prev]', () => goSlot(-1)));
  offs.push(ui.click(root, '[data-next]', () => goSlot(1)));
  offs.push(ui.click(root, '[data-complete]', (e, btn) => markComplete(btn)));
  offs.push(ui.click(root, '[data-dl]', (e, btn) => download(btn)));

  paintRail();
  paintMain();

  return {
    destroy() {
      st.dead = true;
      flushOnLeave();
      clearMedia();
      offs.forEach((off) => off());
    },
  };

  // Best-effort checkpoint when the trainee navigates away mid-video.
  function flushOnLeave() {
    const el = st.media && st.media.el;
    if (!el) return;
    const slot = current();
    if (!slot) return;
    const dur = Math.round(el.duration || (st.detail && st.detail.duration_seconds) || 0);
    const pos = Math.round(el.currentTime || 0);
    if (!dur || !pos) return;
    api('/v1/participation/progress', {
      method: 'POST',
      body: JSON.stringify({
        slot_id: slot.id,
        position_seconds: Math.min(86400, pos),
        duration_seconds: Math.min(86400, dur),
        watched_delta: 0,
      }),
    }).catch(() => {});
  }
}

// ─── 2 · Test runner ───────────────────────────────────────────────────────

export async function attempt(root, ctx) {
  const kind = ctx.params.kind === 'a' ? 'a' : 'q';
  const isExam = kind === 'a';
  const id = ctx.params.id;
  const base = isExam ? '/v1/assessments' : '/v1/questionnaires';
  const user = ctx.user || currentUser();

  const st = {
    kind, id, isExam, base,
    phase: 'boot',
    container: null,
    attempts: [],
    attempt: null,
    questions: [],
    answers: {},
    idx: 0,
    result: null,
    startedAt: 0,
    durationMs: 0,
    tick: 0,
    autosave: 0,
    retry: 0,
    submitting: false,
    dead: false,
    offs: [],
  };

  root.innerHTML = ui.loading(isExam ? 'exam' : 'practice test');

  const stopTimers = () => {
    if (st.tick) { clearInterval(st.tick); st.tick = 0; }
    if (st.autosave) { clearInterval(st.autosave); st.autosave = 0; }
    if (st.retry) { clearTimeout(st.retry); st.retry = 0; }
  };

  const answeredCount = () => st.questions
    .filter((q) => st.answers[q.id]).length;

  const responses = () => st.questions
    .filter((q) => st.answers[q.id])
    .map((q) => ({ question_id: q.id, option_id: st.answers[q.id] }));

  // The answer key never reaches this file: `is_correct` and `explanation`
  // are dropped on the way in, whatever endpoint supplied the question.
  const normalise = (list) => (list || []).map((q) => ({
    id: q.id,
    text: q.text || '',
    difficulty: q.difficulty || 'medium',
    points: Number(q.points) || 1,
    options: (q.options || []).map((o) => ({ id: o.id, text: o.text || '' })),
  }));

  if (user && user.role !== 'ALPHA') {
    root.innerHTML = ui.head({ title: isExam ? 'Examination' : 'Practice test' })
      + ui.blank({
          title: 'Trainees only',
          body: 'A test can only be sat by a trainee account. Sign in as a trainee to take this test.',
          action: 'Back to tests',
          actionHref: '#/tests',
        });
    return {};
  }

  // ── Load the container and any prior attempts ────────────────────────────
  async function mount() {
    st.phase = 'boot';
    root.innerHTML = ui.loading(isExam ? 'exam' : 'practice test');
    let container, attempts;
    try {
      const [cRes, aRes] = await Promise.all([
        api(`${base}/${id}`),
        api(`${base}/${id}/attempts/mine`),
      ]);
      container = ui.data(cRes);
      attempts = ui.data(aRes) || [];
      if (!container) throw new Error('Test not found.');
    } catch (err) {
      root.innerHTML = ui.head({ title: isExam ? 'Examination' : 'Practice test' })
        + ui.errorBlock(err.message);
      return;
    }
    if (st.dead) return;
    st.container = container;
    st.attempts = attempts;

    const live = attempts.find((a) => a.status === 'IN_PROGRESS');
    const maxAttempts = isExam ? 1 : Number(container.max_attempts || 1);
    const deadlinePassed = !!container.overdue
      || (!!container.deadline_at && ui.countdown(container.deadline_at) === 'closed');

    if (!live) {
      if (container.status && container.status !== 'PUBLISHED') {
        paintBlocked('This test is not open',
          `Its status is ${String(container.status).toLowerCase()}, so there is nothing to sit yet.`);
        return;
      }
      if (deadlinePassed) {
        paintBlocked('The deadline has passed',
          `The window for “${container.title}” closed on ${
            ui.fmtDate(container.deadline_at, { withTime: true })}.`);
        return;
      }
      if (attempts.length >= maxAttempts) {
        paintExhausted(container, attempts);
        return;
      }
    }

    st.phase = 'intro';
    paintIntro();
  }

  function paintBlocked(title, body) {
    root.innerHTML = `
      <div class="crumbs"><a href="#/tests">&larr; Tests</a></div>`
      + ui.head({ title: isExam ? 'Examination' : 'Practice test' })
      + ui.blank({ title, body: esc(body), action: 'Back to tests', actionHref: '#/tests' });
  }

  function paintExhausted(container, attempts) {
    const best = attempts.reduce((m, a) => Math.max(m, Number(a.percentage) || 0), 0);
    root.innerHTML = `
      <div class="crumbs"><a href="#/tests">&larr; Tests</a></div>`
      + ui.head({ title: container.title, sub: esc(container.description || '') })
      + ui.blank({
          title: 'No attempts left',
          body: esc(`You have used every attempt for this test. Your best result was ${
            Math.round(best)}%.`),
          action: 'View reports',
          actionHref: '#/reports',
        })
      + (attempts.length ? `<div class="card">${attemptTable(attempts)}</div>` : '');
  }

  function attemptTable(attempts) {
    return ui.table([
      { label: 'Attempt', get: (a) => `#${esc(a.attempt_no)}` },
      { label: 'When', get: (a) => esc(ui.fmtDate(a.submitted_at || a.started_at, { withTime: true })) },
      { label: 'Score', get: (a) => `${esc(a.percentage)}%` },
      { label: 'Status', get: (a) => ui.tag(a.status) },
    ], attempts, 'id');
  }

  // ── Intro ────────────────────────────────────────────────────────────────
  function paintIntro() {
    const c = st.container;
    const live = st.attempts.find((a) => a.status === 'IN_PROGRESS');
    const used = st.attempts.length;
    const maxAttempts = isExam ? 1 : Number(c.max_attempts || 1);
    const cd = c.deadline_at ? ui.countdown(c.deadline_at) : '';

    root.innerHTML = `
      <div class="crumbs"><a href="#/tests">&larr; Tests</a></div>
      ${ui.head({
        title: c.title,
        sub: esc(c.description || ''),
        actions: isExam ? ui.tone('Examination', 'warn') : ui.tone('Practice', 'info'),
      })}
      <div class="ply-intro${isExam ? ' is-exam' : ' is-practice'}">
        <div class="ply-mode">
          <span class="ply-mode-ic">${iconSvg(isExam ? 'cert' : 'quiz')}</span>
          <div>
            <b>${isExam ? 'Formal examination' : 'Practice with a deadline'}</b>
            <p>${isExam
              ? 'One timed attempt. A pass issues a certificate against your record and a full performance report.'
              : 'Formative practice — no certificate is issued, and you may retry while attempts remain.'}</p>
          </div>
        </div>
        ${ui.kv([
          ['Questions', String(c.question_count || 0)],
          ['Time limit', `${Number(c.duration_minutes) || 30} min`],
          ['Deadline', c.deadline_at
            ? ui.fmtDate(c.deadline_at, { withTime: true }) : 'No deadline'],
          isExam ? ['Passing score', `${c.passing_score}% of ${c.max_score}`] : null,
          isExam ? ['Attempts', '1 attempt only']
                 : ['Attempts', `${used} of ${maxAttempts} used`],
          ['Subject', c.subject_name || '—'],
        ].filter(Boolean))}
        ${cd ? ui.note(`${isExam ? 'Closes in' : 'Window:'} <b>${esc(cd)}</b>`) : ''}
        ${!c.question_count
          ? ui.note('This test has no questions yet.', 'warn') : ''}
        <button type="button" class="btn primary block" data-start>${
          live ? 'Resume test'
               : (isExam ? 'Start examination' : 'Start practice')}</button>
        ${st.attempts.length ? `<div class="ply-prior">
          <div class="card-head"><h3>Earlier attempts</h3></div>
          ${attemptTable(st.attempts)}
        </div>` : ''}
      </div>`;
  }

  async function start(btn) {
    await ui.busy(btn, 'Starting…', async () => {
      try {
        const res = await api(`${base}/${id}/start`, { method: 'POST', body: '{}' });
        const d = ui.data(res) || {};
        if (st.dead) return;
        st.attempt = d.attempt || {};
        st.questions = normalise(d.questions);
        if (!st.questions.length) {
          const qRes = await api(`${base}/${id}/questions`);
          st.questions = normalise(ui.data(qRes));
        }
        if (st.dead) return;
        if (!st.questions.length) {
          toast('This test has no questions yet.', 'warn');
          return;
        }
        st.answers = {};
        // Questionnaires keep answers on the attempt, so a resume restores them.
        const saved = Array.isArray(st.attempt.responses) ? st.attempt.responses : [];
        saved.forEach((r) => {
          if (r && r.question_id && r.option_id) st.answers[r.question_id] = r.option_id;
        });
        enterRunner();
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  // ── Runner ───────────────────────────────────────────────────────────────
  function enterRunner() {
    st.phase = 'run';
    st.idx = 0;
    st.submitting = false;
    const minutes = Number(st.container.duration_minutes) || 30;
    st.durationMs = minutes * 60000;
    st.startedAt = Date.parse((st.attempt && st.attempt.started_at) || '') || Date.now();
    paintRun();
    st.tick = setInterval(tickTimer, 1000);
    if (isExam) st.autosave = setInterval(() => saveProgress(), 15000);
    tickTimer();
  }

  function tickTimer() {
    if (st.dead || st.phase !== 'run') return;
    const left = st.startedAt + st.durationMs - Date.now();
    const el = root.querySelector('[data-timer]');
    if (el) {
      el.textContent = fmtClock(left);
      el.classList.toggle('is-low', left < 60000);
    }
    if (left <= 0) submit(true);
  }

  function paintRun() {
    const c = st.container;
    root.innerHTML = `
      <div class="crumbs"><a href="#/tests">&larr; Tests</a></div>
      ${ui.head({
        title: c.title,
        sub: isExam ? 'Formal examination in progress' : 'Practice set in progress',
        actions: isExam ? ui.tone('Examination', 'warn') : ui.tone('Practice', 'info'),
      })}
      <div class="ply-run">
        <div class="ply-run-main" data-run-main></div>
        <aside class="ply-run-side">
          <div class="card ply-time-card">
            <span class="sm muted">Time left</span>
            <span class="ply-timer" data-timer>00:00</span>
            ${isExam ? '<span class="sm muted">Autosaved every 15 s</span>'
                     : '<span class="sm muted">Answers are kept while you go</span>'}
          </div>
          <div class="card ply-nav-card">
            <div class="card-head"><h3>Navigator</h3>
              <span class="sm muted" data-answered>0/${st.questions.length}</span></div>
            <div class="ply-grid" data-grid>${st.questions.map(navBtn).join('')}</div>
            <div class="ply-legend sm muted">
              <span class="ply-num is-ans"></span> answered
              <span class="ply-num is-cur"></span> current
            </div>
          </div>
          <button type="button" class="btn primary block" data-submit>Submit answers</button>
        </aside>
      </div>`;
    paintQuestion();
    refreshNav();
  }

  function navBtn(q, i) {
    return `<button type="button" class="ply-num" data-go-q="${i}">${i + 1}</button>`;
  }

  function paintQuestion() {
    const host = root.querySelector('[data-run-main]');
    if (!host) return;
    const q = st.questions[st.idx];
    if (!q) { host.innerHTML = ui.blank({ title: 'No questions', body: 'This test is empty.' }); return; }
    const chosen = st.answers[q.id];
    host.innerHTML = `
      <div class="card ply-q">
        <div class="card-head">
          <span class="ply-q-n">Question ${st.idx + 1} of ${st.questions.length}</span>
          <span class="tag mute">${esc(q.difficulty)}</span>
          <span class="sm muted">${q.points} ${q.points === 1 ? 'point' : 'points'}</span>
        </div>
        <p class="ply-q-text">${esc(q.text)}</p>
        <div class="ply-opts" role="radiogroup" aria-label="Answer options">
          ${q.options.map((o, i) => `
            <button type="button" class="ply-opt${o.id === chosen ? ' is-sel' : ''}"
                    data-opt="${esc(o.id)}" role="radio"
                    aria-checked="${o.id === chosen}">
              <span class="ply-opt-key">${'ABCDEFGH'[i] || '?'}</span>
              <span class="ply-opt-t">${esc(o.text)}</span>
              <span class="ply-opt-tick">${iconSvg('check')}</span>
            </button>`).join('')}
        </div>
        <div class="card-foot">
          <button type="button" class="btn ghost sm" data-nav="prev"
            ${st.idx === 0 ? 'disabled' : ''}>&larr; Previous</button>
          <span class="grow"></span>
          <button type="button" class="btn ghost sm" data-nav="next">${
            st.idx === st.questions.length - 1 ? 'Review' : 'Next &rarr;'}</button>
        </div>
      </div>`;
  }

  function refreshNav() {
    const grid = root.querySelector('[data-grid]');
    if (grid) {
      [...grid.children].forEach((b, i) => {
        const q = st.questions[i];
        b.classList.toggle('is-cur', i === st.idx);
        b.classList.toggle('is-ans', !!(q && st.answers[q.id]));
      });
    }
    const count = root.querySelector('[data-answered]');
    if (count) count.textContent = `${answeredCount()}/${st.questions.length}`;
  }

  function goto(n) {
    if (n < 0 || n >= st.questions.length) return;
    st.idx = n;
    paintQuestion();
    refreshNav();
    if (isExam) saveProgress();          // a refresh must not lose answers
    const head = root.querySelector('.ply-q');
    if (head && typeof head.scrollIntoView === 'function') {
      head.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function pickOption(btn) {
    const q = st.questions[st.idx];
    if (!q) return;
    st.answers[q.id] = btn.dataset.opt;
    root.querySelectorAll('[data-opt]').forEach((b) => {
      const on = b.dataset.opt === btn.dataset.opt;
      b.classList.toggle('is-sel', on);
      b.setAttribute('aria-checked', String(on));
    });
    refreshNav();
    if (isExam) saveProgress();
  }

  async function saveProgress() {
    if (!isExam || st.phase !== 'run' || st.dead || !st.attempt) return;
    try {
      await api(`${base}/${id}/progress`, {
        method: 'POST',
        body: JSON.stringify({
          responses: responses(),
          duration_seconds: Math.max(0, Math.round((Date.now() - st.startedAt) / 1000)),
        }),
      });
    } catch (_) { /* the next beat tries again */ }
  }

  async function submit(auto) {
    if (st.dead || st.submitting || st.phase !== 'run') return;
    const total = st.questions.length;
    const done = answeredCount();
    if (!auto) {
      const ok = await confirmAction(
        'Submit your answers?',
        `You answered ${done} of ${total} question${total === 1 ? '' : 's'}. Answers cannot be changed after submitting.`,
        'Submit');
      if (!ok || st.dead) return;
    } else {
      toast('Time is up — your answers were submitted.', 'warn');
    }

    st.submitting = true;
    const btn = root.querySelector('[data-submit]');
    if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    stopTimers();

    try {
      const res = await api(`${base}/${id}/submit-attempt`, {
        method: 'POST',
        body: JSON.stringify({
          responses: responses(),
          duration_seconds: Math.max(0, Math.round((Date.now() - st.startedAt) / 1000)),
        }),
      });
      if (st.dead) return;
      st.result = ui.data(res) || {};
      st.phase = 'result';
      paintResult();
    } catch (err) {
      st.submitting = false;
      toast(err.message, 'warn');
      if (btn) { btn.disabled = false; btn.textContent = 'Submit answers'; }
      if (auto && !st.dead) st.retry = setTimeout(() => submit(true), 5000);
      else if (!st.dead) st.tick = setInterval(tickTimer, 1000);
    }
  }

  // ── Result ───────────────────────────────────────────────────────────────
  function paintResult() {
    const r = st.result || {};
    const c = st.container;
    const cert = r.certificate;
    const passed = r.passed;
    const pct = Number(r.percentage) || 0;

    root.innerHTML = `
      <div class="crumbs"><a href="#/tests">&larr; Tests</a></div>
      ${ui.head({
        title: c.title,
        sub: isExam ? 'Examination submitted' : 'Practice set submitted',
        actions: isExam
          ? (passed === true ? ui.tone('Passed', 'ok')
             : passed === false ? ui.tone('Not passed', 'bad') : '')
          : ui.tone('Practice complete', 'info'),
      })}
      <div class="ply-result${isExam ? ' is-exam' : ''}">
        ${cert ? certHtml(cert) : ''}
        <div class="ply-tiles">
          ${ui.tile({ icon: isExam ? 'cert' : 'quiz', value: `${Math.round(pct)}%`, label: 'Score',
            hint: `${r.score ?? 0} of ${r.max_score ?? '—'} marks` })}
          ${ui.tile({ icon: 'check', value: `${answeredCount()}/${st.questions.length}`,
            label: 'Answered', hint: `${st.questions.length} questions` })}
          ${ui.tile({ icon: 'clock', value: fmtClock(Date.now() - st.startedAt),
            label: 'Time taken', hint: `${Number(c.duration_minutes) || 30} min allowed` })}
        </div>
        ${!isExam ? ui.note('Practice only — no certificate is issued for questionnaires.') : ''}
        ${(r.by_difficulty && r.by_difficulty.length) ? diffTable(r.by_difficulty) : ''}
        <div class="ply-review">
          <div class="card-head"><h3>Question review</h3>
            <span class="sm muted">per-question result</span></div>
          ${reviewList(r)}
        </div>
        <div class="row gap ply-result-actions">
          <button type="button" class="btn primary" data-report>View full report</button>
          <a class="btn ghost" href="#/tests">Back to tests</a>
          ${!isExam && st.attempts.length < Number(c.max_attempts || 1)
            ? '<button type="button" class="btn ghost" data-again>Try again</button>' : ''}
        </div>
      </div>`;
  }

  function certHtml(cert) {
    return `
      <div class="ply-cert">
        <span class="ply-cert-ic">${iconSvg('cert')}</span>
        <div class="ply-cert-body">
          <b>Certificate earned</b>
          <p>${esc(cert.title || st.container.title)} &middot; ${esc(cert.percentage)}% passed</p>
          <span class="ply-cert-code">${esc(cert.code || '')}</span>
        </div>
        <span class="tag ok">${esc(cert.status || 'VALID')}</span>
      </div>`;
  }

  function diffTable(rows) {
    return `
      <div class="ply-diff">
        <div class="card-head"><h3>By difficulty</h3></div>
        ${ui.table([
          { label: 'Difficulty', get: (r) => esc(String(r.difficulty || '').replace(/^./, (m) => m.toUpperCase())) },
          { label: 'Correct', get: (r) => `${esc(r.correct)} / ${esc(r.total)}` },
          { label: 'Score', get: (r) => `${esc(r.pct)}%` },
        ], rows, 'difficulty')}
      </div>`;
  }

  function reviewList(result) {
    const byQ = {};
    (result.detail || []).forEach((d) => { byQ[d.question_id] = d; });
    return `
      <ul class="ply-rev">
        ${st.questions.map((q, i) => {
          const d = byQ[q.id] || null;
          const chosen = st.answers[q.id];
          const pick = q.options.find((o) => o.id === chosen);
          const tone = !d ? '' : d.correct ? 'ok' : 'bad';
          return `
            <li class="ply-rev-row${tone ? ' is-' + tone : ''}">
              <span class="ply-rev-n">${i + 1}</span>
              <div class="ply-rev-body">
                <p>${esc(q.text)}</p>
                <span class="sm muted">Your answer: ${pick ? esc(pick.text) : 'not answered'}</span>
              </div>
              ${d ? (d.correct ? ui.tone('Correct', 'ok') : ui.tone('Incorrect', 'bad'))
                  : '<span class="tag mute">—</span>'}
            </li>`;
        }).join('')}
      </ul>`;
  }

  async function openReport(btn) {
    const r = st.result || {};
    if (!r.attempt_id) { toast('No attempt to report on.', 'warn'); return; }
    await ui.busy(btn, 'Preparing…', async () => {
      try {
        const res = await api('/v1/reports/generate', {
          method: 'POST',
          body: JSON.stringify({
            attempt_id: r.attempt_id,
            attempt_kind: isExam ? 'ASSESSMENT' : 'QUESTIONNAIRE',
          }),
        });
        const row = ui.data(res);
        if (!row || !row.id) throw new Error('The report could not be generated.');
        go(`/reports/${row.id}`);
      } catch (err) {
        toast(err.message, 'warn');
      }
    });
  }

  // ── Delegated events (bound once) ────────────────────────────────────────
  st.offs.push(ui.on(root, '[data-retry]', 'click', (e) => { e.preventDefault(); mount(); }));
  st.offs.push(ui.click(root, '[data-start]', (e, btn) => start(btn)));
  st.offs.push(ui.click(root, '[data-opt]', (e, btn) => pickOption(btn)));
  st.offs.push(ui.click(root, '[data-go-q]', (e, btn) => goto(Number(btn.dataset.goQ))));
  st.offs.push(ui.click(root, '[data-nav]', (e, btn) =>
    goto(st.idx + (btn.dataset.nav === 'next' ? 1 : -1))));
  st.offs.push(ui.click(root, '[data-submit]', () => submit(false)));
  st.offs.push(ui.click(root, '[data-report]', (e, btn) => openReport(btn)));
  st.offs.push(ui.click(root, '[data-again]', () => mount()));

  await mount();

  return {
    destroy() {
      st.dead = true;
      stopTimers();
      st.offs.forEach((off) => off());
    },
  };
}
