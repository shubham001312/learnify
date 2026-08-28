import { api, el, toast, openModal, getToken, getUser, isPremium } from './utils.js?v=51';
import { playClick, soundEnabled, setSoundEnabled } from './sound.js?v=51';
import { openLogin } from './auth.js?v=51';

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
        if (window.startRoadmap) window.startRoadmap();
        else if (window.askVeda) window.askVeda('Build a step-by-step, personalised AI upskilling & career roadmap for me as an Indian student, with weekly milestones and free resources.');
      } else if (which === 'scholarship') {
        runSmartMatch();
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
      b.innerHTML = '<span style="font-weight:700;color:var(--gold-deep);min-width:18px">' + labels[oi] + '.</span> <span>' + esc(opt) + '</span>';
      b.addEventListener('click', () => {
        if (wrap.querySelector('.quiz-opt.sel')) return;
        b.classList.add('sel');
        answered++;
        const correct = Number(item.answer) === oi;
        b.classList.add(correct ? 'correct' : 'wrong');
        if (correct) score++;
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
        aiOut.innerHTML = '<div class="notes-ai-out-text">' + esc(reply || 'No output.') + '</div>';
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
      const lines = (reply || '').split('\n').map(l => l.trim()).filter(Boolean);
      let tldr = '', body = [];
      lines.forEach((l, i) => { if (i === 0) tldr = l.replace(/^[-*•]\s*/, ''); else body.push(l.replace(/^[-*•]\s*/, '')); });
      out.innerHTML =
        (tldr ? '<div class="sum-tldr"><span class="sum-tldr-k">TL;DR</span>' + esc(tldr) + '</div>' : '') +
        (body.length ? '<div class="sum-bullets">' + body.map(b => '<div class="sum-b">' + esc(b) + '</div>').join('') + '</div>' : (tldr ? '' : 'No summary.'));
    } catch (e) {
      out.textContent = '⚠️ ' + e.message;
    } finally {
      gen.disabled = false; gen.textContent = 'Summarize';
    }
  });
  const copy = el('sum-copy');
  copy && copy.addEventListener('click', () => {
    playClick();
    const t = (el('sum-output').textContent || '').trim();
    if (!t) { toast('Nothing to copy yet.', 'info'); return; }
    try { navigator.clipboard.writeText(t); toast('Summary copied', 'ok'); } catch (_) {}
  });
  const exp = el('sum-export');
  exp && exp.addEventListener('click', () => {
    playClick();
    if (!isPremium()) { openModal('premium-modal'); return; }
    const t = (el('sum-output').textContent || '').trim();
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

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}
