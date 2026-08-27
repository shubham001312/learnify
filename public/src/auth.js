import { api, setToken, getToken, clearToken, setUser, clearUser, el, toast } from './utils.js';

let mode = 'login';

export function login(email, password) {
  return api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  }).then((data) => {
    if (data && data.session && data.session.access_token) setToken(data.session.access_token);
    if (data && data.user) setUser(data.user);
    return data;
  });
}

export function register(data) {
  return api('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data)
  }).then((d) => {
    if (d && d.session && d.session.access_token) setToken(d.session.access_token);
    if (d && d.user) setUser(d.user);
    return d;
  });
}

export function logout() {
  clearToken();
  clearUser();
  try { localStorage.removeItem("learnify_chat"); } catch (_) {}
}

export function me() {
  return api('/auth/me');
}

export function requireAuth(openLogin) {
  if (getToken()) return true;
  if (openLogin) openLogin();
  return false;
}

function setMode(m) {
  mode = m;
  document.querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('active', b.dataset.auth === m));
  el('auth-name-field').style.display = m === 'register' ? '' : 'none';
  el('auth-lang-field').style.display = m === 'register' ? '' : 'none';
  el('auth-submit').textContent = m === 'register' ? 'Create Account' : 'Login';
  el('auth-err').textContent = '';
}

function submit() {
  const email = el('auth-email').value.trim();
  const pass = el('auth-pass').value;
  if (!email || !pass) { el('auth-err').textContent = 'Email and password are required.'; return; }
  const btn = el('auth-submit');
  btn.disabled = true;

  const done = () => { btn.disabled = false; };

  if (mode === 'register') {
    const payload = {
      email, password: pass,
      name: el('auth-name').value.trim() || email.split('@')[0],
      language: el('auth-lang').value
    };
    register(payload).then((d) => {
      if (d && d.user) {
        toast('Account created. Welcome to Learnify!', 'ok');
        location.reload();
      } else {
        el('auth-err').textContent = 'Registration did not return a user.';
        done();
      }
    }).catch((err) => { el('auth-err').textContent = err.message; done(); });
  } else {
    login(email, pass).then((d) => {
      if (d && d.session) {
        toast('Logged in successfully.', 'ok');
        location.reload();
      } else {
        el('auth-err').textContent = 'Login failed. Check your credentials.';
        done();
      }
    }).catch((err) => { el('auth-err').textContent = err.message; done(); });
  }
}

export function initAuth() {
  document.querySelectorAll('.seg-btn').forEach((b) => {
    b.addEventListener('click', () => setMode(b.dataset.auth));
  });
  const form = el('auth-form');
  if (form) form.addEventListener('submit', (e) => { e.preventDefault(); submit(); });

  document.querySelectorAll('[data-close]').forEach((b) => {
    b.addEventListener('click', () => b.closest('.modal').classList.remove('open'));
  });
  document.querySelectorAll('.modal').forEach((m) => {
    m.addEventListener('click', (e) => { if (e.target === m) m.classList.remove('open'); });
  });
}

export function openLogin() {
  setMode('login');
  document.getElementById('auth-modal').classList.add('open');
}
