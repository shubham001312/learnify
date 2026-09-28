// Public pages: the Alpha-focused home screen and the three role landings.
// Route: `/` and `/{alpha|master|supreme}`
//
// Everything here works signed out, so it may not call the API — the course
// catalogue and dashboards are behind auth.

import { esc } from './utils.js?v=64';
import { iconSvg } from './icons.js?v=64';

const ROLE_CARDS = [
  {
    slug: 'alpha', tag: 'Trainee', key: 'ALPHA', icon: 'graduation',
    title: 'Learn and prove it',
    body: 'Work through published courses, practise with questionnaires, sit '
        + 'formal MCQ assessments and earn a certificate the moment you pass.',
    cta: 'Join as a trainee',
  },
  {
    slug: 'master', tag: 'Trainer', key: 'MASTER', icon: 'flask',
    title: 'Teach and assess',
    body: 'Build courses with a five-step resumable wizard, author question banks, '
        + 'generate AI drafts to edit, then submit your content for release.',
    cta: 'Join as a trainer',
  },
  {
    slug: 'supreme', tag: 'Administrator', key: 'SUPREME', icon: 'shield',
    title: 'Govern and publish',
    body: 'Release or reject every piece of trainer content, control exams live, '
        + 'suspend accounts, publish to the whole organisation and read the audit log.',
    cta: 'Admin sign in',
  },
];

const CAPABILITIES = [
  { icon: 'book', title: 'Courses with a real structure',
    body: 'Five resumable wizard steps: details, modules, slots (video, text, '
        + 'attachments), linked tests, then submit for release.' },
  { icon: 'cpu', title: 'AI question drafting',
    body: 'Groq drafts MCQs with topic tags from your syllabus. Nothing goes '
        + 'live automatically — every draft is editable and queued for review.' },
  { icon: 'quiz', title: 'Practice, then the exam',
    body: 'Questionnaires are practice with a deadline. Assessments are the formal '
        + 'subject-wise paper: timed, supervised, and graded on the spot.' },
  { icon: 'award', title: 'Certificates on passing',
    body: 'Clear the passing score on an assessment and a verifiable certificate is '
        + 'issued automatically, with a code you can share.' },
  { icon: 'chart', title: 'Veda-branded reports',
    body: 'A deterministic score breakdown plus AI-written personalisation, and a '
        + 'curated industry benchmark per subject so you know what good looks like.' },
  { icon: 'target', title: 'Competency mapping',
    body: 'Pick a subject and get a ranked, explainable list of trainers by '
        + 'coverage and proficiency — no black box.' },
];

const STATS = [
  ['3', 'roles', 'Trainee, Trainer and Administrator'],
  ['5', 'wizard steps', 'Resumable course authoring'],
  ['2', 'test types', 'Practice with deadline, formal exam'],
  ['90%', 'watch rule', 'Completion unlocks at 90% of video'],
];

/** Signed-out home screen. Alpha-focused; Master/Supreme live in the footer. */
export function home(root, ctx) {
  root.innerHTML = `
    <section class="cc-hero">
      <span class="role-tag">Learnify</span>
      <h1>Check <span>&amp;</span> Mate</h1>
      <p class="cc-hero-lede">
        A digital capacity building and learning management portal for
        organisational training, competency development and knowledge sharing.
      </p>
      <div class="row gap cc-hero-cta">
        <a class="btn primary" href="#/alpha/signup">Start learning</a>
        <a class="btn ghost" href="#/alpha">How it works</a>
      </div>
    </section>

    <section class="cc-stats">
      ${STATS.map(([n, l, h]) => `
        <div class="cc-stat">
          <b>${esc(n)}</b>
          <span>${esc(l)}</span>
          <small>${esc(h)}</small>
        </div>`).join('')}
    </section>

    <section class="cc-sec">
      <h2 class="section-title">Built for three kinds of people</h2>
      <div class="cc-grid three">
        ${ROLE_CARDS.map((r) => `
          <article class="cc-card role">
            <div class="cc-card-head">
              ${iconSvg(r.icon)}
              <span class="role-tag">${esc(r.tag)} &middot; ${esc(r.key)}</span>
            </div>
            <h3>${esc(r.title)}</h3>
            <p>${esc(r.body)}</p>
            <a class="btn sm primary" href="#/${r.slug}">${esc(r.cta)}</a>
          </article>`).join('')}
      </div>
    </section>

    <section class="cc-sec">
      <h2 class="section-title">What the portal does</h2>
      <div class="cc-grid three">
        ${CAPABILITIES.map((c) => `
          <article class="cc-card">
            <div class="cc-card-head">${iconSvg(c.icon)}</div>
            <h3>${esc(c.title)}</h3>
            <p>${esc(c.body)}</p>
          </article>`).join('')}
      </div>
    </section>

    <section class="cc-cta-band">
      <div>
        <h2>Create your trainee account</h2>
        <p>Name, email, password — that is the whole sign-up. Your profile fills
           in the rest.</p>
      </div>
      <a class="btn primary" href="#/alpha/signup">Join as a trainee</a>
    </section>`;
}

/** One of the three role landings: /alpha, /master, /supreme. */
export function role(root, ctx) {
  const slug = ctx.params.role || 'alpha';
  const card = ROLE_CARDS.find((c) => c.slug === slug) || ROLE_CARDS[0];
  const others = ROLE_CARDS.filter((c) => c.slug !== card.slug);

  const detail = {
    alpha: [
      ['Every published course', 'Nothing is hidden from you — if Supreme has '
        + 'released it, you can enrol.'],
      ['Practice before it counts', 'Questionnaires carry a deadline so you '
        + 'rehearse under light pressure.'],
      ['One attempt that matters', 'Assessments are the formal paper. Pass and '
        + 'the certificate is issued automatically.'],
      ['Know your weak topics', 'Every report ranks topics by accuracy and lines '
        + 'them up against the industry benchmark.'],
    ],
    master: [
      ['Five steps, pick up where you left off', 'The wizard saves after every '
        + 'step — close the tab and come back.'],
      ['Slots, not files', 'A slot is video plus text plus attachments plus its '
        + 'linked test.'],
      ['AI drafts, human judgement', 'Generate MCQs by topic, edit them, publish '
        + 'the ones you trust.'],
      ['Your content waits for release', 'Submit for release; Supreme decides. '
        + 'You always see the status.'],
    ],
    supreme: [
      ['Release or reject anything', 'Courses, questionnaires and assessments '
        + 'queue until you clear them.'],
      ['Six live exam controls', 'Delete, watch live attempts, end now, extend '
        + 'the deadline, void an attempt, suspend an account.'],
      ['Publish to everyone', 'Notifications, announcements, achievements and new '
        + 'content land in the home feed.'],
      ['Every action on record', 'An audit log keeps the timestamps and the actor '
        + 'for every admin decision.'],
    ],
  }[card.slug] || [];

  root.innerHTML = `
    <section class="cc-hero slim">
      <span class="role-tag">${esc(card.tag)} &middot; ${esc(card.key)}</span>
      <h1>${esc(card.title)}</h1>
      <p class="cc-hero-lede">${esc(card.body)}</p>
      <div class="row gap cc-hero-cta">
        <a class="btn primary" href="#/${card.slug}/signup">${esc(card.cta)}</a>
        <a class="btn ghost" href="#/${card.slug}/login">I already have an account</a>
      </div>
    </section>

    <section class="cc-sec">
      <div class="cc-grid two">
        ${detail.map(([t, b]) => `
          <article class="cc-card">
            <div class="cc-card-head">${iconSvg(card.icon)}</div>
            <h3>${esc(t)}</h3>
            <p>${esc(b)}</p>
          </article>`).join('')}
      </div>
    </section>

    <section class="cc-sec">
      <div class="cc-two-col">
        <div>
          <h2 class="section-title">The other seats</h2>
          <p class="cc-muted">Everyone on the portal is one of three roles. Yours
             is the one you signed up for.</p>
        </div>
        <div class="cc-grid two">
          ${others.map((o) => `
            <article class="cc-card compact">
              <span class="role-tag">${esc(o.tag)}</span>
              <h3>${esc(o.title)}</h3>
              <a class="link" href="#/${o.slug}">See the ${esc(o.tag.toLowerCase())} page &rarr;</a>
            </article>`).join('')}
        </div>
      </div>
    </section>

    <section class="cc-cta-band">
      <div>
        <h2>Ready?</h2>
        <p>Create your ${esc(card.tag.toLowerCase())} account in one step.</p>
      </div>
      <a class="btn primary" href="#/${card.slug}/signup">Get started</a>
    </section>`;
}
