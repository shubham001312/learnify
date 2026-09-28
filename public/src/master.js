// Learnify — the trainer (MASTER) dashboard.
// Route: `/home` for MASTER
//
// A trainer's two jobs are visible at the top: make content, and watch it
// move through release into the hands of trainees.

import { api, esc } from './utils.js?v=64';
import * as ui from './ui.js?v=64';
import { currentUser } from './app.js?v=64';
import { iconSvg } from './icons.js?v=64';
import { embed as embedFeed } from './feed.js?v=64';
import { createCourse } from './courses.js?v=64';

export async function render(root, ctx) {
  const user = currentUser();
  const first = ((user && user.name) || 'there').split(' ')[0];

  root.innerHTML = `
    <section class="dash-hero">
      <div>
        <span class="role-tag master">Trainer &middot; MASTER</span>
        <h1>Training desk</h1>
        <p>Write, assess, and send your content to Supreme for release.</p>
      </div>
      <div class="row gap">
        <button class="btn primary sm" data-new-course>+ New course</button>
        <a class="btn ghost sm" href="#/tests">New test</a>
      </div>
    </section>

    <div data-stats class="stat-row mb">${ui.loading('your numbers')}</div>

    <div class="card mb">
      <div class="card-head"><h3>Shortcuts</h3></div>
      <div class="dash-shortcuts">
        ${shortcut('book', 'Courses', 'Build a five-step course', '#/courses')}
        ${shortcut('quiz', 'Questionnaires & exams', 'Author, release, review', '#/tests')}
        ${shortcut('cpu', 'AI draft queue', 'Edit and publish generated MCQs', '#/drafts')}
        ${shortcut('layers', 'Library', 'Reuse lectures and decks', '#/library')}
        ${shortcut('target', 'Competency', 'Declare what you teach', '#/competency')}
        ${shortcut('chart', 'Reports', 'Your trainees\' performance', '#/reports')}
      </div>
    </div>

    <div class="two-col wide-left mb">
      <div class="card">
        <div class="card-head">
          <h3>Your courses</h3>
          <a class="link" href="#/courses">All courses &rarr;</a>
        </div>
        <div data-courses>${ui.loading('your courses')}</div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>Release queue</h3></div>
          <div data-queue>${ui.loading('the queue')}</div>
        </div>

        <div class="card">
          <div class="card-head"><h3>Your tests</h3>
            <a class="link" href="#/tests">All tests &rarr;</a></div>
          <div data-tests>${ui.loading('your tests')}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>What's new</h3>
        <a class="link" href="#/feed">Open the feed &rarr;</a>
      </div>
      <div data-feed class="stack">${ui.loading('updates')}</div>
    </div>`;

  ui.click(root, '[data-new-course]', (e, btn) => createCourse(btn));

  loadStats(root.querySelector('[data-stats]'));
  loadCourses(root.querySelector('[data-courses]'));
  loadQueue(root.querySelector('[data-queue]'));
  loadTests(root.querySelector('[data-tests]'));
  embedFeed(root.querySelector('[data-feed]'), { limit: 4 });

  return { destroy: () => {} };
}

function shortcut(icon, title, sub, href) {
  return `
    <a class="dash-shortcut" href="${esc(href)}">
      <span class="dash-shortcut-ico">${iconSvg(icon)}</span>
      <b>${esc(title)}</b>
      <small>${esc(sub)}</small>
    </a>`;
}

// ─── Stats ──────────────────────────────────────────────────────────────────

async function loadStats(host) {
  try {
    const s = ui.data(await api('/v1/participation/stats')) || {};
    host.innerHTML = [
      ui.tile({ icon: 'book', value: s.courses || 0, label: 'Courses',
        hint: `${s.trainees || 0} enrolments` }),
      ui.tile({ icon: 'quiz', value: s.questionnaires || 0, label: 'Questionnaires',
        hint: 'Practice with a deadline' }),
      ui.tile({ icon: 'flag', value: s.assessments || 0, label: 'Assessments',
        hint: 'Formal exams' }),
      ui.tile({ icon: 'layers', value: s.library_items || 0, label: 'Library items',
        hint: 'Reusable content' }),
      ui.tile({ icon: 'clock', value: s.pending_release || 0, label: 'Waiting on release',
        hint: s.pending_release ? 'Sent to Supreme' : 'Queue is clear' }),
      ui.tile({ icon: 'users', value: s.trainees || 0, label: 'Trainees reached',
        hint: 'Across all your courses' }),
    ].join('');
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

// ─── Courses ────────────────────────────────────────────────────────────────

async function loadCourses(host) {
  try {
    const rows = ui.data(await api('/v1/courses?mine=true&limit=8')) || [];
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'No courses yet',
        body: 'Start with a title and a subject — the wizard saves after every step, '
            + 'so you can come back and finish later.',
        action: 'Start your first course',
        actionHref: '#/courses',
      });
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map(masterCourse).join('')}</div>`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function masterCourse(c) {
  return `
    <a class="dash-course" href="#/courses/${esc(c.id)}">
      <div class="dash-course-ico">${iconSvg('book')}</div>
      <div class="dash-course-main">
        <b>${esc(c.title)}</b>
        <div class="sm muted">
          ${(c.enrolled || 0)} enrolment${(c.enrolled || 0) === 1 ? '' : 's'}
          ${(c.completed || 0) ? ` &middot; ${c.completed} completed` : ''}
          ${c.subject_code ? ' &middot; ' + esc(c.subject_code) : ''}
        </div>
      </div>
      ${ui.tag(c.status)}
      <span class="dash-course-go">${iconSvg('arrow')}</span>
    </a>`;
}

// ─── Release queue ──────────────────────────────────────────────────────────

async function loadQueue(host) {
  try {
    const res = await api('/v1/courses?mine=true&status=PENDING_RELEASE&limit=6');
    const courses = ui.data(res) || [];
    const meta = ui.meta(res) || {};

    if (!courses.length) {
      host.innerHTML = ui.blank({
        title: 'Nothing waiting',
        body: 'Anything you submit for release shows up here until Supreme decides.',
      });
      return;
    }
    host.innerHTML = `
      ${ui.note('<b>' + courses.length + ' course' + (courses.length === 1 ? '' : 's')
        + ' with Supreme.</b><br>Release is decided by an administrator — you keep '
        + 'editing until then.', 'warn')}
      <div class="stack tight mt">${courses.map((c) => `
        <a class="dash-course" href="#/courses/${esc(c.id)}">
          <div class="dash-course-ico">${iconSvg('clock')}</div>
          <div class="dash-course-main">
            <b>${esc(c.title)}</b>
            <div class="sm muted">Submitted ${esc(ui.relTime(c.updated_at))}</div>
          </div>
          <span class="tag warn">Pending</span>
        </a>`).join('')}</div>`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

// ─── Tests ──────────────────────────────────────────────────────────────────

async function loadTests(host) {
  try {
    const [qRes, aRes, dRes] = await Promise.all([
      api('/v1/questionnaires?mine=true&limit=4').catch(() => null),
      api('/v1/assessments?mine=true&limit=4').catch(() => null),
      api('/v1/ai/drafts?limit=1').catch(() => null),
    ]);
    const practice = (qRes ? ui.data(qRes) : []) || [];
    const exams = (aRes ? ui.data(aRes) : []) || [];
    const draftTotal = dRes ? (ui.meta(dRes).total || 0) : 0;

    const items = [
      ...exams.map((t) => ({ ...t, kind: 'a', formal: true })),
      ...practice.map((t) => ({ ...t, kind: 'q', formal: false })),
    ].slice(0, 5);

    if (!items.length && !draftTotal) {
      host.innerHTML = ui.blank({
        title: 'No tests yet',
        body: 'Author a questionnaire for practice or an assessment for the '
            + 'formal paper — AI can draft the MCQs for you.',
        action: 'Open the authoring screen',
        actionHref: '#/tests',
      });
      return;
    }

    host.innerHTML = `
      ${draftTotal ? `<a class="dash-drafts" href="#/drafts">
        ${iconSvg('cpu')}
        <b>${draftTotal} AI draft${draftTotal === 1 ? '' : 's'} waiting for review</b>
        <small>Nothing goes live until you publish it</small>
      </a>` : ''}
      ${items.length ? `<div class="stack tight mt">${items.map((t) => `
        <a class="dash-course" href="#/tests/${t.kind}/${esc(t.id)}">
          <div class="dash-course-ico">${iconSvg(t.formal ? 'flag' : 'quiz')}</div>
          <div class="dash-course-main">
            <b>${esc(t.title)}</b>
            <div class="sm muted">
              ${t.deadline_at ? `Closes ${esc(ui.fmtDate(t.deadline_at))}` : 'No deadline'}
            </div>
          </div>
          ${ui.tag(t.status)}
        </a>`).join('')}</div>` : ''}`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}
