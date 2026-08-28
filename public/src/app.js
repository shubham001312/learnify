import { onReady, openModal, getToken, getUser, setLang, getLang } from './utils.js?v=24';
import { applyLanguage } from './i18n.js?v=24';
import { initNotifications, addNotification } from './notifications.js?v=24';

window.addNotification = addNotification;
import { initAuth, openLogin } from './auth.js?v=24';
import { initVeda } from './veda.js?v=24';
import { initCareer } from './career.js?v=24';
import { initCareers } from './careers.js?v=24';
import { initProfile } from './profile.js?v=24';
import { initPremium } from './premium.js?v=24';
import { api, el, toast, esc } from './utils.js?v=24';
import { playClick } from './sound.js?v=24';
import { initStudyTools } from './tools.js?v=24';

function switchTab(tab) {
  document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
  const pane = document.getElementById('tab-' + tab);
  if (pane) pane.classList.add('active');
  document.querySelectorAll('.tbtn').forEach((b) => b.classList.remove('active'));
  const btn = document.querySelector('.tbtn[data-tab="' + tab + '"]');
  if (btn) btn.classList.add('active');
  const footer = document.querySelector('.foot');
  if (footer) footer.style.display = (tab === 'veda') ? 'none' : '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (tab === 'home') { renderHero(); loadHomeSuggestions(); }
  if (tab === 'career' && window.loadCareers) window.loadCareers();
}

function renderHero() {
  const user = (typeof getUser === 'function' && getUser()) || {};
  const prof = (typeof window !== 'undefined' && window.learnifyProfile) || {};
  const merged = Object.assign({}, prof, user);
  const name = (merged.name && merged.name !== 'Student') ? merged.name.split(' ')[0] : 'Student';
  const h = new Date().getHours();
  let greet, emoji, wish;
  if (h < 12) { greet = 'Good morning'; emoji = '🌅'; wish = "Hope you slept well — let's make today count."; }
  else if (h < 17) { greet = 'Good afternoon'; emoji = '☀️'; wish = "Hope your day is going great so far."; }
  else if (h < 21) { greet = 'Good evening'; emoji = '🌆'; wish = "A little focused study now goes a long way."; }
  else { greet = 'Good night'; emoji = '🌙'; wish = "Late grind? Remember to rest too."; }

  const t = ((merged.target_exam || '') + ' ' + (merged.board || '') + ' ' + (merged.stream || '')).toLowerCase();
  let personal = '';
  if (t.includes('jee')) personal = "Your JEE journey is the focus — small daily wins add up.";
  else if (t.includes('neet')) personal = "NEET needs consistency — you've got this.";
  else if (t.includes('cet') || t.includes('cat') || t.includes('ca ')) personal = "Keep your exam prep steady — we're here to help.";
  else if (merged.premium) personal = "Welcome back, Pro — your AI toolkit is ready.";
  else if (merged.career_goal) personal = "Still aiming for " + merged.career_goal + "? Let's keep moving.";
  else if (merged.grade) personal = "You're in " + merged.grade + " — share your goals with Veda for sharper help.";
  else personal = "Tell Veda your goals for sharper, personal help.";

  const g = el('hero-greet'); if (g) g.textContent = greet + ' ' + emoji;
  const n = el('home-name'); if (n) n.textContent = name;
  const p = el('home-personal'); if (p) p.textContent = wish + ' ' + personal;
}
window.renderHero = renderHero;

function loadHomeSuggestions() {
  const box = el('home-slots');
  if (!box) return;
  if (box.dataset.loaded === '1') return; // session guard
  const user = (typeof getUser === 'function' && getUser()) || {};
  const uid = user.id || 'demo';
  const day = new Date().toISOString().slice(0, 10);
  // App version is embedded in the module URL (?v=NN) and bumps on every deploy,
  // so a new deployment automatically invalidates the cached suggestions.
  const src = (document.querySelector('script[type="module"][src*="src/app.js"]') || {}).src || '';
  const m = src.match(/v=(\d+)/);
  const version = m ? m[1] : '0';
  const cacheKey = 'learnify_home_' + uid + '_' + day + '_v' + version;

  function render(slots) {
    if (!slots || !slots.length) { box.innerHTML = '<div class="slot-skeleton">No suggestions right now.</div>'; return; }
    box.dataset.loaded = '1';
    box.innerHTML = slots.map((s) => {
      const go = s.cta_go || 'veda';
      const arg = (s.cta_arg || '').replace(/"/g, '');
      return '<button class="slot" data-go="' + esc(go) + '"' + (arg ? ' data-arg="' + esc(arg) + '"' : '') + '">' +
        '<div class="slot-ic">' + (s.icon || '✨') + '</div>' +
        '<div class="slot-body"><div class="slot-title">' + esc(s.title || '') + '</div>' +
        '<div class="slot-text">' + esc(s.text || '') + '</div>' +
        '<div class="slot-cta">' + esc(s.cta_label || 'Explore') + ' →</div></div></button>';
    }).join('');
    box.querySelectorAll('.slot').forEach((b) => {
      b.addEventListener('click', () => {
        const go = b.dataset.go;
        const arg = b.dataset.arg;
        if (go === 'career' && arg) openCareer(arg);
        else if (go === 'college') setView('college', true);
        else if (go === 'career') setView('career', true);
        else if (go === 'scholarships') setView('scholarships', true);
        else if (go === 'planner') setView('planner', true);
        else if (go === 'quiz') setView('quiz', true);
        else if (window.askVeda) window.askVeda(arg || '');
        else setView('veda', true);
      });
    });
  }

  // Serve from a per-user daily cache (auto-invalidates when a new version deploys)
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) { render(JSON.parse(cached)); return; }
  } catch (_) {}

  box.innerHTML = '<div class="slot-skeleton">Veda is preparing your personalized suggestions…</div>';
  api('/veda/home-suggestions', { method: 'POST', body: JSON.stringify({ user_id: uid, language: getLang() || 'English' }) })
    .then((d) => {
      const slots = (d && d.slots) || [];
      try { localStorage.setItem(cacheKey, JSON.stringify(slots)); } catch (_) {}
      render(slots);
    })
    .catch(() => {
      try { const stale = localStorage.getItem(cacheKey); if (stale) { render(JSON.parse(stale)); return; } } catch (_) {}
      box.innerHTML = '<div class="slot-skeleton">Could not load suggestions. Try again later.</div>';
    });
}

function openPage(name) {
  const p = document.querySelector('.fullpage[data-page="' + name + '"]');
  if (!p) return;
  document.querySelectorAll('.fullpage').forEach((x) => x.classList.remove('open'));
  p.classList.add('open');
  if (name === 'resume') { ensureResumeRows(); renderResume(); }
  if (name === 'planner') { if (window.loadPlan) loadPlan(); }
  if (name === 'scholarships') { if (window.loadScholarships) loadScholarships(); }
  p.scrollTop = 0;
}
function closePage() {
  document.querySelectorAll('.fullpage').forEach((x) => x.classList.remove('open'));
}

/* ── Global scroll lock: lock background whenever any overlay is open ── */
function _syncScrollLock() {
  const overlay = document.querySelector('.fullpage.open, .modal.open');
  document.documentElement.classList.toggle('no-scroll', !!overlay);
}
const _lockObs = new MutationObserver(_syncScrollLock);
_lockObs.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['class'] });
_syncScrollLock();

/* ── Persistent, history-aware navigation ──
   Tabs and full-page tools are tracked in the URL hash + localStorage so a
   reload restores the last view, and the browser Back/Forward buttons move
   within the app instead of leaving it. */
const _TABS = ['home', 'veda', 'college', 'career', 'profile'];
const _PAGES = ['resume', 'planner', 'scholarships', 'quiz', 'timer', 'notes', 'summarizer', 'about', 'blog', 'privacy', 'terms', 'career-detail'];

function _savedTab() {
  try { return localStorage.getItem('learnify_tab'); } catch (e) { return null; }
}
function applyView(name) {
  if (_PAGES.includes(name)) openPage(name);
  else if (_TABS.includes(name)) switchTab(name);
  else if (name) switchTab(name);
}
function setView(name, push = true) {
  if (!name) return;
  if (_TABS.includes(name)) closePage();
  const prev = (location.hash || '').replace(/^#/, '');
  applyView(name);
  const h = '#' + name;
  try {
    if (push) { if (prev !== name) history.pushState({ view: name }, '', h); }
    else history.replaceState({ view: name }, '', h);
  } catch (e) { /* ignore */ }
  if (_TABS.includes(name)) {
    try { localStorage.setItem('learnify_tab', name); } catch (e) { /* ignore */ }
  }
}
function _restoreView() {
  const hash = (location.hash || '').replace(/^#/, '');
  const view = (hash && (_TABS.includes(hash) || _PAGES.includes(hash)))
    ? hash
    : (_savedTab() && _TABS.includes(_savedTab()) ? _savedTab() : 'home');
  setView(view, false);
}
window.addEventListener('popstate', () => {
  const v = (location.hash || '').replace(/^#/, '');
  if (_PAGES.includes(v)) openPage(v);
  else {
    closePage();
    const t = _TABS.includes(v) ? v : (_savedTab() && _TABS.includes(_savedTab()) ? _savedTab() : 'home');
    switchTab(t);
  }
});
function extractJson(s) {
  if (!s) return null;
  s = s.trim();
  if (s.startsWith('```')) s = s.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '');
  const a = s.indexOf('{'), b = s.lastIndexOf('}');
  if (a === -1 || b === -1) return null;
  try { return JSON.parse(s.slice(a, b + 1)); } catch (_) { return null; }
}
function printArea(node) {
  if (!node) return;
  document.body.classList.add('printing');
  node.classList.add('print-target');
  const cleanup = () => {
    document.body.classList.remove('printing');
    node.classList.remove('print-target');
    window.removeEventListener('afterprint', cleanup);
  };
  window.addEventListener('afterprint', cleanup);
  window.print();
}

function initTools() {
  document.querySelectorAll('[data-tool]').forEach((b) => {
    b.addEventListener('click', () => {
      const t = b.dataset.tool;
      if (t === 'planner' || t === 'resume' || t === 'scholarships') { setView(t, true); return; }
      openModal(t + '-modal');
    });
  });
  document.querySelectorAll('[data-page-close]').forEach((b) => {
    b.addEventListener('click', () => {
      if ((location.hash || '').replace(/^#/, '') && _PAGES.includes((location.hash || '').replace(/^#/, ''))) history.back();
      else closePage();
    });
  });
  document.querySelectorAll('[data-go]').forEach((b) => {
    b.addEventListener('click', () => setView(b.dataset.go, true));
  });
  document.querySelectorAll('.tbtn').forEach((b) => {
    b.addEventListener('click', () => setView(b.dataset.tab, true));
  });

  const avatar = el('top-avatar');
  if (avatar) avatar.addEventListener('click', () => {
    if (getToken()) setView('profile', true);
    else openLogin();
  });

  document.querySelectorAll('.lang').forEach((l) => {
      l.addEventListener('click', () => {
        const lang = l.dataset.lang || l.textContent.trim();
        setLang(lang);
        document.querySelectorAll('.lang').forEach((x) =>
          x.classList.toggle('active', (x.dataset.lang || x.textContent.trim()) === lang));
        const pl = el('profile-lang');
        if (pl) pl.value = lang;
        applyLanguage(lang);
        toast('Language set to ' + lang, 'ok');
      });
  });
}

function initWriting() {
  const go = el('writing-go');
  if (!go) return;
  go.addEventListener('click', () => {
    const text = el('writing-input').value.trim();
    const mode = el('writing-mode').value;
    if (!text) { toast('Enter some text first.', 'info'); return; }
    if (!getToken()) { toast('Login to use the Writing Enhancer.', 'info'); openLogin(); return; }
    const out = el('writing-out');
    out.style.display = 'block';
    out.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    api('/veda/chat', {
      method: 'POST',
      body: JSON.stringify({
        user_id: (getUser() && getUser().email) || 'demo',
        messages: [{ role: 'user', content: mode + ':\n' + text }]
      })
    }).then((d) => {
      out.textContent = (d && d.reply) || 'No response.';
    }).catch((e) => { out.textContent = '⚠️ ' + e.message; });
  });
}

function initCalculator() {
  const screen = el('calc-screen');
  if (!screen) return;
  let expr = '';
  const render = () => { screen.textContent = expr || '0'; };
  document.querySelectorAll('.calc-btn').forEach((b) => {
    b.addEventListener('click', () => {
      playClick();
      const k = b.dataset.k;
      if (k === 'C') expr = '';
      else if (k === '⌫') expr = expr.slice(0, -1);
      else if (k === '=') {
        try { expr = String(Function('"use strict";return (' + expr.replace(/[×÷]/g, m => m === '×' ? '*' : '/') + ')')()); }
        catch (_) { expr = 'Error'; }
      } else expr += k;
      render();
    });
  });

  const convGo = el('conv-go');
  if (convGo) convGo.addEventListener('click', () => {
    const val = parseFloat(el('conv-val').value);
    const from = el('conv-from').value, to = el('conv-to').value;
    const factors = { km: 1000, m: 1, cm: 0.01, mi: 1609.34, kg: 1000, g: 1, lb: 453.592 };
    if (isNaN(val)) { el('conv-out').textContent = 'Enter a value'; return; }
    const meters = val * (factors[from] / factors[to]);
    el('conv-out').textContent = val + ' ' + from + ' = ' + meters.toFixed(4) + ' ' + to;
  });
}

function initResume() {
  const preview = el('r-preview');
  if (!preview) return;

  function addEdu(data) {
    data = data || {};
    const row = document.createElement('div');
    row.className = 'dyn-row';
    row.innerHTML =
      '<input class="edu-school" placeholder="School / University" value="' + esc(data.school || '') + '">' +
      '<input class="edu-degree" placeholder="Degree / Course" value="' + esc(data.degree || '') + '">' +
      '<input class="edu-year" placeholder="Year" value="' + esc(data.year || '') + '">' +
      '<input class="edu-detail" placeholder="Detail (optional)" value="' + esc(data.detail || '') + '">' +
      '<button class="rf-del" title="Remove">×</button>';
    row.querySelector('.rf-del').addEventListener('click', () => { row.remove(); renderResume(); });
    row.querySelectorAll('input').forEach((i) => i.addEventListener('input', renderResume));
    el('r-edu-list').appendChild(row);
  }
  function addExp(data) {
    data = data || {};
    const row = document.createElement('div');
    row.className = 'dyn-row';
    row.innerHTML =
      '<input class="exp-role" placeholder="Role / Project" value="' + esc(data.role || '') + '">' +
      '<input class="exp-org" placeholder="Organisation" value="' + esc(data.org || '') + '">' +
      '<input class="exp-period" placeholder="Period" value="' + esc(data.period || '') + '">' +
      '<textarea class="exp-bullets" rows="2" placeholder="Bullet points (one per line)">' + esc((data.bullets || []).join('\n')) + '</textarea>' +
      '<button class="rf-del" title="Remove">×</button>';
    row.querySelector('.rf-del').addEventListener('click', () => { row.remove(); renderResume(); });
    row.querySelectorAll('input,textarea').forEach((i) => i.addEventListener('input', renderResume));
    el('r-exp-list').appendChild(row);
  }
  window.addEdu = addEdu;
  window.addExp = addExp;

  el('r-add-edu').addEventListener('click', () => addEdu());
  el('r-add-exp').addEventListener('click', () => addExp());

  function ensureResumeRows() {
    if (!el('r-edu-list').children.length) addEdu();
    if (!el('r-exp-list').children.length) addExp();
  }
  window.ensureResumeRows = ensureResumeRows;

  function renderResume() {
    const t = (el('r-template').value) || 'modern';
    preview.className = 'resume tpl-' + t;
    const name = el('r-name').value.trim() || 'Your Name';
    const title = el('r-title').value.trim();
    const email = el('r-email').value.trim();
    const phone = el('r-phone').value.trim();
    const loc = el('r-location').value.trim();
    const links = el('r-links').value.trim();
    const summary = el('r-summary').value.trim();
    const skills = el('r-skills').value.trim();
    const certs = el('r-certs').value.trim();

    const edu = Array.from(el('r-edu-list').children).map((r) => ({
      school: r.querySelector('.edu-school').value.trim(),
      degree: r.querySelector('.edu-degree').value.trim(),
      year: r.querySelector('.edu-year').value.trim(),
      detail: r.querySelector('.edu-detail').value.trim()
    })).filter((e) => e.school || e.degree);
    const exp = Array.from(el('r-exp-list').children).map((r) => ({
      role: r.querySelector('.exp-role').value.trim(),
      org: r.querySelector('.exp-org').value.trim(),
      period: r.querySelector('.exp-period').value.trim(),
      bullets: r.querySelector('.exp-bullets').value.split('\n').map((s) => s.trim()).filter(Boolean)
    })).filter((e) => e.role || e.org);

    let h = '<div class="r-hd"><h1>' + esc(name) + '</h1>'
      + (title ? '<div class="r-tt">' + esc(title) + '</div>' : '')
      + '<div class="r-ct">';
    [email, phone, loc, links].filter(Boolean).forEach((c) => { h += '<span>' + esc(c) + '</span>'; });
    h += '</div></div>';

    if (summary) h += '<div class="r-sec"><h2>Summary</h2><p>' + esc(summary) + '</p></div>';

    if (edu.length) {
      h += '<div class="r-sec"><h2>Education</h2>';
      edu.forEach((e) => {
        h += '<div class="r-item"><div class="r-l"><b>' + esc(e.school || e.degree) + '</b>'
          + (e.degree && e.school ? ' <span>' + esc(e.degree) + '</span>' : '') + '</div>'
          + (e.year ? '<div class="r-r">' + esc(e.year) + '</div>' : '')
          + (e.detail ? '<p>' + esc(e.detail) + '</p>' : '') + '</div>';
      });
      h += '</div>';
    }
    if (exp.length) {
      h += '<div class="r-sec"><h2>Experience</h2>';
      exp.forEach((e) => {
        h += '<div class="r-item"><div class="r-l"><b>' + esc(e.role || e.org) + '</b>'
          + (e.org && e.role ? ' <span>' + esc(e.org) + '</span>' : '') + '</div>'
          + (e.period ? '<div class="r-r">' + esc(e.period) + '</div>' : '');
        if (e.bullets.length) h += '<ul>' + e.bullets.map((b) => '<li>' + esc(b) + '</li>').join('') + '</ul>';
        h += '</div>';
      });
      h += '</div>';
    }
    if (skills) {
      h += '<div class="r-sec"><h2>Skills</h2><p class="r-tags">'
        + esc(skills).split(',').map((s) => '<span>' + esc(s.trim()) + '</span>').join('') + '</p></div>';
    }
    if (certs) h += '<div class="r-sec"><h2>Certifications</h2><p>' + esc(certs) + '</p></div>';
    preview.innerHTML = h;
  }
  window.renderResume = renderResume;

  document.querySelectorAll('.resume-form input, .resume-form textarea, #r-template').forEach((i) => {
    i.addEventListener('input', renderResume);
  });

  el('r-pdf').addEventListener('click', () => printArea(preview));

  el('r-ai').addEventListener('click', async () => {
    if (!getToken()) { toast('Login to use AI Polish.', 'info'); openLogin(); return; }
    const summary = el('r-summary').value.trim();
    const exp = Array.from(el('r-exp-list').children).map((r) => ({
      role: r.querySelector('.exp-role').value.trim(),
      org: r.querySelector('.exp-org').value.trim(),
      bullets: r.querySelector('.exp-bullets').value.split('\n').map((s) => s.trim()).filter(Boolean)
    })).filter((e) => e.role || e.bullets.length);
    if (!summary && !exp.length) { toast('Add a summary or experience first.', 'info'); return; }
    const btn = el('r-ai');
    btn.disabled = true; btn.textContent = 'Polishing…';
    const prompt = 'You are an expert resume writer for Indian students. Improve the content to be concise, impactful and ATS-friendly. Use strong action verbs and quantify achievements where implied. Return ONLY valid JSON (no markdown fences) in this exact shape:\n{\n "summary": string,\n "experience": [ { "bullets": string[] } ]\n}\nProvide one experience object per input entry, in the same order. Do not alter names, roles or orgs.\n\nINPUT SUMMARY: ' + summary + '\n\nINPUT EXPERIENCE: ' + JSON.stringify(exp.map((e) => ({ role: e.role, org: e.org, bullets: e.bullets })));
    try {
      const d = await api('/veda/chat', {
        method: 'POST',
        body: JSON.stringify({ user_id: (getUser() && getUser().email) || 'demo', messages: [{ role: 'user', content: prompt }], mode: 'chat', language: 'English', return_json: true })
      });
      const json = extractJson((d && d.reply) || '');
      if (json && json.summary !== undefined) {
        el('r-summary').value = json.summary;
        if (Array.isArray(json.experience)) {
          const rows = el('r-exp-list').children;
          json.experience.forEach((ex, i) => {
            if (rows[i] && Array.isArray(ex.bullets)) rows[i].querySelector('.exp-bullets').value = ex.bullets.join('\n');
          });
        }
        renderResume();
        toast('Resume polished with AI', 'ok');
      } else {
        toast('AI returned an unexpected format.', 'info');
      }
    } catch (e) {
      toast('AI polish failed: ' + e.message, 'info');
    } finally {
      btn.disabled = false; btn.textContent = 'AI Polish';
    }
  });
}

function initPlanner() {
  const preview = el('pl-preview');
  if (!preview) return;
  const KEY = 'learnify_plan';

  function addSubject(data) {
    data = data || {};
    const row = document.createElement('div');
    row.className = 'subj-row';
    const prio = data.prio || 3;
    row.innerHTML =
      '<input class="pl-sub-name" placeholder="Subject" value="' + esc(data.name || '') + '">' +
      '<select class="pl-sub-prio" title="Priority">' +
      [1, 2, 3, 4, 5].map((p) => '<option value="' + p + '"' + (p == prio ? ' selected' : '') + '>P' + p + '</option>').join('') +
      '</select>' +
      '<div class="pl-lv"><label>Lvl</label><input type="number" class="pl-sub-level" min="0" max="100" value="' + (data.level != null ? data.level : 50) + '"></div>' +
      '<div class="pl-lv"><label>Tgt</label><input type="number" class="pl-sub-target" min="0" max="100" value="' + (data.target != null ? data.target : 90) + '"></div>' +
      '<button class="rf-del" title="Remove">×</button>';
    row.querySelector('.rf-del').addEventListener('click', () => row.remove());
    el('pl-subjects').appendChild(row);
  }
  window.addSubject = addSubject;

  el('pl-add-subject').addEventListener('click', () => addSubject());

  function readSubjects() {
    return Array.from(el('pl-subjects').children).map((r) => ({
      name: r.querySelector('.pl-sub-name').value.trim(),
      prio: parseInt(r.querySelector('.pl-sub-prio').value, 10) || 3,
      level: Math.max(0, Math.min(100, parseInt(r.querySelector('.pl-sub-level').value, 10) || 0)),
      target: Math.max(0, Math.min(100, parseInt(r.querySelector('.pl-sub-target').value, 10) || 0))
    })).filter((s) => s.name);
  }

  function updateCountdown() {
    const exam = el('pl-exam').value;
    const cd = el('pl-countdown');
    if (!exam) { cd.textContent = '—'; cd.className = 'pl-countdown'; return; }
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const end = new Date(exam + 'T00:00:00');
    const days = Math.round((end - today) / 86400000);
    if (days < 0) { cd.textContent = 'Exam date passed'; cd.className = 'pl-countdown overdue'; }
    else if (days === 0) { cd.textContent = 'Exam is today!'; cd.className = 'pl-countdown urgent'; }
    else { cd.textContent = days + ' days left'; cd.className = 'pl-countdown ' + (days <= 14 ? 'urgent' : ''); }
  }
  el('pl-exam').addEventListener('change', updateCountdown);

  function ensureSubjectRows() {
    if (!el('pl-subjects').children.length) {
      addSubject({ name: 'Mathematics', prio: 5, level: 55, target: 90 });
      addSubject({ name: 'Physics', prio: 4, level: 50, target: 85 });
      addSubject({ name: 'Chemistry', prio: 3, level: 60, target: 85 });
    }
  }
  window.ensureSubjectRows = ensureSubjectRows;

  function loadPlan() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) { ensureSubjectRows(); updateCountdown(); return; }
      const p = JSON.parse(raw);
      if (p.exam) el('pl-exam').value = p.exam;
      if (p.hours) el('pl-hours').value = p.hours;
      if (p.brk != null) el('pl-break').value = p.brk;
      if (typeof p.revision === 'boolean') el('pl-revision').checked = p.revision;
      if (Array.isArray(p.subjects) && p.subjects.length) {
        el('pl-subjects').innerHTML = '';
        p.subjects.forEach(addSubject);
      } else ensureSubjectRows();
      updateCountdown();
    } catch (_) { ensureSubjectRows(); }
  }
  window.loadPlan = loadPlan;

  el('pl-save').addEventListener('click', () => {
    const p = {
      exam: el('pl-exam').value,
      hours: el('pl-hours').value,
      brk: el('pl-break').value,
      revision: el('pl-revision').checked,
      subjects: readSubjects()
    };
    try { localStorage.setItem(KEY, JSON.stringify(p)); toast('Plan saved', 'ok'); }
    catch (_) { toast('Could not save plan', 'info'); }
  });

  el('pl-build').addEventListener('click', () => {
    const subs = readSubjects();
    const exam = el('pl-exam').value;
    const hours = parseInt(el('pl-hours').value, 10) || 3;
    const brk = parseInt(el('pl-break').value, 10) || 0;
    const rev = el('pl-revision').checked;
    if (!subs.length) { toast('Add at least one subject.', 'info'); return; }
    if (!exam) { toast('Pick an exam date.', 'info'); return; }

    const today = new Date(); today.setHours(0, 0, 0, 0);
    const end = new Date(exam + 'T00:00:00');
    const days = Math.round((end - today) / 86400000);
    if (days < 1) { toast('Exam date must be in the future.', 'info'); return; }

    const totalHours = days * hours;
    const weights = subs.map((s) => Math.max(0.1, s.prio * (1 + (s.target - s.level) / 100)));
    const sumW = weights.reduce((a, b) => a + b, 0);
    const alloc = subs.map((s, i) => ({
      ...s,
      hrs: Math.round((weights[i] / sumW) * totalHours * 10) / 10
    }));

    const rotation = [];
    alloc.forEach((s, i) => { const n = Math.max(1, Math.round(weights[i])); for (let k = 0; k < n; k++) rotation.push(s.name); });
    if (!rotation.length) rotation.push(subs[0].name);

    let html = '<div class="pl-stats">'
      + '<div class="pl-stat"><b>' + days + '</b><span>days to exam</span></div>'
      + '<div class="pl-stat"><b>' + hours + 'h</b><span>per day</span></div>'
      + '<div class="pl-stat"><b>' + totalHours + '</b><span>total hours</span></div>'
      + '<div class="pl-stat"><b>' + subs.length + '</b><span>subjects</span></div>'
      + '</div>';

    html += '<div class="pl-alloc">';
    alloc.forEach((s) => {
      const gap = Math.max(0, s.target - s.level);
      html += '<div class="pl-alloc-row"><div class="pl-alloc-top"><b>' + esc(s.name) + '</b><span>P' + s.prio + ' · ' + s.hrs + 'h</span></div>'
        + '<div class="pl-bar"><div class="pl-bar-fill" style="width:' + s.level + '%"></div><div class="pl-bar-tgt" style="left:' + s.target + '%"></div></div>'
        + '<div class="pl-alloc-meta">Level ' + s.level + ' → Target ' + s.target + ' (' + gap + ' pts gap)</div></div>';
    });
    html += '</div>';

    html += '<div class="pl-week-head">📅 Day-by-day timetable</div>';
    let week = 0;
    for (let i = 0; i < days; i++) {
      const d = new Date(today); d.setDate(d.getDate() + i);
      const dow = d.getDay();
      const isRev = rev && dow === 0;
      const subj = isRev ? 'Revision & Mock Test' : rotation[i % rotation.length];
      if (dow === 1 || i === 0) { html += '<div class="pl-week">Week ' + (++week) + '</div>'; }
      const sessions = isRev ? 'Full-length mock + error analysis' : (hours + 'h focused · ' + (brk ? brk + 'm breaks' : 'steady pace'));
      html += '<div class="pl-day"><span class="pl-date">' + d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }) +
        '</span><span class="pl-sub' + (isRev ? ' rev' : '') + '">' + esc(subj) + '</span><span class="pl-h">' + esc(sessions) + '</span></div>';
    }
    preview.innerHTML = html;
    preview.style.display = 'block';
    if (window.addNotification) window.addNotification('Study plan ready — ' + days + ' days, ' + totalHours + ' hours scheduled.', 'plan');
  });

  el('pl-pdf').addEventListener('click', () => {
    if (!preview.innerHTML.trim()) { toast('Generate a plan first.', 'info'); return; }
    printArea(preview);
  });
}

function initScholarships() {
  const listEl = el('sch-list');
  if (!listEl) return;
  const searchEl = el('sch-search');
  const stateEl = el('sch-state');
  const collegeEl = el('sch-college');
  const tabsEl = el('sch-tabs');
  const summaryEl = el('sch-summary');
  const matchedEl = el('sch-matched');
  const chipsEl = el('sch-chips');
  let ALL = [];

  let cat = 'All';
  let q = '';
  let state = '';
  let college = '';
  let collegeState = '';
  const NE_STATES = ['assam', 'arunachal pradesh', 'manipur', 'meghalaya', 'mizoram', 'nagaland', 'tripura', 'sikkim'];

  function isApplicable(s, lc, cs) {
    const cols = s.colleges || [];
    if (cols.includes('All')) {
      const st = (s.state || '').toLowerCase();
      if (st === 'central' || st === 'all india') return true;
      if (st === 'north east') return NE_STATES.includes(cs);
      return st === cs;
    }
    return cols.map((x) => String(x).toLowerCase()).includes(lc);
  }

  function load() {
    listEl.innerHTML = '<div class="sch-loading">Loading scholarships…</div>';
    api('/scholarships').then((d) => {
      ALL = (d && d.scholarships) || [];
      buildChips();
      renderMatched();
      populateStates();
      render();
    }).catch(() => {
      toast('Failed to load scholarships', 'info');
      listEl.innerHTML = '<div class="sch-empty">Could not load scholarships.</div>';
    });
  }
  window.loadScholarships = load;

  function matchReasons(s, u) {
    const reasons = [];
    const us = (u.state || '').toLowerCase();
    const st = (s.state || '').toLowerCase();
    if (us && (st === us || st === 'all india' || st === 'central' || (st === 'north east' && NE_STATES.includes(us)))) {
      reasons.push('for ' + (u.state || 'your state'));
    }
    const elig = ((s.eligibility || '') + ' ' + (s.name || '')).toLowerCase();
    const g = (u.gender || '').toLowerCase();
    if (g === 'female' && /girl|women|womens|female/.test(elig)) reasons.push('for girls/women');
    if (g === 'male' && /boy|men|male/.test(elig)) reasons.push('for boys/men');
    if (u.board && elig.includes(u.board.toLowerCase())) reasons.push('for ' + u.board + ' students');
    if (/(merit|topper|rank)/.test(elig)) reasons.push('merit-based');
    return reasons;
  }

  function filtered() {
    let data = ALL.slice();
    const lc = college ? college.toLowerCase() : null;
    const cs = collegeState ? collegeState.toLowerCase() : null;
    if (cat !== 'All') data = data.filter((s) => (s.category || '').toLowerCase() === cat.toLowerCase());
    if (state) data = data.filter((s) => (s.state || '').toLowerCase() === state.toLowerCase());
    if (q) {
      const qq = q.toLowerCase();
      data = data.filter((s) => ((s.name || '') + ' ' + (s.eligibility || '') + ' ' + (s.state || '') + ' ' + (s.category || '') + ' ' + (s.amount || '')).toLowerCase().includes(qq));
    }
    if (lc) data = data.filter((s) => isApplicable(s, lc, cs));
    return data;
  }

  function render() {
    const data = filtered();
    let html = '<span class="sch-count">' + data.length + ' scholarship' + (data.length === 1 ? '' : 's') + '</span>';
    if (college) html += ' <span class="sch-filter">for ' + esc(college) + '</span>';
    if (cat !== 'All') html += ' <span class="sch-filter">' + esc(cat) + '</span>';
    if (state) html += ' <span class="sch-filter">' + esc(state) + '</span>';
    if (q) html += ' <span class="sch-filter">“' + esc(q) + '”</span>';
    summaryEl.innerHTML = html;

    if (!data.length) {
      listEl.innerHTML = '<div class="sch-empty">No scholarships match your filters. Try a suggestion below.</div>';
      return;
    }

    const lc = college ? college.toLowerCase() : null;
    const cs = collegeState ? collegeState.toLowerCase() : null;
    listEl.innerHTML = data.map((s) => {
      const avail = lc ? isApplicable(s, lc, cs) : null;
      const docs = (s.documents || []).map((d) => '<span class="doc-chip">' + esc(d) + '</span>').join('');
      return '<div class="sch-card cat-' + esc(String(s.category || '').toLowerCase()) + '">'
        + '<div class="sch-top"><div class="sch-name">' + esc(s.name) + '</div>'
        + (avail === true ? '<span class="sch-badge avail">✓ At your college</span>'
            : avail === false ? '<span class="sch-badge na">Not listed for your college</span>' : '')
        + '</div>'
        + '<div class="sch-meta"><span class="tag tag-cat">' + esc(s.category || '') + '</span>'
        + '<span class="tag tag-state">' + esc(s.state || '') + '</span></div>'
        + '<div class="sch-amount"><b>' + esc(s.amount || '') + '</b></div>'
        + '<div class="sch-elig"><span>Eligibility:</span> ' + esc(s.eligibility || '') + '</div>'
        + '<div class="sch-deadline"><span>Deadline:</span> ' + esc(s.deadline || '') + '</div>'
        + (docs ? '<div class="sch-docs"><span>Documents:</span> ' + docs + '</div>' : '')
        + '</div>';
    }).join('');
    Array.from(listEl.querySelectorAll('.sch-card')).forEach((card, i) => {
      card.classList.add('clickable');
      card.addEventListener('click', () => window.openScholarshipModal(data[i]));
    });
  }

  function renderMatched() {
    if (!matchedEl) return;
    const u = getUser() || {};
    if (!u.state && !u.gender && !u.board && !u.target_exam) { matchedEl.innerHTML = ''; return; }
    const scored = [];
    ALL.forEach((s) => {
      const reasons = matchReasons(s, u);
      if (reasons.length) scored.push({ s, reasons: reasons.slice(0, 2) });
    });
    if (!scored.length) { matchedEl.innerHTML = ''; return; }
    scored.sort((a, b) => b.reasons.length - a.reasons.length);
    matchedEl.innerHTML = '<div class="sch-section-title">Matched for you</div>' +
      scored.slice(0, 4).map(({ s, reasons }) =>
        '<div class="sch-match" data-name="' + esc(s.name) + '"><div class="sch-match-name">' + esc(s.name) +
        '</div><div class="sch-match-reason">Because ' + reasons.map(esc).join(' · ') + '</div></div>'
      ).join('');
    matchedEl.querySelectorAll('.sch-match').forEach((m) => {
      m.addEventListener('click', () => {
        const s = ALL.find((x) => x.name === m.dataset.name);
        if (s) window.openScholarshipModal(s);
      });
    });
  }

  function buildChips() {
    if (!chipsEl) return;
    const u = getUser() || {};
    const chips = [];
    if (u.state) chips.push({ label: 'In ' + u.state, q: u.state });
    if ((u.gender || '').toLowerCase() === 'female') chips.push({ label: 'For girls/women', q: 'girl women' });
    if (u.board) chips.push({ label: u.board + ' students', q: u.board });
    [
      { label: 'Government', cat: 'Government' },
      { label: 'State', cat: 'State' },
      { label: 'Girls/Women', q: 'girl women' },
      { label: 'SC/ST/OBC', q: 'sc st obc' },
      { label: 'Minority', q: 'minority' },
      { label: 'Merit-based', q: 'merit' },
      { label: 'Engineering', q: 'engineering' },
    ].forEach((c) => chips.push(c));
    chipsEl.innerHTML = chips.map((c, i) => '<button class="sch-chip" data-i="' + i + '">' + esc(c.label) + '</button>').join('');
    chipsEl.querySelectorAll('.sch-chip').forEach((b) => {
      b.addEventListener('click', () => {
        const c = chips[Number(b.dataset.i)];
        q = c.q || ''; searchEl.value = q;
        if (c.cat) {
          cat = c.cat;
          tabsEl.querySelectorAll('.sch-tab').forEach((x) => x.classList.toggle('active', x.dataset.cat === cat));
        } else {
          cat = 'All';
          tabsEl.querySelectorAll('.sch-tab').forEach((x) => x.classList.toggle('active', x.dataset.cat === 'All'));
        }
        render();
        matchedEl && matchedEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });
  }
  searchEl.addEventListener('input', () => { q = searchEl.value.trim(); render(); });
  stateEl.addEventListener('change', () => { state = stateEl.value; render(); });

  tabsEl.querySelectorAll('.sch-tab').forEach((b) => b.addEventListener('click', () => {
    tabsEl.querySelectorAll('.sch-tab').forEach((x) => x.classList.remove('active'));
    b.classList.add('active');
    cat = b.dataset.cat;
    render();
  }));

  function populateStates() {
    if (!stateEl) return;
    const set = new Set();
    ALL.forEach((s) => { if (s.state) set.add(String(s.state)); });
    const opts = Array.from(set).sort((a, b) => a.localeCompare(b));
    stateEl.innerHTML = '<option value="">All states</option>' + opts.map((s) => '<option value="' + esc(s) + '">' + esc(s) + '</option>').join('');
    stateEl.value = state;
  }

  // College autocomplete (43k colleges -> type-ahead, not a dropdown)
  const suggestEl = el('sch-suggest');
  let schTimer = null;
  const collegeMap = {};
  function applyCollege(name, state) {
    college = name;
    collegeState = state || collegeMap[name] || '';
    collegeEl.value = name;
    suggestEl.innerHTML = '';
    suggestEl.style.display = 'none';
    load();
  }
  collegeEl.addEventListener('input', () => {
    const v = collegeEl.value.trim();
    clearTimeout(schTimer);
    if (v.length < 2) { suggestEl.innerHTML = ''; suggestEl.style.display = 'none'; return; }
    schTimer = setTimeout(async () => {
      try {
        const d = await api('/colleges?q=' + encodeURIComponent(v) + '&limit=12');
        const cs = (d && d.colleges) || [];
        if (!cs.length) { suggestEl.innerHTML = ''; suggestEl.style.display = 'none'; return; }
        cs.forEach((c) => { collegeMap[c.name] = c.state || ''; });
        suggestEl.innerHTML = cs.map((c) =>
          '<div class="sch-suggest-item" data-name="' + esc(c.name) + '" data-state="' + esc(c.state || '') + '">' + esc(c.name) +
          (c.state ? ' <span class="sch-suggest-state">' + esc(c.state) + '</span>' : '') + '</div>'
        ).join('');
        suggestEl.style.display = 'block';
      } catch (_) {}
    }, 250);
  });
  collegeEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const v = collegeEl.value.trim();
      applyCollege(v);
    }
  });
  suggestEl.addEventListener('click', (e) => {
    const it = e.target.closest('.sch-suggest-item');
    if (it) applyCollege(it.dataset.name, it.dataset.state);
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.sch-college-wrap')) suggestEl.style.display = 'none';
  });

  // Live web search (Google Programmable Search Engine)
  const liveQ = el('sch-live-q');
  const liveGo = el('sch-live-go');
  const liveRes = el('sch-live-results');
  const liveMeta = el('sch-live-meta');
  function runLive() {
    const q = liveQ.value.trim();
    if (!q) { toast('Type a query to search the web', 'info'); return; }
    liveRes.innerHTML = '<div class="sch-loading">Searching the web…</div>';
    api('/search?q=' + encodeURIComponent(q) + '&num=10').then((d) => {
      const meta = (d && d.meta) || {};
      if (meta.source === 'unconfigured') {
        liveMeta.textContent = 'not configured';
        liveRes.innerHTML = '<div class="sch-empty">Add GOOGLE_CSE_KEY + GOOGLE_CSE_CX in .env to enable live web search.</div>';
        return;
      }
      liveMeta.textContent = (meta.source === 'live' ? 'live' : meta.source) +
        (meta.remaining != null ? ' · ' + meta.remaining + ' queries left today' : '');
      const results = (d && d.results) || [];
      if (!results.length) { liveRes.innerHTML = '<div class="sch-empty">No live results. ' + (meta.note || '') + '</div>'; return; }
      liveRes.innerHTML = results.map((r) =>
        '<a class="sch-live-item" href="' + esc(r.link) + '" target="_blank" rel="noopener">' +
        '<div class="sch-live-title">' + esc(r.title) + '</div>' +
        '<div class="sch-live-src">' + esc(r.source || '') + '</div>' +
        '<div class="sch-live-snippet">' + esc(r.snippet || '') + '</div></a>'
      ).join('');
    }).catch(() => { liveRes.innerHTML = '<div class="sch-empty">Live search failed.</div>'; });
  }
  liveGo.addEventListener('click', runLive);
  liveQ.addEventListener('keydown', (e) => { if (e.key === 'Enter') runLive(); });

  load();
}

function initMisc() {
  const ts = document.querySelector('.top-search input');
  if (ts) ts.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const v = ts.value.trim();
      if (v) {
        const cs = el('college-search');
        if (cs) { cs.value = v; cs.dispatchEvent(new Event('input')); }
        setView('career', true);
      }
    }
  });

  const vu = el('veda-upgrade');
  if (vu) vu.addEventListener('click', (e) => { e.preventDefault(); openModal('premium-modal'); });

  const avatar = el('top-avatar');
  if (avatar) avatar.addEventListener('click', () => {
    if (getToken()) setView('profile');
    else openLogin();
  });

  const map = {
    'Resume Builder': 'resume',
    'Calculator': 'calc-modal',
    'Writing Enhancer': 'writing-modal',
    'Veda AI': 'veda',
    'College Search': 'career',
    'Career Paths': 'career',
    'Scholarships': 'scholarships',
    'Study Planner': 'planner',
  };
  document.querySelectorAll('.foot a').forEach((a) => {
    const t = a.textContent.trim();
    if (map[t]) a.addEventListener('click', (e) => {
      e.preventDefault();
      const target = map[t];
      if (target === 'resume' || target === 'planner' || target === 'scholarships') setView(target, true);
      else if (target.endsWith('-modal')) openModal(target);
      else setView(target, true);
    });
  });
}

function initSystem() {
  const banner = el('offline-banner');
  const update = () => { if (banner) banner.style.display = navigator.onLine ? 'none' : 'flex'; };
  window.addEventListener('online', update);
  window.addEventListener('offline', update);
  update();
  window.addEventListener('error', (e) => console.error('[learnify] error:', e.message));
  window.addEventListener('unhandledrejection', (e) => console.error('[learnify] promise:', e.reason));
}

const LOANS = [
  { bank: 'SBI Education Loan', rate: '8.15% p.a.', note: 'For studies in India & abroad. Moratorium = course + 1 yr.' },
  { bank: 'BoB Education Loan', rate: '8.25% p.a.', note: 'Vidya Lakshmi portal; collateral waived up to ₹7.5L.' },
  { bank: 'Canara Bank', rate: '8.0% p.a.', note: 'Interest subsidy under CSIS for income < ₹4.5L.' },
  { bank: 'HDFC Credila', rate: '9%+ p.a.', note: 'NBFC; faster disbursal, India & overseas courses.' },
];

function askVeda(prompt) {
  setView('veda', true);
  const inp = el('chat-input');
  if (inp) inp.value = prompt;
  if (typeof window.sendMessage === 'function') window.sendMessage();
}

function openModalCard(html) {
  const card = el('detail-card');
  if (card) card.innerHTML = html;
  openModal('detail-modal');
}

window.askVeda = askVeda;
window.setViewNav = setView;
window.openPage = openPage;
window.loadHomeSuggestions = loadHomeSuggestions;

function renderReviews(list) {
  if (!list || !list.length) {
    return '<div class="dm-noreviews">No reviews yet. Be the first to share your experience!</div>';
  }
  return list.map((r) => {
    const stars = '★'.repeat(Math.round(r.rating || 0)) + '☆'.repeat(5 - Math.round(r.rating || 0));
    const pros = (r.pros || '').split('|').filter(Boolean).map((x) => '<li>' + esc(x.trim()) + '</li>').join('');
    const cons = (r.cons || '').split('|').filter(Boolean).map((x) => '<li>' + esc(x.trim()) + '</li>').join('');
    return '<div class="dm-review">' +
      '<div class="dm-review-head"><b>' + esc(r.author || 'Anonymous') + '</b><span class="dm-stars">' + stars + '</span>' +
      (r.created_at ? '<small>' + esc(r.created_at) + '</small>' : '') + '</div>' +
      (r.text ? '<p>' + esc(r.text) + '</p>' : '') +
      (pros ? '<div class="dm-pc-inline"><span class="ok">✓ ' + (pros ? 'Pros' : '') + '</span><ul>' + pros + '</ul></div>' : '') +
      (cons ? '<div class="dm-pc-inline"><span class="bad">✕ ' + (cons ? 'Cons' : '') + '</span><ul>' + cons + '</ul></div>' : '') +
      '</div>';
  }).join('');
}

function openCollegeModal(c) {
  const id = c.id != null ? c.id : null;
  const type = (c.type || '').toLowerCase();
  const typeBadge = type
    ? '<span class="dm-type ' + (type === 'private' ? 'type-priv' : 'type-govt') + '">' + (type === 'private' ? 'Private' : 'Government') + '</span>'
    : '';

  const loc = c.address
    ? c.address
    : [c.district, c.city || c.location, c.state, c.pin_code].filter(Boolean).join(', ');

  let mapHtml = '';
  if (c.lat != null && c.lng != null) {
    const lat = Number(c.lat), lng = Number(c.lng), b = 0.02;
    mapHtml =
      '<div class="dm-map"><iframe loading="lazy" title="Campus map" src="https://www.openstreetmap.org/export/embed.html?bbox=' +
      (lng - b) + '%2C' + (lat - b) + '%2C' + (lng + b) + '%2C' + (lat + b) +
      '&layer=mapnik&marker=' + lat + '%2C' + lng + '"></iframe>' +
      '<a class="dm-link" href="https://www.openstreetmap.org/?mlat=' + lat + '&mlon=' + lng + '#map=15/' + lat + '/' + lng + '" target="_blank" rel="noopener">📍 Open in Maps ↗</a></div>';
  } else if (c.map_link) {
    mapHtml = '<a class="dm-link" href="' + esc(c.map_link) + '" target="_blank" rel="noopener">📍 View on map ↗</a>';
  }

  const stats = [];
  if (c.nirf_rank != null) stats.push('<div class="dm-stat"><small>NIRF ' + esc(c.nirf_year || '2024') + '</small><b>#' + esc(c.nirf_rank) + '</b></div>');
  if (c.avg_package != null) stats.push('<div class="dm-stat"><small>Avg Package</small><b style="color:var(--green)">₹' + esc(c.avg_package) + ' LPA</b></div>');
  if (c.highest_package != null) stats.push('<div class="dm-stat"><small>Highest Package</small><b style="color:var(--gold)">₹' + esc(c.highest_package) + ' LPA</b></div>');
  if (c.placement_pct != null) stats.push('<div class="dm-stat"><small>Placement</small><b>' + esc(c.placement_pct) + '%</b></div>');
  if (c.rating != null) stats.push('<div class="dm-stat"><small>Rating</small><b style="color:var(--gold)">' + esc(c.rating) + ' ★</b></div>');

  const streams = (c.streams || []).map((s) => '<span class="dm-chip">' + esc(s) + '</span>').join('');
  const recruiters = (c.top_recruiters || []).map((s) => '<span class="dm-chip rec">' + esc(s) + '</span>').join('');
  const pros = (c.pros || []).map((s) => '<li>' + esc(s) + '</li>').join('');
  const cons = (c.cons || []).map((s) => '<li>' + esc(s) + '</li>').join('');
  const tags = (c.tags || []).map((s) => '<span class="dm-chip tag">' + esc(s) + '</span>').join('');
  const schols = (c.scholarships_applicable || []).map((s) => '<span class="dm-chip sch">' + esc(s) + '</span>').join('');
  const loans = LOANS.map((l) => '<div class="dm-loan"><b>' + esc(l.bank) + '</b> · <span style="color:var(--teal)">' + esc(l.rate) + '</span><small>' + esc(l.note) + '</small></div>').join('');

  const html =
    '<div class="dm-hero">' + typeBadge + '<h2 class="dm-name">' + esc(c.name) + '</h2>' +
      '<div class="dm-sub">' + esc(c.city || c.location || '') + (c.state ? ', ' + esc(c.state) : '') + '</div>' +
      (tags ? '<div class="dm-chips">' + tags + '</div>' : '') +
    '</div>' +
    (stats.length ? '<div class="dm-stats">' + stats.join('') + '</div>' : '') +
    (loc ? '<div class="dm-sec"><h4>📍 Location</h4><p>' + esc(loc) + '</p>' +
        (c.website ? '<a class="dm-link" href="https://' + esc(c.website) + '" target="_blank" rel="noopener">🌐 Official website ↗</a>' : '') +
        (mapHtml ? mapHtml : '') + '</div>' : '') +
    ((c.affiliation || c.founded) ? '<div class="dm-sec"><h4>🏛 Affiliation & Founding</h4><p>' +
        (c.affiliation ? esc(c.affiliation) : '') +
        (c.affiliation && c.founded ? ' · ' : '') +
        (c.founded ? 'Founded ' + esc(c.founded) : '') + '</p></div>' : '') +
    (streams ? '<div class="dm-sec"><h4>🎓 Streams / Courses</h4><div class="dm-chips">' + streams + '</div></div>' : '') +
    (recruiters ? '<div class="dm-sec"><h4>🏢 Companies that visit (campus recruitment)</h4><div class="dm-chips">' + recruiters + '</div>' +
        '<p class="dm-note">Exact shortlisting & interview-eligibility criteria (CGPA, backlog rules, branches allowed) vary by company and branch. Tap “Ask Veda” for specifics.</p></div>' : '') +
    (c.description ? '<div class="dm-sec"><h4>About</h4><p>' + esc(c.description) + '</p></div>' : '') +
    ((pros || cons) ? '<div class="dm-sec"><div class="dm-pc">' +
        (pros ? '<div class="dm-pros"><h5>✓ Pros</h5><ul>' + pros + '</ul></div>' : '') +
        (cons ? '<div class="dm-cons"><h5>✕ Cons</h5><ul>' + cons + '</ul></div>' : '') +
      '</div></div>' : '') +
    (schols ? '<div class="dm-sec"><h4>Scholarships you may qualify for</h4><div class="dm-chips">' + schols + '</div>' +
        '<p class="dm-note">Eligibility depends on your category, state, and course. Open the Scholarships tab for full details, amounts, and deadlines.</p></div>' : '') +
    '<div class="dm-sec"><h4>Education Loans</h4>' + loans + '</div>' +
    '<div class="dm-sec"><h4>Student Reviews <span class="dm-live">live</span></h4>' +
        '<div id="dm-review-list"><div class="dm-noreviews">Loading reviews…</div></div>' +
        '<form id="dm-review-form" class="review-form">' +
          '<div class="rf-row"><input id="rv-author" placeholder="Your name" maxlength="60">' +
            '<select id="rv-rating"><option value="5">★★★★★</option><option value="4">★★★★☆</option><option value="3">★★★☆☆</option><option value="2">★★☆☆☆</option><option value="1">★☆☆☆☆</option></select></div>' +
          '<textarea id="rv-text" placeholder="Share your honest experience…" maxlength="2000"></textarea>' +
          '<div class="rf-row"><input id="rv-pros" placeholder="Pros (comma separated)"><input id="rv-cons" placeholder="Cons (comma separated)"></div>' +
          '<button type="submit" class="btn primary sm" id="rv-submit">Submit review</button>' +
        '</form>' +
    '</div>' +
    '<button class="btn primary block" id="dm-ask">Ask Veda about this college</button>' +
    '<button class="btn ghost block" id="dm-compare">' + (compareList.some((x) => x.id === c.id) ? '✓ Added to compare' : '➕ Add to compare') + '</button>';

  openModalCard(html);
  renderCompareBar();

  const cmp = el('dm-compare');
  if (cmp) cmp.addEventListener('click', () => toggleCompare(c));

  const ask = el('dm-ask');
  if (ask) ask.addEventListener('click', () => {
    const facts = [
      'College: ' + c.name + (c.type ? ' (' + c.type + ')' : ''),
      c.avg_package != null ? 'Average package ~₹' + c.avg_package + ' LPA' + (c.highest_package != null ? ', highest ~₹' + c.highest_package + ' LPA' : '') : null,
      'Top recruiters: ' + ((c.top_recruiters || []).slice(0, 6).join(', ') || 'n/a'),
      'Scholarships often applicable: ' + ((c.scholarships_applicable || []).slice(0, 5).join(', ') || 'n/a'),
      c.description ? 'About: ' + c.description : null,
    ].filter(Boolean).join('. ');
    askVeda(facts + '. Give a clear, practical overview: strengths, typical placement scenario, and what CGPA/backlog criteria companies usually apply for campus interviews there.');
  });

  const form = el('dm-review-form');
  const list = el('dm-review-list');
  async function loadReviews() {
    if (id == null) { list.innerHTML = '<div class="dm-noreviews">Reviews available for listed institutions.</div>'; return; }
    try {
      const d = await api('/colleges/' + id + '/reviews');
      list.innerHTML = renderReviews((d && d.reviews) || []);
    } catch (e) {
      list.innerHTML = '<div class="dm-noreviews">Could not load reviews.</div>';
    }
  }
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (id == null) { toast('Reviews available for listed institutions only.', 'info'); return; }
      const payload = {
        author: el('rv-author').value.trim() || 'Anonymous',
        rating: parseFloat(el('rv-rating').value) || 0,
        text: el('rv-text').value.trim(),
        pros: el('rv-pros').value.trim(),
        cons: el('rv-cons').value.trim(),
      };
      if (!payload.text && !payload.pros && !payload.cons) { toast('Write something before submitting.', 'info'); return; }
      const btn = el('rv-submit');
      btn.disabled = true; btn.textContent = 'Submitting…';
      try {
        await api('/colleges/' + id + '/reviews', { method: 'POST', body: JSON.stringify(payload) });
        form.reset();
        toast('Thanks! Your review is live.', 'ok');
        await loadReviews();
      } catch (err) {
        toast('Failed to submit: ' + err.message, 'info');
      } finally {
        btn.disabled = false; btn.textContent = 'Submit review';
      }
    });
  }
  loadReviews();
}

function openScholarshipModal(s) {
  const cat = String(s.category || '').toLowerCase().replace(/[^a-z]/g, '');
  const html =
    '<div class="dm-hero sch"><span class="dm-type type-' + esc(cat) + '">' + esc(s.category || '') + '</span>' +
      '<h2 class="dm-name">' + esc(s.name) + '</h2>' +
      '<div class="dm-sub">' + esc(s.state || 'All India') + (s.provider ? ' · ' + esc(s.provider) : '') + '</div>' +
    '</div>' +
    (s.amount ? '<div class="dm-amount">' + esc(s.amount) + '</div>' : '') +
    (s.provider ? '<div class="dm-sec"><h4>Provider</h4><p>' + esc(s.provider) + '</p></div>' : '') +
    (s.eligibility ? '<div class="dm-sec"><h4>Eligibility</h4><p>' + esc(s.eligibility) + '</p></div>' : '') +
    (s.deadline ? '<div class="dm-sec"><h4>Deadline</h4><p>' + esc(s.deadline) + '</p></div>' : '') +
    ((s.documents && s.documents.length) ? '<div class="dm-sec"><h4>Documents required</h4><div class="dm-chips">' + (s.documents || []).map((d) => '<span class="dm-chip">' + esc(d) + '</span>').join('') + '</div></div>' : '') +
    (s.description ? '<div class="dm-sec"><h4>About</h4><p>' + esc(s.description) + '</p></div>' : '') +
    (s.link ? '<a class="btn primary block" href="' + esc(s.link) + '" target="_blank" rel="noopener">Official site / Apply ↗</a>' : '') +
    '<button class="btn ghost block" id="dm-sch-ask">Ask Veda about this scholarship</button>';

  openModalCard(html);
  const ask = el('dm-sch-ask');
  if (ask) ask.addEventListener('click', () => askVeda('Explain the scholarship "' + s.name + '" in simple terms: who can apply, key eligibility, documents needed, and the real application steps.'));
}

window.openCollegeModal = openCollegeModal;
window.openScholarshipModal = openScholarshipModal;

// ---- College compare ----
let compareList = [];
try { compareList = JSON.parse(localStorage.getItem('learnify_compare') || '[]'); } catch (_) {}
function saveCompare() { try { localStorage.setItem('learnify_compare', JSON.stringify(compareList)); } catch (_) {} }
function renderCompareBar() {
  let bar = el('compare-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'compare-bar';
    bar.className = 'compare-bar';
    document.body.appendChild(bar);
  }
  if (!compareList.length) { bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  bar.innerHTML =
    '<span class="cb-title">Compare (' + compareList.length + '/3)</span>' +
    '<div class="cb-chips">' + compareList.map((c, i) => '<span class="cb-chip">' + esc(c.name) + ' <b data-rm="' + i + '">&times;</b></span>').join('') + '</div>' +
    '<button class="btn primary sm" id="cb-open">Compare</button>' +
    '<button class="cb-clear" id="cb-clear">Clear</button>';
  bar.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', (e) => {
    e.stopPropagation();
    compareList.splice(Number(b.dataset.rm), 1); saveCompare(); renderCompareBar();
  }));
  const open = el('cb-open'); if (open) open.addEventListener('click', openCompareModal);
  const clr = el('cb-clear'); if (clr) clr.addEventListener('click', () => { compareList = []; saveCompare(); renderCompareBar(); });
}
function toggleCompare(c) {
  const i = compareList.findIndex((x) => x.id === c.id);
  if (i >= 0) { compareList.splice(i, 1); toast('Removed from compare', 'info'); }
  else {
    if (compareList.length >= 3) { toast('You can compare up to 3 colleges.', 'info'); return; }
    compareList.push({ id: c.id, name: c.name, type: c.type, nirf_rank: c.nirf_rank, avg_package: c.avg_package, highest_package: c.highest_package, city: c.city, state: c.state, rating: c.rating, streams: c.streams });
    toast('Added to compare', 'ok');
  }
  saveCompare(); renderCompareBar();
  const btn = el('dm-compare'); if (btn) btn.textContent = compareList.some((x) => x.id === c.id) ? '✓ Added to compare' : '➕ Add to compare';
}
function openCompareModal() {
  if (!compareList.length) { toast('Add colleges to compare first.', 'info'); return; }
  const rows = [
    ['Type', (c) => ((c.type || '').toString().replace(/^\w/, (m) => m.toUpperCase()) || '—')],
    ['NIRF Rank', (c) => (c.nirf_rank != null ? '#' + c.nirf_rank : '—')],
    ['Avg Package', (c) => (c.avg_package != null ? '₹' + c.avg_package + ' LPA' : '—')],
    ['Highest Package', (c) => (c.highest_package != null ? '₹' + c.highest_package + ' LPA' : '—')],
    ['Location', (c) => ([c.city, c.state].filter(Boolean).join(', ') || '—')],
    ['Rating', (c) => (c.rating != null ? c.rating + ' ★' : '—')],
    ['Streams', (c) => ((c.streams || []).join(', ') || '—')],
  ];
  const head = '<tr><th></th>' + compareList.map((c) => '<th>' + esc(c.name) + '</th>').join('') + '</tr>';
  const body = rows.map(([label, fn]) => '<tr><td class="cmp-label">' + label + '</td>' + compareList.map((c) => '<td>' + esc(fn(c)) + '</td>').join('') + '</tr>').join('');
  const html =
    '<h3 class="modal-title">⚖️ Compare Colleges</h3>' +
    '<div class="cmp-wrap"><table class="cmp-table"><thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>' +
    '<button class="btn ghost block" data-close>Close</button>';
  openModalCard(html);
}
window.openCompareModal = openCompareModal;
renderCompareBar();

onReady(() => {
  initSystem();
  initAuth();
  initVeda();
  initCareer();
  initCareers();
  initProfile();
  initPremium();
  initTools();
  initWriting();
  initCalculator();
  initResume();
  initPlanner();
  initScholarships();
  initMisc();
  initNotifications();
  initStudyTools();
  applyLanguage(getLang());
  _restoreView();
});
