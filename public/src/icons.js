// Shared inline SVG icon system (replaces emoji icons with crisp line-art).
// Style matches the app's existing menu icons: stroke=currentColor, 24x24.
const STROKE = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

const ICON_PATHS = {
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
  graduation: '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1 3 3 6 3s6-2 6-3v-5"/>',
  award: '<circle cx="12" cy="9" r="5"/><path d="M9 14l-1.5 7L12 18l4.5 3L15 14"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 .9-1 1.7"/><path d="M12 17h.01"/>',
  sparkles: '<path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z"/><path d="M19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9z"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5 3 3 0 0 0 2 4 3 3 0 0 0 5 1V5a2.5 2.5 0 0 0-3-1z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5 3 3 0 0 1-2 4 3 3 0 0 1-5 1"/>',
  cog: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 14.1H3a2 2 0 1 1 0-4h1.1A1.7 1.7 0 0 0 5.4 8.6a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 4.6V3a2 2 0 1 1 4 0v1.1A1.7 1.7 0 0 0 16 5.4a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V10a1.7 1.7 0 0 0 1.5 1.6H21a2 2 0 1 1 0 4h-1.1a1.7 1.7 0 0 0-1.5 1.4z"/>',
  heart: '<path d="M20.8 5.6a5.5 5.5 0 0 0-7.8 0L12 6.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z"/><path d="M3.5 12.5H8l2-3 3 5 2-3h4.5"/>',
  flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 14h9"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M3 12h18"/>',
  scale: '<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 6a3 3 0 0 0 6 0L5 7z"/><path d="M19 7l-3 6a3 3 0 0 0 6 0l-3-6z"/><path d="M7 21h10"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-.4-.2-.7-.5-.9-.3-.2-.5-.5-.5-.9 0-.7.8-1.2 1.5-1.2H16a5 5 0 0 0 5-5c0-4.4-4-8-9-8z"/><circle cx="7.5" cy="11.5" r="1"/><circle cx="11" cy="7.5" r="1"/><circle cx="15" cy="8.5" r="1"/><circle cx="8.5" cy="15" r="1"/>',
  landmark: '<path d="M3 21h18"/><path d="M4 21V10l8-5 8 5v11"/><path d="M9 21v-6h6v6"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/>',
  leaf: '<path d="M4 20C4 11 11 4 20 4c0 9-7 16-16 16z"/><path d="M9 15c3-3 6-4 9-5"/>',
  megaphone: '<path d="M3 11v2a1 1 0 0 0 1 1h2l9 5V5L6 10H4a1 1 0 0 0-1 1z"/><path d="M18 8a4 4 0 0 1 0 8"/><path d="M6 14v3a2 2 0 0 0 2 2h1"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z"/><path d="M7 4H4v2a3 3 0 0 0 3 3M17 4h3v2a3 3 0 0 1-3 3"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5 5-2z"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z"/><path d="M4 5v16"/><path d="M9 7h6"/>',
  rupee: '<path d="M7 4h10M12 4v16M7 8h8a3 3 0 0 1 0 6H7"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  star: '<path d="M12 3l2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.8L6.6 19.6l1-6L3.3 9.4l6-.9z"/>',
  computer: '<rect x="4" y="5" width="16" height="10" rx="1"/><path d="M2 20h20"/>',
  cpu: '<rect x="7" y="7" width="10" height="10" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  building: '<path d="M4 21V6l8-3 8 3v15"/><path d="M8 9h2M14 9h2M8 13h2M14 13h2M10 21v-4h4v4"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/>',
  plane: '<path d="M17.8 19.2 16 11l3.5-3.5a2.1 2.1 0 0 0-3-3L13 8 4.8 6.2a1 1 0 0 0-.9 1.7l4.3 2.6L9 15l-2.5 2.5a1 1 0 0 0 1.4 1.4L11 16.5l2.6 4.3a1 1 0 0 0 1.7-.9z"/>',
  car: '<path d="M5 13l1.5-4.5A2 2 0 0 1 8.4 7h7.2a2 2 0 0 1 1.9 1.5L19 13"/><rect x="3" y="13" width="18" height="6" rx="1"/><circle cx="7.5" cy="19" r="1.5"/><circle cx="16.5" cy="19" r="1.5"/>',
  dna: '<path d="M5 3c0 6 14 6 14 12M19 3c0 6-14 6-14 12M5 21c0-2 14-2 14 0M5 3c0 2 14 2 14 0M7 7h10M7 17h10"/>',
  wrench: '<path d="M14.7 6.3a4 4 0 0 1-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.8-.7-.7-2.8 2.8-2.6z"/>',
};

export function iconSvg(name, cls) {
  const p = ICON_PATHS[name] || ICON_PATHS.compass;
  return '<svg ' + STROKE + ' viewBox="0 0 24 24" class="' + (cls || 'icon') + '">' + p + '</svg>';
}

const CATEGORY_ICON = {
  'Engineering': 'cog',
  'Medical & Health': 'heart',
  'Sciences': 'flask',
  'Commerce & Finance': 'chart',
  'Management': 'briefcase',
  'Law': 'scale',
  'Design & Creative': 'palette',
  'Civil Services & Government': 'landmark',
  'Defence': 'shield',
  'Agriculture': 'leaf',
  'Media & Communication': 'megaphone',
  'Hospitality & Sports': 'trophy',
};

const TITLE_HINT = [
  [/computer|csc|information tech|software|it\b|i\.t\./i, 'computer'],
  [/artificial intelligence|\bai\b|machine learning|\bml\b|data scien|robotics|neural/i, 'cpu'],
  [/aerospace|aeronautical|aircraft/i, 'plane'],
  [/automobile|automotive|mechanical/i, 'wrench'],
  [/civil engin|structur/i, 'building'],
  [/electrical|electronics|\bece\b|\beee\b/i, 'bolt'],
  [/chemical/i, 'flask'],
  [/biotech|bio.?tech|genetic/i, 'dna'],
  [/doctor|medic|surgeon|nurs|physician|dentist/i, 'heart'],
  [/architect/i, 'building'],
  [/developer|programmer|engineer/i, 'cog'],
  [/scien|research|physic|chemist|biolog|math/i, 'flask'],
  [/finance|account|econom|bank|business|commerce|mba|manage/i, 'chart'],
  [/law|legal|advocate|judge/i, 'scale'],
  [/design|artist|animat|ux|ui|creative|fashion/i, 'palette'],
  [/ias|ips|govt|ublic|service/i, 'landmark'],
  [/defen|army|navy|air force|military|police/i, 'shield'],
  [/agri|farm|horticult|food scien/i, 'leaf'],
  [/media|journal|film|news|communication|writer/i, 'megaphone'],
  [/sport|hotel|hospitality|tourism|event/i, 'trophy'],
  [/teach|professor|lecturer|edu/i, 'book'],
];

export function careerIcon(category, title) {
  const t = title || '';
  for (const [re, name] of TITLE_HINT) if (re.test(t)) return name;
  if (category && CATEGORY_ICON[category]) return CATEGORY_ICON[category];
  return 'compass';
}

const GO_ICON = {
  'career': 'target',
  'college': 'graduation',
  'scholarships': 'award',
  'planner': 'calendar',
  'quiz': 'quiz',
  'veda': 'brain',
};

export function suggestionIcon(go, title) {
  if (go && GO_ICON[go]) return GO_ICON[go];
  const t = title || '';
  for (const [re, name] of TITLE_HINT) if (re.test(t)) return name;
  return 'sparkles';
}
