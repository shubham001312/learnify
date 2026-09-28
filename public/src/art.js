// Learnify — cartoonish course-cover artwork.
//
// A course card needs a picture before it needs words, but we cannot ship a
// photo per subject and storage uploads stay optional. So each subject area
// gets a hand-built SVG cartoon instead: thick rounded strokes, flat brand
// colours, a tinted rounded background and a mascot with a dot-eyed smile.
// The same drawing is reused everywhere a cover is asked for, which keeps the
// catalogue reading as one set of illustrations rather than clip art.
//
//   import { coverHtml } from './art.js?v=64';
//   root.insertAdjacentHTML('afterbegin',
//     coverHtml(c.cover_image_url, { subject: c.subject_name, cls: 'cc-cover' }));
//
// Every drawing is a self-contained SVG on a 320 x 180 viewBox — no external
// references, no image elements, no CSS imports — so it scales from a 120px
// picker tile to a full-width hero without extra work.

import { esc } from './utils.js?v=64';

// ─── Palette ───────────────────────────────────────────────────────────────
// TK mirrors the design tokens in styles.css `:root`. Inline SVG handed out as
// a string cannot reliably resolve var() inside presentation attributes, so
// the token values are pinned here once — never scattered through the art.
const TK = {
  gold: '#e0a526',
  goldSoft: '#f2c14e',
  goldDeep: '#b07d12',
  teal: '#0ea5a4',
  tealSoft: '#5eead4',
  green: '#16a34a',
  red: '#ef4444',
  violet: '#8b5cf6',
  ink: '#0f172a',
  muted: '#64748b',
  white: '#ffffff',
  // Blush is --red at low alpha so cheeks read on light fills.
  blush: 'rgba(239,68,68,0.32)',
};

// Soft background tints — the tokens lightened for a rounded backplate.
const BG = {
  gold: '#fff8e8',
  teal: '#e7fbf9',
  violet: '#f3edff',
  green: '#eafaf0',
  red: '#fdeeee',
  neutral: '#eef2f7',
};

// ─── Drawing helpers ───────────────────────────────────────────────────────
const n = (v) => Math.round(Number(v) * 100) / 100;

const ROUND = 'stroke-linecap="round" stroke-linejoin="round"';

/** Dot eyes, a smile arc and two blush circles. The house style mascot face. */
function face(x, y, s = 1) {
  const er = n(Math.max(2.4, 3.4 * s));
  const eye = n(y - 4 * s);
  const sw = n(Math.max(2.4, 4 * s));
  const smile = `M${n(x - 8 * s)} ${n(y + 6 * s)} q ${n(8 * s)} ${n(9 * s)} ${n(16 * s)} 0`;
  return [
    `<circle cx="${n(x - 11 * s)}" cy="${eye}" r="${er}" fill="${TK.ink}"/>`,
    `<circle cx="${n(x + 11 * s)}" cy="${eye}" r="${er}" fill="${TK.ink}"/>`,
    `<circle cx="${n(x - 20 * s)}" cy="${n(y + 7 * s)}" r="${n(4.5 * s)}" fill="${TK.blush}"/>`,
    `<circle cx="${n(x + 20 * s)}" cy="${n(y + 7 * s)}" r="${n(4.5 * s)}" fill="${TK.blush}"/>`,
    `<path d="${smile}" fill="none" stroke="${TK.ink}" stroke-width="${sw}" ${ROUND}/>`,
  ].join('');
}

/** Four-point sparkle with concave sides. */
function spark(x, y, s, fill) {
  const k = n(s * 0.3);
  const d = `M${x} ${n(y - s)} Q${n(x + k)} ${n(y - k)} ${n(x + s)} ${y}`
    + ` Q${n(x + k)} ${n(y + k)} ${x} ${n(y + s)}`
    + ` Q${n(x - k)} ${n(y + k)} ${n(x - s)} ${y}`
    + ` Q${n(x - k)} ${n(y - k)} ${x} ${n(y - s)} Z`;
  return `<path d="${d}" fill="${fill}"/>`;
}

/**
 * Cartoon gear: one closed path of trapezoidal teeth. A thick round-joined
 * stroke melts the corners, which is what makes it read as a sticker rather
 * than an engineering drawing.
 */
function gearPath(cx, cy, rOut, rIn, teeth) {
  const pitch = (Math.PI * 2) / teeth;
  const tooth = pitch * 0.42;
  const gap = pitch * 0.1;
  const pts = [];
  const put = (r, a) => pts.push(`${n(cx + Math.cos(a) * r)} ${n(cy + Math.sin(a) * r)}`);
  for (let i = 0; i < teeth; i++) {
    const a = i * pitch - Math.PI / 2;
    put(rOut, a - tooth / 2);
    put(rOut, a + tooth / 2);
    put(rIn, a + tooth / 2 + gap);
    put(rIn, a + pitch - tooth / 2 - gap);
  }
  return 'M' + pts.join('L') + 'Z';
}

function gear(cx, cy, rOut, rIn, teeth, fill, stroke, sw) {
  return `<path d="${gearPath(cx, cy, rOut, rIn, teeth)}" fill="${fill}"`
    + ` stroke="${stroke}" stroke-width="${sw}" ${ROUND}/>`;
}

/**
 * Union outline for shapes that overlap (clouds, chat bubbles, flasks).
 * Layer one paints the shapes in ink with a 16px stroke so the silhouette
 * grows by 8px; layer two repaints the exact shapes in flat colour, leaving a
 * clean 8px contour with no seams where the pieces meet.
 */
function union(shapes, fill) {
  return `<g fill="${TK.ink}" stroke="${TK.ink}" stroke-width="16" ${ROUND}>${shapes}</g>`
    + `<g fill="${fill}">${shapes}</g>`;
}

// ─── Artwork ───────────────────────────────────────────────────────────────
// Each entry is a tinted backplate (`bg`), an accessible title, and a `body`
// drawn on the 320 x 180 canvas. Object key order defines ART_KEYS.

// The two chat bubbles of the communication scene: outlined together in one
// ink pass, then filled separately so they read as a conversation.
const BUB_BIG = '<rect x="54" y="32" width="164" height="106" rx="24"/>'
  + '<path d="M92 126 L84 158 L124 134 Z"/>';
const BUB_SMALL = '<rect x="244" y="70" width="54" height="52" rx="18"/>'
  + '<path d="M254 116 L250 140 L272 122 Z"/>';

const ART = {
  networks: {
    bg: BG.teal,
    title: 'Computer networks',
    body: `<g ${ROUND}>
      <path d="M58 52 L110 100" stroke="${TK.teal}" stroke-width="6" fill="none"/>
      <path d="M262 52 L210 100" stroke="${TK.teal}" stroke-width="6" fill="none"/>
      <path d="M58 144 L110 148" stroke="${TK.teal}" stroke-width="6" fill="none"/>
      <path d="M262 144 L210 148" stroke="${TK.teal}" stroke-width="6" fill="none"/>
      <circle cx="48" cy="42" r="17" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="272" cy="42" r="17" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="48" cy="150" r="17" fill="${TK.green}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="272" cy="150" r="17" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="6"/>
      <path d="M126 96 L112 68" stroke="${TK.ink}" stroke-width="7" fill="none"/>
      <path d="M194 96 L208 68" stroke="${TK.ink}" stroke-width="7" fill="none"/>
      <rect x="98" y="96" width="124" height="58" rx="16" fill="${TK.white}" stroke="${TK.ink}" stroke-width="8"/>
      <circle cx="112" cy="64" r="7" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5"/>
      <circle cx="208" cy="64" r="7" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5"/>
      ${face(160, 125, 1)}
    </g>`,
  },

  code: {
    bg: BG.violet,
    title: 'Programming',
    body: `<g ${ROUND}>
      <rect x="70" y="30" width="180" height="104" rx="14" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="8"/>
      <rect x="84" y="44" width="152" height="76" rx="8" fill="${TK.white}" stroke="${TK.ink}" stroke-width="6"/>
      <path d="M52 134 h216 a10 10 0 0 1 0 20 h-216 a10 10 0 0 1 0 -20 Z" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="8"/>
      <path d="M118 66 L104 82 L118 98" fill="none" stroke="${TK.violet}" stroke-width="7"/>
      <path d="M202 66 L216 82 L202 98" fill="none" stroke="${TK.violet}" stroke-width="7"/>
      ${face(160, 82, 1)}
      ${spark(40, 60, 11, TK.violet)}
      ${spark(284, 120, 10, TK.teal)}
    </g>`,
  },

  database: {
    bg: BG.gold,
    title: 'Databases',
    body: `<g ${ROUND}>
      <path d="M94 54 V136 a66 24 0 0 0 132 0 V54 Z" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="8"/>
      <ellipse cx="160" cy="54" rx="66" ry="24" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="8"/>
      <path d="M94 70 a66 24 0 0 0 132 0" fill="none" stroke="${TK.white}" stroke-width="6"/>
      ${face(160, 110, 1)}
      ${spark(266, 44, 11, TK.violet)}
      ${spark(52, 120, 10, TK.teal)}
    </g>`,
  },

  os: {
    bg: BG.neutral,
    title: 'Operating systems',
    body: `<g ${ROUND}>
      ${gear(246, 128, 36, 24, 8, TK.gold, TK.ink, 7)}
      ${gear(252, 46, 27, 18, 7, TK.teal, TK.ink, 6)}
      ${gear(132, 94, 64, 46, 10, TK.violet, TK.ink, 8)}
      <circle cx="132" cy="94" r="30" fill="${TK.white}" stroke="${TK.ink}" stroke-width="6"/>
      ${face(132, 94, 1)}
      ${spark(52, 44, 12, TK.gold)}
      ${spark(44, 140, 9, TK.teal)}
    </g>`,
  },

  web: {
    bg: BG.green,
    title: 'Web development',
    body: `<g ${ROUND}>
      <rect x="54" y="34" width="212" height="112" rx="16" fill="${TK.white}" stroke="${TK.ink}" stroke-width="8"/>
      <path d="M54 66 V50 A16 16 0 0 1 70 34 H250 A16 16 0 0 1 266 50 V66 Z" fill="${TK.green}" stroke="${TK.ink}" stroke-width="7"/>
      <circle cx="76" cy="50" r="5" fill="${TK.white}"/>
      <circle cx="94" cy="50" r="5" fill="${TK.white}"/>
      <circle cx="112" cy="50" r="5" fill="${TK.white}"/>
      <rect x="134" y="42" width="118" height="16" rx="8" fill="${TK.white}" opacity="0.9"/>
      ${face(160, 110, 1.1)}
      <path d="M224 104 L224 148 L233 139 L240 154 L248 150 L241 135 L254 133 Z" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="6"/>
      ${spark(30, 90, 11, TK.green)}
      ${spark(292, 60, 10, TK.gold)}
    </g>`,
  },

  ai: {
    bg: BG.teal,
    title: 'Artificial intelligence',
    body: `<g ${ROUND}>
      <rect x="120" y="144" width="80" height="24" rx="9" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="7"/>
      <rect x="78" y="76" width="20" height="44" rx="10" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="7"/>
      <rect x="222" y="76" width="20" height="44" rx="10" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="7"/>
      <path d="M160 48 V30" stroke="${TK.ink}" stroke-width="7" fill="none"/>
      <circle cx="160" cy="24" r="9" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="6"/>
      <rect x="96" y="46" width="128" height="106" rx="26" fill="${TK.white}" stroke="${TK.ink}" stroke-width="8"/>
      ${face(160, 96, 1.15)}
      <circle cx="114" cy="132" r="6" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5"/>
      <circle cx="206" cy="132" r="6" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="5"/>
      ${spark(46, 44, 13, TK.gold)}
      ${spark(276, 40, 10, TK.violet)}
      ${spark(40, 132, 9, TK.teal)}
    </g>`,
  },

  security: {
    bg: BG.red,
    title: 'Cyber security',
    body: `<g ${ROUND}>
      <path d="M160 26 L246 52 V104 C246 138 208 158 160 168 C112 158 74 138 74 104 V52 Z" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="8"/>
      ${union(`<circle cx="160" cy="70" r="15"/><path d="M152 78 L147 110 H173 L168 78 Z"/>`, TK.white)}
      ${face(160, 132, 0.9)}
      ${spark(272, 44, 12, TK.teal)}
      ${spark(44, 60, 10, TK.violet)}
    </g>`,
  },

  embedded: {
    bg: BG.gold,
    title: 'Embedded systems',
    body: `<g ${ROUND}>
      <path d="M84 70 H106 M84 92 H106 M84 114 H106 M84 136 H106" stroke="${TK.ink}" stroke-width="9" fill="none"/>
      <path d="M214 70 H236 M214 92 H236 M214 114 H236 M214 136 H236" stroke="${TK.ink}" stroke-width="9" fill="none"/>
      <rect x="104" y="52" width="112" height="96" rx="16" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="8"/>
      ${face(160, 100, 1)}
      <circle cx="256" cy="60" r="9" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="6"/>
      <path d="M272 52 L282 46 M274 62 H286 M272 70 L282 76" stroke="${TK.gold}" stroke-width="5" fill="none"/>
      <path d="M46 162 H112 M208 162 H274" stroke="${TK.ink}" stroke-width="6" fill="none"/>
      <circle cx="44" cy="162" r="7" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="5"/>
      <circle cx="276" cy="162" r="7" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="5"/>
      ${spark(52, 52, 11, TK.teal)}
    </g>`,
  },

  cloud: {
    bg: BG.neutral,
    title: 'Cloud computing',
    body: `${union(
      '<circle cx="118" cy="94" r="40"/><circle cx="168" cy="74" r="46"/>'
      + '<circle cx="214" cy="98" r="36"/><rect x="96" y="96" width="140" height="38" rx="19"/>',
      TK.white)}
      <g ${ROUND}>
        ${face(160, 100, 1.1)}
        <path d="M142 148 V170 M132 160 L142 171 L152 160" stroke="${TK.teal}" stroke-width="7" fill="none"/>
        <path d="M196 170 V148 M186 157 L196 146 L206 157" stroke="${TK.violet}" stroke-width="7" fill="none"/>
        ${spark(48, 44, 12, TK.gold)}
        ${spark(274, 44, 10, TK.violet)}
      </g>`,
  },

  software: {
    bg: BG.violet,
    title: 'Software engineering',
    body: `<g ${ROUND}>
      <rect x="176" y="26" width="104" height="104" rx="22" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="8"/>
      <rect x="186" y="34" width="84" height="16" rx="8" fill="${TK.white}" stroke="${TK.ink}" stroke-width="5"/>
      <rect x="134" y="54" width="104" height="104" rx="22" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="8"/>
      <circle cx="210" cy="96" r="18" fill="${TK.white}" stroke="${TK.ink}" stroke-width="6"/>
      <rect x="52" y="74" width="116" height="92" rx="22" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="8"/>
      ${face(110, 120, 1.05)}
      ${gear(264, 142, 26, 17, 8, TK.goldSoft, TK.ink, 6)}
      ${spark(30, 44, 12, TK.violet)}
    </g>`,
  },

  math: {
    bg: BG.green,
    title: 'Mathematics',
    body: `<g ${ROUND}>
      <g transform="rotate(-28 160 100)">
        <path d="M132 44 H188 V134 L160 176 L132 134 Z" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="7"/>
        <path d="M146 154 L160 176 L174 154 Z" fill="${TK.ink}"/>
        <rect x="130" y="26" width="60" height="24" rx="12" fill="${TK.red}" stroke="${TK.ink}" stroke-width="7"/>
        <path d="M132 54 H188" stroke="${TK.ink}" stroke-width="5" fill="none"/>
        ${face(160, 92, 0.85)}
      </g>
      <path d="M56 52 H86 M71 37 V67" stroke="${TK.violet}" stroke-width="8" fill="none"/>
      <path d="M50 130 H80" stroke="${TK.gold}" stroke-width="8" fill="none"/>
      <path d="M250 58 L274 82 M274 58 L250 82" stroke="${TK.teal}" stroke-width="8" fill="none"/>
      <path d="M244 132 H276" stroke="${TK.violet}" stroke-width="8" fill="none"/>
      <circle cx="260" cy="116" r="5" fill="${TK.violet}"/>
      <circle cx="260" cy="148" r="5" fill="${TK.violet}"/>
    </g>`,
  },

  physics: {
    bg: BG.violet,
    title: 'Physics',
    body: `<g ${ROUND}>
      <ellipse cx="160" cy="90" rx="80" ry="30" fill="none" stroke="${TK.violet}" stroke-width="7"/>
      <ellipse cx="160" cy="90" rx="80" ry="30" fill="none" stroke="${TK.teal}" stroke-width="7" transform="rotate(60 160 90)"/>
      <ellipse cx="160" cy="90" rx="80" ry="30" fill="none" stroke="${TK.gold}" stroke-width="7" transform="rotate(-60 160 90)"/>
      <circle cx="240" cy="90" r="11" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="120" cy="21" r="11" fill="${TK.green}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="120" cy="159" r="11" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="160" cy="90" r="30" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="7"/>
      ${face(160, 90, 0.8)}
      ${spark(296, 60, 10, TK.violet)}
      ${spark(28, 128, 10, TK.teal)}
    </g>`,
  },

  chemistry: {
    bg: BG.teal,
    title: 'Chemistry',
    body: `${union(
      '<path d="M145 62 L100 146 Q96 164 114 164 H206 Q224 164 220 146 L175 62 Z"/>'
      + '<rect x="145" y="34" width="30" height="32"/>', TK.white)}
      <g ${ROUND}>
        <path d="M128 116 H192 L203 142 Q207 152 196 152 H124 Q113 152 117 142 Z" fill="${TK.teal}"/>
        <circle cx="146" cy="138" r="6" fill="${TK.white}"/>
        <circle cx="176" cy="132" r="5" fill="${TK.white}"/>
        <circle cx="160" cy="146" r="4" fill="${TK.white}"/>
        <rect x="136" y="24" width="48" height="16" rx="8" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="7"/>
        ${face(160, 96, 0.85)}
        <circle cx="112" cy="40" r="9" fill="${TK.white}" stroke="${TK.teal}" stroke-width="5"/>
        <circle cx="206" cy="34" r="7" fill="${TK.white}" stroke="${TK.teal}" stroke-width="5"/>
        <circle cx="200" cy="66" r="5" fill="${TK.white}" stroke="${TK.teal}" stroke-width="5"/>
      </g>`,
  },

  biology: {
    bg: BG.green,
    title: 'Biology',
    body: `<g ${ROUND}>
      <circle cx="160" cy="92" r="68" fill="${TK.green}" stroke="${TK.ink}" stroke-width="8"/>
      <circle cx="160" cy="92" r="56" fill="${TK.white}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="106" cy="61" r="5" fill="${TK.white}"/>
      <circle cx="214" cy="61" r="5" fill="${TK.white}"/>
      <circle cx="160" cy="154" r="5" fill="${TK.white}"/>
      <ellipse cx="126" cy="66" rx="12" ry="8" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5" transform="rotate(-30 126 66)"/>
      <ellipse cx="194" cy="116" rx="12" ry="8" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="5" transform="rotate(-30 194 116)"/>
      <circle cx="126" cy="118" r="9" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="5"/>
      <circle cx="198" cy="66" r="8" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5"/>
      <circle cx="160" cy="92" r="32" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="7"/>
      ${face(160, 92, 0.78)}
      ${spark(286, 54, 11, TK.violet)}
      ${spark(34, 146, 10, TK.teal)}
    </g>`,
  },

  business: {
    bg: BG.gold,
    title: 'Business and management',
    body: `<g ${ROUND}>
      <circle cx="52" cy="104" r="17" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="6"/>
      <circle cx="44" cy="128" r="20" fill="${TK.goldSoft}" stroke="${TK.ink}" stroke-width="6"/>
      <path d="M36 122 H52 M36 131 H52" stroke="${TK.ink}" stroke-width="4" fill="none"/>
      <rect x="72" y="66" width="146" height="94" rx="18" fill="${TK.gold}" stroke="${TK.ink}" stroke-width="8"/>
      <path d="M118 66 V54 A12 12 0 0 1 130 42 H158 A12 12 0 0 1 170 54 V66" fill="none" stroke="${TK.ink}" stroke-width="8"/>
      <rect x="133" y="78" width="24" height="22" rx="6" fill="${TK.white}" stroke="${TK.ink}" stroke-width="6"/>
      ${face(145, 126, 0.88)}
      <rect x="236" y="122" width="16" height="38" rx="6" fill="${TK.teal}" stroke="${TK.ink}" stroke-width="5"/>
      <rect x="258" y="100" width="16" height="60" rx="6" fill="${TK.violet}" stroke="${TK.ink}" stroke-width="5"/>
      <rect x="280" y="76" width="16" height="84" rx="6" fill="${TK.green}" stroke="${TK.ink}" stroke-width="5"/>
      <path d="M232 100 L252 82 L268 92 L294 56" fill="none" stroke="${TK.ink}" stroke-width="6"/>
      <path d="M282 56 L294 56 L294 68" fill="none" stroke="${TK.ink}" stroke-width="6"/>
      ${spark(36, 52, 11, TK.teal)}
    </g>`,
  },

  communication: {
    bg: BG.red,
    title: 'Communication skills',
    body: `<g fill="${TK.ink}" stroke="${TK.ink}" stroke-width="16" ${ROUND}>${BUB_BIG}${BUB_SMALL}</g>`
      + `<g fill="${TK.gold}">${BUB_BIG}</g>`
      + `<g fill="${TK.violet}">${BUB_SMALL}</g>`
      + `<g ${ROUND}>
        ${face(136, 84, 1.2)}
        <circle cx="114" cy="120" r="6" fill="${TK.white}"/>
        <circle cx="136" cy="120" r="6" fill="${TK.white}"/>
        <circle cx="158" cy="120" r="6" fill="${TK.white}"/>
        <circle cx="263" cy="94" r="5" fill="${TK.white}"/>
        <circle cx="279" cy="94" r="5" fill="${TK.white}"/>
        ${spark(40, 150, 10, TK.teal)}
        ${spark(296, 40, 10, TK.teal)}
      </g>`,
  },
};

/** Every artwork key, in display order. */
export const ART_KEYS = Object.keys(ART);

// ─── Rendering ─────────────────────────────────────────────────────────────

/** SVG markup for one artwork. `viewBox="0 0 320 180"`, fully self-contained. */
export function artSvg(key, opts = {}) {
  const known = typeof key === 'string' && Object.prototype.hasOwnProperty.call(ART, key);
  const k = known ? key : artKeyFor(key, '');
  const art = ART[k];
  const label = esc(String((opts && opts.title) || art.title || k));
  return `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${label}"><rect width="320" height="180" rx="22" fill="${art.bg}"/>${art.body}</svg>`;
}

// ─── Subject → artwork mapping ─────────────────────────────────────────────
// Keyword rules first (a subject should look like what it teaches), then a
// deterministic hash so an unmapped subject still gets the same picture every
// time it is drawn.

const RULES = [
  ['ai',
    ['ai', 'ml', 'artificial', 'neural', 'genai', 'chatbot', 'llm', 'deeplearning'],
    ['machine learning', 'deep learning', 'data science', 'computer vision',
      'natural language', 'predictive analytic', 'image recognition', 'speech recognition']],
  ['security',
    ['security', 'cyber', 'crypt', 'firewall', 'forensic', 'malware', 'antivirus',
      'virus', 'hacking', 'hacker', 'compliance', 'gdpr', 'siem'],
    ['penetration test', 'infosec', 'ethical hacking', 'data protection']],
  ['networks',
    ['network', 'routing', 'router', 'switching', 'tcp', 'udp', 'packet', 'wireless',
      'subnet', 'dns', 'dhcp', 'bgp', 'ospf', 'lan', 'wan', 'vlan', 'satellite'],
    ['computer network', 'ccna', 'lan wan', 'network design']],
  ['database',
    ['database', 'sql', 'mysql', 'postgres', 'oracle', 'mongodb', 'nosql', 'etl',
      'indexing', 'warehouse'],
    ['data warehouse', 'data model', 'data engineering', 'data analytics']],
  ['cloud',
    ['cloud', 'aws', 'azure', 'devops', 'kubernetes', 'docker', 'serverless',
      'terraform', 'virtualisation', 'virtualization'],
    ['virtual machine', 'microservice', 'site reliability', 'cloud native']],
  ['embedded',
    ['embedded', 'microcontroller', 'arduino', 'raspberry', 'iot', 'firmware', 'vlsi',
      'sensor', 'robotics', 'robot', 'electronics', 'circuit', 'pcb', 'mechatronics', 'drone'],
    ['internet of things', 'embedded system', 'printed circuit']],
  ['web',
    ['web', 'html', 'css', 'javascript', 'typescript', 'frontend', 'backend', 'fullstack',
      'react', 'angular', 'vue', 'django', 'rest', 'browser', 'website', 'wordpress',
      'php', 'jquery', 'bootstrap', 'figma', 'photoshop'],
    ['web design', 'web development', 'front end', 'back end', 'full stack',
      'graphic design', 'single page']],
  ['code',
    ['programming', 'coding', 'python', 'java', 'golang', 'kotlin', 'swift', 'algorithm',
      'compiler', 'debugging', 'git', 'oop'],
    ['data structure', 'object oriented', 'problem solving', 'competitive programming',
      'version control', 'c++', 'c programming']],
  ['os',
    ['operating', 'kernel', 'linux', 'unix', 'windows', 'scheduler', 'filesystem', 'shell'],
    ['operating system', 'system program', 'system administration', 'process management']],
  ['software',
    ['software', 'testing', 'sdlc', 'agile', 'scrum', 'uml', 'jira'],
    ['software engineering', 'software testing', 'quality assurance',
      'test automation', 'system analysis']],
  ['communication',
    ['english', 'communication', 'speaking', 'grammar', 'vocabulary', 'presentation',
      'interview', 'debate', 'literature', 'translation', 'hindi', 'writing', 'oratory'],
    ['public speaking', 'soft skill', 'business english', 'creative writing',
      'language skill', 'interpersonal', 'spoken english']],
  ['business',
    ['account', 'market', 'manage', 'finance', 'financial', 'business', 'econom',
      'entrepreneur', 'startup', 'sales', 'budget', 'profit', 'invoice', 'taxation',
      'commerce', 'mba', 'strategy', 'recruit', 'leadership', 'brand', 'retail',
      'logistics', 'audit', 'banking', 'insurance'],
    ['human resource', 'supply chain', 'project management', 'cost accounting',
      'digital marketing', 'commerce and']],
  ['math',
    ['mathematics', 'math', 'algebra', 'calculus', 'geometry', 'trigonometry',
      'statistics', 'statistic', 'probability', 'arithmetic', 'matrix', 'integral',
      'derivative', 'discrete', 'mensuration'],
    ['pure math', 'applied math', 'linear algebra']],
  ['physics',
    ['physics', 'mechanic', 'thermodynamic', 'quantum', 'relativity', 'optics',
      'electromagnet', 'gravitation', 'newton', 'particle', 'astrophysic', 'nuclear',
      'acoustic', 'magnetism'],
    ['classical mechanics', 'thermal physics', 'electromagnetic induction']],
  ['chemistry',
    ['chemistry', 'chemical', 'titration', 'polymer', 'stoichiometry', 'reagent',
      'molecule', 'molecular', 'periodic', 'electrochemistry', 'organic'],
    ['chemical reaction', 'inorganic', 'lab safety', 'laboratory']],
  ['biology',
    ['biology', 'genetic', 'genome', 'anatomy', 'physiology', 'ecology', 'evolution',
      'zoology', 'botany', 'microbiology', 'photosynthesis', 'cell', 'medicine',
      'nursing', 'histology', 'entomology', 'agriculture', 'horticulture'],
    ['life science', 'human body', 'living organism', 'cell structure']],
];

const DEFAULT_KEY = 'software';

/** Lower-case, punctuation-folded, safe on null. */
function normalize(v) {
  return String(v == null ? '' : v)
    .toLowerCase()
    .replace(/[^a-z0-9+# ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Short tokens must sit on a word boundary so "lan" misses "plant" and "java"
// misses "javascript"; long tokens are safe as substrings so "algorithm" still
// finds "algorithms".
function hasToken(hay, token) {
  if (token.length >= 6 || /[^a-z0-9]/.test(token)) return hay.includes(token);
  return new RegExp(`(^|[^a-z0-9])${escapeRe(token)}([^a-z0-9]|$)`).test(hay);
}

function matchRules(hay) {
  if (!hay) return '';
  for (const [key, tokens, phrases] of RULES) {
    for (const t of tokens) if (hasToken(hay, t)) return key;
    for (const p of phrases) if (hay.includes(p)) return key;
  }
  return '';
}

/** Stable 32-bit string hash (djb2 with xor) — identical on every engine. */
function hash(str) {
  let h = 5381;
  for (let i = 0; i < str.length; i++) h = ((h * 33) ^ str.charCodeAt(i)) >>> 0;
  return h >>> 0;
}

/**
 * Pick the artwork for a subject. Deterministic: the same subject always gets
 * the same picture, and neither `null` nor `''` can make it throw.
 */
export function artKeyFor(subjectName, category) {
  const name = normalize(subjectName);
  const cat = normalize(category);
  if (!name && !cat) return DEFAULT_KEY;

  // The subject name is the stronger signal, so it wins outright; the
  // category only gets a say when the name itself means nothing to us.
  const byName = matchRules(name);
  if (byName) return byName;

  const both = `${name} ${cat}`.trim();
  const byBoth = matchRules(both);
  if (byBoth) return byBoth;

  return ART_KEYS[hash(both) % ART_KEYS.length];
}

// ─── Cover grammar ─────────────────────────────────────────────────────────
// ''                      -> art for the subject
// 'art:<key>'             -> that artwork (falls back to the subject art)
// 'upload:<path>'         -> subject art (a bare storage path is not fetchable)
// 'http(s)://…'           -> <img>, swapped for the subject art on error
// 'none' | 'blank'        -> deliberately nothing
// anything else            -> subject art

const NO_COVER = new Set(['none', 'blank', 'hidden', 'hide']);

const WRAP = (cls, ratio, inner, extra = '') =>
  `<div class="art-cover${cls}" style="aspect-ratio:${ratio}"${extra}>${inner}</div>`;

/**
 * HTML for a cover block. `opts`: `{ subject, category, cls, ratio }`.
 * `cls` appends to the wrapper class; `ratio` defaults to `'16 / 9'`.
 * Returns `''` only when the cover is explicitly switched off.
 */
export function coverHtml(cover, opts = {}) {
  const o = opts || {};
  const subject = o.subject;
  const category = o.category;
  const cls = o.cls ? ` ${esc(String(o.cls))}` : '';
  const ratio = esc(String(o.ratio || '16 / 9'));

  const derived = () => artSvg(artKeyFor(subject, category));
  const src = cover == null ? '' : String(cover).trim();

  if (NO_COVER.has(src.toLowerCase())) return '';

  if (src.startsWith('art:')) {
    const key = src.slice(4).trim();
    return WRAP(cls, ratio, ART_KEYS.includes(key) ? artSvg(key) : derived());
  }

  if (/^https?:\/\//i.test(src)) {
    // index.html ships no CSP, so an inline handler is allowed; the fallback
    // art rides along in data-art and swaps in if the remote file never lands.
    const art = derived();
    const img = `<img src="${esc(src)}" alt="" loading="lazy" decoding="async"`
      + ` onerror="var w=this.parentNode;if(w){w.innerHTML=w.dataset.art;}">`;
    return WRAP(cls, ratio, img, ` data-art="${esc(art)}"`);
  }

  // '' , 'upload:<path>', and every other unrecognised value.
  return WRAP(cls, ratio, derived());
}
