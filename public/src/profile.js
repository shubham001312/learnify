import { api, el, getToken, getUser, setUser, clearToken, clearUser, toast, isAuthed, getLang, setLang } from './utils.js?v=23';
import { applyLanguage } from './i18n.js?v=23';
import { logout, openLogin } from './auth.js?v=23';

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

  const modal = el('doc-preview-modal');
  if (modal) {
    modal.addEventListener('click', (e) => { if (e.target === modal) closeDocPreview(); });
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.addEventListener('click', closeDocPreview);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modal.classList.contains('show')) closeDocPreview(); });
  }

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
          const ex = d.extracted || {};
          status.textContent = '✓ Uploaded. ' + (ex.exam ? ex.exam + ' marks saved.' : 'Document processed.');
          status.style.color = 'var(--green)';
          if (ex.percentage != null) el('stat-12th').textContent = ex.percentage + '%';
          if (ex.cgpa != null) el('stat-cgpa').textContent = ex.cgpa;
          loadDocs();
          loadAcademic();
          if (window.addNotification) window.addNotification('Document "' + fname + '" processed successfully.');
        }
      }).catch((err) => { status.textContent = '⚠️ ' + err.message; status.style.color = '#c0392b'; });
    });
  }

  const fileInput = el('doc-file');
  if (fileInput) fileInput.addEventListener('change', () => {
    const lbl = el('doc-file-label-text');
    if (lbl) lbl.textContent = fileInput.files.length ? fileInput.files[0].name : 'Choose marksheet (PDF / Image)';
  });

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

function docQuotaLeft() {
  const used = Number(el('stat-docs') ? el('stat-docs').textContent : 0) || 0;
  const limit = (getUser() && getUser().premium) ? Infinity : 3;
  return Math.max(0, limit - used);
}

let currentDocs = [];

function loadDocs() {
  const list = el('doc-list');
  if (!list) return;
  api('/documents').then((data) => {
    const docs = (data && data.documents) || [];
    currentDocs = docs;
    if (el('stat-docs')) el('stat-docs').textContent = docs.length;
    if (el('doc-count')) el('doc-count').textContent = docs.length + '/3';
    if (!docs.length) {
      list.innerHTML = '<small style="color:var(--sub)">No documents yet. Upload your marksheet to get started.</small>';
      return;
    }
    list.innerHTML = docs.map((d, i) => {
      const preview = (d.file_type === 'image' && d.file_data)
        ? '<div class="doc-thumb-wrap"><img class="doc-thumb" src="data:image/jpeg;base64,' + esc(d.file_data) + '" alt="doc"></div>'
        : '<div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></div>';
      const meta = (d.extracted && d.extracted.percentage)
        ? '<small>' + esc(d.extracted.exam || '') + ' · ' + esc(d.extracted.percentage) + '%</small>'
        : '<small>' + (d.is_synthetic ? 'Flagged' : 'Clean') + (d.file_type ? (' · ' + esc(d.file_type)) : '') + '</small>';
      return '<div class="sitem" data-idx="' + i + '" role="button" tabindex="0">' + preview +
        '<div class="info"><b>' + esc(d.filename || 'document') + '</b>' + meta + '</div></div>';
    }).join('');
    list.querySelectorAll('.sitem').forEach((node) => {
      node.addEventListener('click', () => openDocPreview(Number(node.dataset.idx)));
      node.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDocPreview(Number(node.dataset.idx)); }
      });
    });
  }).catch(() => { list.innerHTML = ''; });
}

function openDocPreview(i) {
  const d = currentDocs[i];
  if (!d) return;
  const body = el('doc-preview-body');
  let html = '';
  if (d.file_type === 'image' && d.file_data) {
    html += '<img class="doc-full" src="data:image/jpeg;base64,' + esc(d.file_data) + '" alt="document">';
  } else if (d.file_type === 'pdf' && d.file_data) {
    html += '<div class="pdf-mount"><small>Loading PDF…</small></div>';
  } else {
    html += '<p style="color:var(--sub)">Preview not available for this file.</p>';
  }
  const ex = d.extracted || {};
  if (ex.exam || ex.board || ex.percentage || (ex.marks && Object.keys(ex.marks).length)) {
    let meta = '<div class="doc-meta">';
    if (ex.exam) meta += '<span><b>Exam:</b> ' + esc(ex.exam) + '</span>';
    if (ex.board) meta += '<span><b>Board:</b> ' + esc(ex.board) + '</span>';
    if (ex.year) meta += '<span><b>Year:</b> ' + esc(ex.year) + '</span>';
    if (ex.percentage) meta += '<span><b>Percentage:</b> ' + esc(ex.percentage) + '%</span>';
    meta += '</div>';
    if (ex.marks && Object.keys(ex.marks).length) {
      meta += '<div class="doc-marks"><b>Marks:</b><ul>';
      for (const [k, v] of Object.entries(ex.marks)) meta += '<li>' + esc(k) + ': ' + esc(v) + '</li>';
      meta += '</ul></div>';
    }
    html += meta;
  }
  body.innerHTML = html;
  el('doc-preview-modal').classList.add('show');
  if (d.file_type === 'pdf' && d.file_data) {
    decompressPdfInto(body.querySelector('.pdf-mount'), d.file_data);
  }
}

async function decompressPdfInto(mount, b64) {
  if (!mount) return;
  try {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let j = 0; j < bin.length; j++) bytes[j] = bin.charCodeAt(j);
    const stream = new Response(bytes).body.pipeThrough(new DecompressionStream('gzip'));
    const ab = await new Response(stream).arrayBuffer();
    const url = URL.createObjectURL(new Blob([ab], { type: 'application/pdf' }));
    mount.innerHTML = '<iframe class="pdf-frame" src="' + url + '" title="document"></iframe>';
  } catch (e) {
    mount.innerHTML = '<small style="color:var(--sub)">PDF preview unavailable.</small>';
  }
}

function closeDocPreview() {
  const m = el('doc-preview-modal');
  if (!m) return;
  m.classList.remove('show');
  const frame = m.querySelector('iframe');
  if (frame && frame.src) { try { URL.revokeObjectURL(frame.src); } catch (e) {} }
  el('doc-preview-body').innerHTML = '';
}

function loadAcademic() {
  const list = el('academic-list');
  if (!list) return;
  api('/documents/academic').then((data) => {
    const recs = (data && data.records) || [];
    academicRecs = recs;
    if (el('acad-count')) el('acad-count').textContent = recs.length ? recs.length + ' record' + (recs.length > 1 ? 's' : '') : '';
    if (!recs.length) { list.innerHTML = '<small style="color:var(--sub)">No marks yet — upload your marksheet.</small>'; return; }
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

function openAcadEdit(id) {
  const r = (academicRecs || []).find((x) => x.id === id);
  if (!r) return;
  el('acad-id').value = r.id || '';
  el('acad-exam').value = r.exam || '';
  el('acad-board').value = r.board || '';
  el('acad-year').value = r.year || '';
  el('acad-pct').value = r.percentage != null ? r.percentage : '';
  el('acad-marks').value = (r.marks && typeof r.marks === 'object') ? JSON.stringify(r.marks) : '';
  el('acad-status').textContent = '';
  import('./utils.js').then((m) => m.openModal('academic-modal'));
}

if (el('acad-save')) el('acad-save').addEventListener('click', () => {
  const id = el('acad-id').value;
  if (!id) return;
  let marks = null;
  const mraw = el('acad-marks').value.trim();
  if (mraw) {
    try { marks = JSON.parse(mraw); } catch (_) {
      el('acad-status').textContent = 'Marks must be valid JSON, e.g. {"Math":90,"Science":85}';
      el('acad-status').style.color = '#c0392b';
      return;
    }
  }
  const payload = {};
  if (el('acad-exam').value.trim()) payload.exam = el('acad-exam').value.trim();
  if (el('acad-board').value.trim()) payload.board = el('acad-board').value.trim();
  if (el('acad-year').value.trim()) payload.year = parseInt(el('acad-year').value, 10);
  if (el('acad-pct').value.trim()) payload.percentage = parseFloat(el('acad-pct').value);
  if (marks) payload.marks = marks;
  const st = el('acad-status');
  st.textContent = 'Saving…';
  st.style.color = 'var(--sub)';
  api('/documents/academic/' + id, { method: 'PATCH', body: JSON.stringify(payload) })
    .then(() => {
      st.textContent = '✓ Saved.';
      st.style.color = 'var(--green)';
      loadAcademic();
      setTimeout(() => import('./utils.js').then((m) => m.closeModal('academic-modal')), 600);
    })
    .catch((e) => { st.textContent = '⚠ ' + (e && e.message ? e.message : 'failed'); st.style.color = '#c0392b'; });
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
