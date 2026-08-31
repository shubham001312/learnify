import { api, el, getToken, getUser, setUser, clearToken, clearUser, toast, isAuthed, getLang, setLang } from './utils.js?v=59';
import { applyLanguage } from './i18n.js?v=59';
import { logout, openLogin } from './auth.js?v=59';

const SGPA_KEY = 'learnify_sgpa';
let academicRecs = [];

function getSgpa() {
  try { return JSON.parse(localStorage.getItem(SGPA_KEY) || '[]'); } catch (_) { return []; }
}
function setSgpa(arr) {
  try { localStorage.setItem(SGPA_KEY, JSON.stringify(arr)); } catch (_) {}
}

export function initProfile() {
  const STATES = [
    'Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar',
    'Chandigarh', 'Chhattisgarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Goa',
    'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir', 'Jharkhand', 'Karnataka',
    'Kerala', 'Ladakh', 'Lakshadweep', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya',
    'Mizoram', 'Nagaland', 'Odisha', 'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim',
    'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal'
  ];
  const stSel = el('edit-state');
  if (stSel) {
    stSel.insertAdjacentHTML('beforeend',
      STATES.map((s) => '<option value="' + s + '">' + s + '</option>').join(''));
  }
  // College & city suggestion datalists
  api('/colleges?limit=400').then((d) => {
    const dl = document.getElementById('dl-college');
    if (dl) {
      const names = Array.from(new Set(((d && d.colleges) || []).map((c) => c.name).filter(Boolean)));
      dl.innerHTML = names.map((n) => '<option value="' + esc(n) + '"></option>').join('');
    }
  }).catch(() => {});
  api('/colleges/cities').then((d) => {
    const dl = document.getElementById('dl-city');
    if (dl) {
      const cities = (d && d.cities) || [];
      dl.innerHTML = cities.map((c) => '<option value="' + esc(c) + '"></option>').join('');
    }
  }).catch(() => {});

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
      window.learnifyProfile = data.user;
      if (window.renderHero) window.renderHero();
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

  // edit profile
  const openEdit = () => {
    const u = getUser() || {};
    const set = (id, v) => { const e = el(id); if (e) e.value = v || ''; };
    set('edit-name', u.name);
    set('edit-grade', u.grade);
    set('edit-lang', getLang());
    set('edit-phone', u.phone);
    set('edit-gender', u.gender);
    set('edit-state', u.state);
    set('edit-city', u.city);
    set('edit-school', u.school);
    set('edit-board', u.board);
    set('edit-college', u.college);
    set('edit-target', u.target_exam);
    set('edit-dob', u.dob);
    set('edit-bio', u.bio);
    const st = el('edit-status'); if (st) st.textContent = '';
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
      name: (el('edit-name').value || '').trim(),
      grade: (el('edit-grade').value || '').trim(),
      language: el('edit-lang').value,
      school: (el('edit-school').value || '').trim(),
      board: (el('edit-board').value || '').trim(),
      college: (el('edit-college').value || '').trim(),
      dob: (el('edit-dob').value || '').trim(),
      phone: (el('edit-phone').value || '').trim(),
      gender: (el('edit-gender').value || '').trim(),
      state: (el('edit-state').value || '').trim(),
      city: (el('edit-city').value || '').trim(),
      target_exam: (el('edit-target').value || '').trim(),
      bio: (el('edit-bio').value || '').trim(),
    };
    const status = el('edit-status');
    status.textContent = 'Saving…';
    status.style.color = 'var(--sub)';
    api('/auth/profile', { method: 'PUT', body: JSON.stringify(payload) })
      .catch(() => null) // offline fallback below
      .then((d) => {
        const merged = Object.assign({}, getUser() || {}, payload);
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

  loadAcademic();
  loadSgpa();
}

const PERSON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';

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
  const av = el('top-avatar');
  if (av) {
    if (u && (u.id || u.email)) {
      av.classList.add('is-auth');
      av.innerHTML = '<span class="av-init">' + initial + '</span>';
    } else {
      av.classList.remove('is-auth');
      av.innerHTML = PERSON_SVG;
    }
  }
  if (el('home-name')) el('home-name').textContent = name;
    const det = el('profile-details');
    if (det) {
      const rows = [];
      const add = (k, v) => { if (v) rows.push('<div class="pdet"><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>'); };
      add('State', u.state); add('City', u.city); add('School', u.school);
      add('Board', u.board); add('College', u.college); add('Target exam', u.target_exam);
      add('Gender', u.gender); add('Phone', u.phone);
      if (u.age != null) add('Age', u.age);
      det.innerHTML = rows.join('');
      const bioEl = el('profile-bio');
      if (bioEl) bioEl.textContent = u.bio || '';
    }
  if (el('profile-badge')) el('profile-badge').style.display = u.premium ? '' : 'none';
  if (el('sub-label')) el('sub-label').textContent = u.premium ? 'Pro ⚡' : 'Free';
  const mi = el('member-info');
  if (mi) {
    if (u.premium && u.premium_until) {
      mi.innerHTML = '⚡ Pro member until <b>' + fmtDate(u.premium_until) + '</b>';
    } else if (u.created_at) {
      mi.innerHTML = 'Member since <b>' + fmtDate(u.created_at) + '</b>';
    } else {
      mi.innerHTML = 'Free member';
    }
  }
  syncLangUI();
}

function syncLangUI() {
  const lang = getLang();
  document.querySelectorAll('.lang').forEach((b) =>
    b.classList.toggle('active', (b.dataset.lang || b.textContent.trim()) === lang));
}

function loadAcademic() {
  const list = el('academic-list');
  if (!list) return;
  api('/documents/academic').then((data) => {
    const recs = (data && data.records) || [];
    academicRecs = recs;
    if (el('acad-count')) el('acad-count').textContent = recs.length ? recs.length + ' record' + (recs.length > 1 ? 's' : '') : '';
    if (el('stat-docs')) el('stat-docs').textContent = recs.length;
    const tw = recs.find((r) => (r.exam || '').toString().toLowerCase() === '12th');
    if (el('stat-12th')) el('stat-12th').textContent = (tw && tw.percentage != null) ? tw.percentage + '%' : '—';
    if (!recs.length) { list.innerHTML = '<small style="color:var(--sub)">No marks yet — tap “＋ Add” to enter your subjects.</small>'; return; }
    list.innerHTML = recs.map((r) => {
      const marks = (r.marks && typeof r.marks === 'object')
        ? Object.entries(r.marks).map(([k, v]) => esc(k) + ': ' + esc(v)).join(', ')
        : '';
      return '<div class="sitem acad-item">' +
        '<div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1 3 3 6 3s6-2 6-3v-5"/></svg></div>' +
        '<div class="info"><b>' + esc(r.exam || 'Exam') + (r.board ? ' · ' + esc(r.board) : '') + '</b>' +
        '<small>' + (r.percentage != null ? r.percentage + '%' : '') + (marks ? ' · ' + marks : '') + (r.verified ? ' · ✓ verified' : '') + '</small></div>' +
        '<button class="acad-edit" data-edit="' + esc(r.id) + '">Edit</button></div>';
    }).join('');
    list.querySelectorAll('.acad-edit').forEach((b) =>
      b.addEventListener('click', () => openAcadEdit(b.dataset.edit)));
  }).catch(() => { list.innerHTML = ''; });
}

const EXAM_SUBJECTS = {
  '10th': ['Mathematics', 'Science', 'Social Science', 'English', 'Hindi'],
  'Diploma': ['Subject 1', 'Subject 2', 'Subject 3', 'Subject 4', 'Subject 5'],
  'Graduation': ['Semester 1', 'Semester 2', 'Semester 3', 'Semester 4', 'Semester 5', 'Semester 6']
};
const STREAM_SUBJECTS = {
  'PCM': ['Physics', 'Chemistry', 'Mathematics', 'English'],
  'PCMB': ['Physics', 'Chemistry', 'Mathematics', 'Biology', 'English'],
  'PCMc': ['Physics', 'Chemistry', 'Mathematics', 'Computer Science', 'English'],
  'Commerce': ['Accountancy', 'Business Studies', 'Economics', 'English', 'Mathematics'],
  'Humanities': ['History', 'Geography', 'Political Science', 'English', 'Economics'],
  'Arts': ['History', 'Geography', 'Political Science', 'English', 'Fine Arts']
};
let acadCurrentMarks = {};

function populateAcadYear() {
  const sel = el('acad-year');
  if (!sel) return;
  const y = new Date().getFullYear();
  let opts = '<option value="">Select year</option>';
  for (let yr = y + 1; yr >= 2000; yr--) opts += '<option value="' + yr + '">' + yr + '</option>';
  sel.innerHTML = opts;
}

function acadSubjectsFor(exam, stream, marks) {
  if (marks && Object.keys(marks).length) return Object.keys(marks);
  if (exam === '12th') return STREAM_SUBJECTS[stream] || [];
  return EXAM_SUBJECTS[exam] || ['Subject 1', 'Subject 2', 'Subject 3'];
}

function renderAcadSubjects(exam, stream, marks) {
  const wrap = el('acad-subjects');
  if (!wrap) return;
  const subs = acadSubjectsFor(exam, stream, marks);
  wrap.innerHTML = subs.map((s) => {
    const v = (marks && marks[s] != null) ? marks[s] : '';
    return '<div class="acad-row"><label>' + esc(s) + '</label>' +
      '<input type="number" min="0" max="100" step="0.01" class="acad-mark" data-sub="' + esc(s) + '" value="' + esc(v) + '" placeholder="0–100"></div>';
  }).join('');
  wrap.querySelectorAll('.acad-mark').forEach((inp) => inp.addEventListener('input', computeAcadSummary));
  const customWrap = el('acad-custom');
  if (customWrap) {
    customWrap.innerHTML = '';
    const preset = new Set(subs);
    Object.entries(marks || {}).forEach(([k, v]) => {
      if (!preset.has(k)) addCustomRow(customWrap, k, v);
    });
  }
  computeAcadSummary();
}

function addCustomRow(container, name, val) {
  if (!container) return;
  const row = document.createElement('div');
  row.className = 'acad-custom-row';
  row.innerHTML = '<input type="text" class="acad-sub-name" placeholder="Subject name" value="' + esc(name || '') + '">' +
    '<input type="number" min="0" max="100" step="0.01" class="acad-mark-custom" placeholder="0–100" value="' + esc(val != null ? val : '') + '">' +
    '<button type="button" class="acad-rm" title="Remove" aria-label="Remove subject">×</button>';
  row.querySelector('.acad-mark-custom').addEventListener('input', computeAcadSummary);
  row.querySelector('.acad-sub-name').addEventListener('input', computeAcadSummary);
  row.querySelector('.acad-rm').addEventListener('click', () => { row.remove(); computeAcadSummary(); });
  container.appendChild(row);
}

function computeAcadSummary() {
  const wrap = el('acad-subjects');
  const customWrap = el('acad-custom');
  const sumEl = el('acad-summary');
  if (!wrap || !sumEl) return;
  const marks = {};
  let total = 0, count = 0;
  wrap.querySelectorAll('.acad-mark').forEach((inp) => {
    const val = parseFloat(inp.value);
    if (!isNaN(val)) { marks[inp.dataset.sub] = val; total += val; count++; }
  });
  if (customWrap) customWrap.querySelectorAll('.acad-custom-row').forEach((row) => {
    const nm = row.querySelector('.acad-sub-name').value.trim();
    const mv = parseFloat(row.querySelector('.acad-mark-custom').value);
    if (nm && !isNaN(mv)) { marks[nm] = mv; total += mv; count++; }
  });
  acadCurrentMarks = marks;
  if (count === 0) { sumEl.innerHTML = ''; return; }
  const pct = total / count;
  sumEl.innerHTML = '<span><b>Total:</b> ' + total.toFixed(2) + ' / ' + (count * 100) + '</span>' +
    '<span><b>Percentage:</b> ' + pct.toFixed(2) + '%</span>';
}

function openAcadModal(id, rec) {
  el('acad-id').value = id || '';
  const exam = rec ? (rec.exam || '') : '';
  el('acad-exam').value = exam;
  el('acad-board').value = rec ? (rec.board || '') : '';
  el('acad-stream-wrap').style.display = (exam === '12th') ? '' : 'none';
  el('acad-stream').value = '';
  populateAcadYear();
  el('acad-year').value = rec ? (rec.year || '') : '';
  const marks = (rec && rec.marks && typeof rec.marks === 'object') ? rec.marks : {};
  renderAcadSubjects(exam, '', marks);
  el('acad-status').textContent = '';
  import('./utils.js').then((m) => m.openModal('academic-modal'));
}

function openAcadEdit(id) {
  const r = (academicRecs || []).find((x) => x.id === id);
  if (!r) return;
  openAcadModal(id, r);
}

if (el('acad-exam')) el('acad-exam').addEventListener('change', () => {
  const is12 = el('acad-exam').value === '12th';
  el('acad-stream-wrap').style.display = is12 ? '' : 'none';
  if (!is12) el('acad-stream').value = '';
  renderAcadSubjects(el('acad-exam').value, el('acad-stream').value, {});
});
if (el('acad-stream')) el('acad-stream').addEventListener('change', () => {
  renderAcadSubjects(el('acad-exam').value, el('acad-stream').value, {});
});
if (el('acad-add-subject')) el('acad-add-subject').addEventListener('click', () => addCustomRow(el('acad-custom')));

if (el('acad-save')) el('acad-save').addEventListener('click', () => {
  const id = el('acad-id').value;
  const exam = el('acad-exam').value.trim();
  if (!exam) { el('acad-status').textContent = 'Please select an exam.'; el('acad-status').style.color = '#c0392b'; return; }
  const marks = acadCurrentMarks || {};
  if (!Object.keys(marks).length) { el('acad-status').textContent = 'Enter at least one subject mark.'; el('acad-status').style.color = '#c0392b'; return; }
  const total = Object.values(marks).reduce((a, b) => a + Number(b), 0);
  const pct = +(total / Object.keys(marks).length).toFixed(2);
  const payload = { exam: exam, marks: marks, total: total, percentage: pct };
  if (el('acad-board').value.trim()) payload.board = el('acad-board').value.trim();
  if (el('acad-year').value.trim()) payload.year = parseInt(el('acad-year').value, 10);
  const st = el('acad-status');
  st.textContent = 'Saving…'; st.style.color = 'var(--sub)';
  const req = id
    ? api('/documents/academic/' + id, { method: 'PATCH', body: JSON.stringify(payload) })
    : api('/documents/academic', { method: 'POST', body: JSON.stringify(payload) });
  req
    .then(() => {
      st.textContent = '✓ Saved.';
      st.style.color = 'var(--green)';
      loadAcademic();
      if (payload.percentage != null && el('stat-12th')) el('stat-12th').textContent = payload.percentage + '%';
      setTimeout(() => import('./utils.js').then((m) => m.closeModal('academic-modal')), 600);
    })
    .catch((e) => { st.textContent = '⚠ ' + (e && e.message ? e.message : 'failed'); st.style.color = '#c0392b'; });
});

if (el('btn-add-acad')) el('btn-add-acad').addEventListener('click', () => {
  openAcadModal(null, null);
});

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

function fmtDate(s) {
  if (!s) return '';
  try {
    const d = new Date(String(s).slice(0, 19).replace(' ', 'T') + 'Z');
    if (isNaN(d)) return String(s).slice(0, 10);
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch (_) { return String(s).slice(0, 10); }
}
