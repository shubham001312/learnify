import { api, el, toast, openModal, getToken, getUser, isPremium, renderMarkdown, getLang } from './utils.js?v=59';
import { playClick, soundEnabled, setSoundEnabled } from './sound.js?v=59';
import { openLogin } from './auth.js?v=59';

const NOTES_KEY = 'learnify_notes';

export function initStudyTools() {
  wirePremiumTools();
  wireQuiz();
  wireTimer();
  wireNotes();
  wireSummarizer();
  wireSoundSetting();
}

// Premium-gated tools: open the tool for Pro users, otherwise prompt upgrade.
function wirePremiumTools() {
  document.querySelectorAll('[data-premium]').forEach((b) => {
    b.addEventListener('click', () => {
      playClick();
      if (!isPremium()) { openModal('premium-modal'); return; }
      b.classList.add('is-pro');
      const which = b.dataset.premium;
      if (which === 'quiz') { if (window.setViewNav) window.setViewNav('quiz', true); }
      else if (which === 'roadmap') {
        if (window.setViewNav) window.setViewNav('roadmap-pro', true);
      } else if (which === 'scholarship') {
        if (window.setViewNav) window.setViewNav('scholarship-match', true);
      }
    });
  });
}

// Smart Scholarship Match (Pro): uses the live web-search API (3rd integration)
// to surface real, current scholarships instead of only the curated list.
function runSmartMatch() {
  if (window.setViewNav) window.setViewNav('scholarships', true);
  setTimeout(() => {
    const q = el('sch-live-q');
    const go = el('sch-live-go');
    if (q && go) {
      const u = getUser() || {};
      const loc = [u.state, u.board].filter(Boolean).join(' ');
      q.value = (loc ? loc + ' ' : '') + 'scholarships for Indian students 2026';
      go.click();
      const meta = el('sch-live-meta');
      if (meta) meta.textContent = 'Smart Match · scholarship database';
    }
  }, 350);
}

// Stream /api/veda/chat and return the full reply text (the endpoint streams plain text).
async function vedaText(payload) {
  const resp = await fetch('/api/veda/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) throw new Error('Veda request failed (' + resp.status + ')');
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let text = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
  }
  return text;
}

function wireQuiz() {
  const gen = el('quiz-gen');
  if (!gen) return;
  gen.addEventListener('click', async () => {
    const topic = (el('quiz-topic').value || '').trim();
    if (!topic) { toast('Enter a topic first.', 'info'); return; }
    if (!getToken()) { toast('Login to generate a quiz.', 'info'); openLogin(); return; }
    let count = parseInt(el('quiz-count').value, 10) || 5;
    if (!isPremium() && count > 10) count = 10;
    const box = el('quiz-box');
    box.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    gen.disabled = true; gen.textContent = 'Generating…';
    try {
      const text = await vedaText({
        user_id: ((getUser() || {}).email) || 'demo',
        messages: [{ role: 'user', content: `Generate ${count} multiple-choice quiz questions about "${topic}" for an Indian student. Return ONLY a valid JSON array of objects with keys: q (string), options (array of 4 strings), answer (integer 0-3, index of correct option). No markdown, no extra text.` }]
      });
      const arr = extractJsonArray(text);
      if (!arr || !arr.length) throw new Error('Could not parse the quiz. Try again.');
      renderQuiz(arr);
    } catch (e) {
      box.innerHTML = '<div class="modal-sub" style="color:#c0392b">⚠️ ' + esc(e.message) + '</div>';
    } finally {
      gen.disabled = false; gen.textContent = 'Generate Quiz';
    }
  });
}

function renderQuiz(arr) {
  const box = el('quiz-box');
  let score = 0, answered = 0;
  const labels = ['A', 'B', 'C', 'D', 'E', 'F'];
  box.innerHTML = '';
  arr.forEach((item, i) => {
    const wrap = document.createElement('div');
    const qHtml = '<div class="quiz-q">' + (i + 1) + '. ' + esc(item.q || '') + '</div>';
    const optsHtml = '<div class="quiz-opts"></div>';
    wrap.innerHTML = qHtml + optsHtml;
    const optsWrap = wrap.querySelector('.quiz-opts');
    (item.options || []).forEach((opt, oi) => {
      const b = document.createElement('button');
      b.className = 'quiz-opt';
      b.dataset.idx = oi;
      b.innerHTML = '<span style="font-weight:700;color:var(--gold-deep);min-width:18px">' + labels[oi] + '.</span> <span>' + esc(opt) + '</span>';
      b.addEventListener('click', () => {
        if (wrap.querySelector('.quiz-opt.sel')) return;
        b.classList.add('sel');
        answered++;
        const correctIdx = Number(item.answer);
        const isCorrect = correctIdx === oi;
        b.classList.add(isCorrect ? 'correct' : 'wrong');
        if (isCorrect) score++;
        if (!isCorrect) {
          const correctBtn = optsWrap.querySelector('[data-idx="' + correctIdx + '"]');
          if (correctBtn) correctBtn.classList.add('correct');
        }
        if (answered === arr.length) {
          const pct = Math.round((score / arr.length) * 100);
          res.innerHTML = '🎉 You scored <b>' + score + ' / ' + arr.length + '</b> (' + pct + '%)';
        }
      });
      optsWrap.appendChild(b);
    });
    box.appendChild(wrap);
  });
  const res = document.createElement('div');
  res.className = 'quiz-result';
  box.appendChild(res);
}

function extractJsonArray(s) {
  if (!s) return null;
  s = s.trim();
  if (s.startsWith('```')) s = s.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '');
  const a = s.indexOf('['), b = s.lastIndexOf(']');
  if (a === -1 || b === -1) return null;
  try { const arr = JSON.parse(s.slice(a, b + 1)); return Array.isArray(arr) ? arr : null; } catch (_) { return null; }
}

function wireTimer() {
  const disp = el('timer-display');
  if (!disp) return;
  let total = 25 * 60, left = total, timer = null, running = false;
  const status = el('timer-status');
  const render = () => {
    const m = String(Math.floor(left / 60)).padStart(2, '0');
    const s = String(left % 60).padStart(2, '0');
    disp.textContent = m + ':' + s;
  };
  const setMin = (min) => {
    total = min * 60; left = total; render();
    document.querySelectorAll('.timer-presets .tbtn-sm').forEach((x) => x.classList.toggle('active', Number(x.dataset.min) === min));
  };
  document.querySelectorAll('.timer-presets .tbtn-sm').forEach((b) => {
    b.addEventListener('click', () => { playClick(); setMin(Number(b.dataset.min)); if (status) status.textContent = 'Ready'; });
  });
  const start = el('timer-start');
  start && start.addEventListener('click', () => {
    playClick();
    if (running) { clearInterval(timer); running = false; start.textContent = 'Start'; if (status) status.textContent = 'Paused'; return; }
    if (left <= 0) left = total;
    running = true; start.textContent = 'Pause';
    if (status) status.textContent = 'Focusing… stay sharp!';
    timer = setInterval(() => {
      left--; render();
      if (left <= 0) {
        clearInterval(timer); running = false; start.textContent = 'Start';
        if (status) status.textContent = '✅ Session complete!';
      }
    }, 1000);
  });
  const reset = el('timer-reset');
  reset && reset.addEventListener('click', () => {
    playClick(); clearInterval(timer); running = false; left = total; render();
    start.textContent = 'Start'; if (status) status.textContent = 'Pomodoro focus session';
  });
  setMin(25);
}

function wireNotes() {
  const area = el('notes-area');
  if (!area) return;
  try { area.value = localStorage.getItem(NOTES_KEY) || ''; } catch (_) {}
  const status = el('notes-status');
  let t;
  area.addEventListener('input', () => {
    clearTimeout(t);
    if (status) status.textContent = 'Saving…';
    t = setTimeout(() => { try { localStorage.setItem(NOTES_KEY, area.value); if (status) status.textContent = 'Saved ✓'; } catch (_) {} }, 400);
  });
  const copy = el('notes-copy');
  copy && copy.addEventListener('click', () => {
    playClick();
    area.select();
    try { navigator.clipboard.writeText(area.value); toast('Notes copied', 'ok'); } catch (_) { document.execCommand('copy'); }
  });
  const exp = el('notes-export');
  exp && exp.addEventListener('click', () => {
    playClick();
    if (!isPremium()) { openModal('premium-modal'); return; }
    const blob = new Blob([area.value], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'learnify-notes.txt'; a.click();
    URL.revokeObjectURL(a.href);
    toast('Notes exported', 'ok');
  });

  const aiBtn = el('notes-ai');
  const aiOut = el('notes-ai-out');
  const aiMode = el('notes-ai-mode');
  if (aiBtn) {
    aiBtn.addEventListener('click', async () => {
      const src = area.value.trim();
      if (!src) { toast('Write some notes first.', 'info'); return; }
      if (!getToken()) { toast('Login to use AI on notes.', 'info'); openLogin(); return; }
      aiOut.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
      aiBtn.disabled = true; aiBtn.textContent = 'Working…';
      const mode = aiMode ? aiMode.value : 'improve';
      const promptMap = {
        improve: 'Improve and organise the following study notes: fix grammar, structure with headings, keep all facts. Return clean, ready-to-study notes.',
        expand: 'Expand the following study notes with helpful explanations and simple examples for an Indian student. Use markdown headings.',
        guide: 'Turn the following notes into a concise study guide with key points, important definitions/formulas, and a quick recap at the end.',
        explain: 'Explain the following notes simply, as if teaching a complete beginner. Use plain, friendly language.'
      };
      try {
        const reply = await vedaText({ user_id: ((getUser() || {}).email) || 'demo', messages: [{ role: 'user', content: (promptMap[mode] || promptMap.improve) + '\n\n' + src }] });
        aiOut.innerHTML = '<div class="notes-ai-out-text">' + renderMarkdown(reply || 'No output.') + '</div>';
      } catch (e) { aiOut.textContent = '⚠️ ' + e.message; }
      finally { aiBtn.disabled = false; aiBtn.textContent = '✨ AI Magic'; }
    });
  }
}

function wireSummarizer() {
  const gen = el('sum-gen');
  if (!gen) return;
  gen.addEventListener('click', async () => {
    const text = (el('sum-input').value || '').trim();
    if (!text) { toast('Paste some text first.', 'info'); return; }
    if (!getToken()) { toast('Login to use the Summarizer.', 'info'); openLogin(); return; }
    const out = el('sum-output');
    out.textContent = '';
    out.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    gen.disabled = true; gen.textContent = 'Summarizing…';
    let len = el('sum-len').value;
    if (!isPremium() && len === 'detailed') {
      len = 'medium'; el('sum-len').value = 'medium';
      toast('Detailed summaries are a Pro feature — using Medium.', 'info');
    }
    const lenMap = { short: '3-4 short bullet points', medium: '5-6 clear bullet points', detailed: '7-10 detailed bullet points' };
    try {
      const reply = await vedaText({
        user_id: ((getUser() || {}).email) || 'demo',
        messages: [{ role: 'user', content: `Summarize the following text for an Indian student.\nFirst line: a one-sentence TL;DR. Then ${lenMap[len] || '5-6 clear bullet points'} (each line starting with "- "). Keep it clear and concise.\n\n` + text }]
      });
      out.innerHTML = '<div class="sum-rendered">' + renderMarkdown(reply || 'No summary.') + '</div>';
    } catch (e) {
      out.textContent = '⚠️ ' + e.message;
    } finally {
      gen.disabled = false; gen.textContent = 'Summarize';
    }
  });
  const copy = el('sum-copy');
  copy && copy.addEventListener('click', () => {
    playClick();
    const rendered = el('sum-output');
    const t = (rendered ? rendered.textContent : '').trim();
    if (!t) { toast('Nothing to copy yet.', 'info'); return; }
    try { navigator.clipboard.writeText(t); toast('Summary copied', 'ok'); } catch (_) {}
  });
  const exp = el('sum-export');
  exp && exp.addEventListener('click', () => {
    playClick();
    if (!isPremium()) { openModal('premium-modal'); return; }
    const rendered = el('sum-output');
    const t = (rendered ? rendered.textContent : '').trim();
    if (!t) { toast('Nothing to export yet.', 'info'); return; }
    const blob = new Blob([t], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'learnify-summary.txt'; a.click();
    URL.revokeObjectURL(a.href);
    toast('Summary exported', 'ok');
  });
}

function wireSoundSetting() {
  const box = el('settings-sound');
  if (box) box.checked = soundEnabled();
  const openBtn = el('btn-settings');
  if (openBtn) openBtn.addEventListener('click', () => { if (box) box.checked = soundEnabled(); });
  const save = el('settings-save');
  if (save) save.addEventListener('click', () => { if (box) setSoundEnabled(box.checked); });
}

/* ═══════════════════════ SMART SCHOLARSHIP MATCH ═══════════════════════ */

let _smInited = false;
window.initScholarshipMatch = function () {
  if (_smInited) return;
  _smInited = true;
  const u = getUser() || {};
  // Pre-fill from user profile
  const stateEl = el('sm-state');
  const catEl = el('sm-category');
  const eduEl = el('sm-edu');
  if (stateEl) {
    // Populate Indian states
    const states = ['Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal','Delhi','Jammu & Kashmir','Ladakh','Chandigarh','Puducherry','Andaman & Nicobar','Dadra & Nagar Haveli','Lakshadweep'];
    stateEl.innerHTML = '<option value="">Select state</option>' + states.map(s => '<option' + (u.state === s ? ' selected' : '') + '>' + s + '</option>').join('');
  }
  if (catEl && u.category) {
    const opts = catEl.options;
    for (let i = 0; i < opts.length; i++) { if (opts[i].value === u.category || opts[i].text === u.category) { catEl.selectedIndex = i; break; } }
  }
  if (eduEl && u.grade) {
    const g = u.grade.toLowerCase();
    const opts = eduEl.options;
    for (let i = 0; i < opts.length; i++) {
      if ((g.includes('10') && opts[i].text.includes('10')) || (g.includes('12') && opts[i].text.includes('12')) || (g.includes('btech') || g.includes('b.tech') || g.includes('bachelor')) && opts[i].text.includes('UG')) {
        eduEl.selectedIndex = i; break;
      }
    }
  }
  // Match button
  const btn = el('sm-match-btn');
  if (btn) btn.onclick = _runSmartMatch;
};

function _runSmartMatch() {
  const state = (el('sm-state') || {}).value || '';
  const category = (el('sm-category') || {}).value || '';
  const income = parseInt((el('sm-income') || {}).value || '0', 10);
  const edu = (el('sm-edu') || {}).value || '';
  const disability = (el('sm-disability') || {}).value || 'no';
  const gender = (el('sm-gender') || {}).value || '';
  if (!state && !category) { toast('Please select at least your state or category.', 'info'); return; }
  const btn = el('sm-match-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Matching…'; }
  api('/scholarships/match', {
    method: 'POST',
    body: JSON.stringify({ state, category, income, education: edu, disability, gender })
  }).then((d) => {
    const results = d.matches || [];
    const container = el('sm-results');
    const summary = el('sm-summary');
    const list = el('sm-list');
    if (container) container.hidden = false;
    if (summary) summary.innerHTML = '<div class="sm-count">' + results.length + ' scholarships match your profile</div>' + (results.length > 0 ? '<div class="sm-tip">Scores indicate how well you match each scholarship\'s eligibility criteria.</div>' : '');
    if (list) {
      if (results.length === 0) {
        list.innerHTML = '<div class="sm-empty">No exact matches found. Try broadening your filters or <a href="#scholarships" onclick="setView(\'scholarships\',true);return false;">browse all scholarships</a>.</div>';
      } else {
        list.innerHTML = results.map((r) => {
          const pct = r.score || 0;
          const cls = pct >= 80 ? 'high' : pct >= 50 ? 'med' : 'low';
          return '<div class="sm-card ' + cls + '">' +
            '<div class="sm-card-top"><div class="sm-card-name">' + esc(r.name) + '</div>' +
            '<div class="sm-score"><svg class="sm-ring" viewBox="0 0 36 36"><circle class="sm-ring-bg" cx="18" cy="18" r="15.9"/><circle class="sm-ring-fg" cx="18" cy="18" r="15.9" style="stroke-dasharray:' + pct + ' 100"/></svg><span>' + pct + '%</span></div></div>' +
            '<div class="sm-card-meta">' +
            '<span class="sm-tag">' + esc(r.category || '') + '</span>' +
            '<span class="sm-tag">' + esc(r.state || '') + '</span>' +
            (r.amount ? '<span class="sm-amount">' + esc(r.amount) + '</span>' : '') +
            '</div>' +
            '<div class="sm-card-elig">' + esc(r.eligibility || '') + '</div>' +
            (r.deadline ? '<div class="sm-card-deadline">⏰ Deadline: ' + esc(r.deadline) + '</div>' : '') +
            (r.link ? '<a class="sm-apply" href="' + esc(r.link) + '" target="_blank" rel="noopener">Apply →</a>' : '') +
            '</div>';
        }).join('');
      }
    }
  }).catch(() => {
    toast('Could not run matching. Try again.', 'err');
  }).finally(() => {
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Find My Matches'; }
  });
}

/* ═══════════════════════ AI ROADMAP PRO ═══════════════════════ */

let _rmInited = false;
window.initRoadmapPro = function () {
  if (_rmInited) return;
  _rmInited = true;
  const u = getUser() || {};
  if (u.name && el('rm-goal')) el('rm-goal').placeholder = 'e.g. ' + u.name + '\'s goal — Software Engineer, Doctor, IAS…';
  const btn = el('rm-gen-btn');
  if (btn) btn.onclick = _genRoadmap;
  const pdfBtn = el('rm-pdf-btn');
  if (pdfBtn) pdfBtn.onclick = _exportRoadmapPdf;
  const askBtn = el('rm-ask-veda');
  if (askBtn) askBtn.onclick = function () {
    const goal = (el('rm-goal') || {}).value || 'career growth';
    if (window.askVeda) window.askVeda('Give me more details and tips for my roadmap to become ' + goal);
  };
};

async function _genRoadmap() {
  const goal = (el('rm-goal') || {}).value.trim();
  if (!goal) { toast('Enter your career goal first.', 'info'); return; }
  const stage = (el('rm-stage') || {}).value || '';
  const timeline = (el('rm-timeline') || {}).value || '12';
  const skills = (el('rm-skills') || {}).value.trim();
  const constraints = (el('rm-constraints') || {}).value.trim();
  const btn = el('rm-gen-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Building your roadmap…'; }
  const output = el('rm-output');
  const head = el('rm-head');
  const body = el('rm-body');
  if (output) output.hidden = false;
  if (head) head.innerHTML = '<div class="rm-title">🎯 ' + esc(goal) + '</div><div class="rm-meta">' + esc(stage) + ' · ' + timeline + ' months' + (skills ? ' · Skills: ' + esc(skills) : '') + '</div>';
  if (body) body.innerHTML = '<div class="rm-loading"><div class="rm-loading-bar"></div>Analysing your goal and building a personalised plan…</div>';

  try {
    const u = getUser() || {};
    const prompt = 'Build a detailed, step-by-step career roadmap for an Indian student.\n\n' +
      'Goal: ' + goal + '\n' +
      'Current stage: ' + stage + '\n' +
      'Timeline: ' + timeline + ' months\n' +
      (skills ? 'Existing skills: ' + skills + '\n' : '') +
      (constraints ? 'Constraints: ' + constraints + '\n' : '') +
      'Language: ' + (getLang() || 'English') + '\n\n' +
      'Format your response as:\n' +
      '## Overview\n[Brief summary]\n\n' +
      '## Phase 1: Foundation (Months 1-X)\n- [ ] Milestone 1\n- [ ] Milestone 2\n\n## Phase 2: Build (Months X-Y)\n...\n\n## Phase 3: Launch (Months Y-Z)\n...\n\n## Key Resources\n- Free resource 1 (link if known)\n...\n\n## Your Next 3 Actions\n1. ...\n2. ...\n3. ...';

    const text = await vedaText({
      user_id: u.id || 'guest',
      messages: [{ role: 'user', content: prompt }],
      mode: 'roadmap',
      language: getLang() || 'English',
      chat_id: 'roadmap-' + Date.now()
    });

    if (body) body.innerHTML = renderMarkdown(text);
    if (body) body.dataset.raw = text;
  } catch (e) {
    if (body) body.innerHTML = '<div class="rm-error">Could not generate roadmap. Please try again.</div>';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🚀 Generate My Roadmap'; }
  }
}

function _exportRoadmapPdf() {
  const body = el('rm-body');
  const raw = (body ? body.dataset.raw : '') || (body ? body.textContent : '');
  if (!raw) { toast('No roadmap to export yet.', 'info'); return; }
  const goal = (el('rm-goal') || {}).value || 'My Roadmap';
  if (window.generateRoadmapPDF) {
    window.generateRoadmapPDF(raw, goal);
  } else {
    // Fallback: download markdown if jsPDF isn't loaded
    const blob = new Blob(['# ' + goal + '\n\n' + raw], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'learnify-roadmap-' + goal.replace(/[^a-z0-9]+/gi, '-').toLowerCase() + '.md'; a.click();
    URL.revokeObjectURL(a.href);
    toast('Roadmap exported as Markdown', 'ok');
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}
