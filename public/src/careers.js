import { api, el, toast, esc, openModal, closeModal, siteUrl } from './utils.js?v=39';
import { iconSvg, careerIcon } from './icons.js?v=39';

let _careerData = [];
let _careerCats = [];
let _activeCat = null;
let _careerDomains = [];
let _careerStreams = [];
let _careerClasses = [];
let _forYou = false;
let _userAcad = null;

const CAREER_STREAM_MAP = {
  'Engineering': 'Engineering',
  'Medical & Health': 'Medical',
  'Sciences': 'Science',
  'Commerce & Finance': 'Commerce',
  'Management': 'Management',
  'Law': 'Law',
  'Design & Creative': 'Design',
  'Civil Services & Government': 'Arts',
  'Defence': 'Engineering',
  'Agriculture': 'Agriculture',
  'Media & Communication': 'Arts',
  'Hospitality & Sports': 'Management',
};

export function initCareers() {
  const openBtn = el('career-quiz-open');
  if (openBtn) openBtn.addEventListener('click', () => openQuiz());

  // Category chips
  const cats = el('career-cats');
  if (cats) cats.addEventListener('click', (e) => {
    const b = e.target.closest('.cat-chip');
    if (!b) return;
    _activeCat = (b.dataset.cat === '__all') ? null : b.dataset.cat;
    document.querySelectorAll('#career-cats .cat-chip').forEach((x) => x.classList.toggle('active', x === b));
    applyCareerFilters();
  });

  // Filter bar wiring (college-style: search row + Filters modal)
  const cfq = el('cf-q');
  if (cfq) cfq.addEventListener('input', debounceInput(applyCareerFilters, 250));
  const ftrig = el('career-filter-trigger');
  if (ftrig) ftrig.addEventListener('click', () => openModal('career-filter-modal'));
  const fapply = el('career-filter-apply');
  if (fapply) fapply.addEventListener('click', () => { closeModal('career-filter-modal'); applyCareerFilters(); });
  ['cf-class', 'cf-stream', 'cf-domain'].forEach((id) => {
    const node = el(id);
    if (node) node.addEventListener('change', applyCareerFilters);
  });
  const forYou = el('cf-for-you');
  if (forYou) forYou.addEventListener('click', toggleForYou);
  const reset = el('cf-reset');
  if (reset) reset.addEventListener('click', resetCareerFilters);

  // Quiz option selection (single-select per group)
  document.querySelectorAll('#career-quiz-modal .cq-opts').forEach((group) => {
    group.addEventListener('click', (e) => {
      const opt = e.target.closest('.cq-opt');
      if (!opt) return;
      group.querySelectorAll('.cq-opt').forEach((o) => o.classList.remove('active'));
      opt.classList.add('active');
    });
  });

  const submit = el('cq-submit');
  if (submit) submit.addEventListener('click', submitQuiz);

  // Reset quiz when reopened
  const m = el('career-quiz-modal');
  if (m) {
    const obs = new MutationObserver(() => {
      if (m.classList.contains('open')) resetQuiz();
    });
    obs.observe(m, { attributes: true, attributeFilter: ['class'] });
  }

  loadCareers();
}

export function loadCareers() {
  api('/careers').then((d) => {
    _careerData = (d && d.careers) || [];
    _careerCats = (d && d.categories) || [];
    _careerDomains = (d && d.domains) || [];
    _careerStreams = (d && d.streams) || [];
    _careerClasses = (d && d.classes) || [];
    renderCatChips();
    populateFilters();
    applyCareerFilters();
    const c = el('career-count');
    if (c) c.textContent = _careerData.length + ' career paths';
  }).catch(() => {
    const c = el('career-count');
    if (c) c.textContent = 'Could not load careers.';
  });
}
window.loadCareers = loadCareers;

function populateFilters() {
  const fill = (id, items, label) => {
    const s = el(id);
    if (!s) return;
    if (s.options.length <= 1) {
      items.forEach((v) => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v;
        s.appendChild(o);
      });
    }
  };
  fill('cf-class', _careerClasses);
  fill('cf-stream', _careerStreams);
  fill('cf-domain', _careerDomains);
}

function currentCareerFilter() {
  return {
    cls: (el('cf-class') && el('cf-class').value) || null,
    stream: (el('cf-stream') && el('cf-stream').value) || null,
    domain: (el('cf-domain') && el('cf-domain').value) || null,
    q: (el('cf-q') && el('cf-q').value || '').trim().toLowerCase(),
  };
}

function debounceInput(fn, ms) {
  let t = null;
  return function () {
    clearTimeout(t);
    const args = arguments;
    t = setTimeout(() => fn.apply(null, args), ms);
  };
}

function applyCareerFilters() {
  const f = currentCareerFilter();
  let list = _careerData.filter((c) => {
    if (_activeCat && c.category !== _activeCat) return false;
    if (f.cls && !(c.classes || []).includes(f.cls)) return false;
    if (f.stream) {
      const s = c.streams || [];
      if (s.length && !s.includes(f.stream)) return false;
    }
    if (f.domain && !(c.domains || []).includes(f.domain)) return false;
    if (f.q) {
      const hay = (c.title + ' ' + c.category + ' ' + (c.tagline || '') + ' ' + (c.domains || []).join(' ')).toLowerCase();
      if (!hay.includes(f.q)) return false;
    }
    return true;
  });
  if (_forYou && _userAcad) {
    const us = (_userAcad.stream || '').trim();
    list = list.slice().sort((a, b) => forYouScore(b, us) - forYouScore(a, us));
  }
  renderCareerList(list);
  renderActiveFilters();
}

function renderActiveFilters() {
  const f = currentCareerFilter();
  const chips = [];
  if (f.cls) chips.push({ k: 'cls', label: f.cls });
  if (f.stream) chips.push({ k: 'stream', label: f.stream });
  if (f.domain) chips.push({ k: 'domain', label: f.domain });
  if (_forYou) chips.push({ k: 'foryou', label: 'For you' });
  const wrap = el('career-active-filters');
  if (wrap) wrap.innerHTML = chips.map((c) =>
    '<button class="af-chip" data-k="' + esc(c.k) + '">' + esc(c.label) + ' <span>&times;</span></button>'
  ).join('');
  if (wrap) wrap.querySelectorAll('.af-chip').forEach((b) => b.addEventListener('click', () => clearFilter(b.dataset.k)));
  const cnt = el('career-filter-count');
  if (cnt) { cnt.textContent = String(chips.length); cnt.style.display = chips.length ? '' : 'none'; }
}

function clearFilter(k) {
  if (k === 'cls') { const n = el('cf-class'); if (n) n.value = ''; }
  else if (k === 'stream') { const n = el('cf-stream'); if (n) n.value = ''; }
  else if (k === 'domain') { const n = el('cf-domain'); if (n) n.value = ''; }
  else if (k === 'foryou') { _forYou = false; const b = el('cf-for-you'); if (b) b.classList.remove('active'); const nt = el('cf-note'); if (nt) nt.textContent = ''; }
  applyCareerFilters();
}

function forYouScore(c, userStream) {
  const s = c.streams || [];
  if (userStream && s.length && s.includes(userStream)) return 2;
  if (!s.length) return 1;
  return 0;
}

async function toggleForYou() {
  _forYou = !_forYou;
  const btn = el('cf-for-you');
  if (btn) btn.classList.toggle('active', _forYou);
  const note = el('cf-note');
  if (_forYou) {
    try {
      const a = await api('/documents/academic');
      _userAcad = (a && a.exam) ? a : null;
    } catch (e) { _userAcad = null; }
    if (_userAcad && _userAcad.exam) {
      const cs = el('cf-class'); if (cs) cs.value = _userAcad.exam;
      const st = el('cf-stream');
      if (st && _userAcad.stream) {
        const opt = Array.from(st.options).some((o) => o.value === _userAcad.stream);
        if (opt) st.value = _userAcad.stream;
      }
      if (note) note.textContent = 'Personalized for your ' + _userAcad.exam +
        (_userAcad.stream ? ' (' + _userAcad.stream + ')' : '') + ' profile';
    } else if (note) {
      note.textContent = 'Add your marks (Profile → Marks) to personalize this list.';
    }
  } else if (note) {
    note.textContent = '';
  }
  applyCareerFilters();
}

function resetCareerFilters() {
  ['cf-class', 'cf-stream', 'cf-domain'].forEach((id) => { const n = el(id); if (n) n.value = ''; });
  const q = el('cf-q'); if (q) q.value = '';
  _forYou = false;
  const btn = el('cf-for-you'); if (btn) btn.classList.remove('active');
  const note = el('cf-note'); if (note) note.textContent = '';
  _activeCat = null;
  document.querySelectorAll('#career-cats .cat-chip').forEach((x) => x.classList.toggle('active', x.dataset.cat === '__all'));
  applyCareerFilters();
}

function renderCatChips() {
  const wrap = el('career-cats');
  if (!wrap) return;
  const chips = ['<button class="cat-chip active" data-cat="__all">All</button>']
    .concat(_careerCats.map((c) => '<button class="cat-chip" data-cat="' + esc(c) + '">' + esc(c) + '</button>'));
  wrap.innerHTML = chips.join('');
}

function renderCareerList(list) {
  const grid = el('careers-grid');
  if (!grid) return;
  if (!list.length) { grid.innerHTML = '<div class="slot-skeleton">No careers match these filters.</div>'; return; }
  grid.innerHTML = list.map((c) =>
    '<button class="career-card" data-id="' + esc(c.id) + '">' +
      '<div class="cc-ic">' + iconSvg(careerIcon(c.category, c.title)) + '</div>' +
      '<div class="cc-cat">' + esc(c.category) + '</div>' +
      '<div class="cc-title">' + esc(c.title) + '</div>' +
      '<div class="cc-tag">' + esc(c.tagline || '') + '</div>' +
    '</button>'
  ).join('');
  grid.querySelectorAll('.career-card').forEach((b) => {
    b.addEventListener('click', () => openCareer(b.dataset.id));
  });
  const cnt = el('career-count');
  if (cnt) cnt.textContent = list.length + ' of ' + _careerData.length + ' career paths';
}

export function openCareer(id) {
  api('/careers/' + id).then((d) => {
    const c = d && d.career;
    if (!c) { toast('Career not found', 'info'); return; }
    const title = el('career-page-title');
    if (title) title.innerHTML = iconSvg(careerIcon(c.category, c.title)) + ' ' + esc(c.title);
    const body = el('career-page-body');
    if (body) body.innerHTML = careerHTML(c);
    body.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', () => openCareer(b.dataset.id)));
    body.querySelectorAll('[data-company]').forEach((b) => b.addEventListener('click', () => openCompany(b.dataset.company)));
    const ask = el('career-ask-veda');
    if (ask) ask.addEventListener('click', () => {
      const prompt = 'Give me a clear roadmap to become a ' + c.title + ' in India: required exams, top colleges, skills to build, and the first 3 steps I should take now.';
    if (window.askVeda) window.askVeda(prompt);
    else window.setViewNav('veda', true);
  });
  const explore = el('career-explore-colleges');
  if (explore) explore.addEventListener('click', () => {
    const stream = CAREER_STREAM_MAP[c.category] || '';
    if (window.openCollegeForCourse) window.openCollegeForCourse(c.title, stream);
    else window.setViewNav('college', true);
  });
  window.openPage('career-detail');
  }).catch(() => toast('Could not open career', 'info'));
}
window.openCareer = openCareer;

function careerHTML(c) {
  const list = (arr, join = ', ') => (arr && arr.length) ? arr.map((x) => esc(x)).join(join) : '—';
  const steps = (c.roadmap || []).map((s, i) => '<li><b>' + (i + 1) + '.</b> ' + esc(s) + '</li>').join('');
  const related = (c.related_careers || []).map((r) =>
    '<button class="rel-chip" data-id="' + esc(r.id) + '">' + iconSvg(careerIcon(r.category, r.title)) + ' ' + esc(r.title) + '</button>'
  ).join('');
  return (
    '<div class="career-detail">' +
      '<div class="cd-hero">' +
        '<div><div class="cd-cat">' + esc(c.category) + '</div>' +
        '<h2>' + esc(c.title) + '</h2>' +
        '<p class="cd-tag">' + esc(c.tagline || '') + '</p></div>' +
      '</div>' +

      '<div class="row gap" style="margin:6px 0 14px">' +
        '<button class="btn primary" id="career-ask-veda">Ask Veda about this</button>' +
        '<button class="btn" id="career-explore-colleges">Explore colleges</button>' +
      '</div>' +

      section('About', '<p>' + esc(c.description || '') + '</p>') +
      twoCol('Entrance Exams', list(c.exams), 'Eligibility', esc(c.eligibility || '—')) +
      section('Top Colleges', '<div class="dm-chips">' + (c.top_colleges || []).map((x) => '<span class="dm-chip">' + esc(x) + '</span>').join('') + '</div>') +
       section('Key Skills', '<div class="dm-chips">' + (c.skills || []).map((x) => '<span class="dm-chip">' + esc(x) + '</span>').join('') + '</div>') +
       twoCol('Scope', esc(c.scope || '—'), 'Salary', esc(c.salary || '—')) +
       section('Growth', '<p>' + esc(c.growth || '') + '</p>') +
       (companiesHTML(c.companies) ? section('Top companies that hire', companiesHTML(c.companies)) : '') +
       section('Your Roadmap', '<ol class="cd-steps">' + steps + '</ol>') +
       (related ? section('Related careers', '<div class="rel-wrap">' + related + '</div>') : '') +
    '</div>'
  );
}

function section(title, inner) {
  return '<div class="dm-sec"><h4>' + esc(title) + '</h4>' + inner + '</div>';
}
function companiesHTML(companies) {
  if (!companies || !companies.length) return '';
  return '<div class="co-wrap">' + companies.map((co) =>
    '<button class="co-chip" data-company="' + esc(co.id) + '">' +
      '<span class="co-ic">' + iconSvg('briefcase') + '</span>' +
      '<span class="co-meta"><span class="co-nm">' + esc(co.name) + '</span>' +
      '<span class="co-sec">' + esc(co.sector || '') + '</span></span>' +
    '</button>'
  ).join('') + '</div>';
}
function twoCol(a, av, b, bv) {
  return '<div class="dm-grid2">' +
    '<div class="dm-sec"><h4>' + esc(a) + '</h4><p>' + av + '</p></div>' +
    '<div class="dm-sec"><h4>' + esc(b) + '</h4><p>' + bv + '</p></div></div>';
}

/* ── Career Q&A (short survey → AI guidance) ── */
function openQuiz() { resetQuiz(); openModal('career-quiz-modal'); }

function resetQuiz() {
  document.querySelectorAll('#career-quiz-modal .cq-opt').forEach((o) => o.classList.remove('active'));
  const notes = el('cq-notes'); if (notes) notes.value = '';
  const res = el('cq-result'); if (res) res.innerHTML = '';
  const btn = el('cq-submit'); if (btn) { btn.disabled = false; btn.textContent = 'Get my recommendation'; }
}

function submitQuiz() {
  const answers = {};
  document.querySelectorAll('#career-quiz-modal .cq-opts').forEach((g) => {
    const sel = g.querySelector('.cq-opt.active');
    if (sel) answers[g.dataset.q] = sel.dataset.v;
  });
  const notes = el('cq-notes');
  if (notes && notes.value.trim()) answers.notes = notes.value.trim();

  if (!answers.field && !answers.priority && !answers.route) {
    toast('Pick at least one option so Veda can help.', 'info');
    return;
  }

  const btn = el('cq-submit');
  if (btn) { btn.disabled = true; btn.textContent = 'Analyzing…'; }
  const res = el('cq-result');
  if (res) res.innerHTML = '<div class="slot-skeleton">Veda is matching your answers to the best career…</div>';

  const user = (typeof getUser === 'function' && getUser()) || {};
  api('/veda/career-guidance', {
    method: 'POST',
    body: JSON.stringify({ user_id: user.id || 'demo', answers: answers, language: (typeof getLang === 'function' && getLang()) || 'English' }),
  }).then((d) => {
    const g = d && d.guidance;
    if (res) res.innerHTML = renderGuidance(g);
    res.querySelectorAll('[data-go-career]').forEach((b) => b.addEventListener('click', () => {
      const id = b.dataset.goCareer;
      closeModal('career-quiz-modal');
      openCareer(id);
    }));
    const ask = res.querySelector('#cq-ask-veda');
    if (ask) ask.addEventListener('click', () => {
      const t = (g && g.title) || 'this career';
      if (window.askVeda) window.askVeda('Help me plan to become a ' + t + ' in India.');
    });
  }).catch(() => {
    if (res) res.innerHTML = '<div class="slot-skeleton">Could not reach Veda. Please try again.</div>';
    if (btn) { btn.disabled = false; btn.textContent = 'Get my recommendation'; }
  });
}

function renderGuidance(g) {
  if (!g) return '<div class="slot-skeleton">No recommendation available.</div>';
  const title = g.title || 'your best-fit path';
  const match = (typeof g.match === 'number') ? g.match : null;
  const steps = (g.next_steps || []).map((s) => '<li>' + esc(s) + '</li>').join('');
  const also = (g.also_consider || []).filter(Boolean).map((id) =>
    '<button class="rel-chip" data-go-career="' + esc(id) + '">' + esc(id.replace(/-/g, ' ')) + '</button>'
  ).join('');
  return (
    '<div class="guidance">' +
      '<div class="g-head">' +
        '<div class="g-badge">' + iconSvg(careerIcon(g.category, g.title)) + '</div>' +
        '<div><div class="g-cat">' + esc(g.category || 'Recommended') + '</div>' +
        '<h3>' + esc(title) + '</h3></div>' +
        (match != null ? '<div class="g-match">' + match + '%<span>match</span></div>' : '') +
      '</div>' +
      (g.reasoning ? '<p class="g-reason">' + esc(g.reasoning) + '</p>' : '') +
      (steps ? '<div class="dm-sec"><h4>Next steps</h4><ul>' + steps + '</ul></div>' : '') +
      (also ? '<div class="dm-sec"><h4>You may also consider</h4><div class="rel-wrap">' + also + '</div></div>' : '') +
      '<div class="row gap" style="margin-top:12px">' +
        (g.career_id ? '<button class="btn primary" data-go-career="' + esc(g.career_id) + '">Open this career →</button>' : '') +
        '<button class="btn" id="cq-ask-veda">Ask Veda</button>' +
      '</div>' +
    '</div>'
  );
}

/* ── Company detail pop-up ── */
export function openCompany(id) {
  const card = el('company-card');
  if (card) card.innerHTML = '<div class="dm-sec"><div class="slot-skeleton">Loading company…</div></div>';
  openModal('company-modal');
  api('/careers/companies/' + id).then((d) => {
    const co = d && d.company;
    if (!co) { if (card) card.innerHTML = '<div class="dm-sec">Company not found.</div>'; return; }
    if (card) card.innerHTML = companyHTML(co);
    card.querySelectorAll('[data-go-career]').forEach((b) => b.addEventListener('click', () => {
      closeModal('company-modal');
      openCareer(b.dataset.goCareer);
    }));
    const w = card.querySelector('#co-open-site');
    if (w) w.addEventListener('click', () => { const url = siteUrl(co.website); if (url) window.open(url, '_blank', 'noopener'); });
  }).catch(() => {
    if (card) card.innerHTML = '<div class="dm-sec">Could not load company details.</div>';
  });
}
window.openCompany = openCompany;

function companyHTML(co) {
  const rel = (co.related_careers || []).map((r) =>
    '<button class="rel-chip" data-go-career="' + esc(r.id) + '">' + esc(r.title) + '</button>'
  ).join('');
  return (
    '<button class="modal-x" data-close onclick="closeCompany()">&times;</button>' +
    '<div class="company-detail">' +
      '<div class="cd-hero">' +
        '<div class="cd-ic">' + iconSvg('briefcase') + '</div>' +
        '<div><div class="cd-cat">' + esc(co.sector || 'Company') + '</div>' +
        '<h2>' + esc(co.name) + '</h2></div>' +
      '</div>' +
      (co.description ? '<div class="dm-sec"><h4>About</h4><p>' + esc(co.description) + '</p></div>' : '') +
      (co.website ? '<div class="dm-sec"><button class="btn primary" id="co-open-site">🌐 Visit official website ↗</button></div>' : '') +
      (rel ? '<div class="dm-sec"><h4>Careers here relate to</h4><div class="rel-wrap">' + rel + '</div></div>' : '') +
    '</div>'
  );
}

window.closeCompany = function () { closeModal('company-modal'); };
