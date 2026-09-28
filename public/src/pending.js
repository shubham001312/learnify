// Learnify — the "waiting for approval" screen.
// Route: `/pending`
//
// A Trainee or Trainer who signs up lands here. The account exists and the
// credentials are good, but every role-gated route answers
// 403 ACCOUNT_PENDING_APPROVAL until a SUPREME approves it (see
// backend/middleware/rbac.py::_refuse_if_not_active). The screen's job is to
// say that plainly instead of looking like a dashboard that has broken.

import { api, esc, toast, setUser } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { currentUser, bindSignOut, go } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';

const ROLE_NAME = { ALPHA: 'Trainee', MASTER: 'Trainer', SUPREME: 'Administrator' };

// How often to look again on its own. Long enough not to feel twitchy, short
// enough that an approval shows up without anyone pressing a button.
const RECHECK_MS = 45000;

export async function render(root) {
  // A signed-out visitor bounced here by an old link has no account to wait on.
  const u = currentUser();
  if (!u || !u.id) { go('/'); return { destroy: () => {} }; }

  const role = u.role || 'ALPHA';
  const waiting = u.status === 'PENDING';

  root.innerHTML = ui.head({
    title: waiting ? 'Waiting for approval' : 'You are in',
    sub: waiting
      ? 'An administrator has to approve your account before the portal opens up.'
      : 'Your account has been approved.',
  })
  + `<div class="two-col wide-left mb">
      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>What happens next</h3></div>
          <div class="stack">
            ${ui.note(
              'Your account has been created and your sign-in works. Until an '
              + 'administrator approves it you will not be able to open courses, '
              + 'tests or reports — nothing has gone wrong with your details.',
              'warn')}
            <div class="stack tight">
              ${step('check', 'Your registration is in the queue',
                     'It sits with the portal administrators, oldest first.')}
              ${step('users', 'An administrator reviews it',
                     'They approve it as-is, or reject it with a reason.')}
              ${step('book', 'The portal opens up',
                     'You will get a notification, and this screen will change '
                     + 'by itself.')}
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>While you wait</h3></div>
          <div class="stack">
            <p style="margin:0;line-height:1.6">
              You can still fix your own details — a name spelling or a
              department is the most common reason an account gets held up.
            </p>
            <div class="row gap" style="flex-wrap:wrap">
              <a class="btn ghost sm" href="#/profile">Open my profile</a>
              <button class="btn ghost sm" data-recheck type="button">
                Check for approval</button>
              <button class="btn ghost sm" data-signout type="button">Sign out</button>
            </div>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>Your account</h3></div>
          <div class="profile-id">
            ${ui.who(u.name || u.email || 'You', u.email || '')}
            <div class="row gap" style="margin-top:12px;flex-wrap:wrap">
              <span class="role-tag ${esc(String(role).toLowerCase())}">${
                esc(ROLE_NAME[role] || role)}</span>
              ${ui.tag(u.status || 'PENDING')}
            </div>
          </div>
          <div class="mt">${ui.kv([
            ['Applied as', ROLE_NAME[role] || role],
            ['Registered', u.created_at ? ui.fmtDate(u.created_at) : '—'],
            ['Department', u.department],
            ['Designation', u.designation],
          ])}</div>
        </div>

        <div class="card">
          <div class="card-head"><h3>Status</h3></div>
          <div data-status>${ui.loading('your approval status')}</div>
        </div>
      </div>
    </div>`;

  bindSignOut(root.querySelector('[data-signout]'));
  ui.click(root, '[data-recheck]', () => recheck(root, true));
  paintStatus(root);

  // Look again on its own so an approval lands without anyone doing anything.
  const timer = setInterval(() => recheck(root, false), RECHECK_MS);
  return { destroy: () => clearInterval(timer) };
}


function step(icon, title, body) {
  return `
    <div class="dash-shortcut" style="cursor:default">
      <span class="dash-shortcut-ico">${iconSvg(icon)}</span>
      <b>${esc(title)}</b>
      <small>${esc(body)}</small>
    </div>`;
}


async function paintStatus(root) {
  const host = root.querySelector('[data-status]');
  if (!host) return;
  try {
    const u = await fetchAccount();
    if (u && u.status !== 'PENDING') { arrive(u); return; }
    host.innerHTML = ui.note(
      'Still waiting for a decision. This page checks again on its own, so '
      + 'you can leave it open.', 'warn');
  } catch (err) {
    // `/auth/me` is the one call an unapproved account is allowed to make, so
    // failing here means the session or the network is the problem, not the
    // approval — say that rather than blaming the queue.
    host.innerHTML = ui.errorBlock(
      'Could not read your approval status: ' + (err.message || 'try again.'));
  }
}


/** Re-read the account and jump out of the waiting room the moment it flips. */
async function recheck(root, loud) {
  try {
    const u = await fetchAccount();
    if (u && u.status !== 'PENDING') { arrive(u); return; }
    if (loud) toast('Still waiting for approval.', 'warn');
    else paintStatus(root);
  } catch (_) {
    if (loud) toast('Could not check for approval. Try again shortly.', 'warn');
  }
}


/**
 * Read `/auth/me` directly instead of going through `refreshUser()`.
 *
 * That helper signs you out when the call fails, which is right almost
 * everywhere and wrong here: a dropped request would throw an unapproved
 * person out of the only screen they can reach and make the retry loop below
 * useless. A failure here is reported to the caller and changes nothing.
 */
async function fetchAccount() {
  const res = await api('/auth/me');
  const u = (res && res.user) || currentUser();
  if (u && u.id) setUser(u);
  return u;
}


function arrive(u) {
  // `setUser` first: the router's guard reads the cached account, so an
  // approval only opens the rest of the portal once that copy is current.
  if (u && u.id) setUser(u);
  toast('Your account has been approved. Welcome in.');
  go('/home');
}
