import { api, setToken, getToken, clearToken, setUser, clearUser, el, toast } from './utils.js?v=54';

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
  el('auth-extra-fields').style.display = m === 'register' ? '' : 'none';
  el('auth-submit').textContent = m === 'register' ? 'Create Account' : 'Login';
  el('auth-err').textContent = '';
}

function submit() {
  const email = el('auth-email').value.trim();
  const pass = el('auth-pass').value;
  if (!email || !pass) { el('auth-err').textContent = 'Email and password are required.'; return; }
  if (mode === 'register' && pass.length < 10) {
    el('auth-err').textContent = 'Password must be at least 10 characters.';
    return;
  }
  const btn = el('auth-submit');
  btn.disabled = true;

  const done = () => { btn.disabled = false; };

  if (mode === 'register') {
    const payload = {
      email, password: pass,
      name: el('auth-name').value.trim() || email.split('@')[0],
      language: el('auth-lang').value,
      school: el('auth-school').value.trim(),
      board: el('auth-board').value.trim(),
      college: el('auth-college').value.trim(),
      dob: el('auth-dob').value || ''
    };
    register(payload).then((d) => {
      if (d && d.session) {
        toast('Account created. Welcome to Learnify!', 'ok');
        location.reload();
      } else if (d && d.needs_confirmation) {
        showConfirm(email);
        done();
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

  const cb = document.getElementById('confirm-back');
  if (cb) cb.addEventListener('click', (e) => {
    e.preventDefault();
    const cm = document.getElementById('confirm-modal');
    if (cm) cm.classList.remove('open');
    openLogin();
  });

  handleConfirmRedirect();
}

function showConfirm(email) {
  const box = document.getElementById('confirm-modal');
  if (!box) return;
  const em = document.getElementById('confirm-email');
  if (em) em.textContent = email || '';
  const am = document.getElementById('auth-modal');
  if (am) am.classList.remove('open');
  box.classList.add('open');
  const g = document.getElementById('confirm-gmail');
  if (g && email) {
    g.href = 'https://mail.google.com/mail/u/0/#search/' + encodeURIComponent(email);
  }
}

export function handleConfirmRedirect() {
  try {
    const url = new URL(location.href);
    const code = url.searchParams.get('code');
    let token = null;
    if (location.hash && location.hash.includes('access_token')) {
      const params = new URLSearchParams(location.hash.slice(1));
      token = params.get('access_token');
    }
    if (!code && !token) return;
    const q = code
      ? ('?code=' + encodeURIComponent(code))
      : ('?access_token=' + encodeURIComponent(token));
    api('/auth/confirm' + q).then((d) => {
      if (d && d.session) {
        setToken(d.session.access_token);
        setUser(d.user);
        history.replaceState({}, '', location.pathname);
        location.hash = '';
        toast('Email confirmed — you are logged in!', 'ok');
        setTimeout(() => location.reload(), 600);
      } else {
        toast('Confirmation incomplete. Please log in.', 'info');
      }
    }).catch(() => toast('Confirmation failed. Please log in.', 'info'));
  } catch (_) {}
}

export function openLogin() {
  setMode('login');
  document.getElementById('auth-modal').classList.add('open');
}
