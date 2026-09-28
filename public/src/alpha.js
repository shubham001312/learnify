// Learnify — the trainee (ALPHA) dashboard.
// Route: `/home` for ALPHA
//
// Four things a trainee wants on arrival: how am I doing, what was I in the
// middle of, what do I have to sit next, and what changed. Each of those is a
// single section below; the feed is shared with the other dashboards via
// feed.embed().

import { api, esc } from './utils.js?v=64';
import * as ui from './ui.js?v=64';
import { currentUser } from './app.js?v=64';
import { iconSvg } from './icons.js?v=64';
import { embed as embedFeed } from './feed.js?v=64';

export async function render(root, ctx) {
  const user = currentUser();
  const name = (user && user.name) || 'there';
  const first = name.split(' ')[0];

  root.innerHTML = `
    <section class="dash-hero">
      <div>
        <span class="role-tag alpha">Trainee &middot; ALPHA</span>
        <h1>Welcome back, ${esc(first)}</h1>
        <p>Pick up where you left off, or see what is waiting for you.</p>
      </div>
      <div class="row gap">
        <a class="btn primary sm" href="#/courses">Browse courses</a>
        <a class="btn ghost sm" href="#/tests">Take a test</a>
      </div>
    </section>

    <div data-stats class="stat-row mb">${ui.loading('your numbers')}</div>

    <div class="two-col wide-left mb">
      <div class="card">
        <div class="card-head">
          <h3>Continue learning</h3>
          <a class="link" href="#/courses">All courses &rarr;</a>
        </div>
        <div data-courses>${ui.loading('your courses')}</div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head">
            <h3>Waiting for you</h3>
            <a class="link" href="#/tests">All tests &rarr;</a>
          </div>
          <div data-tests>${ui.loading('open tests')}</div>
        </div>

        <div class="card">
          <div class="card-head">
            <h3>Your reports</h3>
            <a class="link" href="#/reports">All reports &rarr;</a>
          </div>
          <div data-reports>${ui.loading('reports')}</div>
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

  // Fire the four panels independently so one slow call does not stall the page.
  loadStats(root.querySelector('[data-stats]'));
  loadCourses(root.querySelector('[data-courses]'));
  loadTests(root.querySelector('[data-tests]'));
  loadReports(root.querySelector('[data-reports]'));
  embedFeed(root.querySelector('[data-feed]'), { limit: 4 });

  return { destroy: () => {} };
}

// ─── Stat tiles ─────────────────────────────────────────────────────────────

async function loadStats(host) {
  try {
    const s = ui.data(await api('/v1/participation/stats')) || {};
    host.innerHTML = [
      ui.tile({
        icon: 'book', value: s.enrolled || 0, label: 'Courses enrolled',
        hint: `${s.completed_courses || 0} completed`,
      }),
      ui.tile({
        icon: 'target', value: `${Math.round(s.avg_progress || 0)}%`,
        label: 'Average progress', hint: `${s.lessons_completed || 0} lessons done`,
      }),
      ui.tile({
        icon: 'cert', value: s.certificates || 0, label: 'Certificates',
        hint: 'Issued on passing',
      }),
      ui.tile({
        icon: 'chart', value: s.exams_taken ? `${Math.round(s.avg_score || 0)}%` : '—',
        label: 'Average score',
        hint: `${s.exams_passed || 0} of ${s.exams_taken || 0} exams passed`,
      }),
    ].join('');
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

// ─── Courses ────────────────────────────────────────────────────────────────

async function loadCourses(host) {
  try {
    const rows = ui.data(await api('/v1/courses?mine=true&limit=6')) || [];
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'You are not on a course yet',
        body: 'Every published course is open to you — enrol and it shows up here.',
        action: 'Browse the catalogue',
        actionHref: '#/courses',
      });
      return;
    }
    host.innerHTML = `<div class="stack">${rows.map(courseRow).join('')}</div>`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function courseRow(c) {
  const pct = Math.round(Number(c.progress_pct) || 0);
  const done = c.enrollment_status === 'COMPLETED' || pct === 100;
  return `
    <a class="dash-course" href="#/courses/${esc(c.id)}">
      <div class="dash-course-ico">${iconSvg('book')}</div>
      <div class="dash-course-main">
        <b>${esc(c.title)}</b>
        <div class="sm muted">
          ${esc(c.trainer_name || 'Independent trainer')}
          ${c.subject_code ? ' &middot; ' + esc(c.subject_code) : ''}
        </div>
        ${ui.progressBar(pct, done ? 'Complete' : `${pct}%`)}
      </div>
      <span class="dash-course-go">${iconSvg('arrow')}</span>
    </a>`;
}

// ─── Open tests ─────────────────────────────────────────────────────────────

async function loadTests(host) {
  try {
    const [aRes, qRes] = await Promise.all([
      api('/v1/assessments?limit=5').catch(() => null),
      api('/v1/questionnaires?limit=5').catch(() => null),
    ]);
    const exams = (aRes ? ui.data(aRes) : []) || [];
    const practice = (qRes ? ui.data(qRes) : []) || [];

    const items = [
      ...exams.map((t) => ({ ...t, kind: 'a', formal: true })),
      ...practice.map((t) => ({ ...t, kind: 'q', formal: false })),
    ].slice(0, 6);

    if (!items.length) {
      host.innerHTML = ui.blank({
        title: 'No open tests',
        body: 'When a trainer releases a questionnaire or an assessment it appears here.',
      });
      return;
    }

    host.innerHTML = `<div class="stack tight">${items.map((t) => {
      const attempts = t.my_attempts || 0;
      const used = t.max_attempts && attempts >= t.max_attempts;
      const live = t.has_live;
      return `
        <a class="dash-test${t.formal ? ' formal' : ''}" href="#/take/${t.kind}/${esc(t.id)}">
          <span class="tag ${t.formal ? 'warn' : 'info'}">${t.formal ? 'Exam' : 'Practice'}</span>
          <div class="dash-test-main">
            <b>${esc(t.title)}</b>
            <div class="sm muted">
              ${t.deadline_at ? `Due ${esc(ui.fmtDate(t.deadline_at, { withTime: true }))}`
                : 'No deadline'}
              ${t.duration_minutes ? ` &middot; ${t.duration_minutes} min` : ''}
            </div>
          </div>
          ${live ? '<span class="tag info">In progress</span>'
            : used ? '<span class="tag mute">Attempts used</span>'
            : t.overdue ? '<span class="tag bad">Closed</span>' : ''}
        </a>`;
    }).join('')}</div>`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

// ─── Reports ────────────────────────────────────────────────────────────────

async function loadReports(host) {
  try {
    const rows = ui.data(await api('/v1/reports?limit=4')) || [];
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'No reports yet',
        body: 'Sit an assessment and your Veda performance report is generated for you.',
        action: 'See open exams',
        actionHref: '#/tests',
      });
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map((r) => `
      <a class="dash-report" href="#/reports/${esc(r.id)}">
        <div>
          <b>${esc(r.subject_name || r.attempt_kind || 'Report')}</b>
          <div class="sm muted">${esc(ui.fmtDate(r.generated_at))}</div>
        </div>
        <span class="dash-report-score ${r.passed ? 'pass' : 'fail'}">
          ${r.percentage != null ? `${Math.round(r.percentage)}%` : '—'}
        </span>
      </a>`).join('')}</div>`;
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}
