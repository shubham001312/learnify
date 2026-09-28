// LEARNIFY — runtime SVG charts for reports and dashboards.
//
// Pure presentation: no API calls, no globals, no DOM access. Every export
// returns a self-contained markup string that a view drops straight into
// `innerHTML`, so a chart always draws from whatever the view already
// fetched — there is no second data source and nothing here can go stale.
//
//   barChart([{ label, value, tone? }], opts)  -> svg string
//   donutChart([{ label, value, tone? }], opts)-> svg string
//   sparkline([n, …], opts)                    -> svg string
//   hbarChart([{ label, value, tone? }], opts) -> svg string
//   emptyChart(msg)                            -> placeholder markup
//
// Held by every function below:
//   * explicit viewBox + width="100%" so the drawing scales to its container;
//   * never throws — bad input degrades to emptyChart(), a non-numeric value
//     counts as 0, and a negative value can never produce a negative bar;
//   * accessible — role="img" with an aria-label, a <title> for the whole
//     chart, and a <title> on every bar/slice so hover reads the number out;
//   * well-formed XML — labels are escaped, so no raw &, < or " survives.

// ─── Palette ───────────────────────────────────────────────────────────────
// These hexes MIRROR styles.css `:root` on purpose instead of referencing the
// tokens: these SVGs are assembled as strings and injected with innerHTML, so
// their presentation attributes must stand on their own. `fill="var(--gold)"`
// only resolves where the custom property is in scope for that element, and
// it never resolves when the markup is read outside this document (XML tooling,
// exports, previews) — an unresolved var() falls back to black and silently
// wrecks the chart. Keep this table in step with :root.

const TK = {
  bg: '#ffffff',
  bgSoft: '#f6f7f9',
  surface: '#ffffff',
  surface2: '#f1f3f6',
  border: 'rgba(15,23,42,0.08)',
  border2: 'rgba(15,23,42,0.12)',
  gold: '#e0a526',
  goldSoft: '#f2c14e',
  goldDeep: '#b07d12',
  teal: '#0ea5a4',
  tealSoft: '#5eead4',
  green: '#16a34a',
  red: '#ef4444',
  violet: '#8b5cf6',
  text: '#0f172a',
  muted: '#64748b',
  sub: '#94a3b8',
  accent: '#0ea5a4',
  fontHead: "'Plus Jakarta Sans', sans-serif",
  fontBody: "'Inter', sans-serif",
};

/** Single-series charts cycle through this order when no tone is given. */
const SERIES = [TK.gold, TK.teal, TK.violet, TK.green];

/** Accepts the token names the views already speak, plus raw hex. */
const TONE = {
  gold: TK.gold, teal: TK.teal, violet: TK.violet, green: TK.green, red: TK.red,
  accent: TK.accent, muted: TK.muted, sub: TK.sub, text: TK.text, bg: TK.bg,
  'gold-soft': TK.goldSoft, 'gold-deep': TK.goldDeep, 'teal-soft': TK.tealSoft,
  'surface-2': TK.surface2, surface2: TK.surface2,
};

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

// ─── Guards ────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[m]));
}

/** Coerce anything at all to a finite number — 0 when it cannot be one. */
function num(v) {
  if (typeof v === 'symbol') return 0;   // Number(Symbol) throws
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Round to 2dp so no NaN/Infinity/float dump can reach the markup. */
function r2(n) {
  const v = Math.round(num(n) * 100) / 100;
  return Number.isFinite(v) ? v : 0;
}

function fmt(v) {
  const n = num(v);
  if (Number.isInteger(n)) return String(n);
  return String(Math.round(n * 10) / 10);
}

function clip(s, n) {
  const str = String(s == null ? '' : s);
  const max = Math.max(1, Math.floor(n));
  if (str.length <= max) return str;
  return str.slice(0, Math.max(1, max - 1)) + '…';
}

/** `opts` may arrive as anything; a chart never throws because of it. */
function opt(o) {
  return o && typeof o === 'object' ? o : {};
}

function emptyMsg(opts, fallback) {
  const m = opts.empty;
  return m == null || m === '' ? fallback : String(m);
}

/** Normalise the item list: objects, primitives and junk all survive. */
function norm(items) {
  if (!Array.isArray(items)) return [];
  const out = [];
  items.forEach((raw) => {
    if (raw == null) return;
    if (typeof raw === 'object') {
      out.push({
        label: raw.label == null || raw.label === '' ? 'Untitled'
          : String(raw.label),
        value: num(raw.value),
        tone: raw.tone == null ? '' : String(raw.tone),
      });
    } else {
      out.push({ label: String(raw), value: num(raw), tone: '' });
    }
  });
  return out;
}

/** Item tone wins, then opts.tone, then the gold/teal/violet/green cycle. */
function colorOf(row, i, opts) {
  const pick = (c) => {
    if (!c) return '';
    if (TONE[c]) return TONE[c];
    if (HEX.test(c)) return c;
    return '';
  };
  let fromOpts = '';
  if (Array.isArray(opts.tone)) {
    const at = opts.tone.length ? i % opts.tone.length : 0;
    fromOpts = typeof opts.tone[at] === 'string' ? pick(opts.tone[at]) : '';
  } else {
    fromOpts = pick(opts.tone);
  }
  return pick(row.tone) || fromOpts || SERIES[i % SERIES.length];
}

/** Human-readable description used for both <title> and aria-label. */
function describe(prefix, rows, unit) {
  const u = unit || '';
  const bits = rows.slice(0, 10).map((r) => `${r.label} ${fmt(r.value)}${u}`);
  if (rows.length > 10) bits.push(`${rows.length - 10} more`);
  return bits.length ? `${prefix}: ${bits.join(', ')}` : prefix;
}

function open(cls, w, h, desc) {
  return `<svg class="chart ${cls}" xmlns="http://www.w3.org/2000/svg"`
    + ` viewBox="0 0 ${r2(w)} ${r2(h)}" width="100%" role="img"`
    + ` aria-label="${esc(desc)}"><title>${esc(desc)}</title>`;
}

// ─── Charts ────────────────────────────────────────────────────────────────

/** Vertical bars: one value per label, rounded caps, value printed on top. */
export function barChart(items, opts = {}) {
  opts = opt(opts);
  const rows = norm(items);
  if (!rows.length) return emptyChart(emptyMsg(opts, 'No data yet'));

  const unit = opts.unit == null ? '' : String(opts.unit);
  const W = 560, H = 240, padL = 44, padR = 14, padT = 30, padB = 44;
  const base = H - padB;
  const slot = (W - padL - padR) / rows.length;
  const bw = Math.max(6, Math.min(56, slot * 0.56));

  let max = 0;
  rows.forEach((r) => { if (r.value > max) max = r.value; });
  const scale = max > 0 ? (base - padT) / max : 0;

  const out = [open('chart-bar', W, H,
    describe(String(opts.title || 'Bar chart'), rows, unit))];

  // Value axis: 0 / half / max, then a firmer baseline.
  if (max > 0) {
    [max, max / 2].forEach((v) => {
      const y = r2(base - v * scale);
      out.push(`<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}"`
        + ` stroke="${TK.border}" stroke-width="1"/>`);
      out.push(`<text x="${padL - 8}" y="${r2(y + 4)}" text-anchor="end"`
        + ` font-family="${TK.fontBody}" font-size="10.5" fill="${TK.muted}">${
          esc(fmt(v))}</text>`);
    });
  }
  out.push(`<line x1="${padL}" y1="${base}" x2="${W - padR}" y2="${base}"`
    + ` stroke="${TK.border2}" stroke-width="1.5"/>`);
  out.push(`<text x="${padL - 8}" y="${base + 4}" text-anchor="end"`
    + ` font-family="${TK.fontBody}" font-size="10.5" fill="${TK.muted}">0</text>`);

  rows.forEach((r, i) => {
    const cx = r2(padL + slot * i + slot / 2);
    const v = Math.max(0, r.value);            // a negative never flips a bar
    const h = scale > 0 ? v * scale : 0;
    const bh = v > 0 ? Math.max(3, h) : 0;
    const y = r2(base - bh);
    const tip = `${r.label}: ${fmt(r.value)}${unit}`;

    if (bh > 0) {
      const w = r2(bw);
      out.push(`<rect x="${r2(cx - w / 2)}" y="${y}" width="${w}" height="${
        r2(bh)}" rx="${r2(Math.min(6, w / 2, bh / 2))}" fill="${
        colorOf(r, i, opts)}"><title>${esc(tip)}</title></rect>`);
    }
    out.push(`<text x="${cx}" y="${r2(Math.max(y - 7, 13))}" text-anchor="middle"`
      + ` font-family="${TK.fontBody}" font-size="11" font-weight="600"`
      + ` fill="${TK.muted}">${esc(fmt(r.value) + unit)}</text>`);
    out.push(`<text x="${cx}" y="${base + 18}" text-anchor="middle"`
      + ` font-family="${TK.fontBody}" font-size="11" fill="${TK.muted}">${
        esc(clip(r.label, Math.max(3, Math.floor((slot - 6) / 6.2))))}</text>`);
  });

  out.push('</svg>');
  return out.join('');
}

/**
 * Horizontal bars for long labels: the label sits on its own left column so a
 * subject or topic name never has to be sacrificed to fit a column width.
 */
export function hbarChart(items, opts = {}) {
  opts = opt(opts);
  const rows = norm(items);
  if (!rows.length) return emptyChart(emptyMsg(opts, 'No data yet'));

  const unit = opts.unit == null ? '' : String(opts.unit);
  const W = 560, rowH = 30, barH = 14, padX = 12, padT = 12, padB = 12;
  const labelW = 168, valueW = 58;
  const trackX = padX + labelW + 12;
  const trackW = W - trackX - padX - valueW;
  const H = padT + rows.length * rowH + padB;

  let max = 0;
  rows.forEach((r) => { if (r.value > max) max = r.value; });
  const scale = max > 0 ? trackW / max : 0;

  const out = [open('chart-hbar', W, H,
    describe(String(opts.title || 'Horizontal bar chart'), rows, unit))];
  const labelChars = Math.max(4, Math.floor((labelW - 6) / 6.3));

  rows.forEach((r, i) => {
    const top = padT + i * rowH;
    const cy = r2(top + rowH / 2);
    if (i > 0) {
      out.push(`<line x1="${padX}" y1="${top}" x2="${W - padX}" y2="${top}"`
        + ` stroke="${TK.border}" stroke-width="1"/>`);
    }
    out.push(`<text x="${padX + labelW}" y="${r2(cy + 4)}" text-anchor="end"`
      + ` font-family="${TK.fontBody}" font-size="11.5" fill="${TK.muted}">${
        esc(clip(r.label, labelChars))}</text>`);
    out.push(`<rect x="${trackX}" y="${r2(cy - barH / 2)}" width="${trackW}"`
      + ` height="${barH}" rx="${barH / 2}" fill="${TK.surface2}"/>`);

    const v = Math.max(0, r.value);            // clamped: never a negative bar
    const w = scale > 0 ? Math.max(3, Math.min(v * scale, trackW)) : 0;
    if (v > 0 && w > 0) {
      out.push(`<rect x="${trackX}" y="${r2(cy - barH / 2)}" width="${r2(w)}"`
        + ` height="${barH}" rx="${r2(Math.min(barH / 2, w / 2))}" fill="${
        colorOf(r, i, opts)}"><title>${esc(
        `${r.label}: ${fmt(r.value)}${unit}`)}</title></rect>`);
    }
    out.push(`<text x="${W - padX}" y="${r2(cy + 4)}" text-anchor="end"`
      + ` font-family="${TK.fontBody}" font-size="11.5" font-weight="600"`
      + ` fill="${TK.muted}">${esc(fmt(r.value) + unit)}</text>`);
  });

  out.push('</svg>');
  return out.join('');
}

/**
 * Donut with a centred total and a built-in legend. Shares are taken from the
 * clamped values, and an all-zero set draws the track ring alone — the total
 * is never used as a divisor before it is known to be non-zero.
 */
export function donutChart(items, opts = {}) {
  opts = opt(opts);
  const rows = norm(items);
  if (!rows.length) return emptyChart(emptyMsg(opts, 'No data yet'));

  const unit = opts.unit == null ? '' : String(opts.unit);
  const values = rows.map((r) => Math.max(0, r.value));
  let total = 0;
  values.forEach((v) => { total += v; });

  const gap = 24, W = 420, R = 66, SW = 26, cx = 106;
  const H = Math.max(216, 44 + rows.length * gap);
  const cy = r2(H / 2);
  const C = 2 * Math.PI * R;

  const out = [open('chart-donut', W, H,
    describe(String(opts.title || 'Donut chart'), rows, unit))];

  out.push(`<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${
    TK.surface2}" stroke-width="${SW}"/>`);

  let offset = 0;
  rows.forEach((r, i) => {
    const share = total > 0 ? values[i] / total : 0;
    const len = share * C;
    if (len <= 0) return;                       // zero slice: nothing to arc
    const start = offset;
    offset += len;
    out.push(`<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${
      colorOf(r, i, opts)}" stroke-width="${SW}" stroke-dasharray="${
      r2(len)} ${r2(C - len)}" stroke-dashoffset="${r2(-start)}"`
      + ` transform="rotate(-90 ${cx} ${cy})"><title>${esc(
      `${r.label}: ${fmt(r.value)}${unit} of ${fmt(total)}${unit}`)}</title></circle>`);
  });

  const centre = opts.center != null ? String(opts.center)
    : fmt(total) + unit;
  const centreLabel = opts.centerLabel != null ? String(opts.centerLabel)
    : 'Total';
  out.push(`<text x="${cx}" y="${r2(cy + 6)}" text-anchor="middle"`
    + ` font-family="${TK.fontHead}" font-size="${centre.length > 7 ? 17 : 24}"`
    + ` font-weight="800" fill="${TK.text}">${esc(centre)}</text>`);
  out.push(`<text x="${cx}" y="${r2(cy + 23)}" text-anchor="middle"`
    + ` font-family="${TK.fontBody}" font-size="11" fill="${TK.muted}">${
      esc(clip(centreLabel, 14))}</text>`);

  const legendX = 200;
  const startY = (H - rows.length * gap) / 2 + 8;
  const labelChars = Math.max(4, Math.floor((W - legendX - 66) / 6.4));
  rows.forEach((r, i) => {
    const y = r2(startY + i * gap);
    out.push(`<rect x="${legendX}" y="${r2(y - 5)}" width="10" height="10"`
      + ` rx="3" fill="${colorOf(r, i, opts)}"/>`);
    out.push(`<text x="${legendX + 18}" y="${r2(y + 4)}"`
      + ` font-family="${TK.fontBody}" font-size="11.5" fill="${TK.text}">${
        esc(clip(r.label, labelChars))}</text>`);
    out.push(`<text x="${W - 12}" y="${r2(y + 4)}" text-anchor="end"`
      + ` font-family="${TK.fontBody}" font-size="11.5" font-weight="600"`
      + ` fill="${TK.muted}">${esc(fmt(r.value) + unit)}</text>`);
  });

  out.push('</svg>');
  return out.join('');
}

/** Tiny trend line (viewBox 0 0 120 32) with a subtle area under it. */
export function sparkline(values, opts = {}) {
  opts = opt(opts);
  const raw = Array.isArray(values) ? values.slice(0, 200) : [];
  const pts = raw.map((v) => num(v));
  if (!pts.length) return emptyChart(emptyMsg(opts, 'No data yet'));

  const W = 120, H = 32, pad = 3;
  let lo = pts[0], hi = pts[0];
  pts.forEach((v) => { if (v < lo) lo = v; if (v > hi) hi = v; });
  const low = lo, high = hi;
  if (hi === lo) { lo -= 1; hi += 1; }          // flat series → centred line

  const step = pts.length > 1 ? (W - pad * 2) / (pts.length - 1) : 0;
  const xAt = (i) => (pts.length > 1 ? pad + step * i : W - pad);
  const yAt = (v) => pad + (1 - (v - lo) / (hi - lo)) * (H - pad * 2);
  const color = colorOf({ tone: '' }, 0, opts);

  const desc = `${String(opts.title || 'Sparkline')}: ${fmt(pts[0])} first, `
    + `${fmt(pts[pts.length - 1])} last, low ${fmt(low)}, high ${fmt(high)}, `
    + `${pts.length} point${pts.length === 1 ? '' : 's'}`;

  const out = [open('chart-spark', W, H, desc)];

  let area = `M ${r2(xAt(0))} ${H}`;
  pts.forEach((v, i) => { area += ` L ${r2(xAt(i))} ${r2(yAt(v))}`; });
  area += ` L ${r2(xAt(pts.length - 1))} ${H} Z`;
  out.push(`<path d="${area}" fill="${color}" fill-opacity="0.16" stroke="none"/>`);

  out.push(`<polyline points="${
    pts.map((v, i) => `${r2(xAt(i))},${r2(yAt(v))}`).join(' ')}"`
    + ` fill="none" stroke="${color}" stroke-width="2"`
    + ` stroke-linecap="round" stroke-linejoin="round"/>`);

  const last = pts[pts.length - 1];
  out.push(`<circle cx="${r2(xAt(pts.length - 1))}" cy="${r2(yAt(last))}"`
    + ` r="2.6" fill="${color}" stroke="${TK.bg}" stroke-width="1.5"/>`);

  out.push('</svg>');
  return out.join('');
}

/** Dignified placeholder — returned whenever there is nothing to draw. */
export function emptyChart(msg = 'No data yet') {
  const text = msg == null || msg === '' ? 'No data yet' : String(msg);
  return `<div class="chart-empty" role="status">${esc(text)}</div>`;
}
