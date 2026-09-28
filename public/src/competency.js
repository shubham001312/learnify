// Learnify — competency mapping: subject → ranked, explainable match.
// Routes: `/competency[/{subject}]` (the hub) and `/trainers/{subject}` (ranking).
//
// The ordering is deterministic by design, so every result prints its own
// reasons: `explanation` comes back from the API as a list of sentences and is
// rendered verbatim — this module never invents commentary of its own.
//
// Follows the courses.js / library.js pattern: fetch with `api()`, unwrap with
// `ui.data()`, render with `ui.*`, bind through `ui.click(root, …)`, and return
// `{ destroy }` so the delegated listeners are released on route teardown.

import { api, esc, toast } from './utils.js?v=64';
import * as ui from './ui.js?v=64';
import { go, confirmAction, currentUser, openAppModal, closeAppModal } from './app.js?v=64';
import { iconSvg } from './icons.js?v=64';

const HUB_SUB = {
  ALPHA: 'Pick a subject to see the trainers ranked for it — with the reasoning printed under every result.',
  MASTER: 'Declare what you can teach and back it with evidence. The ranking reads your declarations the same way every time.',
  SUPREME: 'Review what trainers have declared, verify what you can confirm, and open any subject to see its ranking.',
};

// Route-scoped state; `offs` holds the `off()` handles for everything bound to
// `#view`, plus the one listener that lives on the shared modal host.
const view = { root: null, role: 'ALPHA', offs: [], modalOffs: [] };
const verifyState = { rows: [], filter: 'pending', capped: 0 };

function clearOffs() {
  view.offs.forEach((off) => off());
  view.offs = [];
  view.modalOffs.forEach((off) => off());
  view.modalOffs = [];
}

function teardown() { clearOffs(); }

// ─── Competency hub ─────────────────────────────────────────────────────────

export async function render(root, ctx) {
  clearOffs();

  const user = ctx.user || currentUser() || {};
  const role = user.role || 'ALPHA';
  const subjectParam = (ctx.params && ctx.params.subject) || '';

  view.root = root;
  view.role = role;
  verifyState.rows = [];
  verifyState.filter = 'pending';
  verifyState.capped = 0;

  root.innerHTML = ui.head({ title: 'Competency', sub: HUB_SUB[role] || HUB_SUB.ALPHA })
    + '<div class="stack">'
    + `<div data-picker>${ui.loading('subjects')}</div>`
    + `<div data-role>${role === 'ALPHA' ? '' : ui.loading('declarations')}</div>`
    + '</div>';

  bindHub(root);
  if (role === 'ALPHA') paintExplainer(root.querySelector('[data-role]'));

  // ── Subject picker (+ the requirement list when a subject sits in the path)
  let subjects = [];
  try {
    const res = await api('/v1/subjects?limit=200');
    subjects = ui.data(res) || [];
  } catch (err) {
    const box = root.querySelector('[data-picker]');
    if (box) box.innerHTML = ui.errorBlock(err.message);
  }
  if (subjects.length) {
    await paintPicker(root.querySelector('[data-picker]'), subjects, subjectParam);
  }

  // ── Role panel
  if (role === 'MASTER') await loadMine(root);
  else if (role === 'SUPREME') await loadVerify(root);

  return { destroy: teardown };
}

function paintExplainer(box) {
  if (!box) return;
  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3>How the ranking works</h3>${iconSvg('award')}</div>
      ${ui.note(`Learnify scores every trainer with one fixed formula: weighted
        proficiency against the subject's required competencies, plus a bonus for
        every verified declaration and a small bonus for evidence. The inputs
        never move, so the order never moves — and every card explains its own
        position. <b>Choose a subject below to see who can teach you.</b>`)}
      <div class="wrap mt">
        <span class="tag mute">Deterministic</span>
        <span class="tag mute">Explainable</span>
        <span class="tag mute">No AI in the ranking</span>
      </div>
    </div>`;
}

async function paintPicker(box, subjects, subjectParam) {
  if (!box) return;
  const subject = subjectParam
    ? subjects.find((s) => s.id === subjectParam) : null;

  box.innerHTML = `
    ${subject ? '<div class="card mb" data-reqs>' + ui.loading('requirements') + '</div>' : ''}
    <div class="card">
      <div class="card-head"><h3>Choose a subject</h3>
        <span class="tag mute">${subjects.length}</span></div>
      <div class="toolbar">
        <select data-jump aria-label="Jump to a subject ranking">
          <option value="">Jump to a subject…</option>
          ${subjects.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}
        </select>
        <button class="btn primary sm" data-jump-go>View ranking</button>
      </div>
      <div class="cc-grid three mt">${subjects.map(subjectCard).join('')}</div>
    </div>`;

  if (subject) await loadReqs(box.querySelector('[data-reqs]'), subject);
}

function subjectCard(s) {
  return `
    <a class="cc-card compact subject" href="#/trainers/${esc(s.id)}" style="text-decoration:none">
      <div class="cc-card-head">
        ${iconSvg('award')}
        ${s.code ? `<span class="role-tag">${esc(s.code)}</span>` : ''}
      </div>
      <h3>${esc(s.name)}</h3>
      <span class="link sm">See ranked trainers</span>
    </a>`;
}

async function loadReqs(box, subject) {
  if (!box) return;
  try {
    const res = await api(`/v1/subjects/${encodeURIComponent(subject.id)}/competencies`);
    const rows = ui.data(res) || [];
    box.innerHTML = `
      <div class="card-head">
        <h3>What this subject requires</h3>
        ${subject.code ? `<span class="role-tag">${esc(subject.code)}</span>` : ''}
        <a class="btn primary sm" href="#/trainers/${esc(subject.id)}">See ranked trainers</a>
      </div>
      <b>${esc(subject.name)}</b>
      ${rows.length ? `<ul class="cc-reqlist">${rows.map((r) => `
        <li>
          <span class="cc-req-w">${esc(String(r.required_weight))}&times;</span>
          <div>
            <b>${esc(r.name)}</b>
            ${r.description ? `<p class="sm muted">${esc(r.description)}</p>` : ''}
          </div>
        </li>`).join('')}</ul>`
      : `<div class="empty-state">No competencies have been published for
          ${esc(subject.name)} yet, so the ranking falls back to raw declared strength.</div>`}`;
  } catch (err) {
    box.innerHTML = ui.errorBlock(err.message);
  }
}

// ─── Master: declared competencies ──────────────────────────────────────────

async function loadMine(root) {
  const box = root.querySelector('[data-role]');
  if (!box) return;
  box.innerHTML = ui.loading('your competencies');
  let catalog = [], mine = [];
  try {
    const [cRes, mRes] = await Promise.all([
      api('/v1/competency/catalog'),
      api('/v1/competency/mine'),
    ]);
    catalog = ui.data(cRes) || [];
    mine = ui.data(mRes) || [];
  } catch (err) {
    box.innerHTML = ui.errorBlock(err.message);
    return;
  }
  paintMine(box, catalog, mine);
}

function paintMine(box, catalog, mine) {
  const declared = new Set(mine.map((m) => m.competency_id));
  box.innerHTML = `
    <div class="stack">
      <div class="card">
        <div class="card-head"><h3>My competencies</h3>
          <span class="tag ${mine.length ? 'ok' : 'mute'}">${mine.length} declared</span></div>
        ${mine.length ? mine.map(mineRow).join('') : ui.blank({
          title: 'Nothing declared yet',
          body: 'Add a competency below — the ranking only counts what you declare.',
        })}
      </div>

      <div class="card">
        <div class="card-head"><h3>Declare proficiency</h3></div>
        ${catalog.length ? `
          <form data-declare novalidate>
            <div class="two-col">
              <div class="field">
                <label for="cc-comp">Competency</label>
                <select id="cc-comp" name="competency_id">
                  <option value="">Choose a competency…</option>
                  ${catalog.map((c) => `<option value="${esc(c.id)}">${
                    esc(c.name)}${declared.has(c.id) ? ' (already declared)' : ''}</option>`).join('')}
                </select>
              </div>
              <div class="field">
                <label for="cc-prof">Proficiency (0–100)</label>
                <input id="cc-prof" name="proficiency" type="number" min="0" max="100"
                       step="1" value="60" inputmode="numeric">
              </div>
            </div>
            <div class="field">
              <label for="cc-ev">Evidence (optional, 400 characters)</label>
              <input id="cc-ev" name="evidence" maxlength="400"
                     placeholder="e.g. Certified practitioner, four years of delivery">
            </div>
            <div class="row gap" style="justify-content:flex-end;align-items:center">
              <span class="auth-err" data-err></span>
              <button class="btn primary sm" type="submit">Save declaration</button>
            </div>
          </form>` : `<div class="empty-state">The competency catalogue is empty —
            add one with the form below.</div>`}
      </div>

      <div class="card">
        <div class="card-head"><h3>Add a competency to the catalogue</h3></div>
        <form data-newcomp novalidate>
          <div class="two-col">
            <div class="field">
              <label for="cc-new-name">Name</label>
              <input id="cc-new-name" name="name" maxlength="120"
                     placeholder="e.g. Clinical supervision">
            </div>
            <div class="field">
              <label for="cc-new-desc">Description (optional)</label>
              <input id="cc-new-desc" name="description" maxlength="500"
                     placeholder="What this competency covers">
            </div>
          </div>
          <div class="row gap" style="justify-content:flex-end;align-items:center">
            <span class="auth-err" data-err></span>
            <button class="btn ghost sm" type="submit">Add competency</button>
          </div>
        </form>
        <p class="sm muted mt">Creating it is step one — link it to a subject with a
          required weight to make it count toward a ranking.</p>
      </div>
    </div>`;
}

function mineRow(c) {
  const prof = Number(c.proficiency) || 0;
  return `
    <div class="cc-dec">
      <div class="cc-dec-body">
        <div class="row gap" style="flex-wrap:wrap">
          <b>${esc(c.name)}</b>
          ${c.verified
            ? '<span class="tag ok">Verified</span>'
            : '<span class="tag warn">Self-declared</span>'}
          <span class="grow"></span>
          <span class="sm muted">${prof}% proficiency</span>
        </div>
        ${c.description ? `<p class="sm muted">${esc(c.description)}</p>` : ''}
        ${ui.progressBar(prof, prof + '%')}
        ${c.evidence ? `<p class="sm dim cc-ev">Evidence: ${esc(c.evidence)}</p>` : ''}
        ${c.verified && c.verified_at
          ? `<p class="sm muted">Verified ${esc(ui.fmtDate(c.verified_at))}</p>` : ''}
      </div>
      <button class="btn ghost sm" data-remove="${esc(c.competency_id)}"
              data-name="${esc(c.name)}">Remove</button>
    </div>`;
}

// ─── Supreme: verification queue ────────────────────────────────────────────

async function loadVerify(root) {
  const box = root.querySelector('[data-role]');
  if (!box) return;
  box.innerHTML = ui.loading('declarations awaiting verification');

  const cap = 30;
  let trainers = [];
  try {
    const res = await api(`/v1/admin/users?role=MASTER&status=ACTIVE&limit=${cap}`);
    trainers = ui.data(res) || [];
  } catch (err) {
    box.innerHTML = ui.errorBlock(err.message);
    return;
  }

  // A trainer's profile is the only place that carries per-competency
  // verification state, so the queue is assembled one profile at a time.
  const profiles = await mapLimit(trainers, 6, (t) =>
    api(`/v1/competency/trainers/${encodeURIComponent(t.id)}/profile`)
      .then((r) => ui.data(r)).catch(() => null));

  const rows = [];
  profiles.filter(Boolean).forEach((p) => {
    const t = p.trainer || {};
    (p.competencies || []).forEach((c) => rows.push({
      trainer_id: t.id,
      trainer_name: t.name || 'Unknown trainer',
      trainer_designation: t.designation || t.department || '',
      competency_id: c.competency_id,
      name: c.name || c.competency_id,
      evidence: c.evidence || '',
      proficiency: Number(c.proficiency) || 0,
      verified: !!c.verified,
      verified_at: c.verified_at || '',
    }));
  });

  verifyState.rows = rows;
  verifyState.capped = trainers.length >= cap ? cap : 0;
  paintVerify(box);
}

function paintVerify(box) {
  if (!box) return;
  const all = verifyState.rows;
  const pending = all.filter((r) => !r.verified);
  const rows = verifyState.filter === 'all' ? all : pending;

  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3>Verification queue</h3>
        ${pending.length
          ? `<span class="tag warn">${pending.length} pending</span>`
          : '<span class="tag ok">All clear</span>'}</div>
      ${ui.pillbar([
        { key: 'pending', label: 'Awaiting verification', count: pending.length },
        { key: 'all', label: 'All declarations', count: all.length },
      ], verifyState.filter)}
      ${verifyState.capped
        ? `<p class="sm muted">Scanned the first ${verifyState.capped} active trainers.</p>`
        : ''}
      ${rows.length
        ? ui.table(vCols(), rows)
        : (verifyState.filter === 'all'
            ? ui.blank({ title: 'No declarations on record',
                body: 'Trainers have not declared any competencies yet.' })
            : ui.blank({ title: 'Nothing waiting for verification',
                body: 'Every declaration has been reviewed. Switch to “All declarations” to withdraw a verification.' }))}
    </div>`;
}

function vCols() {
  return [
    { label: 'Trainer', get: (r) => ui.who(r.trainer_name, r.trainer_designation) },
    { label: 'Competency', get: (r) => `<b>${esc(r.name)}</b>` },
    { label: 'Proficiency', get: (r) => ui.progressBar(r.proficiency, r.proficiency + '%') },
    { label: 'Evidence', get: (r) => (r.evidence
        ? `<span class="sm dim">${esc(r.evidence)}</span>`
        : '<span class="sm muted">—</span>') },
    { label: 'Status', get: (r) => (r.verified
        ? '<span class="tag ok">Verified</span>'
        : '<span class="tag warn">Pending</span>') },
    { label: 'Action', get: (r) => (r.verified
        ? `<button class="btn ghost sm" data-vfy="0" data-trainer="${esc(r.trainer_id)}"
             data-comp="${esc(r.competency_id)}">Unverify</button>`
        : `<button class="btn primary sm" data-vfy="1" data-trainer="${esc(r.trainer_id)}"
             data-comp="${esc(r.competency_id)}">Verify</button>`) },
  ];
}

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) },
    async () => {
      while (next < items.length) {
        const i = next++;
        out[i] = await fn(items[i], i);
      }
    });
  await Promise.all(workers);
  return out;
}

// ─── Hub events ─────────────────────────────────────────────────────────────

function bindHub(root) {
  view.offs.push(ui.click(root, '[data-retry]', (e) => {
    e.preventDefault();
    render(root, { params: {}, user: currentUser(), route: null });
  }));

  view.offs.push(ui.click(root, '[data-jump-go]', () => {
    const sel = root.querySelector('[data-jump]');
    const id = sel ? sel.value : '';
    if (!id) { toast('Choose a subject first.', 'warn'); return; }
    go('/trainers/' + id);
  }));

  view.offs.push(ui.click(root, '[data-remove]', async (e, btn) => {
    const id = btn.dataset.remove;
    const name = btn.dataset.name || 'This competency';
    const ok = await confirmAction('Remove this declaration?',
      `${name} will stop counting toward your ranking until you declare it again.`,
      'Remove');
    if (!ok) return;
    try {
      await api(`/v1/competency/mine/${encodeURIComponent(id)}`, { method: 'DELETE' });
      toast('Declaration removed.');
      if (view.role === 'MASTER') await loadMine(view.root);
    } catch (err) { toast(err.message, 'warn'); }
  }));

  view.offs.push(ui.on(root, '[data-declare]', 'submit', async (e, form) => {
    e.preventDefault();
    const v = ui.formValues(form);
    const prof = Number(v.proficiency);
    if (!v.competency_id) { ui.formError(form, 'Choose a competency first.'); return; }
    if (!isFinite(prof) || prof < 0 || prof > 100) {
      ui.formError(form, 'Proficiency must be between 0 and 100.');
      return;
    }
    ui.formError(form, '');
    const btn = form.querySelector('button[type=submit]');
    await ui.busy(btn, 'Saving…', async () => {
      try {
        await api('/v1/competency/mine', {
          method: 'PUT',
          body: JSON.stringify({
            items: [{
              competency_id: v.competency_id,
              proficiency: Math.round(prof),
              evidence: String(v.evidence || '').slice(0, 400),
            }],
          }),
        });
        toast('Declaration saved.');
        await loadMine(view.root);
      } catch (err) { ui.formError(form, err.message); }
    });
  }));

  view.offs.push(ui.on(root, '[data-newcomp]', 'submit', async (e, form) => {
    e.preventDefault();
    const v = ui.formValues(form);
    const name = String(v.name || '').trim();
    if (!name) { ui.formError(form, 'A name is required.'); return; }
    ui.formError(form, '');
    const btn = form.querySelector('button[type=submit]');
    await ui.busy(btn, 'Adding…', async () => {
      try {
        await api('/v1/subjects/competencies', {
          method: 'POST',
          body: JSON.stringify({ name, description: String(v.description || '').trim() }),
        });
        toast('Competency added to the catalogue.');
        await loadMine(view.root);
      } catch (err) { ui.formError(form, err.message); }
    });
  }));

  view.offs.push(ui.click(root, '[data-pill]', (e, btn) => {
    verifyState.filter = btn.dataset.pill || 'pending';
    paintVerify(view.root.querySelector('[data-role]'));
  }));

  view.offs.push(ui.click(root, '[data-vfy]', async (e, btn) => {
    const willVerify = btn.dataset.vfy === '1';
    const ok = await confirmAction(
      willVerify ? 'Verify this declaration?' : 'Withdraw this verification?',
      willVerify
        ? 'Your verification adds a bonus to this trainer’s score in every ranking.'
        : 'The bonus for this declaration comes off the trainer’s score immediately.',
      willVerify ? 'Verify' : 'Unverify');
    if (!ok) return;
    try {
      await api('/v1/competency/verify', {
        method: 'POST',
        body: JSON.stringify({
          trainer_id: btn.dataset.trainer,
          competency_id: btn.dataset.comp,
          verified: willVerify,
        }),
      });
      toast(willVerify ? 'Competency verified.' : 'Verification withdrawn.');
      if (view.role === 'SUPREME') await loadVerify(view.root);
    } catch (err) { toast(err.message, 'warn'); }
  }));
}

// ─── Ranked trainers ────────────────────────────────────────────────────────

export async function rank(root, ctx) {
  clearOffs();
  view.root = root;
  view.role = (ctx.user || currentUser() || {}).role || 'ALPHA';

  const subjectId = (ctx.params && ctx.params.subject) || '';
  paintRankShell(root, subjectId, 'Loading subjects');
  bindRank(root, ctx);

  let subjects = [];
  try {
    const res = await api('/v1/subjects?limit=200');
    subjects = ui.data(res) || [];
  } catch (_) { subjects = []; }

  const subject = subjects.find((s) => s.id === subjectId);
  paintRankShell(root, subjectId, subject ? subject.name : subjectId, subjects, subject);

  const body = root.querySelector('[data-body]');
  let rows = [], meta = {};
  try {
    const res = await api(`/v1/competency/trainers/${encodeURIComponent(subjectId)}?limit=50`);
    rows = ui.data(res) || [];
    meta = ui.meta(res);
  } catch (err) {
    body.innerHTML = ui.errorBlock(err.message);
    return { destroy: teardown };
  }

  body.innerHTML = rows.length
    ? metaBar(meta)
      + `<div class="stack">${rows.map((r, i) => rankCard(r, i, view.role)).join('')}</div>`
      + `<p class="muted sm center mt">${rows.length} trainer${
          rows.length === 1 ? '' : 's'} shown — the order is fixed by the formula, not by opinion.</p>`
    : ui.blank({
        title: 'No trainers match yet',
        body: 'No trainer has declared proficiency against this subject. Trainers: open the Competency page, declare what you know and add evidence, and you will appear here.',
      });

  return { destroy: teardown };
}

function paintRankShell(root, subjectId, title, subjects, subject) {
  const switcher = (subjects && subjects.length)
    ? `<div class="toolbar">
        <select data-rank-jump aria-label="Switch subject">
          ${subjects.map((s) => `<option value="${esc(s.id)}"${
            s.id === subjectId ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}
        </select>
        <button class="btn primary sm" data-rank-go>View ranking</button>
      </div>`
    : '';
  const code = subject && subject.code ? esc(subject.code) + ' · ' : '';

  root.innerHTML = `
    <div class="crumbs"><a href="#/competency">&larr; Competency</a></div>
    ${ui.head({
      title,
      sub: `${code}Trainers ranked by weighted proficiency, verification and
        evidence — the reasoning is printed on every card.`,
    })}
    ${switcher}
    <div data-body>${ui.loading('ranked trainers')}</div>`;
}

function metaBar(meta) {
  const bits = Object.entries(meta || {}).filter(([, v]) =>
    v !== null && v !== undefined && v !== '' && typeof v !== 'object');
  if (!bits.length) return '';
  return `<div class="wrap mb">${bits.map(([k, v]) =>
    `<span class="tag mute">${esc(sentence(k))}: ${esc(String(v))}</span>`).join('')}</div>`;
}

function sentence(k) {
  return String(k).replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function rankCard(row, index, role) {
  const why = Array.isArray(row.explanation)
    ? row.explanation
    : (row.explanation ? [row.explanation] : []);
  const canProfile = role === 'MASTER' || role === 'SUPREME';

  const coverageTags = row.required
    ? `<span class="tag info">${esc(String(row.matched))} of ${esc(String(row.required))} competencies</span>
       <span class="tag mute">${esc(String(row.coverage))}% coverage</span>`
    : `<span class="tag mute">${esc(String(row.matched))} declared</span>`;

  return `
    <div class="cc-rank">
      <div class="cc-rank-n">${index + 1}</div>
      <div class="cc-rank-main">
        <div class="cc-rank-top">
          ${ui.who(row.name, [row.designation, row.department].filter(Boolean).join(' · '))}
          <span class="grow"></span>
          <div class="cc-score"><b>${esc(String(row.score))}</b><small>score</small></div>
        </div>

        ${row.headline ? `<p class="sm dim">${esc(row.headline)}</p>` : ''}

        <div class="wrap cc-rank-tags">
          ${coverageTags}
          ${Number(row.verified) > 0
            ? `<span class="tag ok">${esc(String(row.verified))} verified</span>`
            : '<span class="tag warn">Nothing verified</span>'}
        </div>

        <div class="cc-why">
          <b>Why this rank</b>
          ${why.length
            ? `<ul>${why.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>`
            : '<p class="sm muted">No breakdown was returned for this trainer.</p>'}
        </div>

        ${canProfile ? `
          <div class="card-foot">
            <span class="grow"></span>
            <button class="btn ghost sm" data-profile="${esc(row.id)}">Full profile</button>
          </div>` : ''}
      </div>
    </div>`;
}

function bindRank(root, ctx) {
  view.offs.push(ui.click(root, '[data-retry]', (e) => {
    e.preventDefault();
    rank(root, ctx);
  }));

  view.offs.push(ui.click(root, '[data-rank-go]', () => {
    const sel = root.querySelector('[data-rank-jump]');
    if (!sel || !sel.value) { toast('Choose a subject first.', 'warn'); return; }
    go('/trainers/' + sel.value);
  }));

  view.offs.push(ui.on(root, '[data-rank-jump]', 'change', (e, sel) => {
    if (sel.value) go('/trainers/' + sel.value);
  }));

  view.offs.push(ui.click(root, '[data-profile]', async (e, btn) => {
    const id = btn.dataset.profile;
    openAppModal(`
      <h3 class="modal-title">Competency profile</h3>
      <p class="modal-sub">Loading the full breakdown…</p>`);
    try {
      const res = await api(`/v1/competency/trainers/${encodeURIComponent(id)}/profile`);
      const p = ui.data(res);
      if (!p || !p.trainer) throw new Error('Profile not found.');
      openAppModal(profileHtml(p));
    } catch (err) {
      openAppModal(`
        <h3 class="modal-title">Profile unavailable</h3>
        <p class="modal-sub">${esc(err.message)}</p>
        <div class="row gap" style="justify-content:flex-end;margin-top:16px">
          <button class="btn ghost sm" data-close-modal>Close</button>
        </div>`);
    }
  }));

  // The modal host outlives the view, so its listener is tracked separately.
  const modalBody = document.getElementById('app-modal-body');
  if (modalBody) {
    view.modalOffs.push(ui.click(modalBody, '[data-close-modal]',
      () => closeAppModal()));
  }
}

function profileHtml(p) {
  const t = p.trainer || {};
  const rows = p.competencies || [];
  const avg = rows.length
    ? Math.round(rows.reduce((s, r) => s + (Number(r.proficiency) || 0), 0) / rows.length) + '%'
    : '—';

  return `
    <h3 class="modal-title">${esc(t.name || 'Trainer')}</h3>
    <p class="modal-sub">${esc([t.designation, t.department].filter(Boolean).join(' · ')
      || 'Trainer')}</p>
    ${ui.kv([
      ['Declared', String(rows.length)],
      ['Verified', String(p.verified_count || 0)],
      ['Average proficiency', avg],
    ])}
    ${t.headline ? `<p class="sm dim mt">${esc(t.headline)}</p>` : ''}
    ${rows.length ? `<div class="stack mt">${rows.map((r) => {
      const prof = Number(r.proficiency) || 0;
      return `
        <div class="cc-dec">
          <div class="cc-dec-body">
            <div class="row gap" style="flex-wrap:wrap">
              <b>${esc(r.name)}</b>
              ${r.verified
                ? '<span class="tag ok">Verified</span>'
                : '<span class="tag warn">Pending</span>'}
              <span class="grow"></span>
              <span class="sm muted">${prof}%</span>
            </div>
            ${ui.progressBar(prof, prof + '%')}
            ${r.evidence ? `<p class="sm dim cc-ev">Evidence: ${esc(r.evidence)}</p>` : ''}
          </div>
        </div>`;
    }).join('')}</div>`
    : '<div class="empty-state">This trainer has not declared anything yet.</div>'}
    <div class="row gap" style="justify-content:flex-end;margin-top:16px">
      <button class="btn ghost sm" data-close-modal>Close</button>
    </div>`;
}
