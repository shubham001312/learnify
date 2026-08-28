const BASE = '/api';

export function api(path, opts = {}) {
  const token = getToken();
  const headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  if (token) headers['Authorization'] = 'Bearer ' + token;
  return fetch(BASE + path, Object.assign({}, opts, { headers })).then(async (res) => {
    let data = null;
    try { data = await res.json(); } catch (_) { /* ignore */ }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message || data.error)) || ('Request failed (' + res.status + ')');
      throw new Error(msg);
    }
    return data;
  });
}

export function qs(params) {
  const u = new URLSearchParams();
  for (const k in params) {
    const v = params[k];
    if (v !== undefined && v !== null && v !== '') u.set(k, v);
  }
  const s = u.toString();
  return s ? '?' + s : '';
}

export function el(id) {
  return document.getElementById(id);
}

export function formatINR(n) {
  const num = Number(n);
  if (!isFinite(num)) return '₹0';
  return '₹' + num.toLocaleString('en-IN');
}

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

const TOKEN_KEY = 'learnify_token';
const USER_KEY = 'learnify_user';

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch (_) { return null; }
}
export function setToken(t) {
  try { localStorage.setItem(TOKEN_KEY, t); } catch (_) { /* ignore */ }
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch (_) { /* ignore */ }
}

export function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (_) { return null; }
}
export function setUser(u) {
  try { localStorage.setItem(USER_KEY, JSON.stringify(u)); } catch (_) { /* ignore */ }
}
export function clearUser() {
  try { localStorage.removeItem(USER_KEY); } catch (_) { /* ignore */ }
}

export function isAuthed() {
  return !!getToken();
}

export function isPremium() {
  const u = getUser();
  return !!(u && u.premium);
}

const LANG_KEY = 'learnify_lang';
export function getLang() {
  try { return localStorage.getItem(LANG_KEY) || 'English'; } catch (_) { return 'English'; }
}
export function setLang(l) {
  try { localStorage.setItem(LANG_KEY, l); } catch (_) { /* ignore */ }
}

const VEDA_KEY = 'learnify_veda';
function _vedaState() {
  const today = new Date().toISOString().slice(0, 10);
  let data;
  try { data = JSON.parse(localStorage.getItem(VEDA_KEY) || '{}'); } catch (_) { data = {}; }
  if (data.date !== today) data = { date: today, count: 0 };
  return data;
}
export function vedaQuotaLeft() {
  const limit = isPremium() ? Infinity : 10;
  return Math.max(0, limit - _vedaState().count);
}
export function incVeda() {
  const data = _vedaState();
  data.count = (data.count || 0) + 1;
  try { localStorage.setItem(VEDA_KEY, JSON.stringify(data)); } catch (_) { /* ignore */ }
}
export function docQuotaLeft() {
  const used = Number(el('stat-docs') ? el('stat-docs').textContent : 0) || 0;
  const limit = isPremium() ? Infinity : 3;
  return Math.max(0, limit - used);
}

export function toast(msg, kind = 'info') {
  const t = el('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast show ' + kind;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 2600);
}

export function openModal(id) {
  const m = el(id);
  if (m) m.classList.add('open');
}
export function closeModal(id) {
  const m = el(id);
  if (m) m.classList.remove('open');
}

export function onReady(fn) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fn);
  } else {
    fn();
  }
}

// Lightweight, safe markdown renderer for Veda's chat replies.
// Input is HTML-escaped first, so user/AI text can never inject markup.
export function renderMarkdown(src) {
  if (!src) return '';
  const esc = (s) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const inline = (s) => {
    // links [text](https://...)
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, t, u) => {
      const safe = u.replace(/"/g, '%22');
      return `<a href="${safe}" target="_blank" rel="noopener noreferrer">${t}</a>`;
    });
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>'); // bold
    s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>'); // italic
    s = s.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, '$1<em>$2</em>'); // italic _
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>'); // inline code
    return s;
  };

  const lines = esc(src).split('\n');
  let html = '';
  let para = [];
  let listType = null;

  const flushPara = () => {
    if (para.length) {
      html += '<p>' + inline(para.join('<br>')) + '</p>';
      para = [];
    }
  };
  const closeList = () => {
    if (listType) {
      html += '</' + listType + '>';
      listType = null;
    }
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (/^```/.test(line)) {
      flushPara();
      closeList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      i++;
      html += '<pre><code>' + buf.join('\n') + '</code></pre>';
      continue;
    }

    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara();
      closeList();
      html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`;
      i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      flushPara();
      closeList();
      html += '<blockquote>' + inline(line.replace(/^>\s?/, '')) + '</blockquote>';
      i++;
      continue;
    }

    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    if (ul) {
      flushPara();
      if (listType !== 'ul') {
        closeList();
        html += '<ul>';
        listType = 'ul';
      }
      html += '<li>' + inline(ul[1]) + '</li>';
      i++;
      continue;
    }

    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (ol) {
      flushPara();
      if (listType !== 'ol') {
        closeList();
        html += '<ol>';
        listType = 'ol';
      }
      html += '<li>' + inline(ol[1]) + '</li>';
      i++;
      continue;
    }

    if (!line.trim()) {
      flushPara();
      closeList();
      i++;
      continue;
    }

    para.push(line);
    i++;
  }
  flushPara();
  closeList();
  return html;
}
