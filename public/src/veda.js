import { api, el, getToken, getUser, toast, getLang, openModal, vedaQuotaLeft, incVeda, renderMarkdown, setUser } from './utils.js?v=34';
import { openLogin } from './auth.js?v=34';
import { playChatDing } from './sound.js?v=34';

const esc = (s) => String(s == null ? '' : s).replace(/[<>&]/g, '');

let messages = [];
let currentChatId = null;
let chatList = [];
let greetingHTML = '';
let streamEl = null;
let user = null;
let userId = 'demo';

const CHAT_KEY = "learnify_chat";

function saveChatLocal() {
  try { localStorage.setItem(CHAT_KEY, JSON.stringify({ id: currentChatId, messages })); } catch (_) {}
}
function updateQuota() {
  const q = el('veda-quota');
  if (!q) return;
  const user = getUser();
  if (user && user.premium) { q.textContent = 'Unlimited questions'; return; }
  const left = vedaQuotaLeft();
  q.textContent = left === Infinity ? 'Unlimited questions' : (left + ' question' + (left === 1 ? '' : 's') + ' left today');
}

function appendBubble(who, text) {
  const wrap = el('chat-messages');
  const row = document.createElement('div');
  row.className = 'msg' + (who === 'user' ? ' user' : '');
  const avClass = who === 'user' ? 'u' : 'v';
  const u = getUser();
  const av = who === 'user' ? (u ? (u.name || 'S').charAt(0).toUpperCase() : 'S') : 'V';
  row.innerHTML = `<div class="msg-av ${avClass}">${av}</div><div class="bubble ${avClass}"></div>`;
  const bubble = row.querySelector('.bubble');
  if (who === 'v') bubble.innerHTML = renderMarkdown(text);
  else bubble.textContent = text;
  if (who === 'v') addMsgActions(row, bubble);
  wrap.appendChild(row);
  return row.querySelector('.bubble');
}

function addMsgActions(row, bubble) {
  const bar = document.createElement('div');
  bar.className = 'msg-actions';
  bar.innerHTML = '<button class="msg-copy" title="Copy reply">⧉ Copy</button>';
  bar.querySelector('.msg-copy').addEventListener('click', () => {
    const txt = (bubble.innerText || '').replace(/⧉\s*Copy/g, '').trim();
    if (navigator.clipboard) navigator.clipboard.writeText(txt)
      .then(() => toast('Copied to clipboard', 'ok')).catch(() => {});
  });
  row.appendChild(bar);
}

function beginStream() {
  const wrap = el('chat-messages');
  const row = document.createElement('div');
  row.className = 'msg';
  row.innerHTML = '<div class="msg-av v">V</div><div class="bubble v"></div>';
  wrap.appendChild(row);
  streamEl = row.querySelector('.bubble');
  addMsgActions(row, streamEl);
  scrollDown();
  return streamEl;
}

function showTyping() {
  const wrap = el('chat-messages');
  const row = document.createElement('div');
  row.className = 'msg'; row.id = 'typing-row';
  row.innerHTML = '<div class="msg-av v">V</div><div class="bubble v typing"><span></span><span></span><span></span> <i class="t-label">Veda is typing…</i></div>';
  wrap.appendChild(row); scrollDown();
}
function removeTyping() {
  const t = document.getElementById('typing-row');
  if (t) t.remove();
}
function scrollDown() { const w = el('chat-messages'); if (w) w.scrollTop = w.scrollHeight; }

function showProfileToast(d) {
  const parts = [];
  if (d.profile) {
    for (const k in d.profile) parts.push(k + ' → ' + d.profile[k]);
  }
  if (d.academic) {
    d.academic.forEach((a) => parts.push('Marks: ' + a.exam + ' ' + a.value));
  }
  if (parts.length) toast('✅ Profile updated — ' + parts.join(', '), 'success');
}

async function loadChatList() {
  if (!getToken()) { chatList = []; renderChatList(); return; }
  const u = getUser();
  const uid = (u && (u.id || u.email)) || '';
  try {
    const data = await api('/veda/chats?user_id=' + encodeURIComponent(uid));
    chatList = (data && data.chats) || [];
  } catch (_) { chatList = []; }
  renderChatList();
}

function renderChatList() {
  const list = el('veda-chat-list');
  if (!list) return;
  if (!chatList.length) { list.innerHTML = '<div class="vh-empty">No past chats yet</div>'; return; }
  const esc = (s) => String(s == null ? '' : s).replace(/[<>&]/g, '');
  list.innerHTML = chatList.map((c) => {
    const active = c.id === currentChatId ? ' active' : '';
    return `<div class="vh-item${active}" data-id="${c.id}">` +
      `<span class="vh-title">${esc(c.title || 'New chat')}</span>` +
      `<button class="vh-del" data-del="${c.id}" title="Delete">🗑</button></div>`;
  }).join('');
  list.querySelectorAll('.vh-item').forEach((it) => {
    it.addEventListener('click', (e) => {
      if (e.target.closest('.vh-del')) return;
      openChat(it.dataset.id);
      const p = el('veda-hist-panel'); if (p) p.hidden = true;
    });
  });
  list.querySelectorAll('.vh-del').forEach((b) => {
    b.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = b.dataset.del;
      try { await api('/veda/chats/' + id + '?user_id=' + encodeURIComponent(userId), { method: 'DELETE' }); } catch (_) {}
      if (id === currentChatId) newChat();
      await loadChatList();
    });
  });
}

async function openChat(id) {
  currentChatId = id;
  try {
    const data = await api('/veda/chats/' + id + '?user_id=' + encodeURIComponent(userId));
    const msgs = (data && data.messages) || [];
    messages = msgs.slice();
    const wrap = el('chat-messages');
    wrap.innerHTML = '';
    messages.forEach((m) => appendBubble(m.role === 'user' ? 'user' : 'v', m.content));
    scrollDown();
  } catch (_) {}
  renderChatList();
  renderSuggestions();
}

function newChat() {
  currentChatId = null;
  messages = [];
  const wrap = el('chat-messages');
  wrap.innerHTML = greetingHTML;
  scrollDown();
  renderChatList();
  renderSuggestions();
}

function syncVedaUser() {
  user = getUser();
  userId = (user && (user.id || user.email)) || (getToken() ? 'auth-user' : 'demo');
  updateQuota();
  const upg = el('veda-upgrade');
  if (upg) upg.style.display = (user && user.premium) ? 'none' : '';
  const cav = document.querySelector('.veda-av');
  if (cav) cav.textContent = 'V';
}

function buildGreeting() {
  const u = getUser();
  const name = (u && u.name) ? u.name.trim().split(' ')[0] : '';
  const hi = name ? ('Hi ' + name + '! I’m ') : 'Hi! I’m ';
  return '<div class="msg"><div class="msg-av v">V</div><div class="bubble v">' +
    hi + '<b>Veda</b>, your AI study companion. I can help you with:' +
    '<ul><li>Finding the right college or stream</li><li>Career guidance & planning</li>' +
    '<li>Scholarships, loans & admissions</li><li>Study plans, quizzes & notes</li></ul>' +
    'Ask me anything — or tap a suggestion below.</div></div>';
}

function lastAssistant() {
  for (let i = messages.length - 1; i >= 0; i--)
    if (messages[i].role === 'assistant') return messages[i].content || '';
  return '';
}

function buildSuggestions() {
  const u = getUser();
  const grade = (u && (u.grade || u.target_exam)) || '';
  const sugs = [];
  const last = lastAssistant().toLowerCase();
  if (messages.length) {
    if (last.includes('roadmap') || last.includes('step') || last.includes('phase') || last.includes('milestone'))
      sugs.push({ q: 'Save this roadmap as a PDF', tag: 'pdf' });
    if (last.includes('scholarship')) sugs.push({ q: 'What is the eligibility for these?' });
    if (last.includes('college')) sugs.push({ q: 'Compare the top 2 colleges you mentioned' });
    let lastUser = null;
    for (let i = messages.length - 1; i >= 0; i--) { if (messages[i].role === 'user') { lastUser = messages[i].content; break; } }
    if (lastUser) sugs.push({ q: '↻ Regenerate response', tag: 'regen' });
    sugs.push({ q: 'Give me a weekly study plan' });
    sugs.push({ q: 'Explain this more simply' });
  }
  if (grade) {
    sugs.push({ q: 'Plan my study schedule for ' + grade });
    sugs.push({ q: 'Best colleges for ' + grade });
  }
  if (chatList && chatList.length) {
    const t = (chatList[0] && chatList[0].title) || '';
    if (t && t !== 'New chat') sugs.push({ q: 'Continue our chat: ' + t });
  }
  if (!sugs.length) {
    sugs.push({ q: 'Compare top 2 colleges for my profile' });
    sugs.push({ q: 'What scholarships can I apply for?' });
    sugs.push({ q: 'Which stream should I pick?' });
  }
  const seen = new Set(), out = [];
  for (const s of sugs) { if (!seen.has(s.q)) { seen.add(s.q); out.push(s); } }
  return out.slice(0, 4);
}

function renderSuggestions() {
  const wrap = document.querySelector('.suggest');
  if (!wrap) return;
  const sugs = buildSuggestions();
  wrap.innerHTML = sugs.map((s) =>
    '<button data-q="' + esc(s.q) + '"' + (s.tag ? ' data-tag="' + esc(s.tag) + '"' : '') + '>' + esc(s.q) + '</button>'
  ).join('');
}

function downloadLastRoadmap() {
  const text = lastAssistant();
  if (!text) { toast('No roadmap to save yet. Ask Veda to build one first.', 'info'); return; }
  const u = getUser();
  const grade = (u && (u.grade || u.target_exam)) || '';
  generateRoadmapPDF(text, 'My Learning Roadmap' + (grade ? ' — ' + grade : ''));
}

function generateRoadmapPDF(markdown, title) {
  const jspdf = window.jspdf;
  if (!jspdf) { toast('PDF library not ready. Try again in a moment.', 'info'); return; }
  const doc = new jspdf.jsPDF({ unit: 'pt', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 48;
  const maxW = pageW - margin * 2;
  let y = margin;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(20);
  doc.text(title || 'Learning Roadmap', margin, y);
  y += 28;
  doc.setDrawColor(224, 165, 38);
  doc.setLineWidth(2);
  doc.line(margin, y, pageW - margin, y);
  y += 22;

  const stripMd = (s) => s
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/[*_`#]/g, '')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/–/g, '-');
  const draw = (text, size, style, indent, prefix) => {
    doc.setFont('helvetica', style);
    doc.setFontSize(size);
    const full = (prefix || '') + text;
    const wrapped = doc.splitTextToSize(full, maxW - indent);
    for (const w of wrapped) {
      if (y > pageH - margin) { doc.addPage(); y = margin; }
      doc.text(w, margin + indent, y);
      y += size + 6;
    }
  };

  for (const raw of (markdown || '').split('\n')) {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) { y += 6; continue; }
    if (/^###\s/.test(line)) { draw(line.replace(/^###\s/, ''), 13, 'bold', 0); y += 2; continue; }
    if (/^##\s/.test(line)) { y += 4; draw(line.replace(/^##\s/, ''), 15, 'bold', 0); y += 4; continue; }
    if (/^#\s/.test(line)) { y += 4; draw(line.replace(/^#\s/, ''), 17, 'bold', 0); y += 4; continue; }
    const m = line.match(/^(\d+)\.\s/);
    if (m) { draw(stripMd(line.replace(/^\d+\.\s/, '')), 11, 'normal', 18, m[1] + '. '); continue; }
    if (/^[-*]\s/.test(line)) { draw(stripMd(line.replace(/^[-*]\s/, '')), 11, 'normal', 14, '•  '); continue; }
    draw(stripMd(line), 11, 'normal', 0, '');
  }

  const safe = (title || 'roadmap').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
  doc.save((safe || 'roadmap') + '-veda.pdf');
  toast('✅ Roadmap PDF downloaded', 'success');
}

async function startRoadmap() {
  if (!getToken()) { toast('Please log in to build a roadmap.', 'info'); openLogin(); return; }
  const u = getUser();
  const grade = (u && (u.grade || u.target_exam)) || '';
  let prompt = 'Build a detailed, personalised study & career roadmap for me as an Indian student';
  if (grade) prompt += ' preparing for ' + grade;
  prompt += ': split it into clear phases (Foundation, Skill-building, Exams & Applications, Placement), ' +
    'with weekly milestones, free resources, and the exact next 3 actions. Use headings and bullet points.';
  const input = el('chat-input');
  if (input) input.value = prompt;
  const text = await window.sendMessage();
  if (text) generateRoadmapPDF(text, 'My Learning Roadmap' + (grade ? ' — ' + grade : ''));
}
window.startRoadmap = startRoadmap;
window.downloadLastRoadmap = downloadLastRoadmap;

export function initVeda() {
  const input = el('chat-input');
  const wrap = el('chat-messages');
  if (!input || !wrap) return;
  const sendBtn = document.querySelector('.chat-input button.send');
  let busy = false;

  syncVedaUser();
  greetingHTML = buildGreeting();
  newChat();

  loadChatList().then(() => renderSuggestions());
  window.addEventListener('learnify:login', () => {
    syncVedaUser();
    greetingHTML = buildGreeting();
    newChat();
    loadChatList().then(() => renderSuggestions());
  });

  const newBtn = el('veda-new');
  if (newBtn) newBtn.addEventListener('click', newChat);
  const histBtn = el('veda-hist');
  if (histBtn) histBtn.addEventListener('click', () => {
    const p = el('veda-hist-panel'); if (p) p.hidden = !p.hidden;
  });
  const histClose = el('veda-hist-close');
  if (histClose) histClose.addEventListener('click', () => { el('veda-hist-panel').hidden = true; });

  window.sendMessage = async function sendMessage() {
    if (busy) return;
    syncVedaUser();
    const msg = input.value.trim();
    if (!msg) return;
    if (!getToken()) { toast('Please log in to chat with Veda.', 'info'); openLogin(); return; }
    const premium = !!(user && user.premium);
    if (!premium && vedaQuotaLeft() <= 0) {
      toast('Daily free limit reached. Upgrade to Premium for unlimited chat.', 'info');
      if (window.addNotification) window.addNotification('Daily Veda limit reached — upgrade to Premium for unlimited chat.');
      openModal('premium-modal');
      return;
    }

    messages.push({ role: 'user', content: msg });
    appendBubble('user', msg);
    input.value = '';
    input.blur();
    scrollDown();
    showTyping();
    busy = true;
    input.disabled = true;
    if (sendBtn) { sendBtn.disabled = true; sendBtn.classList.add('busy'); }

    try {
      if (!currentChatId) {
        const cr = await api('/veda/chats', {
          method: 'POST',
          body: JSON.stringify({ user_id: userId, title: msg.slice(0, 60) })
        });
        currentChatId = cr && cr.id;
      }
      const resp = await fetch('/api/veda/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, messages, language: getLang(), chat_id: currentChatId })
      });
      if (!resp.ok) throw new Error('Veda request failed (' + resp.status + ')');

      // Two-way profile sync: show a toast when Veda saved facts from the chat.
      const pu = resp.headers.get('X-Profile-Updated');
      if (pu) {
        try {
          const d = JSON.parse(decodeURIComponent(pu));
          showProfileToast(d);
          api('/auth/me').then((r) => { if (r && r.user) setUser(r.user); }).catch(() => {});
        } catch (_) {}
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let text = '';
      removeTyping();
      beginStream();
      let dinged = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
        if (streamEl) streamEl.innerHTML = renderMarkdown(text);
        if (!dinged && text.trim()) { dinged = true; try { playChatDing(); } catch (_) {} }
        scrollDown();
      }
       messages.push({ role: 'assistant', content: text });
       if (!premium) incVeda();
       updateQuota();
       saveChatLocal();
       renderSuggestions();
       await loadChatList();
       return text;
     } catch (err) {
      removeTyping();
      appendBubble('v', '⚠ Sorry, ' + (err && err.message ? err.message : 'network error. Please try again.'));
      scrollDown();
    } finally {
      busy = false;
      input.disabled = false;
      if (sendBtn) { sendBtn.disabled = false; sendBtn.classList.remove('busy'); }
      input.focus();
    }
  };

  const suggestWrap = document.querySelector('.suggest');
  if (suggestWrap) suggestWrap.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.tag === 'pdf') { downloadLastRoadmap(); return; }
    if (b.dataset.tag === 'regen') {
      const input2 = el('chat-input');
      let um = null;
      for (let i = messages.length - 1; i >= 0; i--) { if (messages[i].role === 'user') { um = messages[i].content; break; } }
      if (um && input2) { input2.value = um; window.sendMessage(); }
      return;
    }
    input.value = b.dataset.q || b.textContent;
    window.sendMessage();
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') window.sendMessage(); });

  const quizBtn = el('veda-quiz');
  if (quizBtn) quizBtn.addEventListener('click', startQuiz);
  const qModal = el('quiz-modal');
  if (qModal) {
    qModal.addEventListener('click', (e) => { if (e.target === qModal) closeQuiz(); });
    const qClose = qModal.querySelector('.modal-close');
    if (qClose) qClose.addEventListener('click', closeQuiz);
  }
}

function closeQuiz() {
  const m = el('quiz-modal');
  if (m) m.classList.remove('show');
  const body = el('quiz-body');
  if (body) body.innerHTML = '';
}

async function startQuiz() {
  const user = getUser();
  const defTopic = (user && (user.target_exam || user.grade)) ? (user.target_exam || user.grade) : 'General studies for Indian students';
  const topic = (window.prompt ? window.prompt('Quiz topic (e.g. Photosynthesis, Indian History, Algebra):', defTopic) : '') || defTopic;
  const body = el('quiz-body');
  if (!body) return;
  body.innerHTML = '<p style="color:var(--sub)">Generating quiz on “' + esc(topic) + '”…</p>';
  el('quiz-modal').classList.add('show');
  try {
    const data = await api('/veda/quiz', {
      method: 'POST',
      body: JSON.stringify({ topic, count: 5, difficulty: 'Mixed', language: getLang() })
    });
    const qs = (data && data.questions) || [];
    if (!qs.length) { body.innerHTML = '<p style="color:var(--sub)">Could not generate a quiz right now. Try again.</p>'; return; }
    body.innerHTML = '';
    qs.forEach((q, qi) => {
      const card = document.createElement('div');
      card.className = 'quiz-q';
      let opts = '';
      (q.options || []).forEach((o, oi) => {
        opts += '<button class="quiz-opt" data-q="' + qi + '" data-o="' + oi + '">' + esc(o) + '</button>';
      });
      card.innerHTML = '<div class="quiz-n">Q' + (qi + 1) + '. ' + esc(q.question) + '</div><div class="quiz-opts">' + opts + '</div><div class="quiz-fb" data-fb="' + qi + '"></div>';
      body.appendChild(card);
    });
    body.querySelectorAll('.quiz-opt').forEach((btn) => {
      btn.addEventListener('click', () => {
        const qi = Number(btn.dataset.q);
        const oi = Number(btn.dataset.o);
        const q = qs[qi];
        const fb = body.querySelector('.quiz-fb[data-fb="' + qi + '"]');
        if (fb.dataset.done) return;
        fb.dataset.done = '1';
        const correct = oi === q.answer_index;
        btn.classList.add(correct ? 'correct' : 'wrong');
        if (!correct) {
          const right = body.querySelector('.quiz-opt[data-q="' + qi + '"][data-o="' + q.answer_index + '"]');
          if (right) right.classList.add('correct');
        }
        body.querySelectorAll('.quiz-opt[data-q="' + qi + '"]').forEach((b) => { b.disabled = true; });
        fb.innerHTML = (correct ? '✅ Correct! ' : '❌ Correct answer: ' + esc(q.options[q.answer_index]) + '. ')
          + (q.explanation ? '<span>' + esc(q.explanation) + '</span>' : '');
        fb.classList.add(correct ? 'ok' : 'no');
      });
    });
  } catch (e) {
    body.innerHTML = '<p style="color:var(--sub)">Quiz failed: ' + esc(e && e.message ? e.message : 'error') + '</p>';
  }
}
