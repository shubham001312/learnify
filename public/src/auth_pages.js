// Sign-in and registration screens — one pair per role.
// Route: /{alpha|master|supreme}/{login|signup}

import { esc, toast } from './utils.js?v=62';
import { login, register, homeFor, isPending } from './auth.js?v=62';
import { go, ROLE_LABEL } from './app.js?v=62';

// The Administrator sign-up is invitation-only, so the token travels in the
// URL (`#/supreme/signup?invite=…`) of the link an Administrator shared.
// `currentPath()` strips the query, so it is read straight off the hash here.
function inviteToken() {
  try {
    const raw = location.hash || '';
    const q = raw.indexOf('?') === -1 ? '' : raw.slice(raw.indexOf('?') + 1);
    return new URLSearchParams(q).get('invite') || '';
  } catch (_) {
    return '';
  }
}

const ROLES = {
  alpha: {
    key: 'ALPHA', tag: 'Trainee', title: 'Start learning',
    blurb: 'Work through published courses, sit assessments, earn certificates '
         + 'and see exactly where you stand against the industry benchmark.',
    perks: ['All published courses', 'Timed practice and formal assessments',
            'Veda-branded performance reports', 'Certificates on passing'],
  },
  master: {
    key: 'MASTER', tag: 'Trainer', title: 'Build and deliver training',
    blurb: 'Author courses with the five-step wizard, write questionnaires and '
         + 'assessments, generate question drafts with AI, then submit your work '
         + 'for release.',
    perks: ['Five-step resumable course wizard', 'AI question drafts you can edit',
            'Trainee roster and progress', 'Competency self-assessment'],
  },
  supreme: {
    key: 'SUPREME', tag: 'Administrator', title: 'Run the portal',
    blurb: 'Publish to the whole organisation, release or reject trainer content, '
         + 'watch exams live, and keep every account and audit entry in view.',
    perks: ['Release and reject all content', 'Live exam controls',
            'Account suspension and audit log', 'Organisation-wide feed'],
  },
};

export function auth(root, ctx) {
  const slug = ctx.params.role || 'alpha';
  const mode = ctx.params.mode === 'signup' ? 'signup' : 'login';
  const r = ROLES[slug] || ROLES.alpha;
  const other = slug === 'alpha' ? 'master' : 'alpha';
  // Only the Administrator sign-up travels with a token, and only on signup.
  const invite = mode === 'signup' && r.key === 'SUPREME' ? inviteToken() : '';

  root.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-hero">
        <span class="role-tag">${esc(r.tag)} &middot; ${esc(r.key)}</span>
        <h1>${esc(mode === 'signup' ? r.title : 'Welcome back')}</h1>
        <p>${esc(r.blurb)}</p>
        ${mode === 'signup' ? `<ul class="perk-list">${r.perks.map(
          (p) => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}
      </div>

      <div class="auth-card">
        <div class="seg" role="tablist">
          <button class="seg-btn${mode === 'login' ? ' active' : ''}" data-go="/${slug}/login">Sign in</button>
          <button class="seg-btn${mode === 'signup' ? ' active' : ''}" data-go="/${slug}/signup">Create account</button>
        </div>

        ${mode === 'signup' && r.key === 'SUPREME' ? `
          <p class="auth-alt dim" style="margin-top:10px">
            ${invite
              ? 'Invite link recognised — this address will become an administrator.'
              : 'Administrator sign-up is invitation-only: ask an administrator to '
                + 'send you a link to this page. On a brand-new portal the very '
                + 'first administrator can register directly.'}
          </p>` : ''}

        <form class="auth-form" id="auth-form" novalidate>
          ${mode === 'signup' ? `
            <div class="field">
              <label for="f-name">Full name</label>
              <input id="f-name" name="name" type="text" autocomplete="name" required
                     placeholder="e.g. Ravi Sharma">
            </div>` : ''}

          ${mode === 'signup' && r.key === 'SUPREME' ? `
            <div class="field">
              <label for="f-invite">Administrator invite</label>
              <input id="f-invite" name="invite" type="text" autocomplete="off"
                     maxlength="200" value="${esc(invite)}"${invite ? ' readonly' : ''}
                     placeholder="${invite ? 'Invite from your link' : 'Paste your invite token'}">
            </div>` : ''}

          <div class="field">
            <label for="f-email">Email</label>
            <input id="f-email" name="email" type="email" autocomplete="email" required
                   placeholder="you@organisation.org">
          </div>

          <div class="field">
            <label for="f-pass">Password</label>
            <input id="f-pass" name="password" type="password"
                   autocomplete="${mode === 'signup' ? 'new-password' : 'current-password'}"
                   required minlength="8"
                   placeholder="${mode === 'signup' ? 'At least 8 characters' : 'Your password'}">
          </div>

          <div class="auth-err" id="auth-err" role="alert"></div>

          <button class="btn primary block" type="submit" id="auth-submit">
            ${mode === 'signup' ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <p class="auth-alt">
          ${mode === 'signup'
            ? `Already registered? <a href="#/${slug}/login">Sign in</a>`
            : `No account yet? <a href="#/${slug}/signup">Create one</a>`}
        </p>
        <p class="auth-alt">
          I am a <a href="#/${other}/${mode}">${other === 'alpha' ? 'trainee' : 'trainer'}</a> &middot;
          <a href="#/supreme/${mode}">administrator</a>${mode === 'signup'
            ? ' <span class="dim">(by invite)</span>' : ''}
        </p>
        <p class="auth-alt dim">
          Signed up by mistake? <a href="#/">Back to home</a>
        </p>
      </div>
    </div>`;

  root.querySelectorAll('[data-go]').forEach((b) =>
    b.addEventListener('click', () => go(b.dataset.go)));

  const form = root.querySelector('#auth-form');
  const errBox = root.querySelector('#auth-err');
  const submit = root.querySelector('#auth-submit');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.textContent = '';

    const email = form.email.value.trim();
    const password = form.password.value;
    const name = mode === 'signup' ? form.name.value.trim() : '';

    if (mode === 'signup' && !name) { errBox.textContent = 'Please enter your name.'; return; }
    if (!email) { errBox.textContent = 'Please enter your email.'; return; }
    if (!password) { errBox.textContent = 'Please enter your password.'; return; }
    if (mode === 'signup' && password.length < 8) {
      errBox.textContent = 'Password must be at least 8 characters.'; return;
    }

    submit.disabled = true;
    submit.textContent = mode === 'signup' ? 'Creating…' : 'Signing in…';

    try {
      let signed;
      if (mode === 'signup') {
        const inviteField = form.querySelector('#f-invite');
        signed = await register({
          name, email, password, role: r.key,
          invite: inviteField ? inviteField.value.trim() : '',
        });
      } else {
        signed = await login(email, password);
      }

      const account = (signed && signed.user) || null;
      if (isPending(account)) {
        // The account exists but nothing is reachable yet, so send it to the
        // screen that says so instead of a dashboard that answers every call
        // with 403. The server decides approval, never this branch.
        toast(mode === 'signup'
          ? 'Account created. An administrator has to approve it before you can use the portal.'
          : 'Signed in — your account is still waiting for approval.');
        go('/pending');
        return;
      }
      toast(mode === 'signup'
        ? `Welcome, ${name.split(' ')[0]}. Your ${r.tag.toLowerCase()} account is ready.`
        : 'Signed in.');
      go(homeFor(account));
    } catch (err) {
      errBox.textContent = err && err.message ? err.message : 'Could not sign you in.';
      submit.disabled = false;
      submit.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
    }
  });
}
