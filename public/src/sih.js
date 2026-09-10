/* ═══════════════════════════════════════════════════════════════════
   SIH Module — Skills, Opportunities, Internships, Portfolio, Analytics
   Learnify · SIH 2026 (SIH26044)
   ═══════════════════════════════════════════════════════════════════ */

import { api, el, esc, qs, getToken } from './utils.js?v=51';

/* ── helpers ────────────────────────────────────────────────────── */
const h = (tag, cls, inner) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (inner != null) e.innerHTML = inner;
  return e;
};
const fmt = (n) => n == null ? '—' : Number(n).toFixed(1);
const pct = (n) => n == null ? '—' : Math.round(n) + '%';

function requireLogin() {
  if (!getToken()) {
    document.getElementById('auth-modal')?.classList.add('open');
    return false;
  }
  return true;
}

/* ──────────────────────────────────────────────────────────────────
   1. SKILLS PAGE
   ────────────────────────────────────────────────────────────────── */
export function initSkills() {
  const root = document.getElementById('page-skills');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const searchInput = el('skills-search');
  const categoryFilter = el('skills-category');
  const list = el('skills-list');
  const mySkills = el('my-skills');
  const saveBtn = el('skills-save');

  let allSkills = [];
  let mySkillIds = new Set();

  async function loadSkills() {
    try {
      const data = await api('/v1/skills?limit=200');
      allSkills = data.items || data || [];
    } catch { allSkills = []; }
    renderSkills();
  }

  async function loadMySkills() {
    if (!getToken()) return;
    try {
      const data = await api('/v1/student/skills');
      mySkillIds = new Set((data || []).map(s => s.skill_id || s.id));
    } catch { mySkillIds = new Set(); }
    renderMySkills();
  }

  function renderSkills() {
    if (!list) return;
    const q = (searchInput?.value || '').toLowerCase();
    const cat = categoryFilter?.value || '';
    let filtered = allSkills;
    if (q) filtered = filtered.filter(s => (s.name || '').toLowerCase().includes(q) || (s.aliases || '').toLowerCase().includes(q));
    if (cat) filtered = filtered.filter(s => s.category === cat);

    if (!filtered.length) { list.innerHTML = '<div class="sih-empty">No skills found.</div>'; return; }
    list.innerHTML = filtered.map(s => `
      <label class="skill-chip ${mySkillIds.has(s.id) ? 'active' : ''}" data-id="${esc(s.id)}">
        <input type="checkbox" ${mySkillIds.has(s.id) ? 'checked' : ''} style="display:none">
        <span class="skill-name">${esc(s.name)}</span>
        <span class="skill-cat">${esc(s.category || '')}</span>
      </label>
    `).join('');

    list.querySelectorAll('.skill-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const id = chip.dataset.id;
        if (mySkillIds.has(id)) { mySkillIds.delete(id); chip.classList.remove('active'); }
        else { mySkillIds.add(id); chip.classList.add('active'); }
        renderMySkills();
      });
    });
  }

  function renderMySkills() {
    if (!mySkills) return;
    const mine = allSkills.filter(s => mySkillIds.has(s.id));
    if (!mine.length) { mySkills.innerHTML = '<div class="sih-empty">Select skills from the catalog above.</div>'; return; }
    mySkills.innerHTML = mine.map(s => `
      <div class="my-skill-tag">${esc(s.name)} <button class="ms-rm" data-id="${esc(s.id)}">&times;</button></div>
    `).join('');
    mySkills.querySelectorAll('.ms-rm').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        mySkillIds.delete(btn.dataset.id);
        renderMySkills();
        renderSkills();
      });
    });
  }

  async function saveSkills() {
    if (!requireLogin() || !saveBtn) return;
    saveBtn.textContent = 'Saving…';
    try {
      const skills = Array.from(mySkillIds).map(id => ({ skill_id: id, proficiency: 5 }));
      await api('/v1/student/skills', { method: 'POST', body: JSON.stringify({ skills }) });
      saveBtn.textContent = 'Saved!';
      setTimeout(() => { saveBtn.textContent = 'Save My Skills'; }, 2000);
    } catch (e) {
      saveBtn.textContent = 'Error — retry';
      setTimeout(() => { saveBtn.textContent = 'Save My Skills'; }, 2000);
    }
  }

  searchInput?.addEventListener('input', renderSkills);
  categoryFilter?.addEventListener('change', renderSkills);
  saveBtn?.addEventListener('click', saveSkills);

  loadSkills();
  loadMySkills();
}

/* ──────────────────────────────────────────────────────────────────
   2. OPPORTUNITIES PAGE
   ────────────────────────────────────────────────────────────────── */
export function initOpportunities() {
  const root = document.getElementById('page-opportunities');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const list = el('opp-list');
  const searchInput = el('opp-search');
  const typeFilter = el('opp-type');
  const myApps = el('opp-my-apps');

  async function load() {
    if (!list) return;
    list.innerHTML = '<div class="sih-loading">Loading opportunities…</div>';
    try {
      const params = {};
      if (typeFilter?.value) params.type = typeFilter.value;
      const data = await api('/v1/opportunities' + qs(params));
      const items = data.items || data || [];
      if (!items.length) { list.innerHTML = '<div class="sih-empty">No opportunities found.</div>'; return; }
      list.innerHTML = items.map(o => `
        <div class="opp-card">
          <div class="opp-head">
            <div class="opp-title">${esc(o.title || o.name || '')}</div>
            <span class="opp-type-badge">${esc(o.type || 'Internship')}</span>
          </div>
          <div class="opp-meta">
            ${o.organization_name ? '<span class="opp-org">' + esc(o.organization_name) + '</span>' : ''}
            ${o.location ? '<span class="opp-loc">📍 ' + esc(o.location) + '</span>' : ''}
            ${o.stipend ? '<span class="opp-stip">💰 ' + esc(String(o.stipend)) + '</span>' : ''}
            ${o.duration_weeks ? '<span class="opp-dur">' + esc(String(o.duration_weeks)) + ' weeks</span>' : ''}
          </div>
          <div class="opp-skills">${(o.required_skills || []).map(s => '<span class="opp-skill-tag">' + esc(s) + '</span>').join('')}</div>
          <div class="opp-actions">
            <button class="btn primary sm opp-apply" data-id="${esc(o.id)}">Apply</button>
            <button class="btn ghost sm opp-detail" data-id="${esc(o.id)}">Details</button>
          </div>
        </div>
      `).join('');

      list.querySelectorAll('.opp-apply').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!requireLogin()) return;
          btn.textContent = 'Applying…';
          try {
            await api('/v1/internships/apply/' + btn.dataset.id, { method: 'POST' });
            btn.textContent = 'Applied ✓';
            btn.disabled = true;
          } catch (e) {
            btn.textContent = e.message.includes('Already') ? 'Already applied' : 'Error';
            setTimeout(() => { btn.textContent = 'Apply'; btn.disabled = false; }, 2000);
          }
        });
      });
    } catch {
      list.innerHTML = '<div class="sih-empty">Could not load opportunities.</div>';
    }
  }

  async function loadMyApps() {
    if (!myApps || !getToken()) return;
    try {
      const data = await api('/v1/internships/my-applications');
      const items = data.items || data || [];
      if (!items.length) { myApps.innerHTML = '<div class="sih-empty">No applications yet.</div>'; return; }
      myApps.innerHTML = '<h3>My Applications</h3>' + items.map(a => `
        <div class="app-card">
          <div class="app-title">${esc(a.opportunity_title || '')}</div>
          <div class="app-org">${esc(a.organization || '')}</div>
          <span class="app-status status-${(a.status || '').toLowerCase()}">${esc(a.status)}</span>
          <span class="app-date">${a.applied_at ? new Date(a.applied_at).toLocaleDateString() : ''}</span>
        </div>
      `).join('');
    } catch { myApps.innerHTML = ''; }
  }

  searchInput?.addEventListener('input', load);
  typeFilter?.addEventListener('change', load);

  load();
  loadMyApps();
}

/* ──────────────────────────────────────────────────────────────────
   3. INTERNSHIPS PAGE
   ────────────────────────────────────────────────────────────────── */
export function initInternships() {
  const root = document.getElementById('page-internships');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const activeList = el('intern-active');
  const feedbackList = el('intern-feedback');
  const credList = el('intern-credentials');

  async function loadActive() {
    if (!activeList) return;
    if (!getToken()) { activeList.innerHTML = '<div class="sih-empty">Login to view internships.</div>'; return; }
    try {
      const data = await api('/v1/internships/active');
      const items = data || [];
      if (!items.length) { activeList.innerHTML = '<div class="sih-empty">No active internships.</div>'; return; }
      activeList.innerHTML = items.map(i => `
        <div class="intern-card">
          <div class="intern-head">
            <div class="intern-title">${esc(i.title || '')}</div>
            <span class="intern-status status-${(i.status || '').toLowerCase()}">${esc(i.status)}</span>
          </div>
          <div class="intern-meta">
            ${i.organization_name ? '<span>' + esc(i.organization_name) + '</span>' : ''}
            ${i.start_date ? '<span>Started ' + new Date(i.start_date).toLocaleDateString() + '</span>' : ''}
          </div>
          <div class="intern-progress">
            <div class="progress-bar"><div class="progress-fill" style="width:${i.completion_pct || 0}%"></div></div>
            <span class="progress-label">${pct(i.completion_pct)}</span>
          </div>
        </div>
      `).join('');
    } catch { activeList.innerHTML = '<div class="sih-empty">Could not load internships.</div>'; }
  }

  async function loadFeedback() {
    if (!feedbackList || !getToken()) return;
    try {
      const data = await api('/v1/mentor/my-feedback');
      if (!data || !data.length) { feedbackList.innerHTML = '<div class="sih-empty">No mentor feedback yet.</div>'; return; }
      feedbackList.innerHTML = data.map(f => `
        <div class="feedback-card">
          <div class="fb-header">
            <span class="fb-rating">⭐ ${fmt(f.overall_rating)}</span>
            <span class="fb-mentor">${esc(f.mentor_name || 'Mentor')}</span>
          </div>
          ${f.strengths ? '<div class="fb-strengths"><b>Strengths:</b> ' + esc(f.strengths) + '</div>' : ''}
          ${f.areas_for_improvement ? '<div class="fb-improve"><b>Improve:</b> ' + esc(f.areas_for_improvement) + '</div>' : ''}
          ${f.comments ? '<div class="fb-comments">' + esc(f.comments) + '</div>' : ''}
        </div>
      `).join('');
    } catch { feedbackList.innerHTML = ''; }
  }

  async function loadCredentials() {
    if (!credList || !getToken()) return;
    try {
      const data = await api('/v1/credentials/my');
      if (!data || !data.length) { credList.innerHTML = '<div class="sih-empty">No credentials yet.</div>'; return; }
      credList.innerHTML = data.map(c => `
        <div class="cred-card">
          <div class="cred-title">${esc(c.title || '')}</div>
          <div class="cred-meta">
            <span class="cred-status status-${(c.status || '').toLowerCase()}">${esc(c.status)}</span>
            ${c.organization_name ? '<span>' + esc(c.organization_name) + '</span>' : ''}
            ${c.final_score != null ? '<span>Score: ' + fmt(c.final_score) + '</span>' : ''}
          </div>
          ${c.status === 'ISSUED' ? '<a class="btn ghost sm" href="/api/v1/credentials/' + esc(c.id) + '/verify" target="_blank">Verify</a>' : ''}
        </div>
      `).join('');
    } catch { credList.innerHTML = ''; }
  }

  loadActive();
  loadFeedback();
  loadCredentials();
}

/* ──────────────────────────────────────────────────────────────────
   4. PORTFOLIO PAGE
   ────────────────────────────────────────────────────────────────── */
export function initPortfolio() {
  const root = document.getElementById('page-portfolio');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const list = el('portfolio-list');
  const addBtn = el('portfolio-add-btn');
  const addForm = el('portfolio-add-form');
  const saveBtn = el('portfolio-save');
  const cancelBtn = el('portfolio-cancel');

  async function load() {
    if (!list || !getToken()) { if (list) list.innerHTML = '<div class="sih-empty">Login to view your portfolio.</div>'; return; }
    try {
      const data = await api('/v1/portfolio/my');
      if (!data || !data.length) { list.innerHTML = '<div class="sih-empty">No portfolio items yet. Add your first project!</div>'; return; }
      list.innerHTML = data.map(p => `
        <div class="portfolio-card">
          <div class="pf-head">
            <div class="pf-title">${esc(p.title || '')}</div>
            <span class="pf-cat">${esc(p.category || 'PROJECT')}</span>
          </div>
          <div class="pf-desc">${esc(p.description || '')}</div>
          <div class="pf-skills">${(p.skills_used || []).map(s => '<span class="pf-skill">' + esc(s) + '</span>').join('')}</div>
          <div class="pf-actions">
            ${p.file_url ? '<a class="btn ghost sm" href="' + esc(p.file_url) + '" target="_blank">View</a>' : ''}
            <button class="btn ghost sm pf-delete" data-id="${esc(p.id)}">Delete</button>
          </div>
        </div>
      `).join('');

      list.querySelectorAll('.pf-delete').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Delete this portfolio item?')) return;
          try {
            await api('/v1/portfolio/' + btn.dataset.id, { method: 'DELETE' });
            load();
          } catch {}
        });
      });
    } catch { list.innerHTML = '<div class="sih-empty">Could not load portfolio.</div>'; }
  }

  addBtn?.addEventListener('click', () => { addForm?.classList.toggle('hidden'); });
  cancelBtn?.addEventListener('click', () => { addForm?.classList.add('hidden'); });
  saveBtn?.addEventListener('click', async () => {
    if (!requireLogin()) return;
    const title = el('pf-title')?.value;
    const desc = el('pf-desc')?.value;
    const cat = el('pf-category')?.value;
    const skills = (el('pf-skills-input')?.value || '').split(',').map(s => s.trim()).filter(Boolean);
    if (!title) { alert('Title required'); return; }
    try {
      await api('/v1/portfolio/add', { method: 'POST', body: JSON.stringify({ title, description: desc, category: cat, skills_used: skills }) });
      addForm?.classList.add('hidden');
      el('pf-title').value = '';
      el('pf-desc').value = '';
      el('pf-skills-input').value = '';
      load();
    } catch (e) { alert(e.message); }
  });

  load();
}

/* ──────────────────────────────────────────────────────────────────
   5. ANALYTICS PAGE
   ────────────────────────────────────────────────────────────────── */
export function initAnalytics() {
  const root = document.getElementById('page-analytics');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const stats = el('analytics-stats');
  const demand = el('analytics-demand');

  async function loadStats() {
    if (!stats) return;
    if (!getToken()) { stats.innerHTML = '<div class="sih-empty">Login to see your analytics.</div>'; return; }
    try {
      const data = await api('/v1/analytics/student');
      stats.innerHTML = `
        <div class="analytics-grid">
          <div class="stat-card"><div class="stat-num">${data.skills_count || 0}</div><div class="stat-label">Skills Tracked</div></div>
          <div class="stat-card"><div class="stat-num">${data.assessments_taken || 0}</div><div class="stat-label">Assessments Done</div></div>
          <div class="stat-card"><div class="stat-num">${fmt(data.avg_score)}</div><div class="stat-label">Avg Score</div></div>
          <div class="stat-card"><div class="stat-num">${data.applications || 0}</div><div class="stat-label">Applications</div></div>
          <div class="stat-card"><div class="stat-num">${data.placed || 0}</div><div class="stat-label">Placed</div></div>
          <div class="stat-card"><div class="stat-num">${data.credentials || 0}</div><div class="stat-label">Credentials</div></div>
        </div>
      `;
    } catch { stats.innerHTML = '<div class="sih-empty">Could not load analytics.</div>'; }
  }

  async function loadDemand() {
    if (!demand) return;
    try {
      const data = await api('/v1/analytics/skill-demand');
      if (!data || !data.length) { demand.innerHTML = '<div class="sih-empty">No skill demand data yet.</div>'; return; }
      demand.innerHTML = '<h3>Top In-Demand Skills</h3>' + data.map((s, i) => `
        <div class="demand-row">
          <span class="demand-rank">#${i + 1}</span>
          <span class="demand-name">${esc(s.skill_name || s.skill_id)}</span>
          <span class="demand-bar"><span class="demand-fill" style="width:${Math.min(100, s.count * 10)}%"></span></span>
          <span class="demand-count">${s.count}x</span>
        </div>
      `).join('');
    } catch { demand.innerHTML = ''; }
  }

  loadStats();
  loadDemand();
}

/* ──────────────────────────────────────────────────────────────────
   6. LEARNING RESOURCES PAGE
   ────────────────────────────────────────────────────────────────── */
export function initLearning() {
  const root = document.getElementById('page-learning');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const list = el('learning-list');
  const recList = el('learning-recommended');
  const searchInput = el('learning-search');
  const catFilter = el('learning-category');

  async function loadResources() {
    if (!list) return;
    const params = {};
    if (searchInput?.value) params.skill = searchInput.value;
    if (catFilter?.value) params.category = catFilter.value;
    list.innerHTML = '<div class="sih-loading">Loading resources…</div>';
    try {
      const data = await api('/v1/learning-resources' + qs(params));
      const items = data.items || data || [];
      if (!items.length) { list.innerHTML = '<div class="sih-empty">No resources found.</div>'; return; }
      list.innerHTML = items.map(r => `
        <a href="${esc(r.url || '#')}" target="_blank" rel="noopener" class="learning-card">
          <div class="lc-head">
            <div class="lc-title">${esc(r.title || '')}</div>
            <span class="lc-provider">${esc(r.provider || '')}</span>
          </div>
          <div class="lc-desc">${esc(r.description || '')}</div>
          <div class="lc-meta">
            <span class="lc-diff">${esc(r.difficulty || '')}</span>
            ${r.duration_minutes ? '<span>' + Math.round(r.duration_minutes / 60) + 'h</span>' : ''}
            ${r.rating ? '<span>⭐ ' + fmt(r.rating) + '</span>' : ''}
            <span class="lc-skill">${esc(r.skill_name || '')}</span>
          </div>
        </a>
      `).join('');
    } catch { list.innerHTML = '<div class="sih-empty">Could not load resources.</div>'; }
  }

  async function loadRecommended() {
    if (!recList || !getToken()) return;
    try {
      const data = await api('/v1/learning-resources/recommended');
      if (!data || !data.length) { recList.innerHTML = ''; return; }
      recList.innerHTML = '<h3>Recommended For You</h3>' + data.map(r => `
        <a href="${esc(r.url || '#')}" target="_blank" rel="noopener" class="learning-card rec">
          <div class="lc-head">
            <div class="lc-title">${esc(r.title || '')}</div>
            <span class="lc-rec-for">For: ${esc(r.recommended_for || '')}</span>
          </div>
          <div class="lc-meta">
            <span>${esc(r.provider || '')}</span>
            <span class="lc-diff">${esc(r.difficulty || '')}</span>
            ${r.rating ? '<span>⭐ ' + fmt(r.rating) + '</span>' : ''}
          </div>
        </a>
      `).join('');
    } catch { recList.innerHTML = ''; }
  }

  searchInput?.addEventListener('input', loadResources);
  catFilter?.addEventListener('change', loadResources);

  loadResources();
  loadRecommended();
}

/* ──────────────────────────────────────────────────────────────────
   7. ASSESSMENT PAGE
   ────────────────────────────────────────────────────────────────── */
export function initAssessments() {
  const root = document.getElementById('page-assessments');
  if (!root || root.dataset.init) return;
  root.dataset.init = '1';

  const list = el('assess-list');

  async function load() {
    if (!list) return;
    list.innerHTML = '<div class="sih-loading">Loading assessments…</div>';
    try {
      const data = await api('/v1/assessments');
      const items = data.items || data || [];
      if (!items.length) { list.innerHTML = '<div class="sih-empty">No assessments available yet.</div>'; return; }
      list.innerHTML = items.map(a => `
        <div class="assess-card">
          <div class="ac-head">
            <div class="ac-title">${esc(a.title || '')}</div>
            <span class="ac-skill">${esc(a.skill_name || '')}</span>
          </div>
          <div class="ac-desc">${esc(a.description || '')}</div>
          <div class="ac-meta">
            <span>${a.question_count || 0} questions</span>
            <span>${a.time_limit_minutes || '—'} min</span>
          </div>
          <button class="btn primary sm assess-start" data-id="${esc(a.id)}">Start Assessment</button>
        </div>
      `).join('');

      list.querySelectorAll('.assess-start').forEach(btn => {
        btn.addEventListener('click', () => startAssessment(btn.dataset.id));
      });
    } catch { list.innerHTML = '<div class="sih-empty">Could not load assessments.</div>'; }
  }

  async function startAssessment(id) {
    if (!requireLogin()) return;
    try {
      const data = await api('/v1/assessments/' + id + '/start', { method: 'POST' });
      renderQuiz(id, data);
    } catch (e) { alert(e.message); }
  }

  function renderQuiz(assessId, data) {
    if (!list || !data) return;
    const questions = data.questions || [];
    const attemptId = data.attempt_id;
    let current = 0;
    const answers = {};

    function render() {
      if (current >= questions.length) { submitQuiz(assessId, attemptId, answers); return; }
      const q = questions[current];
      list.innerHTML = `
        <div class="quiz-progress">Question ${current + 1} of ${questions.length}</div>
        <div class="quiz-question">${esc(q.question_text || q.text || '')}</div>
        <div class="quiz-options">
          ${(q.options || []).map((o, i) => `
            <button class="quiz-opt ${answers[q.id] === o.id ? 'selected' : ''}" data-qid="${esc(q.id)}" data-oid="${esc(o.id)}">${esc(o.text || o.option_text || '')}</button>
          `).join('')}
        </div>
        <div class="quiz-nav">
          <button class="btn ghost" id="quiz-prev" ${current === 0 ? 'disabled' : ''}>← Previous</button>
          <button class="btn primary" id="quiz-next">${current === questions.length - 1 ? 'Submit' : 'Next →'}</button>
        </div>
      `;
      list.querySelectorAll('.quiz-opt').forEach(btn => {
        btn.addEventListener('click', () => {
          answers[btn.dataset.qid] = btn.dataset.oid;
          list.querySelectorAll('.quiz-opt').forEach(b => b.classList.remove('selected'));
          btn.classList.add('selected');
        });
      });
      el('quiz-prev')?.addEventListener('click', () => { if (current > 0) { current--; render(); } });
      el('quiz-next')?.addEventListener('click', () => { current++; render(); });
    }
    render();
  }

  async function submitQuiz(assessId, attemptId, answers) {
    if (!list) return;
    try {
      const responses = Object.entries(answers).map(([qid, oid]) => ({ question_id: qid, selected_option_id: oid }));
      const data = await api('/v1/assessments/' + assessId + '/submit', { method: 'POST', body: JSON.stringify({ attempt_id: attemptId, responses }) });
      list.innerHTML = `
        <div class="quiz-result">
          <div class="qr-score">Score: ${fmt(data.score)} / ${data.total || '—'}</div>
          <div class="qr-percent">${pct(data.percentage)}</div>
          ${data.passed ? '<div class="qr-pass">✅ Passed!</div>' : '<div class="qr-fail">Keep practicing!</div>'}
          <button class="btn primary" onclick="location.reload()">Back to Assessments</button>
        </div>
      `;
    } catch (e) { list.innerHTML = '<div class="sih-empty">Submit failed: ' + esc(e.message) + '</div>'; }
  }

  load();
}

/* ──────────────────────────────────────────────────────────────────
   8. NOTIFICATION BADGE UPDATER
   ────────────────────────────────────────────────────────────────── */
export async function updateNotifBadge() {
  if (!getToken()) return;
  try {
    const data = await api('/v1/notifications/unread-count');
    const badge = el('notif-badge');
    if (badge) {
      const c = data.count || 0;
      badge.textContent = c;
      badge.style.display = c > 0 ? '' : 'none';
    }
  } catch {}
}

/* ──────────────────────────────────────────────────────────────────
   INIT ALL
   ────────────────────────────────────────────────────────────────── */
export function initSIH() {
  initSkills();
  initOpportunities();
  initInternships();
  initPortfolio();
  initAnalytics();
  initLearning();
  initAssessments();
  updateNotifBadge();
  setInterval(updateNotifBadge, 60000);
}

window.initSIH = initSIH;
