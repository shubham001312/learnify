import { api, el, getToken, getUser, toast, getLang, openModal, vedaQuotaLeft, incVeda, renderMarkdown, setUser } from './utils.js?v=12';
import { openLogin } from './auth.js?v=12';
import { playChatDing } from './sound.js?v=12';

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
  wrap.appendChild(row);
  return row.querySelector('.bubble');
}

function beginStream() {
  const wrap = el('chat-messages');
  const row = document.createElement('div');
  row.className = 'msg';
  row.innerHTML = '<div class="msg-av v">V</div><div class="bubble v"></div>';
  wrap.appendChild(row);
  streamEl = row.querySelector('.bubble');
  scrollDown();
  return streamEl;
}

function showTyping() {
  const wrap = el('chat-messages');
  const row = document.createElement('div');
  row.className = 'msg'; row.id = 'typing-row';
  row.innerHTML = '<div class="msg-av v">V</div><div class="bubble v typing"><span></span><span></span><span></span></div>';
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
      try { await api('/veda/chats/' + id, { method: 'DELETE' }); } catch (_) {}
      if (id === currentChatId) newChat();
      await loadChatList();
    });
  });
}

async function openChat(id) {
  currentChatId = id;
  try {
    const data = await api('/veda/chats/' + id);
    const msgs = (data && data.messages) || [];
    messages = msgs.slice();
    const wrap = el('chat-messages');
    wrap.innerHTML = '';
    messages.forEach((m) => appendBubble(m.role === 'user' ? 'user' : 'v', m.content));
    scrollDown();
  } catch (_) {}
  renderChatList();
}

function newChat() {
  currentChatId = null;
  messages = [];
  const wrap = el('chat-messages');
  wrap.innerHTML = greetingHTML;
  scrollDown();
  renderChatList();
}

function syncVedaUser() {
  user = getUser();
  userId = (user && (user.id || user.email)) || (getToken() ? 'auth-user' : 'demo');
  updateQuota();
  const upg = el('veda-upgrade');
  if (upg) upg.style.display = (user && user.premium) ? 'none' : '';
  const cav = document.querySelector('.veda-av');
  if (cav) {
    const ini = (((user && user.name) || 'S').charAt(0) || 'S').toUpperCase();
    cav.textContent = (user && (user.id || user.email)) ? ini : 'V';
  }
}

export function initVeda() {
  const input = el('chat-input');
  const wrap = el('chat-messages');
  if (!input || !wrap) return;
  const sendBtn = document.querySelector('.chat-input button.send');
  let busy = false;

  syncVedaUser();
  greetingHTML = wrap.innerHTML;

  loadChatList();
  window.addEventListener('learnify:login', () => {
    syncVedaUser();
    newChat();
    loadChatList();
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
      await loadChatList();
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

  document.querySelectorAll('.suggest button').forEach((b) => {
    b.addEventListener('click', () => {
      input.value = b.dataset.q || b.textContent;
      window.sendMessage();
    });
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') window.sendMessage(); });
}
