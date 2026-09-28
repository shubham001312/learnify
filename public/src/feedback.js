// Learnify — star rating + comment screen.
// Routes: `/feedback/course/{id}` and `/feedback/content/{id}`
//
// Feedback exists per course AND per content item — both are first class.
// The summary endpoint already reports the caller's own rating, so one fetch
// drives the prefill, the average, the distribution and the comment list.

import { api, esc, toast } from './utils.js?v=63';
import * as ui from './ui.js?v=63';
import { go, confirmAction, currentUser, openAppModal, closeAppModal } from './app.js?v=63';
import { iconSvg } from './icons.js?v=63';

// Only one view is mounted at a time, so the listener set can be module state:
// it is released before every (re)render and on teardown.
let offs = [];
let epoch = 0;  // stale-render guard: bumped by every render and by teardown
const draft = { rating: 0 };

function clearOffs() {
  offs.forEach((off) => { try { off(); } catch (_) { /* already unbound */ } });
  offs = [];
}

function teardown() {
  epoch += 1;
  clearOffs();
}

// ─── Page ──────────────────────────────────────────────────────────────────

export async function render(root, ctx) {
  const myEpoch = ++epoch;
  clearOffs();

  const kind = ctx.params.kind === 'content' ? 'content' : 'course';
  const id = ctx.params.id;
  const user = ctx.user || currentUser() || {};
  // The API only accepts ratings from trainees (require_role(ALPHA)).
  const canRate = user.role === 'ALPHA';
  const title = kind === 'course' ? 'Rate this course' : 'Rate this content';

  root.innerHTML = ui.loading(kind === 'course' ? 'course feedback' : 'content feedback');

  let summary = null;
  let mine = null;
  let target = null;

  try {
    if (kind === 'course') {
      const [cRes, sRes, mRes] = await Promise.all([
        api(`/v1/courses/${encodeURIComponent(id)}`).catch(() => null),
        api(`/v1/feedback/course/${encodeURIComponent(id)}`),
        api(`/v1/feedback/course/${encodeURIComponent(id)}/mine`).catch(() => null),
      ]);
      const course = cRes ? ui.data(cRes) : null;
      summary = ui.data(sRes);
      mine = mRes ? ui.data(mRes) : null;
      target = {
        name: (course && course.title) || '',
        sub: course
          ? [course.trainer_name, course.subject_name].filter(Boolean).join(' · ')
          : '',
        back: `#/courses/${encodeURIComponent(id)}`,
        backLabel: (course && course.title) || 'All courses',
      };
    } else {
      const found = await resolveContent(id);
      const sRes = await api(`/v1/feedback/content/${found.type}/${encodeURIComponent(id)}`);
      summary = ui.data(sRes);
      target = found;
    }
    if (!summary) throw new Error('Feedback for this item could not be loaded.');
  } catch (err) {
    if (epoch !== myEpoch) return;
    root.innerHTML = ui.head({ title }) + ui.errorBlock(err.message);
    offs.push(ui.click(root, '[data-retry]', (e) => {
      e.preventDefault();
      render(root, ctx);
    }));
    return { destroy: teardown };
  }

  // Superseded while fetching — app.js must keep the handle of the view that
  // owns the screen now, so hand back no `destroy` at all.
  if (epoch !== myEpoch) return;

  const myRating = Math.round(Number((mine && mine.rating) ?? summary.my_rating)) || 0;
  const myComment = String((mine && mine.comment) ?? summary.my_comment ?? '');
  draft.rating = myRating;

  const headSub = [target.name, target.sub].filter(Boolean).join(' · ');

  root.innerHTML = `
    <div class="crumbs"><a href="${esc(target.back)}">&larr; ${
      esc(target.backLabel || 'Back')}</a></div>
    ${ui.head({ title, sub: headSub ? esc(headSub) : '' })}
    <div class="two-col wide-left">
      <div class="stack">
        ${canRate ? ratingCard(myRating, myComment) : ''}
        ${commentsCard(summary, user)}
      </div>
      <div class="stack">
        ${summaryCard(summary, kind)}
        ${canRate ? '' : ui.note(
          'Ratings are written by trainees. You are seeing the aggregate for this '
          + (kind === 'course' ? 'course.' : 'content item.'))}
      </div>
    </div>`;

  if (canRate) {
    const starBox = root.querySelector('[data-rate-stars]');
    if (starBox) {
      ui.stars(starBox, {
        value: myRating,
        id: 'fb-rate',
        onPick: (n) => {
          draft.rating = n;
          const errBox = root.querySelector('[data-err]');
          if (errBox) errBox.textContent = '';
        },
      });
    }
    offs.push(ui.click(root, '[data-submit]', (e, btn) =>
      submit(root, ctx, { kind, id, type: target.type, updating: myRating > 0 }, btn)));
  }

  paintReadonlyStars(root, summary);

  return { destroy: teardown };
}

/** Library items carry their own title; a course slot has no public lookup. */
async function resolveContent(id) {
  try {
    const res = await api(`/v1/library/${encodeURIComponent(id)}`);
    const item = ui.data(res);
    if (item && item.id) {
      return {
        type: 'LIBRARY',
        name: String(item.title || ''),
        sub: [item.trainer_name, item.subject_name].filter(Boolean).join(' · '),
        back: '#/library',
        backLabel: 'Library',
      };
    }
  } catch (_) { /* not a library item — treat it as a course slot */ }
  return { type: 'SLOT', name: '', sub: '', back: '#/courses', backLabel: 'Courses' };
}

// ─── Submit ────────────────────────────────────────────────────────────────

async function submit(root, ctx, opts, btn) {
  const errBox = root.querySelector('[data-err]');
  if (!draft.rating) {
    if (errBox) errBox.textContent = 'Pick a star rating first.';
    return;
  }
  if (errBox) errBox.textContent = '';
  const ta = root.querySelector('#fb-comment');
  const comment = ta ? ta.value.trim() : '';

  await ui.busy(btn, opts.updating ? 'Updating…' : 'Saving…', async () => {
    try {
      if (opts.kind === 'course') {
        await api('/v1/feedback/course', {
          method: 'POST',
          body: JSON.stringify({
            course_id: opts.id, rating: draft.rating, comment,
          }),
        });
      } else {
        await api('/v1/feedback/content', {
          method: 'POST',
          body: JSON.stringify({
            content_type: opts.type,
            content_id: opts.id,
            rating: draft.rating,
            comment,
          }),
        });
      }
      toast('Thanks — your rating is recorded.');
      await render(root, ctx);
    } catch (err) {
      if (errBox) errBox.textContent = err.message;
      toast(err.message, 'warn');
    }
  });
}

// ─── Cards ─────────────────────────────────────────────────────────────────

function ratingCard(myRating, myComment) {
  return `
    <div class="card">
      <div class="card-head"><h3>Your rating</h3>${
        myRating ? '<span class="tag ok">Rated</span>' : '<span class="tag mute">Not rated</span>'}</div>
      <div data-rate-stars></div>
      <div class="field">
        <label for="fb-comment">Your comment</label>
        <textarea id="fb-comment" rows="3" maxlength="2000"
          placeholder="What worked, and what could be better?">${esc(myComment)}</textarea>
      </div>
      <p class="auth-err" data-err></p>
      <button class="btn primary sm" data-submit>${
        myRating ? 'Update rating' : 'Submit rating'}</button>
    </div>`;
}

function summaryCard(summary, kind) {
  const count = Number(summary.count) || 0;
  const avg = Number(summary.average) || 0;
  return `
    <div class="card">
      <div class="card-head"><h3>Ratings</h3>
        <span class="tag ${count ? 'info' : 'mute'}">${count} rating${
          count === 1 ? '' : 's'}</span></div>
      ${count ? `
        <div class="fb-avg">
          <b>${esc(avg.toFixed(1))}</b>
          <div data-avg-stars></div>
          <span class="sm muted">Average of ${count} rating${count === 1 ? '' : 's'}</span>
        </div>
        ${distribution(summary.distribution, count)}`
        : ui.blank({
            title: 'No ratings yet',
            body: `Be the first to rate this ${
              kind === 'course' ? 'course' : 'content item'}.`,
          })}
    </div>`;
}

function distribution(dist, count) {
  const d = dist || {};
  return `<div class="fb-dist">${[5, 4, 3, 2, 1].map((n) => {
    const c = Number(d[n]) || 0;
    const pct = count ? Math.round((c / count) * 100) : 0;
    return `
      <div class="fb-dist-row">
        <span class="fb-dist-label sm muted">${n} star${n === 1 ? '' : 's'}</span>
        <span class="fb-bar"><i style="width:${pct}%"></i></span>
        <span class="fb-dist-n sm muted">${c}</span>
      </div>`;
  }).join('')}</div>`;
}

function commentsCard(summary, user) {
  const rows = (summary.comments || [])
    .filter((c) => c && String(c.comment || '').trim());
  return `
    <div class="card">
      <div class="card-head"><h3>Comments</h3>
        <span class="sm muted">${rows.length
          ? `${rows.length} shown` : 'None yet'}</span></div>
      ${rows.length
        ? `<div class="fb-list">${rows.map((c, i) => commentRow(c, i, user)).join('')}</div>`
        : ui.blank({
            title: 'No comments yet',
            body: 'Ratings without a comment still count towards the average.',
          })}
    </div>`;
}

function commentRow(c, i, user) {
  const mine = !!c.mine;
  const name = mine ? ((user && user.name) || 'You') : 'Anonymous trainee';
  return `
    <div class="fb-comment${mine ? ' mine' : ''}">
      <div class="fb-comment-top">
        ${ui.who(name, ui.relTime(c.created_at))}
        <span class="grow"></span>
        <span data-cstar="${Number(c.rating) || 0}"></span>
      </div>
      <p>${esc(c.comment)}</p>
      ${mine ? '<span class="tag info">You</span>' : ''}
    </div>`;
}

function paintReadonlyStars(root, summary) {
  const avg = root.querySelector('[data-avg-stars]');
  if (avg) {
    ui.stars(avg, { value: Number(summary.average) || 0, id: 'fb-avg' });
    const box = avg.querySelector('.stars');
    if (box) box.classList.add('readonly');
  }
  root.querySelectorAll('[data-cstar]').forEach((el, i) => {
    ui.stars(el, { value: Number(el.dataset.cstar) || 0, id: 'fb-c' + i });
    const box = el.querySelector('.stars');
    if (box) box.classList.add('readonly', 'sm');
  });
}
