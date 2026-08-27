import { api, el, getToken, getUser, setUser, clearToken, clearUser, toast, isAuthed, getLang, setLang } from './utils.js';
import { applyLanguage } from './i18n.js';
import { logout, openLogin } from './auth.js';

const SGPA_KEY = 'learnify_sgpa';

function getSgpa() {
  try { return JSON.parse(localStorage.getItem(SGPA_KEY) || '[]'); } catch (_) { return []; }
}
function setSgpa(arr) {
  try { localStorage.setItem(SGPA_KEY, JSON.stringify(arr)); } catch (_) {}
}

export function initProfile() {
  const token = getToken();
  const loggedOut = el('profile-loggedout');
  const main = el('profile-main');

  if (!token) {
    if (loggedOut) loggedOut.style.display = 'flex';
    if (main) main.style.display = 'none';
    const lb = el('profile-login-btn');
    if (lb) lb.addEventListener('click', () => openLogin());
    return; // nothing else to wire while logged out
  }

  if (loggedOut) loggedOut.style.display = 'none';
  if (main) main.style.display = 'block';

  const user = getUser();
  if (user) applyUser(user);

  api('/auth/me').then((data) => {
    if (data && data.user) {
      applyUser(data.user);
      setUser(data.user);
    }
  }).catch(() => { /* cached */ });

  // language
  const langSel = el('profile-lang');
  if (langSel) {
    langSel.value = getLang();
    langSel.addEventListener('change', () => {
      setLang(langSel.value);
      syncLangUI();
      applyLanguage(langSel.value);
      toast('Language set to ' + langSel.value, 'ok');
    });
  }

  // document upload
  const docForm = el('doc-form');
  if (docForm) {
    docForm.addEventListener('submit', (e) => {
      e.preventDefault();
    const fileInput = el('doc-file');
    if (!fileInput.files.length) return;
    const fname = fileInput.files[0].name;
      if (docQuotaLeft() <= 0) {
        toast('Free plan allows 3 documents. Upgrade to Premium for unlimited.', 'info');
        import('./utils.js').then((m) => m.openModal('premium-modal'));
        return;
      }
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      const status = el('doc-status');
      status.textContent = 'Uploading & scanning…';
      fetch('/api/documents/upload', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token },
        body: fd
      }).then(async (res) => {
        const d = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(d.detail || 'Upload failed');
        if (d.is_synthetic) {
          status.textContent = '⚠️ ' + (d.message || 'Please re-upload a genuine document.');
          status.style.color = '#c0392b';
        } else {
          status.textContent = '✓ Uploaded. Extracted: ' + JSON.stringify(d.extracted || {});
          status.style.color = 'var(--green)';
          if (d.extracted && d.extracted.cgpa) el('stat-cgpa').textContent = d.extracted.cgpa;
          if (d.extracted && d.extracted.marks) el('stat-12th').textContent = d.extracted.marks + '%';
          loadDocs();
          if (window.addNotification) window.addNotification('Document "' + fname + '" processed successfully.');
        }
      }).catch((err) => { status.textContent = '⚠️ ' + err.message; status.style.color = '#c0392b'; });
    });
  }

  // edit profile
  const openEdit = () => {
    const u = getUser() || {};
    el('edit-name').value = u.name || '';
    el('edit-grade').value = u.grade || '';
    el('edit-lang').value = getLang();
    el('edit-status').textContent = '';
    import('./utils.js').then((m) => m.openModal('edit-modal'));
  };
  if (el('profile-edit-pen')) el('profile-edit-pen').addEventListener('click', openEdit);
  if (el('btn-edit')) el('btn-edit').addEventListener('click', openEdit);

  const copyUid = el('profile-uid-copy');
  if (copyUid) copyUid.addEventListener('click', () => {
    const id = (getUser() || {}).id;
    if (!id) return;
    navigator.clipboard.writeText(id)
      .then(() => toast('User ID copied: ' + id, 'ok'))
      .catch(() => toast('Copy failed', 'info'));
  });

  if (el('edit-save')) el('edit-save').addEventListener('click', () => {
    const payload = {
      name: el('edit-name').value.trim(),
      grade: el('edit-grade').value.trim(),
      language: el('edit-lang').value
    };
    const status = el('edit-status');
    status.textContent = 'Saving…';
    status.style.color = 'var(--sub)';
    api('/profile', { method: 'PUT', body: JSON.stringify(payload) })
      .catch(() => null) // offline fallback below
      .then((d) => {
        const merged = Object.assign({}, getUser() || {}, {
          name: payload.name, grade: payload.grade, language: payload.language
        });
        setUser(merged);
        applyUser(merged);
        setLang(payload.language);
        syncLangUI();
        status.textContent = '✓ Profile updated.';
        status.style.color = 'var(--green)';
        toast('Profile updated', 'ok');
        setTimeout(() => import('./utils.js').then((m) => m.closeModal('edit-modal')), 700);
      });
  });

  // documents shortcut
  if (el('btn-docs')) el('btn-docs').addEventListener('click', () => {
    if (el('doc-file')) el('doc-file').click();
  });

  // sgpa
  if (el('btn-sgpa')) el('btn-sgpa').addEventListener('click', () => {
    renderSgpa();
    import('./utils.js').then((m) => m.openModal('sgpa-modal'));
  });
  if (el('sgpa-add')) el('sgpa-add').addEventListener('click', () => {
    const sem = el('sgpa-sem').value.trim();
    const val = parseFloat(el('sgpa-val').value);
    if (!sem || isNaN(val)) { el('sgpa-status').textContent = 'Enter semester & SGPA.'; return; }
    const arr = getSgpa();
    arr.push({ semester: sem, sgpa: val });
    setSgpa(arr);
    api('/sgpa', { method: 'POST', body: JSON.stringify({ semester: sem, sgpa: val }) }).catch(() => null);
    el('sgpa-sem').value = ''; el('sgpa-val').value = '';
    renderSgpa();
    computeCgpa();
    el('sgpa-status').textContent = '✓ Added.';
    el('sgpa-status').style.color = 'var(--green)';
  });

  // settings
  if (el('btn-settings')) el('btn-settings').addEventListener('click', () => {
    el('settings-lang').value = getLang();
    import('./utils.js').then((m) => m.openModal('settings-modal'));
  });
  if (el('settings-save')) el('settings-save').addEventListener('click', () => {
    setLang(el('settings-lang').value);
    syncLangUI();
    applyLanguage(getLang());
    if (el('profile-lang')) el('profile-lang').value = getLang();
    toast('Settings saved', 'ok');
    import('./utils.js').then((m) => m.closeModal('settings-modal'));
  });
  if (el('settings-clear')) el('settings-clear').addEventListener('click', () => {
    ['learnify_user', 'learnify_token', 'learnify_lang', 'learnify_sgpa', 'learnify_veda'].forEach((k) => {
      try { localStorage.removeItem(k); } catch (_) {}
    });
    toast('Local data cleared. Please log in again.', 'info');
    setTimeout(() => location.reload(), 800);
  });

  // upgrade + logout
  if (el('btn-upgrade')) el('btn-upgrade').addEventListener('click', () => {
    import('./utils.js').then((m) => m.openModal('premium-modal'));
  });
  if (el('btn-logout')) el('btn-logout').addEventListener('click', () => {
    logout();
    toast('Logged out.', 'info');
    location.reload();
  });

  loadDocs();
  loadSgpa();
}

function applyUser(u) {
  const name = u.name || 'Student';
  const initial = (name || 'S').charAt(0).toUpperCase();
  if (el('profile-name')) el('profile-name').textContent = name;
  if (el('profile-av')) el('profile-av').textContent = initial;
  if (el('profile-role')) {
    const parts = [];
    if (u.grade) parts.push(u.grade);
    if (u.language) parts.push(u.language);
    el('profile-role').textContent = parts.length ? parts.join(' · ') : (u.email || 'Student');
  }
  if (el('profile-uid')) el('profile-uid').textContent = u.id || '—';
  if (el('top-avatar')) el('top-avatar').classList.add('is-auth');
  if (el('home-name')) el('home-name').textContent = name;
  if (el('profile-badge')) el('profile-badge').style.display = u.premium ? '' : 'none';
  if (el('sub-label')) el('sub-label').textContent = u.premium ? 'Pro ⚡' : 'Free';
  syncLangUI();
}

function syncLangUI() {
  const lang = getLang();
  document.querySelectorAll('.lang').forEach((b) =>
    b.classList.toggle('active', (b.dataset.lang || b.textContent.trim()) === lang));
}

function docQuotaLeft() {
  const used = Number(el('stat-docs') ? el('stat-docs').textContent : 0) || 0;
  const limit = (getUser() && getUser().premium) ? Infinity : 3;
  return Math.max(0, limit - used);
}

function loadDocs() {
  const list = el('doc-list');
  if (!list) return;
  api('/documents').then((data) => {
    const docs = (data && data.documents) || [];
    if (el('stat-docs')) el('stat-docs').textContent = docs.length;
    if (el('doc-count')) el('doc-count').textContent = docs.length + '/3';
    list.innerHTML = docs.map((d) => '' +
      '<div class="sitem"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></div><div class="info"><b>' + esc(d.filename || 'document') + '</b>' +
      '<small>' + (d.is_synthetic ? 'Flagged' : 'Clean') + '</small></div></div>'
    ).join('');
  }).catch(() => { list.innerHTML = ''; });
}

function loadSgpa() {
  api('/sgpa').then((data) => {
    const entries = (data && data.entries) || [];
    if (entries.length) {
      setSgpa(entries.map((e) => ({ semester: e.semester, sgpa: e.sgpa })));
      computeCgpa();
    }
  }).catch(() => { computeCgpa(); });
}

function renderSgpa() {
  const list = el('sgpa-list');
  if (!list) return;
  const arr = getSgpa();
  if (!arr.length) { list.innerHTML = '<small style="color:var(--sub)">No entries yet.</small>'; return; }
  list.innerHTML = arr.map((s) =>
    '<div class="sitem"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1 3 3 6 3s6-2 6-3v-5"/></svg></div><div class="info"><b>Semester ' + esc(s.semester) + '</b><small>SGPA: ' + esc(s.sgpa) + '</small></div></div>'
  ).join('');
}

function computeCgpa() {
  const arr = getSgpa();
  if (!arr.length || !el('stat-cgpa')) return;
  const avg = arr.reduce((a, b) => a + Number(b.sgpa), 0) / arr.length;
  el('stat-cgpa').textContent = avg.toFixed(2);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}
