// Learnify — the profile screen.
// Route: `/profile`
//
// Signup only collects a name, an email and a password, so this is where the
// rest of the identity is actually filled in. Two independent forms share the
// view deliberately: a person changing their password should not have to
// resubmit their department, and a failed save should not clear either.

import { api, esc, toast } from './utils.js?v=62';
import * as ui from './ui.js?v=62';
import { currentUser, refreshUser, bindSignOut } from './app.js?v=62';
import { iconSvg } from './icons.js?v=62';

// Where each role is most likely to want to go next.
const ROLE_LINKS = {
  ALPHA: [
    ['book', 'My courses', 'Pick up where you left off', '#/courses'],
    ['quiz', 'Open tests', 'Practice sets and formal exams', '#/tests'],
    ['chart', 'My reports', 'Veda performance reports', '#/reports'],
    ['target', 'Competency', 'What you are working towards', '#/competency'],
  ],
  MASTER: [
    ['book', 'My courses', 'Build and submit content', '#/courses'],
    ['quiz', 'Questionnaires & exams', 'Author and release tests', '#/tests'],
    ['cpu', 'AI draft queue', 'Review generated questions', '#/drafts'],
    ['layers', 'Library', 'Reusable lectures and decks', '#/library'],
  ],
  SUPREME: [
    ['shield', 'Control room', 'Platform overview', '#/admin'],
    ['send', 'Content queue', 'Release what trainers submit', '#/admin/content'],
    ['flag', 'Exam controls', 'Live, extend, void, delete', '#/admin/exams'],
    ['users', 'Users', 'Roles, suspensions, records', '#/admin/users'],
  ],
};

const ROLE_NAME = { ALPHA: 'Trainee', MASTER: 'Trainer', SUPREME: 'Administrator' };

// Each role comes to this page with a different question — "what am I
// covered by", "what have I shipped", "what is waiting on me" — so the page
// leads with the answer to that one instead of showing everybody the same
// screen with different link labels.
const ROLE_COPY = {
  ALPHA: {
    title: 'Your trainee profile',
    sub: 'How you appear to trainers, and where you stand in your courses.',
    statsTitle: 'Your learning',
    statsHint: 'Live numbers from your enrolments, attempts and certificates.',
    statsHref: '#/courses',
    aboutTitle: 'About you',
    aboutHint: 'Trainers see this on your competency and report pages.',
    jump: 'Pick up where you left off',
  },
  MASTER: {
    title: 'Your trainer profile',
    sub: 'What you have authored, and how it is doing with your trainees.',
    statsTitle: 'Your content',
    statsHint: 'Everything you have built, and what is waiting on a decision.',
    statsHref: '#/courses',
    aboutTitle: 'About you',
    aboutHint: 'Shown to trainees on the courses you deliver.',
    jump: 'Go straight to your work',
  },
  SUPREME: {
    title: 'Your administrator profile',
    sub: 'Your account, plus the state of the portal as of right now.',
    statsTitle: 'Portal at a glance',
    statsHint: 'Accounts, approvals and content waiting on a decision.',
    statsHref: '#/admin',
    aboutTitle: 'About you',
    aboutHint: 'Shown beside your actions in the audit trail.',
    jump: 'Open the console',
  },
};

export async function render(root, ctx) {
  // Read the role once here so the whole layout is built for it; the identity
  // card below re-reads the account afterwards in case the cache is stale.
  const role = ((currentUser() || {}).role) || 'ALPHA';
  const copy = ROLE_COPY[role] || ROLE_COPY.ALPHA;

  root.innerHTML = ui.head({
    title: copy.title,
    sub: copy.sub,
  })
  + `<div class="two-col wide-left">
      <div class="stack">
        <div class="card" data-rolecard>${ui.loading('your numbers')}</div>
        <div class="card">
          <div class="card-head">
            <h3>${esc(copy.aboutTitle)}</h3>
            <span class="sm muted">${esc(copy.aboutHint)}</span>
          </div>
          <div data-about>${ui.loading('your details')}</div>
        </div>
        <div class="card">
          <div class="card-head"><h3>Change password</h3></div>
          <div data-password>${ui.loading('password form')}</div>
        </div>
      </div>

      <div class="stack">
        <div class="card" data-identity>${ui.loading('your account')}</div>
        <div class="card">
          <div class="card-head"><h3>${esc(copy.jump)}</h3></div>
          <div data-links class="stack tight"></div>
        </div>
      </div>
    </div>`;

  paintLinks(root.querySelector('[data-links]'));
  loadIdentity(root);
  loadRoleCard(root, role, copy);
  await loadAbout(root);
  bindPassword(root);
  return { destroy: () => {} };
}

// ─── Role-specific numbers ─────────────────────────────────────────────────

async function loadRoleCard(root, role, copy) {
  const host = root.querySelector('[data-rolecard]');
  if (!host) return;

  const me = currentUser() || {};
  if (me.status === 'PENDING') {
    // Every one of the endpoints below is role-gated, so an unapproved
    // account would just collect 403s. Say why instead.
    host.innerHTML = `
      <div class="card-head"><h3>${esc(copy.statsTitle)}</h3></div>
      ${ui.note('These numbers appear once an administrator approves your '
        + 'account.', 'warn')}`;
    return;
  }

  const endpoint = role === 'SUPREME'
    ? '/v1/admin/dashboard' : '/v1/participation/stats';
  const title = esc(copy.statsTitle);

  let payload;
  try {
    payload = ui.data(await api(endpoint)) || {};
  } catch (err) {
    host.innerHTML = `<div class="card-head"><h3>${title}</h3></div>`
      + ui.errorBlock(err.message);
    return;
  }

  host.innerHTML = `
    <div class="card-head">
      <h3>${title}</h3>
      <a class="link" style="margin-left:auto" href="${esc(copy.statsHref)}">Open &rarr;</a>
    </div>
    <p class="sm muted" style="margin:0 0 12px">${esc(copy.statsHint)}</p>
    <div class="stat-row">${tilesFor(role, payload)}</div>`;
}

/** The four-to-six numbers that actually describe this role's work. */
function tilesFor(role, s) {
  if (role === 'SUPREME') {
    const c = s.counts || {};
    const learn = s.learning || {};
    const certs = s.certificates || {};
    const queue = Array.isArray(s.pending) ? s.pending.length : 0;
    return [
      ui.tile({ icon: 'users', value: c.users || 0, label: 'Accounts',
        hint: `${Number(s.pending_accounts) || 0} awaiting approval` }),
      ui.tile({ icon: 'send', value: queue, label: 'Content queue',
        hint: queue ? 'Awaiting release' : 'Nothing waiting' }),
      ui.tile({ icon: 'book', value: c.courses || 0, label: 'Courses',
        hint: `${learn.enrollments || 0} enrolments` }),
      ui.tile({ icon: 'flag', value: c.assessments || 0, label: 'Assessments',
        hint: `${c.questionnaires || 0} questionnaires` }),
      ui.tile({ icon: 'cert', value: certs.valid || 0, label: 'Certificates',
        hint: `${certs.revoked || 0} revoked` }),
    ].join('');
  }

  if (role === 'MASTER') {
    return [
      ui.tile({ icon: 'book', value: s.courses || 0, label: 'Courses',
        hint: `${s.trainees || 0} enrolments` }),
      ui.tile({ icon: 'quiz', value: s.questionnaires || 0,
        label: 'Questionnaires', hint: 'Practice with a deadline' }),
      ui.tile({ icon: 'flag', value: s.assessments || 0, label: 'Assessments',
        hint: 'Formal exams' }),
      ui.tile({ icon: 'layers', value: s.library_items || 0,
        label: 'Library items', hint: 'Reusable content' }),
      ui.tile({ icon: 'clock', value: s.pending_release || 0,
        label: 'Waiting on release',
        hint: s.pending_release ? 'Sent to Supreme' : 'Queue is clear' }),
      ui.tile({ icon: 'users', value: s.trainees || 0, label: 'Trainees reached',
        hint: 'Across all your courses' }),
    ].join('');
  }

  return [
    ui.tile({ icon: 'book', value: s.enrolled || 0, label: 'Courses enrolled',
      hint: `${s.completed_courses || 0} completed` }),
    ui.tile({ icon: 'target', value: `${Math.round(s.avg_progress || 0)}%`,
      label: 'Average progress',
      hint: `${s.lessons_completed || 0} lessons done` }),
    ui.tile({ icon: 'cert', value: s.certificates || 0, label: 'Certificates',
      hint: 'Issued on passing' }),
    ui.tile({ icon: 'chart',
      value: s.exams_taken ? `${Math.round(s.avg_score || 0)}%` : '—',
      label: 'Average score',
      hint: `${s.exams_passed || 0} of ${s.exams_taken || 0} exams passed` }),
  ].join('');
}

// ─── Identity card ──────────────────────────────────────────────────────────

async function loadIdentity(root) {
  const host = root.querySelector('[data-identity]');
  let u;
  try {
    // Prefer the live account over the cached one — a profile edit elsewhere
    // in the app can leave the cache a few steps behind.
    const res = await api('/auth/me');
    u = (res && res.user) || currentUser() || {};
  } catch (err) {
    u = currentUser() || {};
    if (!u.id) { host.innerHTML = ui.errorBlock(err.message); return; }
  }

  const role = u.role || 'ALPHA';
  const status = u.status || 'ACTIVE';

  host.innerHTML = `
    <div class="profile-id">
      ${ui.who(u.name || u.email || 'You', u.email || '')}
      <div class="row gap" style="margin-top:12px;flex-wrap:wrap">
        <span class="role-tag ${esc(String(role).toLowerCase())}">${esc(ROLE_NAME[role] || role)}</span>
        ${ui.tag(status)}
      </div>
      ${u.must_change_password ? ui.note(
        'Your password still needs to be changed. Use the form below.',
        'warn') : ''}
      <div class="row gap" style="margin-top:14px;flex-wrap:wrap">
        <button class="btn ghost sm" data-signout type="button">Sign out</button>
      </div>
    </div>
    <div class="mt">${ui.kv([
      ['Department', u.department],
      ['Designation', u.designation],
      ['Headline', u.headline],
      ['Phone', u.phone],
      ['Member since', u.created_at ? ui.fmtDate(u.created_at) : ''],
    ])}</div>
    ${u.bio ? `<div class="mt"><div class="section-title">Bio</div>
      <p style="margin:0;line-height:1.6;white-space:pre-wrap">${esc(u.bio)}</p></div>` : ''}`;

  bindSignOut(host.querySelector('[data-signout]'));
}

function paintLinks(host) {
  const role = (currentUser() && currentUser().role) || 'ALPHA';
  const links = ROLE_LINKS[role] || ROLE_LINKS.ALPHA;
  host.innerHTML = links.map(([icon, title, sub, href]) => `
    <a class="dash-shortcut" href="${esc(href)}">
      <span class="dash-shortcut-ico">${iconSvg(icon)}</span>
      <b>${esc(title)}</b>
      <small>${esc(sub)}</small>
    </a>`).join('');
}

// ─── About form ─────────────────────────────────────────────────────────────

async function loadAbout(root) {
  const host = root.querySelector('[data-about]');
  const u = (currentUser() || {});
  const v = (k) => esc(u[k] == null ? '' : String(u[k]));

  // `profile` fields only — role/status are protected server-side and cannot
  // be self-escalated through this endpoint.
  host.innerHTML = `
    <form class="stack" data-about-form novalidate>
      <div class="field">
        <label for="pf-name">Full name</label>
        <input id="pf-name" name="name" type="text" maxlength="120"
          value="${v('name')}" required autocomplete="name">
      </div>
      <div class="two-col" style="gap:12px">
        <div class="field">
          <label for="pf-dept">Department</label>
          <input id="pf-dept" name="department" type="text" maxlength="120"
            value="${v('department')}" placeholder="e.g. Computer Science">
        </div>
        <div class="field">
          <label for="pf-desig">Designation</label>
          <input id="pf-desig" name="designation" type="text" maxlength="120"
            value="${v('designation')}" placeholder="e.g. Assistant Professor">
        </div>
      </div>
      <div class="field">
        <label for="pf-head">Headline</label>
        <input id="pf-head" name="headline" type="text" maxlength="160"
          value="${v('headline')}" placeholder="One line about what you do">
      </div>
      <div class="field">
        <label for="pf-phone">Phone</label>
        <input id="pf-phone" name="phone" type="tel" maxlength="30"
          value="${v('phone')}" placeholder="Optional">
      </div>
      <div class="field">
        <label for="pf-bio">Bio</label>
        <textarea id="pf-bio" name="bio" rows="4" maxlength="2000"
          placeholder="Background, interests, what you teach or are learning.">${v('bio')}</textarea>
      </div>
      <div class="auth-err" data-err role="alert"></div>
      <div class="row gap" style="justify-content:flex-end">
        <button class="btn primary sm" type="submit">Save changes</button>
      </div>
    </form>`;

  const form = host.querySelector('[data-about-form]');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    ui.formError(form, '');
    const name = form.querySelector('[name=name]').value.trim();
    if (!name) { ui.formError(form, 'A name is required.'); return; }

    const values = ui.formValues(form);
    Object.keys(values).forEach((k) => { values[k] = values[k].trim(); });

    const btn = form.querySelector('button[type=submit]');
    try {
      await ui.busy(btn, 'Saving…', async () => {
        const res = await api('/auth/profile', {
          method: 'PUT', body: JSON.stringify(values),
        });
        const saved = (res && res.user) || null;
        if (saved) await refreshUser(saved);
        else await refreshUser();
        toast('Profile saved.');
        await loadIdentity(root);
      });
    } catch (err) {
      ui.formError(form, err.message);
    }
  });
}

// ─── Password form ──────────────────────────────────────────────────────────

function bindPassword(root) {
  const host = root.querySelector('[data-password]');
  host.innerHTML = `
    <form class="stack" data-pw-form novalidate>
      <div class="field">
        <label for="pw-current">Current password</label>
        <input id="pw-current" name="current_password" type="password"
          autocomplete="current-password" required>
      </div>
      <div class="field">
        <label for="pw-new">New password</label>
        <input id="pw-new" name="new_password" type="password"
          autocomplete="new-password" minlength="8" required>
      </div>
      <div class="field">
        <label for="pw-confirm">Confirm new password</label>
        <input id="pw-confirm" name="confirm" type="password"
          autocomplete="new-password" minlength="8" required>
      </div>
      <div class="auth-err" data-err role="alert"></div>
      <div class="row gap" style="justify-content:flex-end">
        <button class="btn primary sm" type="submit">Update password</button>
      </div>
    </form>`;

  const form = host.querySelector('[data-pw-form]');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    ui.formError(form, '');
    const values = ui.formValues(form);
    const cur = values.current_password || '';
    const next = values.new_password || '';
    const again = values.confirm || '';

    if (!cur) { ui.formError(form, 'Enter your current password.'); return; }
    if (next.length < 8) {
      ui.formError(form, 'The new password must be at least 8 characters.');
      return;
    }
    if (next !== again) { ui.formError(form, 'The two new passwords do not match.'); return; }
    if (next === cur) { ui.formError(form, 'Choose a password you have not used here.'); return; }

    const btn = form.querySelector('button[type=submit]');
    try {
      await ui.busy(btn, 'Updating…', async () => {
        await api('/auth/change-password', {
          method: 'POST',
          body: JSON.stringify({
            current_password: cur,
            new_password: next,
            confirm_password: again,
          }),
        });
        form.reset();
        await refreshUser();
        toast('Password updated.');
        await loadIdentity(root);
      });
    } catch (err) {
      ui.formError(form, err.message);
    }
  });
}
