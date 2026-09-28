// Learnify — course catalogue and course detail.
// Routes: `/courses` and `/courses/{id}`
//
// This is the reference module: fetch with `api()`, unwrap with `ui.data()`,
// render with `ui.*`, bind through `ui.click(root, ...)` so re-renders never
// leak listeners, and return `{ destroy }` if anything was scheduled.

import { api, esc, toast } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { go, confirmAction, currentUser } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';
import { coverHtml } from './art.js?v=63';

// Filters survive a re-render within the route but reset when you leave.
const filters = { q: '', subject: '', status: '', mine: false };
let debounce = 0;

// ─── Catalogue ──────────────────────────────────────────────────────────────

export async function list(root, ctx) {
  const user = currentUser();
  const canAuthor = user && (user.role === 'MASTER' || user.role === 'SUPREME');
  if (!canAuthor) { filters.status = ''; filters.mine = false; }

  root.innerHTML = ui.head({
    title: 'Courses',
    sub: canAuthor
      ? 'Everything you teach, plus every course waiting on the portal.'
      : 'Every published course is open to you — enrol whenever you like.',
    actions: canAuthor
      ? '<button class="btn primary sm" data-new-course>+ New course</button>'
      : '',
  }) + '<div data-body>' + ui.loading('courses') + '</div>';

  const body = root.querySelector('[data-body]');
  ui.click(root, '[data-new-course]', (e, btn) => createCourse(btn));

  // Subject filter options come from the catalogue, not hardcoded.
  let subjects = [];
  try {
    const res = await api('/v1/subjects?limit=200');
    subjects = ui.data(res) || [];
  } catch (_) { subjects = []; }

  renderToolbar(root, subjects, canAuthor);
  const paint = () => loadCourses(body, canAuthor);
  paint();
  return { destroy: () => clearTimeout(debounce) };
}

function renderToolbar(root, subjects, canAuthor) {
  const bar = document.createElement('div');
  bar.className = 'toolbar';
  bar.innerHTML = `
    <div class="grow"><input type="search" name="q" placeholder="Search courses…"
      value="${esc(filters.q)}" aria-label="Search courses"></div>
    <select name="subject" aria-label="Filter by subject">
      <option value="">All subjects</option>
      ${subjects.map((s) => `<option value="${esc(s.id)}"${
        filters.subject === s.id ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}
    </select>
    ${canAuthor ? `
      <select name="status" aria-label="Filter by status">
        <option value="">Any status</option>
        ${['DRAFT', 'IN_PROGRESS', 'PENDING_RELEASE', 'PUBLISHED', 'REJECTED']
          .map((s) => `<option value="${s}"${
            filters.status === s ? ' selected' : ''}>${s.replace(/_/g, ' ')
              .replace(/\b\w/g, (c) => c.toUpperCase())}</option>`).join('')}
      </select>
      <button class="btn ghost sm${filters.mine ? ' active' : ''}" data-mine>
        Mine only</button>` : ''}
    <button class="btn primary sm" data-apply>Apply</button>`;

  root.insertBefore(bar, root.querySelector('[data-body]'));

  const apply = () => {
    filters.q = bar.querySelector('[name=q]').value.trim();
    filters.subject = bar.querySelector('[name=subject]').value;
    const st = bar.querySelector('[name=status]');
    if (st) filters.status = st.value;
    const mine = bar.querySelector('[data-mine]');
    if (mine) filters.mine = !filters.mine;
    loadCourses(root.querySelector('[data-body]'), canAuthor);
  };

  ui.click(bar, '[data-apply]', apply);
  ui.click(bar, '[data-mine]', apply);
  bar.querySelector('[name=q]').addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(apply, 320);
  });
  bar.querySelector('[name=subject]').addEventListener('change', apply);
  const st = bar.querySelector('[name=status]');
  if (st) st.addEventListener('change', apply);
}

async function loadCourses(target, canAuthor) {
  target.innerHTML = ui.loading('courses');
  try {
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.subject) params.set('subject_id', filters.subject);
    if (filters.status) params.set('status', filters.status);
    if (filters.mine) params.set('mine', 'true');
    params.set('limit', '120');

    const res = await api('/v1/courses?' + params.toString());
    const rows = ui.data(res) || [];
    target.innerHTML = rows.length
      ? `<div class="cc-grid three">${rows.map(card).join('')}</div>
         <p class="muted sm center mt">${rows.length} course${
           rows.length === 1 ? '' : 's'} shown</p>`
      : ui.blank({
          title: 'No courses match',
          body: 'Try clearing the search or choosing a different subject.',
          action: filters.q || filters.subject || filters.status
            ? 'Clear filters' : '',
          actionHref: '#/courses',
        });
  } catch (err) {
    target.innerHTML = ui.errorBlock(err.message);
  }
}

function card(c) {
  const owner = c.can_edit;
  return `
    <a class="cc-card course" href="#/courses/${esc(c.id)}" style="text-decoration:none">
      ${coverHtml(c.cover_image_url, {
        subject: c.subject_name,
        category: c.subject_category,
        cls: 'cc-cover',
      })}
      <div class="cc-card-head">
        ${c.subject_code ? `<span class="role-tag">${esc(c.subject_code)}</span>` : ''}
        ${owner ? ui.tag(c.status) : (c.status === 'PUBLISHED' ? '' : ui.tag(c.status))}
      </div>
      <h3>${esc(c.title)}</h3>
      <p>${esc((c.description || '').slice(0, 150))}${
        (c.description || '').length > 150 ? '…' : ''}</p>
      <div class="card-foot">
        ${c.trainer_name ? `<span class="sm dim">${esc(c.trainer_name)}</span>` : ''}
        <span class="grow"></span>
        <span class="sm muted">${esc(ui.fmtHours(c.duration_hours))}</span>
        <span class="sm muted">Level ${esc(c.level || '—')}</span>
      </div>
    </a>`;
}

/** Create a blank draft and hand off to the wizard. Reused by the dashboard. */
export async function createCourse(btn) {
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Creating…';
  try {
    const res = await api('/v1/courses', {
      method: 'POST',
      body: JSON.stringify({ title: 'Untitled course' }),
    });
    const row = ui.data(res);
    if (!row || !row.id) throw new Error('The course could not be created.');
    toast('Draft created — pick up at step 1.');
    go(`/courses/${row.id}/edit`);
  } catch (err) {
    toast(err.message, 'warn');
    btn.disabled = false;
    btn.textContent = label;
  }
}

// ─── Course detail ──────────────────────────────────────────────────────────

export async function detail(root, ctx) {
  const id = ctx.params.id;
  const user = currentUser();
  root.innerHTML = ui.loading('course');

  let course, outline;
  try {
    const [cRes, oRes] = await Promise.all([
      api(`/v1/courses/${id}`),
      api(`/v1/courses/${id}/outline`).catch(() => null),
    ]);
    course = ui.data(cRes);
    outline = oRes ? ui.data(oRes) : null;
    if (!course) throw new Error('Course not found.');
  } catch (err) {
    root.innerHTML = ui.head({ title: 'Course' })
      + ui.blank({ title: 'Course unavailable', body: esc(err.message) });
    return;
  }

  paint(root, course, outline, user);
  bind(root, course, outline, user);
  return {};
}

function paint(root, course, outline, user) {
  const mods = (outline && outline.modules) || [];
  const counts = (outline && outline.counts) || {};
  const enrollment = (outline && outline.enrollment) || null;
  const prog = (outline && outline.progress) || null;
  const isOwner = course.can_edit;
  const total = prog ? prog.total_slots : 0;
  const done = prog ? prog.completed_slots : 0;
  const pctv = total ? Math.round((done / total) * 100) : (course.progress_pct || 0);

  const actions = [];
  if (isOwner) {
    actions.push(`<a class="btn primary sm" href="#/courses/${esc(course.id)}/edit">Edit course</a>`);
    if (course.status === 'PENDING_RELEASE') {
      actions.push('<button class="btn ghost sm" data-submit>Withdraw to draft</button>');
    } else if (course.status === 'PUBLISHED') {
      actions.push('<button class="btn ghost sm" data-feedback>Feedback</button>');
    } else {
      actions.push('<button class="btn ghost sm" data-submit>Submit for release</button>');
    }
  } else if (user && user.role === 'ALPHA') {
    if (enrollment) {
      const first = firstPlayable(mods);
      actions.push(`<a class="btn primary sm" href="#/learn/${esc(course.id)}${
        first ? '/' + esc(first) : ''}">${enrollment.status === 'COMPLETED'
          ? 'Review course' : pctv > 0 ? 'Continue learning' : 'Start course'}</a>`);
      actions.push('<button class="btn ghost sm" data-drop>Leave course</button>');
    } else if (course.status === 'PUBLISHED') {
      actions.push('<button class="btn primary sm" data-enrol>Enrol</button>');
    }
    if (enrollment) actions.push(`<a class="btn ghost sm" href="#/feedback/course/${esc(course.id)}">Rate</a>`);
  }

  root.innerHTML = `
    <div class="crumbs"><a href="#/courses">&larr; All courses</a></div>
    ${ui.head({
      title: course.title,
      sub: isOwner ? '' : `${esc(course.trainer_name || 'Independent trainer')}${
        course.subject_name ? ' · ' + esc(course.subject_name) : ''}`,
      actions: actions.join(''),
    })}

    <div class="wrap mb">
      ${ui.tag(course.status)}
      <span class="tag mute">${esc(course.level || 'Beginner')}</span>
      ${course.subject_code ? `<span class="tag info">${esc(course.subject_code)}</span>` : ''}
      ${counts.with_video ? `<span class="tag mute">${counts.with_video} video${
        counts.with_video === 1 ? '' : 's'}</span>` : ''}
      ${counts.with_test ? `<span class="tag mute">${counts.with_test} linked test${
        counts.with_test === 1 ? '' : 's'}</span>` : ''}
    </div>

    ${course.description
      ? `<div class="card mb"><p class="page-sub" style="margin:0">${
        esc(course.description)}</p></div>` : ''}

    <div class="two-col wide-left">
      <div class="stack">
        ${coverHtml(course.cover_image_url, {
          subject: course.subject_name,
          category: course.subject_category,
          cls: 'cc-hero',
        })}
        ${enrollment && total ? `
          <div class="card">
            <div class="card-head"><h3>Your progress</h3>
              <span class="tag ${pctv === 100 ? 'ok' : 'info'}">${pctv}%</span></div>
            ${ui.progressBar(pctv, `${done} / ${total} slots`)}
          </div>` : ''}

        <div class="card">
          <div class="card-head"><h3>Course outline</h3>
            <span class="sm muted">${mods.length} module${
              mods.length === 1 ? '' : 's'}</span></div>
          ${mods.length ? mods.map((m, i) => moduleBlock(course, m, i)).join('')
            : '<div class="empty-state">No modules yet.</div>'}
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>Details</h3></div>
          ${ui.kv([
            ['Trainer', course.trainer_name || '—'],
            ['Designation', course.trainer_designation || ''],
            ['Subject', course.subject_name || 'Unassigned'],
            ['Duration', ui.fmtHours(course.duration_hours)],
            ['Modules', String(counts.modules || mods.length || 0)],
            ['Slots', String(counts.slots || 0)],
            ['Course code', course.code || ''],
          ])}
        </div>

        ${isOwner ? ownerPanel(course) : ''}
      </div>
    </div>`;
}

function ownerPanel(course) {
  const s = course.status;
  if (s === 'PENDING_RELEASE') {
    return `<div class="note warn"><b>Waiting on Supreme.</b><br>
      This course is in the release queue. You will be notified either way.</div>`;
  }
  if (s === 'REJECTED') {
    return `<div class="note bad"><b>Changes requested.</b><br>
      Supreme sent this back. Edit it and submit again.</div>`;
  }
  if (s === 'PUBLISHED') {
    return `<div class="note"><b>Live on the portal.</b><br>
      Trainees can find and enrol in this course.</div>`;
  }
  return `<div class="note"><b>Still a draft (step ${course.draft_step || 1} of 5).</b><br>
    Finish the wizard, then submit it for release.</div>`;
}

function moduleBlock(course, m, index) {
  const slots = m.slots || [];
  return `
    <div class="mod">
      <div class="mod-head">
        <span class="mod-n">${index + 1}</span>
        <div>
          <b>${esc(m.title)}</b>
          ${m.description ? `<p class="sm muted">${esc(m.description)}</p>` : ''}
        </div>
      </div>
      ${slots.length ? `<ul class="slotlist">${slots.map((s) => `
        <li>
          <span class="slot-ico">${iconSvg(
            s.kind === 'VIDEO' ? 'video'
            : s.kind === 'READING' ? 'file'
            : s.kind === 'LINK' ? 'link' : 'quiz')}</span>
          <span class="slot-t">${esc(s.title)}</span>
          ${s.linked_test_id ? '<span class="tag info">Test</span>' : ''}
          ${s.has_video && s.duration_seconds
            ? `<span class="sm muted">${Math.round(s.duration_seconds / 60)} min</span>` : ''}
          ${course.can_edit
            ? `<a class="link" href="#/learn/${esc(course.id)}/${esc(s.id)}">Open</a>`
            : ''}
        </li>`).join('')}</ul>` : ''}
    </div>`;
}

function firstPlayable(mods) {
  for (const m of mods) {
    if (m.slots && m.slots.length) return m.slots[0].id;
  }
  return '';
}

function bind(root, course, outline, user) {
  const id = course.id;

  ui.click(root, '[data-enrol]', async (e, btn) => {
    await ui.busy(btn, 'Enrolling…', async () => {
      try {
        await api(`/v1/courses/${id}/enroll`, { method: 'POST', body: '{}' });
        toast('Enrolled — good luck.');
        location.reload();
      } catch (err) { toast(err.message, 'warn'); }
    });
  });

  ui.click(root, '[data-drop]', async (e, btn) => {
    const ok = await confirmAction('Leave this course?',
      'Your progress stays on record, but you will lose your place in the outline.',
      'Leave course');
    if (!ok) return;
    try {
      await api(`/v1/courses/${id}/leave`, { method: 'POST', body: '{}' });
      toast('You have left the course.');
      location.reload();
    } catch (err) { toast(err.message, 'warn'); }
  });

  ui.click(root, '[data-submit]', async (e, btn) => {
    try {
      await api(`/v1/courses/${id}/submit`, { method: 'POST', body: '{}' });
      toast('Sent to Supreme for release.');
      location.reload();
    } catch (err) { toast(err.message, 'warn'); }
  });

  ui.click(root, '[data-feedback]', (e, btn) => go(`/feedback/course/${id}`));
}
