// LEARNIFY — the administrator (SUPREME) console.
// Routes: `/home` (render), `/admin/users`, `/admin/content`,
//         `/admin/exams`, `/admin/audit`
//
// The exam screen is where the six Supreme controls live:
//   1 delete an exam · 2 watch live attempts · 3 end now
//   4 extend / reopen the deadline · 5 void a trainee's attempt
//   6 suspend an account

import { api, esc, toast, el } from './utils.js?v=62';
import * as ui from './ui.js?v=62';
import {
  openAppModal, closeAppModal, confirmAction, go,
} from './app.js?v=62';
import { iconSvg } from './icons.js?v=62';
import { embed as embedFeed } from './feed.js?v=62';
import { barChart, donutChart, sparkline, emptyChart } from './charts.js?v=62';

const SECTIONS = [
  ['#/admin/approvals', 'Approvals'],
  ['#/admin/content', 'Content queue'],
  ['#/admin/exams', 'Exams'],
  ['#/admin/users', 'Users'],
  ['#/admin/audit', 'Audit log'],
];

function adminNav(active) {
  return `<nav class="admin-nav">${SECTIONS.map(([href, label]) => `
    <a class="admin-nav-link${href === active ? ' active' : ''}" href="${href}">
      ${esc(label)}</a>`).join('')}</nav>`;
}

/** `/admin/<anything-else>` — keep the visitor inside the console. */
function notFound(root, page) {
  root.innerHTML = ui.head({ title: 'No such console page', sub: '' })
    + adminNav('')
    + ui.blank({
        title: `Unknown section: ${esc(page)}`,
        body: 'Pick one of the sections above.',
        action: 'Control room',
        actionHref: '#/admin',
      });
}

// ═══ Approvals ═════════════════════════════════════════════════════════════
// Two gates live on this screen:
//   * Trainee and Trainer sign-ups land in PENDING and can reach nothing but
//     the waiting screen until one of these buttons is pressed.
//   * Creating an Administrator is never a public act — the only way to make
//     one is to mint a token here and share
//     `#/supreme/signup?invite=<token>`.

const ROLE_SHORT = { ALPHA: 'Trainee', MASTER: 'Trainer', SUPREME: 'Administrator' };

async function approvals(root) {
  root.innerHTML = ui.head({
    title: 'Approvals',
    sub: 'Accounts waiting for a decision, and the links that make administrators.',
  })
  + adminNav('#/admin/approvals')
  + `<div class="two-col wide-left mb">
      <div class="stack">
        <div class="card">
          <div class="card-head">
            <h3>Accounts waiting for a decision</h3>
            <a class="link" style="margin-left:auto" href="#/admin/users">All users &rarr;</a>
          </div>
          <div data-pending>${ui.loading('pending accounts')}</div>
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>Invite an administrator</h3></div>
          <div data-invite-form></div>
        </div>
        <div class="card">
          <div class="card-head"><h3>Invitations sent</h3></div>
          <div data-invites>${ui.loading('invitations')}</div>
        </div>
      </div>
    </div>`;

  loadPending(root.querySelector('[data-pending]'));
  paintInviteForm(root.querySelector('[data-invite-form]'));
  loadInvites(root.querySelector('[data-invites]'));
  return { destroy: () => {} };
}

// ── Pending accounts ───────────────────────────────────────────────────────

async function loadPending(host) {
  try {
    const res = await api('/v1/admin/pending');
    const rows = ui.data(res) || [];
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'Nothing waiting',
        body: 'Every account that has registered has had a decision. '
            + 'New sign-ups appear here the moment they are created.',
      });
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map(pendingRow).join('')}</div>`;
    ui.click(host, '[data-approve]', (e, b) => decide(host, b, 'approve'));
    ui.click(host, '[data-reject]', (e, b) => decide(host, b, 'reject'));
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function pendingRow(r) {
  const role = String(r.role || 'ALPHA').toUpperCase();
  return `
    <div class="row gap" style="align-items:center;justify-content:space-between;
         padding:10px 0;border-bottom:1px solid var(--border);flex-wrap:wrap">
      <div class="row gap" style="min-width:0;flex-wrap:wrap">
        ${ui.who(r.name || r.email, r.email || '')}
        <span class="role-tag ${esc(role.toLowerCase())}">${
          esc(ROLE_SHORT[role] || role)}</span>
      </div>
      <div class="row gap" style="justify-content:flex-end;flex-wrap:wrap">
        <span class="sm muted">Joined ${esc(ui.relTime(r.created_at))}</span>
        <button class="btn ghost sm" data-reject="${esc(r.id)}" type="button">Reject</button>
        <button class="btn primary sm" data-approve="${esc(r.id)}" type="button">Approve</button>
      </div>
    </div>`;
}

async function decide(host, btn, kind) {
  const id = btn.dataset[kind];
  const approving = kind === 'approve';
  const ok = await confirmAction(
    approving ? 'Approve this account?' : 'Reject this registration?',
    approving
      ? 'They get into the portal straight away, as the role they applied for.'
      : 'The account stays on record as refused and they are told why. '
        + 'You can still approve it later if this was a mistake.',
    approving ? 'Approve' : 'Reject');
  if (!ok) return;

  try {
    await ui.busy(btn, approving ? 'Approving…' : 'Rejecting…', async () => {
      await api(`/v1/admin/${kind}`, {
        method: 'POST', body: JSON.stringify({ user_id: id }),
      });
    });
    toast(approving ? 'Account approved.' : 'Registration rejected.');
    loadPending(host);
  } catch (err) {
    toast(err.message || 'That decision did not go through.', 'warn');
  }
}

// ── Administrator invitations ──────────────────────────────────────────────

function inviteLink(token) {
  // Built from the host actually being browsed, so a link minted on the
  // laptop still points at the deployed portal when it is shared — and works
  // on localhost without being rewritten by hand.
  return `${location.origin}${location.pathname}`
       + `#/supreme/signup?invite=${encodeURIComponent(token)}`;
}

async function copyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {
    // Permission denied or an insecure origin — fall back rather than fail.
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const done = document.execCommand('copy');
    document.body.removeChild(ta);
    return done;
  } catch (_) {
    return false;
  }
}

function paintInviteForm(host) {
  host.innerHTML = `
    <p class="sm muted" style="margin:0 0 12px">
      Administrator sign-up is closed to the public. Mint a token, send the
      link it produces, and whoever opens it can register as an administrator
      — once per use.
    </p>
    <form class="stack tight" data-invite-form novalidate>
      <div class="two-col">
        <div class="field">
          <label for="iv-email">Email (optional)</label>
          <input id="iv-email" name="email" type="email" maxlength="254"
                 placeholder="Leave blank for any address">
        </div>
        <div class="field">
          <label for="iv-days">Valid for (days)</label>
          <input id="iv-days" name="days" type="number" min="1" max="365" value="7">
        </div>
      </div>
      <div class="two-col">
        <div class="field">
          <label for="iv-uses">Uses</label>
          <input id="iv-uses" name="max_uses" type="number" min="1" max="500" value="1">
        </div>
        <div class="field">
          <label for="iv-note">Note</label>
          <input id="iv-note" name="note" type="text" maxlength="200"
                 placeholder="Who is this for?">
        </div>
      </div>
      <div class="auth-err" data-invite-err role="alert"></div>
      <div class="row gap" style="justify-content:flex-end">
        <button class="btn primary sm" type="submit">Create invite link</button>
      </div>
    </form>
    <div data-invite-out class="mt"></div>`;

  const form = host.querySelector('[data-invite-form]');
  const errBox = host.querySelector('[data-invite-err]');
  const out = host.querySelector('[data-invite-out]');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.textContent = '';
    const payload = {
      email: (form.email.value || '').trim(),
      note: (form.note.value || '').trim(),
      days: Math.max(1, Math.min(365, Number(form.days.value) || 7)),
      max_uses: Math.max(1, Math.min(500, Number(form.max_uses.value) || 1)),
    };
    const btn = form.querySelector('button[type=submit]');
    try {
      await ui.busy(btn, 'Creating…', async () => {
        const d = ui.data(await api('/v1/admin/invites', {
          method: 'POST', body: JSON.stringify(payload),
        })) || {};
        if (!d.token) throw new Error('No invite token came back.');
        showInvite(out, d);
      });
      form.reset();
      toast('Invite link created.');
      loadInvites(document.querySelector('[data-invites]'));
    } catch (ex) {
      errBox.textContent = (ex && ex.message)
        ? ex.message : 'Could not create the invite.';
    }
  });
}

function showInvite(out, d) {
  const link = inviteLink(d.token);
  out.innerHTML = `
    <div class="card">
      <div class="card-head"><h3>Send this link</h3></div>
      <div class="stack tight">
        <input type="text" readonly value="${esc(link)}" data-invite-link
               style="width:100%;box-sizing:border-box;font:500 12px var(--font-mono,monospace)">
        <div class="row gap" style="flex-wrap:wrap;align-items:center">
          <button class="btn primary sm" data-copy type="button">Copy link</button>
          <span class="sm muted">Expires ${esc(ui.fmtDate(d.expires_at))}
            &middot; ${Number(d.max_uses) || 1} use${
              Number(d.max_uses) === 1 ? '' : 's'}</span>
        </div>
      </div>
    </div>`;

  ui.click(out, '[data-copy]', async (e, b) => {
    const done = await copyText(link);
    toast(done ? 'Invite link copied.'
               : 'Could not copy — select the link and copy it yourself.',
          done ? 'ok' : 'warn');
    if (done && b) b.textContent = 'Copied';
  });
}

async function loadInvites(host) {
  if (!host) return;
  try {
    const res = await api('/v1/admin/invites');
    const rows = ui.data(res) || [];
    if (!rows.length) {
      host.innerHTML = '<p class="sm muted" style="margin:0">No invitations yet.</p>';
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map(inviteRow).join('')}</div>`;

    ui.click(host, '[data-copy-link]', async (e, b) => {
      const done = await copyText(b.dataset.copyLink);
      toast(done ? 'Invite link copied.' : 'Could not copy that link.',
            done ? 'ok' : 'warn');
    });
    ui.click(host, '[data-revoke]', async (e, b) => {
      const ok = await confirmAction(
        'Revoke this invitation?',
        'The link stops working immediately and cannot be brought back. '
        + 'You can always mint a new one.', 'Revoke');
      if (!ok) return;
      try {
        await ui.busy(b, 'Revoking…', async () => {
          await api(`/v1/admin/invites/${encodeURIComponent(b.dataset.revoke)}`,
                    { method: 'DELETE' });
        });
        toast('Invitation revoked.');
        loadInvites(host);
      } catch (err) {
        toast(err.message || 'Could not revoke that invitation.', 'warn');
      }
    });
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function inviteRow(r) {
  const state = String(r.state || 'active').toLowerCase();
  const tone = state === 'active' ? 'ok'
    : state === 'exhausted' ? 'mute'
    : 'bad';
  const label = state.charAt(0).toUpperCase() + state.slice(1);
  return `
    <div class="row gap" style="align-items:center;justify-content:space-between;
         padding:9px 0;border-bottom:1px solid var(--border);flex-wrap:wrap">
      <div style="min-width:0">
        <div class="row gap" style="flex-wrap:wrap">
          <b class="sm">${esc(r.email || 'Any address')}</b>
          ${ui.tone(label, tone)}
        </div>
        <div class="sm muted">
          ${Number(r.used_count) || 0}/${Number(r.max_uses) || 1} used
          &middot; expires ${esc(ui.fmtDate(r.expires_at))}
          ${r.note ? `&middot; ${esc(r.note)}` : ''}
        </div>
      </div>
      ${state === 'revoked' ? '' : `
        <div class="row gap">
          <button class="btn ghost sm" type="button"
                  data-copy-link="${esc(inviteLink(r.token))}">Copy link</button>
          <button class="btn ghost sm" type="button"
                  data-revoke="${esc(r.token)}">Revoke</button>
        </div>`}
    </div>`;
}


// ═══ Dashboard ═════════════════════════════════════════════════════════════

export async function render(root, ctx) {
  // `/admin`, `/admin/content`, `/admin/exams`, `/admin/users` and
  // `/admin/audit` all arrive here — the router hands the tail to us as
  // `params.page`, so this function is the dispatch point for the console.
  const page = (ctx && ctx.params && ctx.params.page) || '';
  if (page === 'users') return users(root, ctx);
  if (page === 'approvals') return approvals(root, ctx);
  if (page === 'content') return content(root, ctx);
  if (page === 'exams') return exams(root, ctx);
  if (page === 'audit') return audit(root, ctx);
  if (page) return notFound(root, page);

  root.innerHTML = `
    <section class="dash-hero">
      <div>
        <span class="role-tag supreme">Administrator &middot; SUPREME</span>
        <h1>Control room</h1>
        <p>Release content, run exams live, and keep the whole portal accountable.</p>
      </div>
      <div class="row gap">
        <button class="btn primary sm" data-new-post>+ Publish to the feed</button>
        <a class="btn ghost sm" href="#/admin/content">Open the queue</a>
      </div>
    </section>

    <div data-stats class="stat-row mb">${ui.loading('platform numbers')}</div>

    <div class="two-col mb" data-charts>
      <div class="chart-card">
        <div class="chart-title">Certificates by status</div>
        ${ui.loading('certificates')}
      </div>
      <div class="chart-card">
        <div class="chart-title">Accounts by role</div>
        ${ui.loading('accounts')}
      </div>
    </div>

    <div class="two-col wide-left mb">
      <div class="card">
        <div class="card-head">
          <h3>Waiting on your decision</h3>
          <a class="link" href="#/admin/content">Full queue &rarr;</a>
        </div>
        <div data-queue>${ui.loading('the queue')}</div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h3>People</h3>
            <a class="link" href="#/admin/users">Manage &rarr;</a></div>
          <div data-people>${ui.loading('accounts')}</div>
        </div>
        <div class="card">
          <div class="card-head"><h3>Recent activity</h3>
            <a class="link" href="#/admin/audit">Audit log &rarr;</a></div>
          <div data-activity>${ui.loading('activity')}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>What's new</h3>
        <a class="link" href="#/feed">Open the feed &rarr;</a>
      </div>
      <div data-feed class="stack">${ui.loading('updates')}</div>
    </div>`;

  ui.click(root, '[data-new-post]', () => go('/feed'));
  embedFeed(root.querySelector('[data-feed]'), { limit: 4, manage: true });
  loadDashboard(root);
  return { destroy: () => {} };
}

async function loadDashboard(root) {
  let d;
  try {
    d = ui.data(await api('/v1/admin/dashboard'));
    if (!d) throw new Error('The dashboard did not load.');
  } catch (err) {
    root.querySelector('[data-stats]').innerHTML = ui.errorBlock(err.message);
    return;
  }

  const c = d.counts || {};
  const learn = d.learning || {};
  const certs = d.certificates || {};

  root.querySelector('[data-stats]').innerHTML = [
    ui.tile({ icon: 'users', value: c.users || 0, label: 'Accounts',
      hint: 'Trainees, trainers, admins' }),
    ui.tile({ icon: 'book', value: c.courses || 0, label: 'Courses',
      hint: `${learn.enrollments || 0} enrolments` }),
    ui.tile({ icon: 'flag', value: c.assessments || 0, label: 'Assessments',
      hint: `${c.questionnaires || 0} questionnaires` }),
    ui.tile({ icon: 'target', value: `${learn.completion_rate || 0}%`,
      label: 'Completion rate', hint: `${learn.completed || 0} courses finished` }),
    ui.tile({ icon: 'cert', value: certs.valid || 0, label: 'Valid certificates',
      hint: `${certs.revoked || 0} revoked` }),
    ui.tile({ icon: 'chart', value: c.reports || 0, label: 'Reports',
      hint: 'Veda performance reports' }),
  ].join('');

  const queue = d.pending || [];
  const qHost = root.querySelector('[data-queue]');
  qHost.innerHTML = queue.length
    ? `<div class="stack tight">${queue.slice(0, 7).map(queueRow).join('')}</div>`
    : ui.blank({
        title: 'The queue is clear',
        body: 'Nothing is waiting on you. Trainers see their status on their own dashboard.',
      });

  const byRole = d.users_by_role || {};
  root.querySelector('[data-people]').innerHTML = `
    <div class="stack tight">
      ${['ALPHA', 'MASTER', 'SUPREME'].map((r) => {
        const v = byRole[r] || { total: 0, active: 0, suspended: 0 };
        const label = r === 'ALPHA' ? 'Trainees' : r === 'MASTER' ? 'Trainers' : 'Administrators';
        return `
          <div class="dash-role">
            <span class="role-tag ${r.toLowerCase()}">${esc(label)}</span>
            <div class="dash-role-num">
              <b>${v.total || 0}</b>
              <small class="sm muted">${v.active || 0} active${
                v.suspended ? ` · ${v.suspended} suspended` : ''}${
                v.pending ? ` · ${v.pending} waiting` : ''}</small>
            </div>
            <a class="link" href="#/admin/users">View &rarr;</a>
          </div>`;
      }).join('')}
      ${Number(d.pending_accounts) ? `
        <a class="dash-shortcut" href="#/admin/approvals">
          <span class="dash-shortcut-ico">${iconSvg('clock')}</span>
          <b>${Number(d.pending_accounts)} waiting for approval</b>
          <small>Registered, but unable to get in until you decide</small>
        </a>` : ''}
    </div>`;

  // Charts read the same payload as the tiles above — no second request.
  const chartsBox = root.querySelector('[data-charts]');
  if (chartsBox) chartsBox.innerHTML = certChart(certs) + roleChart(byRole);

  const acts = d.activity || [];
  root.querySelector('[data-activity]').innerHTML = acts.length
    ? `${activitySpark(acts)}<div class="stack tight">${acts.slice(0, 8).map((a) => `
        <div class="dash-act">
          <span class="dash-act-act">${esc(prettifyAction(a.action))}</span>
          <span class="sm muted">${esc(a.actor)} · ${esc(ui.relTime(a.created_at))}</span>
        </div>`).join('')}</div>`
    : '<div class="empty-state">No activity recorded yet.</div>';
}

// ─── Dashboard charts ──────────────────────────────────────────────────────

/** Valid vs revoked certificates, with the average score kept as a caption. */
function certChart(certs) {
  const valid = Number(certs.valid) || 0;
  const revoked = Number(certs.revoked) || 0;
  const body = valid + revoked > 0
    ? `<p class="chart-note">Average score across valid certificates: ${
        ui.pct(Number(certs.avg_score) || 0)}.</p>
       ${donutChart([
         { label: 'Valid', value: valid, tone: 'green' },
         { label: 'Revoked', value: revoked, tone: 'red' },
       ], { title: 'Certificates by status' })}`
    : emptyChart('No certificates have been issued yet.');
  return `
    <div class="chart-card">
      <div class="chart-title">Certificates by status</div>
      ${body}
    </div>`;
}

/** Accounts per role — the shape behind the People card's three rows. */
function roleChart(byRole) {
  const at = (role) => Number((byRole[role] || {}).total) || 0;
  const items = [
    { label: 'Trainees', value: at('ALPHA') },
    { label: 'Trainers', value: at('MASTER') },
    { label: 'Administrators', value: at('SUPREME') },
  ];
  const total = items.reduce((s, i) => s + i.value, 0);
  const body = total > 0
    ? `<p class="chart-note">${total} account${total === 1 ? '' : 's'} in total.</p>
       ${barChart(items, { title: 'Accounts by role' })}`
    : emptyChart('No accounts exist yet.');
  return `
    <div class="chart-card">
      <div class="chart-title">Accounts by role</div>
      ${body}
    </div>`;
}

/**
 * Daily count of logged actions across the last 14 days, taken from the
 * activity list already fetched (the endpoint returns the 30 most recent).
 */
function activitySpark(acts) {
  const values = dailyCounts(acts, 14);
  const total = values.reduce((s, n) => s + n, 0);
  if (!total) return '';
  return `
    <div class="chart-row">
      ${sparkline(values, { tone: 'teal', title: 'Logged actions per day' })}
      <p class="chart-note">Actions per day over the last 14 days, counted from
        the ${acts.length} most recent log entries.</p>
    </div>`;
}

function dailyCounts(acts, days) {
  const today = new Date();
  const keys = [];
  const counts = new Map();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    keys.push(dayKey(d));
    counts.set(dayKey(d), 0);
  }
  acts.forEach((a) => {
    const t = new Date(a.created_at);
    if (isNaN(t.getTime())) return;
    const k = dayKey(t);
    if (counts.has(k)) counts.set(k, (counts.get(k) || 0) + 1);
  });
  return keys.map((k) => counts.get(k) || 0);
}

function dayKey(d) {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function prettifyAction(action) {
  return String(action || '')
    .replace(/[._]/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function queueRow(item) {
  const path = item.kind === 'course' ? `#/courses/${item.id}`
    : `#/tests/${item.kind === 'questionnaire' ? 'q' : 'a'}/${item.id}`;
  return `
    <a class="dash-course" href="${path}">
      <div class="dash-course-ico">${iconSvg(
        item.kind === 'course' ? 'book' : item.kind === 'assessment' ? 'flag' : 'quiz')}</div>
      <div class="dash-course-main">
        <b>${esc(item.title)}</b>
        <div class="sm muted">
          ${esc(item.owner || 'Unknown trainer')}
          ${item.subject ? ' · ' + esc(item.subject) : ''}
          ${item.updated_at ? ' · ' + esc(ui.relTime(item.updated_at)) : ''}
        </div>
      </div>
      <span class="tag warn">${esc(item.action)}</span>
    </a>`;
}

// ═══ Content queue ═════════════════════════════════════════════════════════

const contentState = { tab: 'courses', scope: 'pending' };

export async function content(root, ctx) {
  root.innerHTML = ui.head({
    title: 'Content queue',
    sub: 'Every trainer submission reaches the portal through this screen.',
    actions: '<a class="btn ghost sm" href="#/feed">Publish an announcement</a>',
  })
    + adminNav('#/admin/content')
    + `<div class="pillbar">
        ${['courses', 'questionnaires', 'assessments'].map((k) => `
          <button data-tab="${k}"${contentState.tab === k ? ' class="active"' : ''}>
            ${k[0].toUpperCase() + k.slice(1)}</button>`).join('')}
        <span class="pillbar-gap"></span>
        <button data-scope="pending"${contentState.scope === 'pending' ? ' class="active"' : ''}>
          Awaiting release</button>
        <button data-scope="published"${contentState.scope === 'published' ? ' class="active"' : ''}>
          Published</button>
      </div>`
    + `<div data-body>${ui.loading('content')}</div>`;

  const paint = () => loadContent(root.querySelector('[data-body]'));
  ui.click(root, '[data-tab]', (e, b) => { contentState.tab = b.dataset.tab; paint(); rearm(root); });
  ui.click(root, '[data-scope]', (e, b) => { contentState.scope = b.dataset.scope; paint(); rearm(root); });
  paint();
  return { destroy: () => {} };
}

/** Re-bind the tab buttons after a wholesale re-render of the pillbar. */
function rearm(root) {
  root.querySelectorAll('[data-tab]').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === contentState.tab);
  });
  root.querySelectorAll('[data-scope]').forEach((b) => {
    b.classList.toggle('active', b.dataset.scope === contentState.scope);
  });
}

async function loadContent(host) {
  host.innerHTML = ui.loading('content');
  const tab = contentState.tab;
  const status = contentState.scope === 'pending' ? 'PENDING_RELEASE' : 'PUBLISHED';
  const base = tab === 'courses' ? '/v1/courses' : tab === 'questionnaires'
    ? '/v1/questionnaires' : '/v1/assessments';

  try {
    const res = await api(`${base}?status=${status}&limit=100`);
    const rows = ui.data(res) || [];
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: contentState.scope === 'pending'
          ? 'Nothing waiting for release'
          : 'Nothing published yet',
        body: contentState.scope === 'pending'
          ? 'When a trainer submits ' + tab + ' they land here.'
          : 'Release something and it appears here.',
      });
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map((r) => queueCard(tab, r)).join('')}</div>`;
    bindContent(host, tab, contentState.scope);
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function queueCard(tab, r) {
  const kind = tab === 'questionnaires' ? 'q' : tab === 'assessments' ? 'a' : '';
  const href = tab === 'courses' ? `#/courses/${r.id}` : `#/tests/${kind}/${r.id}`;
  const pending = r.status === 'PENDING_RELEASE';
  return `
    <div class="qcard" data-id="${esc(r.id)}">
      <div class="qcard-main">
        <div class="row gap">
          ${ui.tag(r.status)}
          ${r.subject_code ? `<span class="tag mute">${esc(r.subject_code)}</span>` : ''}
          ${r.level ? `<span class="tag mute">${esc(r.level)}</span>` : ''}
        </div>
        <b>${esc(r.title)}</b>
        <div class="sm muted">
          ${esc(r.trainer_name || 'Independent trainer')}
          · updated ${esc(ui.relTime(r.updated_at))}
        </div>
        ${r.description ? `<p class="sm muted">${esc(r.description.slice(0, 160))}</p>` : ''}
      </div>
      <div class="qcard-actions">
        <a class="btn ghost sm" href="${href}">Open</a>
        ${pending ? `
          <button class="btn primary sm" data-act="release">Release</button>
          <button class="btn ghost sm" data-act="reject">Send back</button>` : `
          <button class="btn ghost sm" data-act="archive">Archive</button>`}
      </div>
    </div>`;
}

function bindContent(host, tab, scope) {
  const pending = scope === 'pending';
  const base = tab === 'courses' ? '/v1/courses' : tab === 'questionnaires'
    ? '/v1/questionnaires' : '/v1/assessments';

  ui.click(host, '[data-act]', async (e, btn) => {
    const id = btn.closest('[data-id]').dataset.id;
    const act = btn.dataset.act;

    if (act === 'archive') {
      const ok = await confirmAction('Archive this?',
        'It is removed from the catalogue but kept on record.', 'Archive');
      if (!ok) return;
      try {
        await api(`/v1/courses/${id}/status`, { method: 'POST', body: JSON.stringify({ status: 'ARCHIVED' }) });
        toast('Archived.');
        loadContent(host);
      } catch (err) { toast(err.message, 'warn'); }
      return;
    }

    try {
      if (act === 'release') {
        await api(`${base}/${id}/release`, { method: 'POST', body: '{}' });
        toast('Released — it is live on the portal.');
      } else {
        // Courses require an explicit target status; the tests do not.
        const body = tab === 'courses' ? JSON.stringify({ status: 'DRAFT' }) : '{}';
        await api(`${base}/${id}/reject`, { method: 'POST', body });
        toast('Sent back to the trainer as a draft.');
      }
      loadContent(host);
    } catch (err) {
      toast(err.message, 'warn');
    }
  });
}

// ═══ Users ═════════════════════════════════════════════════════════════════

const userState = { q: '', role: '', status: '', offset: 0, limit: 50 };

export async function users(root, ctx) {
  root.innerHTML = ui.head({
    title: 'Users',
    sub: 'Change roles, suspend accounts, or inspect one person’s record.',
    actions: '<a class="btn ghost sm" href="#/admin/approvals">Approval queue</a>',
  })
    + adminNav('#/admin/users')
    + `<div class="toolbar">
        <div class="grow"><input type="search" name="q" placeholder="Search name, email or department…"
          value="${esc(userState.q)}" aria-label="Search users"></div>
        <select name="role" aria-label="Filter by role">
          <option value="">All roles</option>
          ${['ALPHA', 'MASTER', 'SUPREME'].map((r) => `<option value="${r}"${
            userState.role === r ? ' selected' : ''}>${r}</option>`).join('')}
        </select>
        <select name="status" aria-label="Filter by status">
          <option value="">Any status</option>
          ${[['PENDING', 'Waiting for approval'], ['ACTIVE', 'Active'],
             ['SUSPENDED', 'Suspended']].map(([s, label]) => `<option value="${s}"${
            userState.status === s ? ' selected' : ''}>${label}</option>`).join('')}
        </select>
        <button class="btn primary sm" data-apply>Apply</button>
      </div>`
    + `<div data-body>${ui.loading('users')}</div>`;

  const apply = () => {
    userState.q = root.querySelector('[name=q]').value.trim();
    userState.role = root.querySelector('[name=role]').value;
    userState.status = root.querySelector('[name=status]').value;
    userState.offset = 0;
    loadUsers(root.querySelector('[data-body]'));
  };
  ui.click(root, '[data-apply]', apply);
  root.querySelector('[name=q]').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') apply();
  });
  loadUsers(root.querySelector('[data-body]'));
  return { destroy: () => {} };
}

async function loadUsers(host) {
  host.innerHTML = ui.loading('users');
  try {
    const p = new URLSearchParams();
    if (userState.q) p.set('q', userState.q);
    if (userState.role) p.set('role', userState.role);
    if (userState.status) p.set('status', userState.status);
    p.set('limit', String(userState.limit));
    p.set('offset', String(userState.offset));

    const res = await api('/v1/admin/users?' + p.toString());
    const rows = ui.data(res) || [];
    const total = (ui.meta(res) || {}).total || rows.length;

    if (!rows.length) {
      host.innerHTML = ui.blank({ title: 'No users match', body: 'Clear a filter and try again.' });
      return;
    }

    host.innerHTML = ui.table([
      { label: 'Person', get: (r) => ui.who(r.name, r.email) },
      { label: 'Role', get: (r) => `<span class="role-tag ${String(r.role).toLowerCase()}">${esc(r.role)}</span>` },
      { label: 'Status', get: (r) => ui.tag(r.status) },
      { label: 'Department', get: (r) => esc(r.department || '—') },
      { label: 'Enrolments', get: (r) => String(r.enrollments || 0) },
      { label: 'Courses taught', get: (r) => String(r.courses || 0) },
      { label: 'Certificates', get: (r) => String(r.certificates || 0) },
      { label: 'Joined', get: (r) => esc(ui.fmtDate(r.created_at)) },
      { label: '', get: (r) => `<div class="row gap">
          <button class="btn ghost sm" data-view="${esc(r.id)}">Open</button>
        </div>` },
    ], rows, 'id')
    + `<div class="row gap mt" style="justify-content:space-between">
        <span class="sm muted">Showing ${rows.length} of ${total}</span>
        <div class="row gap">
          <button class="btn ghost sm" data-prev ${userState.offset === 0 ? 'disabled' : ''}>Previous</button>
          <button class="btn ghost sm" data-next ${
            userState.offset + userState.limit >= total ? 'disabled' : ''}>Next</button>
        </div>
      </div>`;

    ui.click(host, '[data-view]', (e, b) => openUser(b.dataset.view, host));
    ui.click(host, '[data-prev]', () => {
      userState.offset = Math.max(0, userState.offset - userState.limit);
      loadUsers(host);
    });
    ui.click(host, '[data-next]', () => {
      userState.offset += userState.limit;
      loadUsers(host);
    });
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

async function openUser(userId, host) {
  openAppModal('<h3 class="modal-title">Loading account…</h3>');
  let d;
  try {
    d = ui.data(await api(`/v1/admin/users/${userId}`));
  } catch (err) {
    openAppModal(`<h3 class="modal-title">Could not load this account</h3>
      <p class="modal-sub">${esc(err.message)}</p>`);
    return;
  }

  const u = d.user || {};
  const st = d.stats || {};
  const body = el('app-modal-body');

  openAppModal(`
    <h3 class="modal-title">${esc(u.name || 'Unnamed')}</h3>
    <p class="modal-sub">${esc(u.email || '')}</p>
    <div class="row gap mb">
      <span class="role-tag ${String(u.role).toLowerCase()}">${esc(u.role)}</span>
      ${ui.tag(u.status)}
    </div>
    <div class="kv mb">
      <div class="k"><span>Department</span><b>${esc(u.department || '—')}</b></div>
      <div class="k"><span>Designation</span><b>${esc(u.designation || '—')}</b></div>
      <div class="k"><span>Enrolments</span><b>${st.enrollments || 0}</b></div>
      <div class="k"><span>Courses taught</span><b>${st.courses || 0}</b></div>
      <div class="k"><span>Certificates</span><b>${st.certificates || 0}</b></div>
      <div class="k"><span>Exams taken</span><b>${st.attempts || 0}</b></div>
    </div>

    ${(d.enrollments || []).length ? `
      <h4 class="section-title">Enrolled in</h4>
      <div class="stack tight mb">
        ${(d.enrollments || []).map((e) => `
          <div class="dash-course">
            <div class="dash-course-main">
              <b>${esc(e.title || 'Untitled course')}</b>
              <div class="sm muted">${Math.round(e.progress_pct || 0)}% complete</div>
            </div>
            ${ui.tag(e.status)}
          </div>`).join('')}
      </div>` : ''}

    ${(d.certificates || []).length ? `
      <h4 class="section-title">Certificates</h4>
      <div class="stack tight mb">
        ${(d.certificates || []).map((c) => `
          <div class="dash-course">
            <div class="dash-course-main">
              <b>${esc(c.title || 'Certificate')}</b>
              <div class="sm muted">Code ${esc(c.code || '—')} · ${c.percentage != null ? Math.round(c.percentage) + '%' : '—'}</div>
            </div>
            ${ui.tag(c.status)}
          </div>`).join('')}
      </div>` : ''}

    <div class="field">
      <label for="u-role">Role</label>
      <div class="row gap">
        <select id="u-role">
          ${['ALPHA', 'MASTER', 'SUPREME'].map((r) => `<option value="${r}"${
            u.role === r ? ' selected' : ''}>${r}</option>`).join('')}
        </select>
        <button class="btn ghost sm" data-role>Change</button>
      </div>
    </div>

    <div class="auth-err" data-err role="alert"></div>
    <div class="row gap" style="justify-content:space-between;margin-top:14px">
      <button class="btn ghost sm" data-del>Delete account</button>
      <div class="row gap">
        ${u.status === 'SUSPENDED'
          ? '<button class="btn primary sm" data-unsuspend>Reinstate</button>'
          : '<button class="btn primary sm" data-suspend>Suspend</button>'}
        <button class="btn ghost sm" data-cancel>Close</button>
      </div>
    </div>`);

  const card = el('app-modal-body');
  const errBox = card.querySelector('[data-err]');
  card.querySelector('[data-cancel]').addEventListener('click', closeAppModal);

  card.querySelector('[data-role]').addEventListener('click', async (e) => {
    const role = card.querySelector('#u-role').value;
    if (role === u.role) { errBox.textContent = 'That is already their role.'; return; }
    const ok = await confirmAction(`Change ${u.name || 'this user'} to ${role}?`,
      'The change takes effect on their next page load.', 'Change role');
    if (!ok) return;
    try {
      await api('/v1/admin/role', { method: 'POST', body: JSON.stringify({ user_id: u.id, role }) });
      toast('Role changed.');
      closeAppModal();
      loadUsers(host);
    } catch (err) { errBox.textContent = err.message; }
  });

  card.querySelector('[data-suspend]').addEventListener('click', async (e) => {
    const ok = await confirmAction('Suspend this account?',
      'They are signed out and cannot log in until you reinstate them.', 'Suspend');
    if (!ok) return;
    try {
      await ui.busy(e.target, 'Suspending…', async () => {
        await api('/v1/admin/suspend', { method: 'POST', body: JSON.stringify({ user_id: u.id }) });
        toast('Account suspended.');
        closeAppModal();
        loadUsers(host);
      });
    } catch (err) { errBox.textContent = err.message; }
  });

  const un = card.querySelector('[data-unsuspend]');
  if (un) un.addEventListener('click', async (e) => {
    try {
      await ui.busy(e.target, 'Reinstating…', async () => {
        await api('/v1/admin/unsuspend', { method: 'POST', body: JSON.stringify({ user_id: u.id }) });
        toast('Account reinstated.');
        closeAppModal();
        loadUsers(host);
      });
    } catch (err) { errBox.textContent = err.message; }
  });

  card.querySelector('[data-del]').addEventListener('click', async () => {
    const ok = await confirmAction('Delete this account?',
      'This removes the person and everything they own. It cannot be undone.',
      'Delete permanently');
    if (!ok) return;
    try {
      await api(`/v1/admin/users/${u.id}`, { method: 'DELETE' });
      toast('Account deleted.');
      closeAppModal();
      loadUsers(host);
    } catch (err) { errBox.textContent = err.message; }
  });
}

// ═══ Exams — the six Supreme controls ══════════════════════════════════════

export async function exams(root, ctx) {
  root.innerHTML = ui.head({
    title: 'Exam controls',
    sub: 'Six live controls: delete · watch live attempts · end now · '
       + 'extend or reopen the deadline · void an attempt · suspend an account.',
  })
    + adminNav('#/admin/exams')
    + `<div class="toolbar">
        <div class="grow"><input type="search" name="q" placeholder="Search exams…"
          value="" aria-label="Search exams"></div>
        <select name="status" aria-label="Filter by status">
          <option value="">Any status</option>
          ${['PENDING_RELEASE', 'PUBLISHED', 'ENDED', 'DRAFT'].map((s) =>
            `<option value="${s}">${s.replace(/_/g, ' ')}</option>`).join('')}
        </select>
        <button class="btn primary sm" data-apply>Apply</button>
      </div>
    <div data-body>${ui.loading('exams')}</div>`;

  const apply = () => loadExams(root.querySelector('[data-body]'), {
    q: root.querySelector('[name=q]').value.trim(),
    status: root.querySelector('[name=status]').value,
  });
  ui.click(root, '[data-apply]', apply);
  root.querySelector('[name=q]').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') apply();
  });
  loadExams(root.querySelector('[data-body]'), { q: '', status: '' });
  return { destroy: () => {} };
}

async function loadExams(host, filt) {
  host.innerHTML = ui.loading('exams');
  try {
    const res = await api(`/v1/assessments?limit=100${
      filt.status ? '&status=' + encodeURIComponent(filt.status) : ''}`);
    let rows = ui.data(res) || [];
    if (filt.q) {
      const ql = filt.q.toLowerCase();
      rows = rows.filter((r) => (r.title || '').toLowerCase().includes(ql));
    }
    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'No exams here',
        body: 'Assessments created by trainers show up with their status and their roster.',
        action: 'Open the content queue',
        actionHref: '#/admin/content',
      });
      return;
    }
    host.innerHTML = `<div class="stack tight">${rows.map(examRow).join('')}</div>`;
    bindExams(host);
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}

function examRow(a) {
  const ended = a.status === 'ENDED';
  return `
    <div class="exam-card" data-id="${esc(a.id)}">
      <div class="exam-main">
        <div class="row gap">
          ${ui.tag(a.status)}
          ${a.subject_code ? `<span class="tag mute">${esc(a.subject_code)}</span>` : ''}
          ${a.passing_score != null ? `<span class="tag mute">Pass ≥ ${a.passing_score}%</span>` : ''}
          ${a.deadline_at ? `<span class="tag ${ended ? 'mute' : 'info'}">${
            esc(ui.countdown(a.deadline_at))}</span>` : ''}
        </div>
        <b>${esc(a.title)}</b>
        <div class="sm muted">
          ${a.duration_minutes ? `${a.duration_minutes} min · ` : ''}
          ${a.max_score != null ? `max score ${a.max_score} · ` : ''}
          ${esc(ui.relTime(a.updated_at))}
        </div>
      </div>
      <div class="exam-actions">
        <button class="btn ghost sm" data-act="live">Live attempts</button>
        <button class="btn ghost sm" data-act="roster">All attempts</button>
        ${ended
          ? '<button class="btn ghost sm" data-act="reopen">Reopen / extend</button>'
          : `<button class="btn ghost sm" data-act="reopen">Extend</button>
             <button class="btn primary sm" data-act="end">End now</button>`}
        <button class="btn ghost sm" data-act="delete">Delete</button>
      </div>
    </div>`;
}

function bindExams(host) {
  ui.click(host, '[data-act]', async (e, btn) => {
    const id = btn.closest('[data-id]').dataset.id;
    const act = btn.dataset.act;

    if (act === 'live') return showLive(id);
    if (act === 'roster') return showRoster(id, host);
    if (act === 'reopen') return showReopen(id, host);
    if (act === 'end') {
      const ok = await confirmAction('End this exam now?',
        'Anyone still sitting is force-submitted with what they have written so far.',
        'End the exam');
      if (!ok) return;
      try {
        const r = ui.data(await api(`/v1/assessments/${id}/end`, { method: 'POST', body: '{}' }));
        toast(`Exam ended${r && r.force_submitted ? ` — ${r.force_submitted} attempt(s) submitted` : ''}.`);
        loadExams(host, { q: '', status: '' });
      } catch (err) { toast(err.message, 'warn'); }
      return;
    }
    if (act === 'delete') {
      const ok = await confirmAction('Delete this exam?',
        'The exam, its questions and every attempt taken on it are removed. '
        + 'This cannot be undone.', 'Delete exam');
      if (!ok) return;
      try {
        await api(`/v1/assessments/${id}`, { method: 'DELETE' });
        toast('Exam deleted.');
        loadExams(host, { q: '', status: '' });
      } catch (err) { toast(err.message, 'warn'); }
    }
  });
}

async function showLive(id) {
  openAppModal('<h3 class="modal-title">Loading live attempts…</h3>');
  try {
    const rows = ui.data(await api(`/v1/assessments/${id}/live`)) || [];
    openAppModal(`
      <h3 class="modal-title">Live attempts</h3>
      <p class="modal-sub">${rows.length
        ? `${rows.length} trainee${rows.length === 1 ? ' is' : 's are'} sitting this exam right now.`
        : 'Nobody is sitting this exam at the moment.'}</p>
      ${rows.length ? `<div class="stack tight">${rows.map((r) => `
        <div class="exam-card">
          <div class="exam-main">
            <b>${esc(r.trainee_name || r.name || 'Trainee')}</b>
            <div class="sm muted">Started ${esc(ui.relTime(r.started_at))} · elapsed ${
              Math.round((r.elapsed || 0) / 60)} min · ${r.answered ?? 0} answered</div>
          </div>
        </div>`).join('')}</div>` : ''}
      <div class="row gap" style="justify-content:flex-end;margin-top:16px">
        <button class="btn ghost sm" data-close>Close</button>
      </div>`);
    const liveCard = el('app-modal-body');
    wireModalClose();
    liveCard.querySelector('[data-close]').addEventListener('click', closeAppModal);
  } catch (err) {
    openAppModal(`<h3 class="modal-title">Could not load live attempts</h3>
      <p class="modal-sub">${esc(err.message)}</p>`);
    wireModalClose();
  }
}

async function showRoster(id, host) {
  openAppModal('<h3 class="modal-title">Loading attempts…</h3>');
  try {
    const rows = ui.data(await api(`/v1/assessments/${id}/attempts?limit=200`)) || [];
    openAppModal(`
      <h3 class="modal-title">All attempts</h3>
      <p class="modal-sub">${rows.length} attempt${rows.length === 1 ? '' : 's'} on record.
        Voiding removes an attempt without touching the person's account.</p>
      ${rows.length ? `<div class="stack tight">${rows.map((r) => `
        <div class="exam-card" data-attempt="${esc(r.id)}">
          <div class="exam-main">
            <b>${esc(r.trainee_name || r.name || 'Trainee')}</b>
            <div class="sm muted">
              ${r.percentage != null ? `${Math.round(r.percentage)}% · ` : ''}
              ${esc(ui.relTime(r.submitted_at || r.started_at))}
            </div>
          </div>
          <div class="exam-actions">
            ${r.passed ? '<span class="tag ok">Passed</span>'
              : r.passed === false ? '<span class="tag bad">Failed</span>'
              : ui.tag(r.status || 'IN_PROGRESS')}
            <button class="btn ghost sm" data-void>Void attempt</button>
          </div>
        </div>`).join('')}</div>` : '<div class="empty-state">No attempts yet.</div>'}
      <div class="row gap" style="justify-content:flex-end;margin-top:16px">
        <button class="btn ghost sm" data-close>Close</button>
      </div>`);

    const card = el('app-modal-body');
    wireModalClose();
    card.querySelector('[data-close]').addEventListener('click', closeAppModal);
    ui.click(card, '[data-void]', async (e, btn) => {
      const attemptId = btn.closest('[data-attempt]').dataset.attempt;
      const ok = await confirmAction('Void this attempt?',
        'The score is discarded and the trainee may sit the exam again.', 'Void attempt');
      if (!ok) return;
      try {
        await api(`/v1/assessments/${id}/attempts/${attemptId}/void`, { method: 'POST', body: '{}' });
        toast('Attempt voided.');
        closeAppModal();
        showRoster(id, host);
      } catch (err) { toast(err.message, 'warn'); }
    });
  } catch (err) {
    openAppModal(`<h3 class="modal-title">Could not load attempts</h3>
      <p class="modal-sub">${esc(err.message)}</p>`);
    wireModalClose();
  }
}

function showReopen(id, host) {
  openAppModal(`
    <h3 class="modal-title">Extend or reopen the deadline</h3>
    <p class="modal-sub">Leave the field empty to remove the deadline entirely,
      or set a later one to reopen submissions.</p>
    <div class="field">
      <label for="dl">New deadline</label>
      <input type="datetime-local" id="dl" value="">
    </div>
    <div class="auth-err" data-err role="alert"></div>
    <div class="row gap" style="justify-content:flex-end;margin-top:14px">
      <button class="btn ghost sm" data-close>Cancel</button>
      <button class="btn primary sm" data-save>Apply</button>
    </div>`);

  const card = el('app-modal-body');
  wireModalClose();
  card.querySelector('[data-close]').addEventListener('click', closeAppModal);
  card.querySelector('[data-save]').addEventListener('click', async (e) => {
    const raw = card.querySelector('#dl').value;
    try {
      await ui.busy(e.target, 'Applying…', async () => {
        await api(`/v1/assessments/${id}/reopen`, {
          method: 'POST',
          body: JSON.stringify({ deadline_at: raw ? new Date(raw).toISOString() : '' }),
        });
        toast('Deadline updated.');
        closeAppModal();
        loadExams(host, { q: '', status: '' });
      });
    } catch (err) {
      card.querySelector('[data-err]').textContent = err.message;
    }
  });
}

function wireModalClose() {
  const body = el('app-modal-body');
  ui.click(body, '[data-close-btn]', closeAppModal);
}

// ═══ Audit log ═════════════════════════════════════════════════════════════

const auditState = { action: '', offset: 0, limit: 100 };

export async function audit(root, ctx) {
  root.innerHTML = ui.head({
    title: 'Audit log',
    sub: 'Every administrative decision, with the actor and the timestamp.',
  })
    + adminNav('#/admin/audit')
    + `<div class="toolbar">
        <div class="grow"><input type="search" name="action"
          placeholder="Filter by action, e.g. course.release…"
          value="${esc(auditState.action)}" aria-label="Filter by action"></div>
        <button class="btn primary sm" data-apply>Apply</button>
        <button class="btn ghost sm" data-clear>Clear</button>
      </div>
    <div data-body>${ui.loading('the audit log')}</div>`;

  const apply = () => {
    auditState.action = root.querySelector('[name=action]').value.trim();
    auditState.offset = 0;
    loadAudit(root.querySelector('[data-body]'));
  };
  ui.click(root, '[data-apply]', apply);
  ui.click(root, '[data-clear]', () => {
    auditState.action = '';
    root.querySelector('[name=action]').value = '';
    auditState.offset = 0;
    loadAudit(root.querySelector('[data-body]'));
  });
  loadAudit(root.querySelector('[data-body]'));
  return { destroy: () => {} };
}

async function loadAudit(host) {
  host.innerHTML = ui.loading('the audit log');
  try {
    const p = new URLSearchParams();
    if (auditState.action) p.set('action', auditState.action);
    p.set('limit', String(auditState.limit));
    p.set('offset', String(auditState.offset));

    const res = await api('/v1/admin/audit?' + p.toString());
    const rows = ui.data(res) || [];
    const total = (ui.meta(res) || {}).total || rows.length;

    if (!rows.length) {
      host.innerHTML = ui.blank({
        title: 'Nothing recorded yet',
        body: 'Administrative actions are logged the moment you take one.',
      });
      return;
    }

    host.innerHTML = ui.table([
      { label: 'Action', get: (r) => `<b>${esc(prettifyAction(r.action))}</b>` },
      { label: 'Actor', get: (r) => ui.who(r.actor_name || 'system', r.actor_email || r.actor_id || '') },
      { label: 'Resource', get: (r) => esc(r.resource_type || '—') },
      { label: 'Reference', get: (r) => `<code class="sm">${esc(
        (r.resource_id || '').slice(0, 12))}${(r.resource_id || '').length > 12 ? '…' : ''}</code>` },
      { label: 'When', get: (r) => esc(ui.fmtDate(r.created_at, { withTime: true })) },
    ], rows, 'id')
    + `<div class="row gap mt" style="justify-content:space-between">
        <span class="sm muted">Showing ${rows.length} of ${total}</span>
        <div class="row gap">
          <button class="btn ghost sm" data-prev ${auditState.offset === 0 ? 'disabled' : ''}>Previous</button>
          <button class="btn ghost sm" data-next ${
            auditState.offset + auditState.limit >= total ? 'disabled' : ''}>Next</button>
        </div>
      </div>`;

    ui.click(host, '[data-prev]', () => {
      auditState.offset = Math.max(0, auditState.offset - auditState.limit);
      loadAudit(host);
    });
    ui.click(host, '[data-next]', () => {
      auditState.offset += auditState.limit;
      loadAudit(host);
    });
  } catch (err) {
    host.innerHTML = ui.errorBlock(err.message);
  }
}
