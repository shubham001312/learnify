// LEARNIFY — Veda performance reports.
// Routes: `/reports` (list) and `/reports/{id}` (the branded Veda document).
//
// A report has two layers and this module keeps them visibly separate: the
// deterministic base (scores, topics, difficulty, benchmark) is always shown,
// and the AI layer is only ever rendered when `ai_generated` is true — the text
// comes straight from the API, never from here.
//
// Follows the courses.js / library.js pattern: fetch with `api()`, unwrap with
// `ui.data()`, render with `ui.*`, bind through `ui.click(root, …)`, and return
// `{ destroy }` so delegated listeners are released on route teardown.

import { api, esc, toast } from './utils.js?v=64';
import * as ui from './ui.js?v=64';
import { go, confirmAction, currentUser, openAppModal, closeAppModal } from './app.js?v=64';
import { iconSvg } from './icons.js?v=64';
import { donutChart, hbarChart, emptyChart } from './charts.js?v=64';

// Neutral lines used only when the API returned no text for a key — a plain
// statement that the section is empty, never invented commentary.
const NO_TEXT = {
  weak_points: 'Veda has not written a weak-point summary for this report yet.',
  improve: 'Veda has not written an improvement note for this report yet.',
  industry: 'Veda has not written an industry comparison for this report yet.',
  learn_next: 'Veda has not suggested what to learn next for this report yet.',
  suggestions: 'No study actions have been generated for this report yet.',
};

const KIND_LABEL = { ASSESSMENT: 'Assessment', QUESTIONNAIRE: 'Questionnaire' };

// Route-scoped state.
const view = { root: null, mode: 'list', role: 'ALPHA', reportId: '', offs: [] };
const filters = { subject: '', kind: '', trainee: '' };
let traineeOpts = [];

function clearOffs() {
  view.offs.forEach((off) => off());
  view.offs = [];
}

function teardown() { clearOffs(); }

// ─── List ───────────────────────────────────────────────────────────────────

export async function list(root, ctx) {
  clearOffs();

  const user = ctx.user || currentUser() || {};
  const role = user.role || 'ALPHA';
  view.root = root;
  view.mode = 'list';
  view.role = role;
  view.reportId = '';
  filters.subject = '';
  filters.kind = '';
  filters.trainee = '';
  traineeOpts = [];

  const sub = {
    ALPHA: 'Every assessment and questionnaire you have sat, written up by Veda.',
    MASTER: 'Your trainees’ results, plus the weak topics the platform keeps seeing.',
    SUPREME: 'Platform-wide performance — every report, benchmark and weak topic.',
  }[role] || 'Every attempt, written up by Veda.';

  root.innerHTML = ui.head({ title: 'Performance reports', sub })
    + '<div data-toolbar></div>'
    + (role === 'SUPREME' ? '<div data-summary></div>' : '')
    + `<div data-list>${ui.loading('reports')}</div>`
    + (role === 'ALPHA' ? '' : `<div data-weak>${ui.loading('weak topics')}</div>`);

  bindList(root);

  let subjects = [];
  try {
    const res = await api('/v1/subjects?limit=200');
    subjects = ui.data(res) || [];
  } catch (_) { subjects = []; }
  paintToolbar(root, root.querySelector('[data-toolbar]'), subjects);

  await loadList(root);
  if (role !== 'ALPHA') loadWeakTopics(root);
  if (role === 'SUPREME') loadSummary(root);

  return { destroy: teardown };
}

function paintToolbar(root, box, subjects) {
  if (!box) return;
  const bar = document.createElement('div');
  bar.className = 'toolbar';
  bar.innerHTML = `
    <select name="subject" aria-label="Filter by subject">
      <option value="">All subjects</option>
      ${subjects.map((s) => `<option value="${esc(s.id)}"${
        filters.subject === s.id ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}
    </select>
    <select name="kind" aria-label="Filter by attempt kind">
      <option value="">Assessments &amp; questionnaires</option>
      <option value="ASSESSMENT"${filters.kind === 'ASSESSMENT' ? ' selected' : ''}>Assessments only</option>
      <option value="QUESTIONNAIRE"${filters.kind === 'QUESTIONNAIRE' ? ' selected' : ''}>Questionnaires only</option>
    </select>
    ${view.role !== 'ALPHA' ? `
      <select name="trainee" aria-label="Filter by trainee">
        <option value="">Everyone</option>
      </select>` : ''}
    <button class="btn primary sm" data-apply>Apply</button>`;

  box.innerHTML = '';
  box.appendChild(bar);
  refreshTraineeOptions(box);

  const apply = () => {
    filters.subject = bar.querySelector('[name=subject]').value;
    filters.kind = bar.querySelector('[name=kind]').value;
    const t = bar.querySelector('[name=trainee]');
    filters.trainee = t ? t.value : '';
    loadList(root);
    if (view.role !== 'ALPHA') loadWeakTopics(root);
  };

  view.offs.push(ui.click(bar, '[data-apply]', apply));
  view.offs.push(ui.on(bar, '[name=subject]', 'change', apply));
  view.offs.push(ui.on(bar, '[name=kind]', 'change', apply));
  view.offs.push(ui.on(bar, '[name=trainee]', 'change', apply));
}

function refreshTraineeOptions(scope) {
  const sel = scope.querySelector('[name=trainee]');
  if (!sel) return;
  const current = filters.trainee;
  sel.innerHTML = '<option value="">Everyone</option>'
    + traineeOpts.map((t) => `<option value="${esc(t.id)}"${
        current === t.id ? ' selected' : ''}>${esc(t.name)}</option>`).join('');
}

async function loadList(root) {
  const box = root.querySelector('[data-list]');
  if (!box) return;
  box.innerHTML = ui.loading('reports');

  try {
    const p = new URLSearchParams();
    if (filters.subject) p.set('subject_id', filters.subject);
    if (filters.kind) p.set('kind', filters.kind);
    if (filters.trainee) p.set('trainee_id', filters.trainee);
    if (view.role === 'ALPHA') p.set('mine', 'true');
    p.set('limit', '200');

    const res = await api('/v1/reports?' + p.toString());
    const rows = ui.data(res) || [];
    const total = Number(ui.meta(res).total) || 0;

    // The trainee filter is built from the rows we can already see — that is
    // exactly the audience this caller is allowed to query.
    if (view.role !== 'ALPHA') {
      const seen = new Map(traineeOpts.map((t) => [t.id, t]));
      rows.forEach((r) => {
        if (r.trainee_id && r.trainee_name && !seen.has(r.trainee_id)) {
          seen.set(r.trainee_id, { id: r.trainee_id, name: r.trainee_name });
        }
      });
      traineeOpts = Array.from(seen.values())
        .sort((a, b) => a.name.localeCompare(b.name));
      refreshTraineeOptions(root);
    }

    box.innerHTML = rows.length
      ? `<div class="stack">
           <div class="card">
             <div class="card-head"><h3>All reports</h3>
               <span class="tag mute">${rows.length}${
                 total > rows.length ? ' of ' + total : ''}</span></div>
             ${ui.table(cols(), rows, 'id')}
           </div>
           ${subjectChart(rows)}
         </div>`
      : emptyList();
  } catch (err) {
    box.innerHTML = ui.errorBlock(err.message);
  }
}

// Questionnaires carry no pass mark, so the backend always stores
// `passed: false` for them — only an assessment can actually fail.
function resultTag(r) {
  if (r.passed) return ui.tag('PASSED');
  if (r.attempt_kind === 'ASSESSMENT') return ui.tag('FAILED');
  return ui.tone('Practice run', 'info');
}

function emptyList() {
  const filtering = filters.subject || filters.kind || filters.trainee;
  if (view.role === 'ALPHA' && !filtering) {
    return ui.blank({
      title: 'No reports yet',
      body: 'Sit an assessment and your Veda report is built from the results automatically.',
      action: 'Open tests',
      actionHref: '#/tests',
    });
  }
  return ui.blank({
    title: filtering ? 'No reports match these filters' : 'No reports on record',
    body: filtering
      ? 'Clear the filters to see everything again.'
      : 'Nothing has been generated for this audience yet.',
    action: filtering ? 'Clear filters' : '',
    actionHref: '#/reports',
  });
}

// Score by subject, aggregated from the rows already on screen — the chart
// fetches nothing of its own, so it can never disagree with the table above.
// One subject on its own is not a comparison, so nothing is drawn then.
function subjectChart(rows) {
  const by = new Map();
  rows.forEach((r) => {
    const key = r.subject_name || 'Unassigned subject';
    const bucket = by.get(key) || { sum: 0, n: 0 };
    bucket.sum += Number(r.percentage) || 0;
    bucket.n += 1;
    by.set(key, bucket);
  });

  const items = Array.from(by.entries())
    .map(([label, b]) => ({ label, value: Math.round(b.sum / (b.n || 1) * 10) / 10 }))
    .sort((a, b) => a.value - b.value);        // lowest subject first

  if (items.length < 2) return '';

  const noun = `${rows.length} report${rows.length === 1 ? '' : 's'}`;
  return `
    <div class="chart-card">
      <div class="chart-title">Average score by subject</div>
      <p class="chart-note">Mean percentage across the ${noun} listed above,
        lowest subject first.</p>
      ${hbarChart(items, { unit: '%', title: 'Average score by subject' })}
    </div>`;
}

function cols() {
  const out = [];
  if (view.role !== 'ALPHA') {
    out.push({ label: 'Trainee', get: (r) => ui.who(r.trainee_name || 'Unknown learner', '') });
  }
  out.push(
    { label: 'Subject', get: (r) => (r.subject_code
        ? `<b>${esc(r.subject_name || 'Unassigned')}</b> <span class="role-tag">${esc(r.subject_code)}</span>`
        : `<b>${esc(r.subject_name || 'Unassigned')}</b>`) },
    { label: 'Attempt', get: (r) => esc(KIND_LABEL[r.attempt_kind] || r.attempt_kind || '—') },
    { label: 'Score', get: (r) => `<b>${esc(String(r.percentage))}%</b>
        <span class="sm muted">${esc(String(r.score))} pts</span>` },
    { label: 'Result', get: (r) => resultTag(r) },
    { label: 'Generated', get: (r) => esc(ui.fmtDate(r.generated_at, { withTime: true })) },
    { label: 'Report', get: (r) => `<a class="link" href="#/reports/${esc(r.id)}">Open</a>` },
  );
  return out;
}

async function loadWeakTopics(root) {
  const box = root.querySelector('[data-weak]');
  if (!box) return;
  box.innerHTML = ui.loading('weak topics');

  try {
    const p = new URLSearchParams();
    if (filters.subject) p.set('subject_id', filters.subject);
    p.set('limit', '12');

    const res = await api('/v1/reports/stats/weak-topics?' + p.toString());
    const rows = ui.data(res) || [];
    const meta = ui.meta(res);

    box.innerHTML = `
      <div class="card">
        <div class="card-head"><h3>Weak topics</h3>
          <span class="tag warn">${rows.length}</span></div>
        <p class="sm muted">Lowest average score first, across every assessment
          report${filters.subject ? ' for the selected subject' : ''}.</p>
        ${Object.keys(meta).length
          ? `<div class="wrap mb">${Object.entries(meta).map(([k, v]) =>
              `<span class="tag mute">${esc(sentence(k))}: ${esc(String(v))}</span>`).join('')}</div>`
          : ''}
        ${rows.length ? rows.map(weakRow).join('')
          : '<div class="empty-state">No assessment reports have been generated yet.</div>'}
      </div>`;
  } catch (err) {
    box.innerHTML = `
      <div class="blank">
        <b>Could not load this</b>
        <p>${esc(err.message || 'Something went wrong while fetching this page.')}</p>
        <p><a href="#" data-retry-weak>Try again</a></p>
      </div>`;
  }
}

function weakRow(t, i) {
  const pct = Number(t.avg_pct) || 0;
  const n = Number(t.appearances) || 0;
  const answers = Number(t.learner_total) || 0;
  return `
    <div class="wk-row">
      <span class="wk-n">${i + 1}</span>
      <div class="wk-body">
        <div class="row gap">
          <b>${esc(t.topic || 'General')}</b>
          <span class="grow"></span>
          <span class="sm muted">${n} report${n === 1 ? '' : 's'}</span>
        </div>
        ${ui.progressBar(pct, pct + '%')}
        <span class="sm dim">${answers} question response${
          answers === 1 ? '' : 's'} behind this average</span>
      </div>
    </div>`;
}

async function loadSummary(root) {
  const box = root.querySelector('[data-summary]');
  if (!box) return;
  try {
    const res = await api('/v1/reports/stats/summary');
    const s = ui.data(res) || {};
    box.innerHTML = `
      <div class="stat-row mb">
        ${ui.tile({ value: ui.fmtNum(s.reports), label: 'Reports generated' })}
        ${ui.tile({ value: (Number(s.avg_pct) || 0) + '%', label: 'Average score' })}
        ${ui.tile({ value: (Number(s.pass_rate) || 0) + '%', label: 'Pass rate',
            hint: `${Number(s.assessments) || 0} assessments` })}
        ${ui.tile({ value: ui.fmtNum(s.ai_personalised), label: 'Personalised by Veda' })}
        ${ui.tile({ value: ui.fmtNum(s.subjects), label: 'Subjects covered' })}
      </div>`;
  } catch (_) {
    box.innerHTML = '';
  }
}

function bindList(root) {
  view.offs.push(ui.click(root, '[data-retry]', (e) => {
    e.preventDefault();
    loadList(view.root);
  }));
  view.offs.push(ui.click(root, '[data-retry-weak]', (e) => {
    e.preventDefault();
    loadWeakTopics(view.root);
  }));
}

// ─── Detail — the Veda report ───────────────────────────────────────────────

export async function detail(root, ctx) {
  clearOffs();

  const id = (ctx.params && ctx.params.id) || view.reportId;
  view.root = root;
  view.mode = 'detail';
  view.reportId = id;

  root.innerHTML = `
    <div class="crumbs"><a href="#/reports">&larr; Performance reports</a></div>
    <div data-body>${ui.loading('report')}</div>`;
  bindDetail(root);

  let report;
  try {
    const res = await api(`/v1/reports/${encodeURIComponent(id)}`);
    report = ui.data(res);
    if (!report) throw new Error('Report not found.');
  } catch (err) {
    const box = root.querySelector('[data-body]');
    if (box) box.innerHTML = ui.errorBlock(err.message);
    return { destroy: teardown };
  }

  const body = root.querySelector('[data-body]');
  if (!body) return { destroy: teardown };
  body.innerHTML = `
    ${ui.head({
      title: 'Veda Report',
      sub: `${esc(report.subject_name || 'Unassigned subject')} · ${
        esc(KIND_LABEL[report.attempt_kind] || report.attempt_kind || '')} · ${
        esc(ui.fmtDate(report.generated_at, { withTime: true }))}`,
    })}
    <div class="stack">${docSections(report)}</div>`;

  return { destroy: teardown };
}

function docSections(r) {
  const src = r.source || {};
  const bench = (r.benchmark && typeof r.benchmark === 'object') ? r.benchmark : {};
  const benchTopics = Array.isArray(bench.topics) ? bench.topics : [];
  const ai = (r.ai_insights && typeof r.ai_insights === 'object') ? r.ai_insights : {};
  const steps = Array.isArray(r.next_steps) ? r.next_steps : [];

  return [
    headerCard(r, src),
    headlineCard(r, src),
    benchmarkCard(r, benchTopics),
    chartsRow(r),
    topicCard(r),
    difficultyCard(r),
    aiCard(r, ai),
    stepsCard(steps, ai, !!r.ai_generated),
  ].join('');
}

// 2b ── Overview charts (both drawn from numbers already in the report)
function chartsRow(r) {
  return `
    <div class="two-col">
      ${topicChartCard(r)}
      ${difficultyChartCard(r)}
    </div>`;
}

// Every topic on the attempt, weakest first. The lists below keep the exact
// counts — this is the at-a-glance order, not a replacement for them.
function topicChartCard(r) {
  const strong = Array.isArray(r.strong_topics) ? r.strong_topics : [];
  const weak = Array.isArray(r.weak_topics) ? r.weak_topics : [];
  const items = [...weak, ...strong]
    .map((t) => {
      const pct = Number(t.pct) || 0;
      return {
        label: t.topic || 'General',
        value: pct,
        tone: pct >= 70 ? 'green' : 'red',
      };
    })
    .sort((a, b) => a.value - b.value);

  return `
    <div class="chart-card">
      <div class="chart-title">Score by topic</div>
      ${items.length ? `
        <p class="chart-note">Every topic on this attempt, lowest first.</p>
        ${hbarChart(items, { unit: '%', title: 'Score by topic' })}
        <div class="chart-legend">
          <span class="lg"><span class="dot green"></span>Cleared 70% or more</span>
          <span class="lg"><span class="dot red"></span>Below 70%</span>
        </div>`
      : emptyChart('No topic split was recorded for this attempt.')}
    </div>`;
}

// What the paper was made of, by question count. Only an object carrying a
// real `total` per level counts — a percentage here would be a false share.
function difficultyChartCard(r) {
  const diff = (r.difficulty_breakdown && typeof r.difficulty_breakdown === 'object')
    ? r.difficulty_breakdown : {};
  const items = Object.keys(diff).map((k) => {
    const v = diff[k];
    const isObj = v && typeof v === 'object';
    return { label: sentence(k), value: isObj ? (Number(v.total) || 0) : 0 };
  });
  const questions = items.reduce((s, i) => s + i.value, 0);

  return `
    <div class="chart-card">
      <div class="chart-title">Questions by difficulty</div>
      ${questions > 0 ? `
        <p class="chart-note">How many questions sat at each level.</p>
        ${donutChart(items, { centerLabel: 'Questions', title: 'Questions by difficulty' })}`
      : emptyChart('No question counts were recorded for this attempt.')}
    </div>`;
}

// 1 ── Veda header
function headerCard(r, src) {
  const kind = KIND_LABEL[r.attempt_kind] || r.attempt_kind || '';
  return `
    <div class="veda-head">
      <div class="veda-brand">
        <span class="veda-mark">${iconSvg('sparkles')}</span>
        <div class="veda-name">
          <b>Veda Report</b>
          <small>Learnify performance briefing · Check &amp; Mate</small>
        </div>
        <span class="grow"></span>
        ${resultTag(r)}
      </div>
      <div class="veda-body">
        ${ui.who(r.trainee_name || 'Unknown learner',
          [r.trainee_designation, r.trainee_department].filter(Boolean).join(' · '))}
        ${ui.kv([
          ['Subject', r.subject_name || 'Unassigned'],
          ['Subject code', r.subject_code || ''],
          ['Attempt type', kind],
          [r.attempt_kind === 'QUESTIONNAIRE' ? 'Questionnaire' : 'Assessment',
            src.title || 'Untitled'],
          ['Attempt number', (src.attempt_no === undefined || src.attempt_no === null)
            ? '' : String(src.attempt_no)],
          ['Started', src.started_at ? ui.fmtDate(src.started_at, { withTime: true }) : ''],
          ['Submitted', src.submitted_at ? ui.fmtDate(src.submitted_at, { withTime: true }) : ''],
          ['Generated', ui.fmtDate(r.generated_at, { withTime: true })],
          ['Report id', r.id || ''],
        ])}
        ${r.certificate ? `
          <div class="note mt"><b>Certificate ${esc(r.certificate.code || '')}.</b>
            ${esc(r.certificate.title || '')} — ${ui.tag(r.certificate.status)}${
            r.certificate.issued_at
              ? ' issued ' + esc(ui.fmtDate(r.certificate.issued_at)) : ''}</div>` : ''}
      </div>
    </div>`;
}

// 2 ── Headline
function headlineCard(r, src) {
  const pct = Number(r.percentage) || 0;
  const spent = duration(src.started_at, src.submitted_at);
  return `
    <div class="card">
      <div class="card-head"><h3>Headline</h3>${resultTag(r)}</div>
      <div class="stat-row">
        ${ui.tile({ value: String(r.score), label: 'Score',
            hint: src.max_score ? 'out of ' + String(src.max_score) : '' })}
        ${ui.tile({ value: pct + '%', label: 'Percentage' })}
        ${spent ? ui.tile({ value: spent, label: 'Time spent' }) : ''}
        ${src.passing_score
          ? ui.tile({ value: String(src.passing_score), label: 'Passing score' }) : ''}
      </div>
      ${r.verdict ? ui.note(`<b>${esc(r.verdict)}</b>`) : ''}
    </div>`;
}

// 3 ── Benchmark comparison
function benchmarkCard(r, topics) {
  const pct = Number(r.percentage) || 0;
  const name = r.trainee_name || 'This learner';

  if (!topics.length) {
    return `
      <div class="card">
        <div class="card-head"><h3>Industry benchmark</h3>
          <span class="tag mute">Not curated</span></div>
        ${ui.note(`No industry benchmark has been curated for ${
          esc(r.subject_name || 'this subject')} yet. The comparison will appear here
          as soon as a Master or Supreme publishes one.`)}
      </div>`;
  }

  const expected = Math.round(
    topics.reduce((s, t) => s + (Number(t.expected) || 0), 0) / topics.length);
  const beat = pct >= expected;
  const diff = Math.round(pct - expected);

  return `
    <div class="card">
      <div class="card-head"><h3>Industry benchmark</h3>
        ${beat ? '<span class="tag ok">Above standard</span>'
               : '<span class="tag warn">Below standard</span>'}</div>
      ${ui.note(
        `<b>${esc(name)} scored ${pct}% against an expected ${expected}% — ${
          beat ? 'ahead of the published standard'
               : Math.abs(diff) + ' point' + (Math.abs(diff) === 1 ? '' : 's')
                 + ' behind it'}.</b><br>
         The standard below is the curated reference for ${
          esc(r.subject_name || 'this subject')}; expected proficiency is the minimum
         a working practitioner is held to.`,
        beat ? '' : 'warn')}
      ${ui.table([
        { label: 'Topic', get: (t) => `<b>${esc(t.topic || 'General')}</b>` },
        { label: 'Industry standard', get: (t) => `<span class="sm">${
          esc(t.standard || '—')}</span>` },
        { label: 'Expected proficiency', get: (t) => ui.progressBar(Number(t.expected) || 0,
            (Number(t.expected) || 0) + '%') },
      ], topics.map((t, i) => ({ id: i, ...t })), 'id')}
    </div>`;
}

// 4 ── Topic breakdown
function topicCard(r) {
  const strong = Array.isArray(r.strong_topics) ? r.strong_topics : [];
  const weak = Array.isArray(r.weak_topics) ? r.weak_topics : [];
  return `
    <div class="two-col">
      <div class="card">
        <div class="card-head"><h3>Strong topics</h3>
          <span class="tag ok">${strong.length}</span></div>
        ${strong.length ? strong.map(topicRow).join('')
          : '<div class="empty-state">No topic cleared 70% on this attempt.</div>'}
      </div>
      <div class="card">
        <div class="card-head"><h3>Weak topics</h3>
          <span class="tag warn">${weak.length}</span></div>
        ${weak.length ? weak.map(topicRow).join('')
          : '<div class="empty-state">No weak topic was recorded — every topic cleared 70%.</div>'}
      </div>
    </div>`;
}

function topicRow(t) {
  const pct = Number(t.pct) || 0;
  const correct = Number(t.correct) || 0;
  const total = Number(t.total) || 0;
  return `
    <div class="tp-row">
      <div class="row gap">
        <b>${esc(t.topic || 'General')}</b>
        <span class="grow"></span>
        <span class="sm muted">${correct}/${total}</span>
      </div>
      ${ui.progressBar(pct, pct + '%')}
    </div>`;
}

// 5 ── Difficulty breakdown
function difficultyCard(r) {
  const diff = (r.difficulty_breakdown && typeof r.difficulty_breakdown === 'object')
    ? r.difficulty_breakdown : {};
  const keys = Object.keys(diff);
  return `
    <div class="card">
      <div class="card-head"><h3>Difficulty breakdown</h3>
        <span class="tag mute">${keys.length} level${keys.length === 1 ? '' : 's'}</span></div>
      ${keys.length ? keys.map((k) => {
        const v = diff[k];
        const isObj = v && typeof v === 'object';
        const pct = isObj ? (Number(v.pct) || 0) : (Number(v) || 0);
        const correct = isObj ? (Number(v.correct) || 0) : null;
        const total = isObj ? (Number(v.total) || 0) : null;
        return `
          <div class="tp-row">
            <div class="row gap">
              <b>${esc(sentence(k))}</b>
              <span class="grow"></span>
              ${correct !== null ? `<span class="sm muted">${correct}/${total}</span>` : ''}
            </div>
            ${ui.progressBar(pct, pct + '%')}
          </div>`;
      }).join('')
      : '<div class="empty-state">No difficulty split was recorded for this attempt.</div>'}
    </div>`;
}

// 6 ── AI personalisation
function aiCard(r, ai) {
  const generated = !!r.ai_generated;

  const head = `
    <div class="card-head"><h3>Veda personalisation</h3>
      ${generated
        ? '<span class="tag ok">Written by Veda</span>'
        : '<span class="tag mute">Not generated</span>'}
      ${r.ai_model ? `<span class="tag mute">${esc(r.ai_model)}</span>` : ''}
      <button class="btn ${generated ? 'ghost' : 'primary'} sm" data-personalise="${
        esc(r.id)}">${generated ? 'Refresh' : 'Personalise with Veda'}</button>
    </div>`;

  if (!generated) {
    return `
      <div class="card">
        ${head}
        ${ui.note(`The scores, topics and benchmark above are computed and complete on
          their own. Veda adds the written layer: what tripped this learner up, what to
          fix first, and how it compares with the industry standard.`)}
        <span class="auth-err" data-ai-err></span>
      </div>`;
  }

  const blocks = [
    ['Where they lost ground', ai.weak_points, NO_TEXT.weak_points],
    ['What to fix first', ai.improve, NO_TEXT.improve],
    ['Against the industry standard', ai.industry, NO_TEXT.industry],
    ['What to learn next', ai.learn_next, NO_TEXT.learn_next],
  ];
  const suggestions = Array.isArray(ai.suggestions) ? ai.suggestions : [];

  return `
    <div class="card">
      ${head}
      <div class="stack">
        ${blocks.map(([title, value, fallback]) => `
          <div class="ai-block">
            <b>${esc(title)}</b>
            <p>${esc(String(value || fallback))}</p>
          </div>`).join('')}
        <div class="ai-block">
          <b>Suggested study actions</b>
          ${suggestions.length
            ? `<ul class="cc-steps">${suggestions.map((s) =>
                `<li>${esc(String(s))}</li>`).join('')}</ul>`
            : `<p>${esc(NO_TEXT.suggestions)}</p>`}
        </div>
      </div>
      <span class="auth-err" data-ai-err></span>
    </div>`;
}

// 7 ── Next steps
function stepsCard(steps, ai, generated) {
  const learn = generated && ai.learn_next;
  const total = steps.length + (learn ? 1 : 0);
  return `
    <div class="card">
      <div class="card-head"><h3>Next steps</h3>
        <span class="tag info">${total} action${total === 1 ? '' : 's'}</span></div>
      ${total ? `
        <ol class="cc-steps">
          ${steps.map((s) => `
            <li>
              <span class="tag ${s.priority === 'high' ? 'bad'
                : s.priority === 'medium' ? 'warn' : 'mute'}">${
                esc(String(s.priority || 'medium').toUpperCase())}</span>
              <span>${esc(String(s.action || ''))}</span>
            </li>`).join('')}
          ${learn ? `<li><span class="tag info">VEDA</span>
            <span>${esc(String(ai.learn_next))}</span></li>` : ''}
        </ol>`
      : '<div class="empty-state">No next steps were generated for this report.</div>'}
    </div>`;
}

// ─── Detail events ──────────────────────────────────────────────────────────

function bindDetail(root) {
  view.offs.push(ui.click(root, '[data-retry]', (e) => {
    e.preventDefault();
    detail(view.root, { params: { id: view.reportId } });
  }));

  view.offs.push(ui.click(root, '[data-personalise]', async (e, btn) => {
    const id = btn.dataset.personalise || view.reportId;
    if (!id) return;
    await ui.busy(btn, 'Writing…', async () => {
      try {
        const res = await api('/v1/ai/personalise-report', {
          method: 'POST',
          body: JSON.stringify({ report_id: id }),
        });
        const out = ui.data(res);
        if (out && out.ai_generated) toast('Veda has personalised this report.');
        else toast('Veda could not personalise this report.', 'warn');
        await detail(view.root, { params: { id } });
      } catch (err) {
        const box = view.root.querySelector('[data-ai-err]');
        if (box) box.textContent = err.message;
        else toast(err.message, 'warn');
      }
    });
  }));
}

// ─── Shared bits ────────────────────────────────────────────────────────────

function duration(start, end) {
  if (!start || !end) return '';
  const ms = new Date(end) - new Date(start);
  if (!isFinite(ms) || ms < 0) return '';
  const mins = Math.round(ms / 60000);
  if (mins < 1) return '< 1 min';
  if (mins < 60) return mins + ' min';
  return Math.floor(mins / 60) + ' h ' + (mins % 60) + ' min';
}

function sentence(k) {
  return String(k).replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
