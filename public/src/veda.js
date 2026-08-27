import { api, el, getToken, getUser, toast, getLang, openModal, vedaQuotaLeft, incVeda } from './utils.js';
import { openLogin } from './auth.js';

let messages = [];

const CHAT_KEY = "learnify_chat";

function saveChat() {
  try { localStorage.setItem(CHAT_KEY, JSON.stringify(messages)); } catch (_) {}
}
function loadChat() {
  try { return JSON.parse(localStorage.getItem(CHAT_KEY) || "[]"); } catch (_) { return []; }
}

function updateQuota() {
  const q = el('veda-quota');
  if (!q) return;
  const left = vedaQuotaLeft();
  q.textContent = left === Infinity ? 'Unlimited questions' : (left + ' question' + (left === 1 ? '' : 's') + ' left today');
}

export function initVeda() {
  const input = el('chat-input');
  const wrap = el('chat-messages');
  if (!input || !wrap) return;
  const sendBtn = document.querySelector('.chat-input button.send');
  let busy = false;

  const user = getUser();
  const userId = (user && (user.email || user.id)) || (getToken() ? "auth-user" : "demo");
  updateQuota();

  const saved = loadChat();
  if (saved.length) {
    wrap.innerHTML = "";
    saved.forEach((m) => appendBubble(m.role === "user" ? "user" : "v", m.content));
    messages = saved;
  }

  const newChat = el("veda-new");
  if (newChat) newChat.addEventListener("click", () => {
    messages = [];
    saveChat();
    wrap.innerHTML =
      '<div class="msg"><div class="msg-av v">V</div><div class="bubble v">' +
      "Hi! I'm <b>Veda</b>, your AI study companion. What would you like to know?</div></div>";
    scrollDown();
  });

  window.sendMessage = function sendMessage() {
    if (busy) return;
    const msg = input.value.trim();
    if (!msg) return;

    if (!getToken()) {
      toast('Please log in to chat with Veda.', 'info');
      openLogin();
      return;
    }
    if (vedaQuotaLeft() <= 0) {
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
    saveChat();

    busy = true;
    input.disabled = true;
    if (sendBtn) { sendBtn.disabled = true; sendBtn.classList.add('busy'); }

    api('/veda/chat', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, messages, language: getLang() })
    }).then((data) => {
      incVeda();
      updateQuota();
      removeTyping();
      const reply = (data && (data.reply || data.message)) || 'Sorry, I could not come up with a response.';
      messages.push({ role: 'assistant', content: reply });
      appendBubble('v', reply);
      scrollDown();
      saveChat();
    }).catch((err) => {
      removeTyping();
      appendBubble('v', '⚠ Sorry, ' + (err && err.message ? err.message : 'network error. Please try again.'));
      scrollDown();
    }).finally(() => {
      busy = false;
      input.disabled = false;
      if (sendBtn) { sendBtn.disabled = false; sendBtn.classList.remove('busy'); }
      input.focus();
    });
  };

  function appendBubble(who, text) {
    const row = document.createElement('div');
    row.className = 'msg' + (who === 'user' ? ' user' : '');
    const avClass = who === 'user' ? 'u' : 'v';
    const av = who === 'user' ? (getUser() ? (getUser().name || 'S').charAt(0).toUpperCase() : 'S') : 'V';
    row.innerHTML = '<div class="msg-av ' + avClass + '">' + av + '</div><div class="bubble ' + avClass + '"></div>';
    row.querySelector('.bubble').textContent = text;
    wrap.appendChild(row);
  }

  function showTyping() {
    const row = document.createElement('div');
    row.className = 'msg'; row.id = 'typing-row';
    row.innerHTML = '<div class="msg-av v">V</div><div class="bubble v typing"><span></span><span></span><span></span></div>';
    wrap.appendChild(row); scrollDown();
  }
  function removeTyping() {
    const t = document.getElementById('typing-row');
    if (t) t.remove();
  }

  function scrollDown() { wrap.scrollTop = wrap.scrollHeight; }

  document.querySelectorAll('.suggest button').forEach((b) => {
    b.addEventListener('click', () => {
      input.value = b.dataset.q || b.textContent;
      window.sendMessage();
    });
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') window.sendMessage(); });
}
