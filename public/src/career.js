import { api, el, qs, esc } from './utils.js?v=14';

let scholarships = [];

export function initCareer() {
  const list = el('college-list');
  if (!list) return;

  const search = el('college-search');
  const stateSel = el('f-state');
  const countEl = el('college-count');
  const loadMore = el('college-loadmore');
  const activeEl = el('active-filters');
  const filterTrigger = el('filter-trigger');

  const PAGE = 30;
  let currentType = '';
  let currentState = '';
  let currentStream = '';
  let currentMinPkg = null;
  let currentMinRank = null;
  let currentSort = 'default';
  let currentQ = '';
  let offset = 0;
  let total = 0;
  let moreLoading = false;
  let allLoaded = false;
  let reqToken = 0;
  const colMap = {};

  // Populate state dropdown
  api('/colleges/states').then((d) => {
    const states = (d && d.states) || [];
    stateSel.insertAdjacentHTML('beforeend',
      states.map((s) => '<option value="' + esc(s) + '">' + esc(s) + '</option>').join(''));
  }).catch(() => {});

  function typeLabel(t) {
    return t === 'govt' ? 'Government' : t === 'private' ? 'Private' : t === 'top100' ? 'Top Ranked' : 'All';
  }
  function sortLabel(s) {
    return s === 'nirf' ? 'NIRF rank' : s === 'package' ? 'Avg package' : s === 'name' ? 'Name' : '';
  }

  function filters() {
    return {
      type: currentType === 'top100' ? '' : currentType,
      top: currentType === 'top100',
      state: currentState,
      q: currentQ,
      stream: currentStream,
      min_package: currentMinPkg,
      min_rank: currentMinRank,
      sort: currentSort,
    };
  }

  function buildQuery(extra) {
    const f = filters();
    const p = { limit: PAGE, offset: 0 };
    if (f.type) p.type = f.type;
    if (f.top) p.top = true;
    if (f.state) p.state = f.state;
    if (f.q) p.q = f.q;
    if (f.stream) p.stream = f.stream;
    if (f.min_package != null) p.min_package = f.min_package;
    if (f.min_rank != null) p.min_rank = f.min_rank;
    if (f.sort && f.sort !== 'default') p.sort = f.sort;
    if (extra) Object.assign(p, extra);
    return qs(p);
  }

  function updateCount(shown) {
    if (countEl) {
      countEl.textContent = total.toLocaleString() + ' college' + (total === 1 ? '' : 's') +
        (shown < total ? ' · showing ' + shown : '');
    }
    if (loadMore) loadMore.style.display = (offset < total && !allLoaded) ? 'block' : 'none';
  }

  function renderActiveFilters() {
    const chips = [];
    if (currentType && currentType !== 'top100') chips.push(typeLabel(currentType));
    if (currentType === 'top100') chips.push('Top Ranked');
    if (currentState) chips.push(currentState);
    if (currentStream) chips.push(currentStream);
    if (currentMinPkg != null) chips.push('≥ ₹' + currentMinPkg + ' LPA');
    if (currentMinRank != null) chips.push('NIRF ≤ ' + currentMinRank);
    if (currentSort && currentSort !== 'default') chips.push('Sort: ' + sortLabel(currentSort));
    activeEl.innerHTML = chips.map((c) => '<span class="af">' + esc(c) + '</span>').join('') +
      (chips.length ? ' <button class="af-clear" id="af-clear">Clear all</button>' : '');
    const fc = el('filter-count');
    if (fc) { fc.style.display = chips.length ? 'inline-flex' : 'none'; fc.textContent = chips.length; }
    const clr = el('af-clear');
    if (clr) clr.addEventListener('click', resetFilters);
  }

  async function loadInitial() {
    const my = ++reqToken;
    offset = 0;
    allLoaded = false;
    list.innerHTML = '<div class="loading">Loading colleges…</div>';
    try {
      const d = await api('/colleges' + buildQuery());
      if (my !== reqToken) return;
      const cols = (d && d.colleges) || [];
      total = d ? (d.total || cols.length) : cols.length;
      offset = cols.length;
      renderColleges(cols, true);
      updateCount(offset);
      renderActiveFilters();
    } catch (e) {
      if (my !== reqToken) return;
      list.innerHTML = '<div class="empty-state">Failed to load colleges. Please try again.</div>';
    }
  }

  async function loadMoreClick() {
    if (moreLoading || allLoaded) return;
    moreLoading = true;
    try {
      const d = await api('/colleges' + buildQuery({ offset }));
      const cols = (d && d.colleges) || [];
      offset += cols.length;
      renderColleges(cols, false);
      updateCount(offset);
      if (offset >= total) allLoaded = true;
    } catch (e) { /* keep current */ }
    moreLoading = false;
  }

  function statTile(small, value, color) {
    return '<div><small>' + small + '</small><span' + (color ? ' style="color:' + color + '"' : '') + '>' + value + '</span></div>';
  }

  function renderColleges(cols, replace) {
    if (!cols.length && replace) {
      list.innerHTML = '<div class="empty-state">No colleges match your filters. Try a different keyword or filter.</div>';
      return;
    }
    if (replace) list.innerHTML = '';
    const tmp = document.createElement('div');
    tmp.innerHTML = cols.map(collegeCard).join('');
    cols.forEach((c) => { colMap[c.id != null ? c.id : c.name] = c; });
    tmp.querySelectorAll('.college').forEach((card) => {
      card.addEventListener('click', () => {
        const key = card.dataset.id;
        const c = colMap[key];
        if (c && window.openCollegeModal) window.openCollegeModal(c);
      });
    });
    while (tmp.firstChild) list.appendChild(tmp.firstChild);
  }

  function collegeCard(c) {
    const id = c.id != null ? c.id : c.name;
    const type = (c.type || '').toLowerCase();
    const tag = type
      ? '<span class="tag ' + (type === 'private' ? 'priv' : 'govt') + '">' + (type === 'private' ? 'Private' : 'Government') + '</span>'
      : '';
    const rank = c.nirf_rank != null
      ? '<div class="rank"><small>NIRF ' + esc(c.nirf_year || '2024') + '</small><b>#' + esc(c.nirf_rank) + '</b></div>'
      : '';

    const stats = [];
    if (c.nirf_rank != null) stats.push(statTile('NIRF', '#' + esc(c.nirf_rank)));
    if (c.avg_package != null) stats.push(statTile('Avg Package', '₹' + esc(c.avg_package) + ' LPA', 'var(--green)'));
    if (c.placement_pct != null) stats.push(statTile('Placement', esc(c.placement_pct) + '%'));
    if (c.rating != null) stats.push(statTile('Rating', esc(c.rating) + ' ★', 'var(--gold)'));

    const statsHtml = stats.length
      ? '<div class="cstats">' + stats.join('') + '</div>'
      : '<div class="cstats cstats-empty"><div><small>Stats</small><span>Limited — open for details</span></div></div>';

    const recruiters = (c.top_recruiters || []).slice(0, 3).map((r) => esc(r)).join(', ');

    return '' +
      '<div class="college clickable" data-id="' + esc(id) + '">' +
        '<div class="college-top">' +
          '<div>' +
            '<div class="college-name">' + esc(c.name) + (tag ? ' ' + tag : '') + '</div>' +
            '<div class="loc"><svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z"/></svg> ' + esc(c.city || c.location) + (c.state ? ', ' + esc(c.state) : '') + '</div>' +
          '</div>' +
          rank +
        '</div>' +
        statsHtml +
        (recruiters ? '<div class="recruiters"><small>Recruiters:</small> ' + recruiters + '</div>' : '') +
        '<div class="open-hint">Tap to view full details →</div>' +
      '</div>';
  }

  // ---- Filter popup ----
  function syncFilterModal() {
    document.querySelectorAll('#f-type .fpill').forEach((p) => {
      p.classList.toggle('active', (p.dataset.type || '') === currentType);
    });
    if (stateSel) stateSel.value = currentState;
    el('f-stream').value = currentStream;
    el('f-pkg').value = currentMinPkg != null ? currentMinPkg : '';
    el('f-rank').value = currentMinRank != null ? currentMinRank : '';
    el('f-sort').value = currentSort;
  }

  function applyFiltersFromModal() {
    const active = document.querySelector('#f-type .fpill.active');
    currentType = (active && active.dataset.type) || '';
    currentState = stateSel ? stateSel.value : '';
    currentStream = el('f-stream').value.trim();
    const pkg = parseFloat(el('f-pkg').value);
    const rk = parseInt(el('f-rank').value, 10);
    currentMinPkg = isNaN(pkg) ? null : pkg;
    currentMinRank = isNaN(rk) ? null : rk;
    currentSort = el('f-sort').value;
    closeFilterModal();
    loadInitial();
  }

  function resetFilters() {
    currentType = ''; currentState = ''; currentStream = '';
    currentMinPkg = null; currentMinRank = null; currentSort = 'default';
    syncFilterModal();
    closeFilterModal();
    loadInitial();
  }

  function closeFilterModal() {
    const m = el('filter-modal');
    if (m) m.classList.remove('open');
  }

  if (filterTrigger) filterTrigger.addEventListener('click', () => {
    syncFilterModal();
    const m = el('filter-modal');
    if (m) m.classList.add('open');
  });
  const fApply = el('f-apply');
  if (fApply) fApply.addEventListener('click', applyFiltersFromModal);
  const fReset = el('f-reset');
  if (fReset) fReset.addEventListener('click', resetFilters);
  document.querySelectorAll('#f-type .fpill').forEach((p) => {
    p.addEventListener('click', () => {
      document.querySelectorAll('#f-type .fpill').forEach((x) => x.classList.remove('active'));
      p.classList.add('active');
    });
  });

  // ---- Wiring ----
  let debounce;
  if (search) {
    search.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { currentQ = search.value.trim(); loadInitial(); }, 350);
    });
  }
  if (loadMore) loadMore.addEventListener('click', loadMoreClick);

  loadInitial();
}
