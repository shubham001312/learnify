# Learnify

**Check & Mate** — a digital capacity building and learning management portal.

Trainers build and publish courses, trainees work through them and sit formal
assessments, and every attempt rolls up into competency and performance
reporting. Single codebase, three roles, no build step.

## Stack

| Layer | What |
|---|---|
| **Frontend** | Vanilla HTML/CSS/JS — ES modules, no bundler, no framework |
| **Backend** | FastAPI (Python) |
| **Database / Auth** | Supabase — PostgreSQL + GoTrue |
| **Storage** | Supabase Storage (`avatars`, `trainer-library`, `course-attachments`, `course-covers`) |
| **AI** | Groq — `openai/gpt-oss-120b` (override with `GROQ_MODEL`) |
| **Charts** | Runtime inline SVG (`public/src/charts.js`) — no chart library |
| **Artwork** | 16 hand-authored cartoonish SVG covers (`public/src/art.js`) |

## Roles

| Role | Who | Can |
|---|---|---|
| **ALPHA** | Trainee | Enrol, watch lessons, sit assessments, read reports — sees every published course |
| **MASTER** | Trainer | Build courses through the 5-step wizard, manage library, draft AI questionnaires |
| **SUPREME** | Administrator | Publish/unpublish courses, feed posts, people, dashboards, audit — plus the Approvals console: approve or reject trainer sign-ups and mint administrator invites |

**Administrator sign-up is invite-only.** There is no hard-coded bootstrap
account and no public path to one: an existing SUPREME mints an invite from the
**Approvals** console and shares the link, and registration without a valid
token is refused with `403`. An invite can be bound to a specific address,
and is single-use, revocable and expires after 7 days.

`SUPREME_SIGNUP_OPEN=true` is a separate, explicit operator opt-in that opens
self-service admin sign-up on a **fresh** project — it defaults to closed, and
it is only honoured while zero SUPREMEs exist, so it cannot be used to add
administrators once the portal is running.

Signup itself is deliberately minimal — `email`, `password`, `name`, `role`.
Qualifications, bio and avatar are completed later on the profile page.

**Trainers are gated; trainees are not.** A trainee account is usable the
moment it registers — nobody has to say yes. A trainer lands as `PENDING` and
every gated route refuses it with `ACCOUNT_PENDING_APPROVAL` until a SUPREME
approves it from the Approvals console. Rejecting suspends rather than deletes,
so the record stays auditable. A pending trainer sees a dedicated waiting
screen that re-checks itself and hides the navigation.

## What's implemented

**Courses**
- 5-step resumable wizard: **Basics → Structure → Content → Tests → Review**
  (progress persists across reloads and rail jumps)
- Lessons are video (upload ≤ 100 MB, or a YouTube link), reading, link or test
- A lesson is complete at **≥ 90% watched** — scrubbing forward past the bar
  still counts; an explicit "mark as done" is only honoured once the bar was met
- Only **SUPREME** can move a course to `PUBLISHED`
- Cover art is chosen per course: subject-derived art, one of the 16 preset
  cartoon covers, or an uploaded image (public bucket, image mime, ≤ 5 MB)

**Assessment**
- Questionnaires (practice) and assessments (examinations), with live exam
  controls for SUPREME: extend, end, force-submit, reopen
- **AI drafting is draft → edit → publish.** Groq output lands in a queue that
  trainers review and edit; nothing reaches a trainee until someone explicitly
  publishes it

**Reporting**
- Veda-branded performance reports — deterministic scoring plus an AI narrative
- Competency ranking per subject
- Runtime SVG charts: bars, horizontal bars, donuts, sparklines

**Platform**
- Home feed — 4 post types, published and pinned by SUPREME
- Notifications, library, feedback, participation tracking
- Admin console — dashboards, suspension, audit log, **approval queue**
  (pending trainer sign-ups → approve/reject) and **administrator invites**
  (mint, copy link, revoke)
- **Send a notification** — compose once and fan out to everyone, one role
  (trainees / trainers / administrators / the approval queue) or a
  hand-picked list, with the recipient count and a live preview before it
  goes. Every send is written to the audit log.

## Run locally

```bash
# 1. Environment
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # fill in Supabase + Groq keys

# 2. Schema + reference subjects (idempotent — safe to re-run)
python scripts/apply_lms_schema.py
python scripts/seed_subjects.py

# 3. Server (root serves the SPA)
python -m uvicorn backend.main:app --port 8021
# open http://127.0.0.1:8021/
```

There is **no demo or seed data** — no sample users, courses or posts. The only
seeded content is the subject list, which is reference data, not content.

## Project layout

```
backend/
  main.py              app, mounts public/ at /, exception handlers
  routes/              auth, courses, assessments, questionnaires, ai,
                       reports, feed, admin, library, subjects, competency,
                       feedback, participation, profiles, notifications
  services/            db (PostgREST helper), ai (Groq), auth, detector
  database/            client.py, schema.sql
public/
  index.html           SPA shell, 13 module CSS links
  src/                 ES modules — one file per route/feature
  styles.css           tokens + layout + MOBILE HARDENING block
  styles/modules/      per-feature CSS (art, wizard, charts, courses, …)
  assets/              logo, PWA icons, og-cover
docs/
  API.md               generated contract — 170 operations
  LIVE_HANDOFF.md      run / verify / deploy notes
scripts/               checks, schema, seeding, image generation, e2e
```

## Checks

```bash
python scripts/check_frontend.py   # modules, handlers, imports, icons, API paths
python scripts/verify_routes.py    # mounted routes vs docs/API.md, no legacy surface
python scripts/dump_api.py         # regenerate docs/API.md from the live OpenAPI
python scripts/e2e_test.py         # full three-role flow against a running server
python scripts/test_ratelimit.py   # auth rate limiting: budget, 429 contract, bypass
python scripts/gen_images.py       # PWA icons + OG card from public/assets/logo.jpeg
```

`e2e_test.py` now ends with a teardown: it removes the accounts it created
(and any `e2e.*` account an older run left behind) together with everything
those accounts own, and **fails the run** if any survive — the suite shares a
database with production, so a leak there is a real one.

The frontend checker is the useful early-warning signal: it resolves every
`import`, every named import against its source module, and every API path in
the frontend against the documented contract.

## Notes

- Design tokens live in `styles.css` `:root`. Inline SVG built from strings
  cannot resolve `var()` — mirror the hex values in the component's own table.
- API responses use one envelope: `{"success", "data", "error"}`; failures add
  `detail`.
- See `docs/API.md` for the full endpoint contract.
