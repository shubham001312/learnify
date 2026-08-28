import { api, el, toast, esc, openModal, closeModal } from './utils.js?v=23';

let _careerData = [];
let _careerCats = [];
let _activeCat = null;

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
    renderCareers(_careerData);
  });

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
    renderCatChips();
    renderCareers(_careerData);
    const c = el('career-count');
    if (c) c.textContent = _careerData.length + ' career paths';
  }).catch(() => {
    const c = el('career-count');
    if (c) c.textContent = 'Could not load careers.';
  });
}
window.loadCareers = loadCareers;

function renderCatChips() {
  const wrap = el('career-cats');
  if (!wrap) return;
  const chips = ['<button class="cat-chip active" data-cat="__all">All</button>']
    .concat(_careerCats.map((c) => '<button class="cat-chip" data-cat="' + esc(c) + '">' + esc(c) + '</button>'));
  wrap.innerHTML = chips.join('');
}

function renderCareers(list) {
  const grid = el('careers-grid');
  if (!grid) return;
  const shown = _activeCat ? list.filter((c) => c.category === _activeCat) : list;
  if (!shown.length) { grid.innerHTML = '<div class="slot-skeleton">No careers in this category.</div>'; return; }
  grid.innerHTML = shown.map((c) =>
    '<button class="career-card" data-id="' + esc(c.id) + '">' +
      '<div class="cc-ic">' + (c.icon || '🎯') + '</div>' +
      '<div class="cc-cat">' + esc(c.category) + '</div>' +
      '<div class="cc-title">' + esc(c.title) + '</div>' +
      '<div class="cc-tag">' + esc(c.tagline || '') + '</div>' +
    '</button>'
  ).join('');
  grid.querySelectorAll('.career-card').forEach((b) => {
    b.addEventListener('click', () => openCareer(b.dataset.id));
  });
}

export function openCareer(id) {
  api('/careers/' + id).then((d) => {
    const c = d && d.career;
    if (!c) { toast('Career not found', 'info'); return; }
    const title = el('career-page-title');
    if (title) title.innerHTML = (c.icon || '🎯') + ' ' + esc(c.title);
    const body = el('career-page-body');
    if (body) body.innerHTML = careerHTML(c);
    body.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', () => openCareer(b.dataset.id)));
    const ask = el('career-ask-veda');
    if (ask) ask.addEventListener('click', () => {
      const prompt = 'Give me a clear roadmap to become a ' + c.title + ' in India: required exams, top colleges, skills to build, and the first 3 steps I should take now.';
    if (window.askVeda) window.askVeda(prompt);
    else window.setViewNav('veda', true);
  });
  const explore = el('career-explore-colleges');
  if (explore) explore.addEventListener('click', () => window.setViewNav('college', true));
  window.openPage('career-detail');
  }).catch(() => toast('Could not open career', 'info'));
}
window.openCareer = openCareer;

function careerHTML(c) {
  const list = (arr, join = ', ') => (arr && arr.length) ? arr.map((x) => esc(x)).join(join) : '—';
  const steps = (c.roadmap || []).map((s, i) => '<li><b>' + (i + 1) + '.</b> ' + esc(s) + '</li>').join('');
  const related = (c.related_careers || []).map((r) =>
    '<button class="rel-chip" data-id="' + esc(r.id) + '">' + esc(r.icon || '•') + ' ' + esc(r.title) + '</button>'
  ).join('');
  return (
    '<div class="career-detail">' +
      '<div class="cd-hero">' +
        '<div class="cd-ic">' + (c.icon || '🎯') + '</div>' +
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
      section('Your Roadmap', '<ol class="cd-steps">' + steps + '</ol>') +
      (related ? section('Related careers', '<div class="rel-wrap">' + related + '</div>') : '') +
    '</div>'
  );
}

function section(title, inner) {
  return '<div class="dm-sec"><h4>' + esc(title) + '</h4>' + inner + '</div>';
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
        '<div class="g-badge">' + (g.icon || '🎯') + '</div>' +
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
