================================================================================
  LEARNIFY — HAND-OFF
================================================================================

STATUS: ALL VERIFICATION GATES GREEN  |  DEPLOYMENT NOT SCRIPTED IN THIS REPO

Live site: https://learnify.hosteler.shop
Local:     python -m uvicorn backend.main:app --port 8021  ->  http://127.0.0.1:8021/

--------------------------------------------------------------------------------
1. WHAT THIS IS NOW
--------------------------------------------------------------------------------
   A centralised LMS / digital capacity building portal. Three roles:
     ALPHA   trainee     — enrol, watch, sit assessments, read reports
     MASTER  trainer     — 5-step course wizard, library, AI drafting
     SUPREME administrator — publishing, feed, people, dashboards, audit

   The portal is GATED. Administrator sign-up is invite-only (an existing
   SUPREME mints the token from the Approvals console); trainees and trainers
   register freely but land as PENDING and are refused every gated route with
   ACCOUNT_PENDING_APPROVAL until approved. Rejection suspends rather than
   deletes. See section 2 for the environment switch.

   This document previously described the original Learnify — college and
   career discovery, scholarships, Razorpay premium, the Veda chatbot and
   resume builder. That product has been fully removed. Do not follow any
   instruction referencing colleges, careers, scholarships, premium,
   internships, mentor, milestones, portfolio, SGPA, OCR/documents or Veda
   chat: those routers, tables and scripts are gone.

   Veda survives only as the *brand* on generated performance reports.

--------------------------------------------------------------------------------
2. ENVIRONMENT
--------------------------------------------------------------------------------
   cp .env.example .env    then fill in:

     SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_JWKS_URL
     GROQ_API_KEY, GROQ_MODEL            (default openai/gpt-oss-120b)
     SUPABASE_PAT, SUPABASE_PROJECT      (maintenance scripts only)
     SUPREME_SIGNUP_OPEN                 (defaults CLOSED — see below)

   Administrator sign-up is NEVER public. Registration requires a token from
   the `admin_invites` table; without one the request is refused with 403
   before anything is written.

     SUPREME_SIGNUP_OPEN=true   operator opt-in that opens self-service, but
                                it is only honoured while ZERO SUPREMEs exist
                                (defaults to closed)
     bootstrap                  zero SUPREMEs and no invite required — same
                                gate, the first admin earns its way in

   So the switch can only ever create the FIRST administrator on a fresh
   project. Once admins exist it is ignored and an invite is the only way in.
   A token is consumed before the account is created, so a replayed, expired,
   revoked or exhausted token fails without a side effect.

   Trainees and trainers have no switch: they always register as PENDING and
   need a SUPREME to approve them from the Approvals console.

--------------------------------------------------------------------------------
3. DATABASE
--------------------------------------------------------------------------------
   Schema is applied ONLY through scripts/apply_lms_schema.py (optionally
   --only <section>). Do not paste schema.sql into the dashboard by hand —
   the script is the idempotent path and also creates storage buckets.

   python scripts/apply_lms_schema.py        # full, safe to re-run
   python scripts/seed_subjects.py           # 24 subjects, idempotent
   python scripts/dedupe_subjects.py         # run only if duplicates appear

   Uniqueness of a subject name is enforced three ways:
     * partial unique index subjects_name_uk on lower(name)
     * guards in create_subject / update_subject
     * the e2e test reuses an existing subject instead of creating one

   Storage buckets:
     avatars             public
     trainer-library     private
     course-attachments  private
     course-covers       public   (covers are rendered directly by URL)

   Backup before any destructive script: scripts/backup_live_db.py, which
   writes under backups/.

--------------------------------------------------------------------------------
4. VERIFICATION GATES — run these after any change
--------------------------------------------------------------------------------
   python scripts/check_frontend.py    17 route modules, 25 handler exports,
                                       imports resolve, 59 icons, 122 frontend
                                       API paths matched against 168 contract ops
   python scripts/verify_routes.py     mounted routes vs docs/API.md, and the
                                       deleted surface must still be absent
   python scripts/e2e_test.py          full three-role flow against a live
                                       server (default http://127.0.0.1:8021),
                                       including invite/pending/approval; it
                                       ends with a teardown that fails the run
                                       if any e2e.* account survives
   python scripts/test_ratelimit.py    30 assertions: budget, 429 contract,
                                       spoofing, per-address isolation
   python scripts/dump_api.py          regenerate docs/API.md

   Order matters: run e2e BEFORE test_ratelimit — the rate-limit test
   exhausts the loopback login bucket and the e2e's logins would then 429.

   Last run: ALL of the above PASSED.

   check_frontend.py is the fastest early signal — it catches a broken named
   import or an API path the contract does not know about before you start
   the server.

--------------------------------------------------------------------------------
5. FRONTEND CONVENTIONS
--------------------------------------------------------------------------------
   * No build step. public/index.html links styles/modules/*.css at ?v=62;
     JS imports each other at ?v=62. Bump both when deploying.
   * One module per route in public/src/, matching the export contract
     documented at the top of scripts/check_frontend.py.
   * Design tokens in styles.css :root. Inline SVG built from strings cannot
     resolve var() — mirror the hexes in a local table (see art.js, charts.js).
   * Component CSS goes in styles/modules/<feature>.css, linked from
     index.html. Do not add feature rules to styles.css; the MOBILE HARDENING
     block at its end exists specifically to win specificity ties.
   * Response envelope: {"success", "data", "error"}; failures add "detail".

--------------------------------------------------------------------------------
6. DEPLOYMENT
--------------------------------------------------------------------------------
   Current deployment is VERCEL, built from this repository's `main` branch.
   The Supabase and Groq credentials live as Vercel environment variables —
   they are NOT in the repository, and must never be committed (`.env` and
   `backups/` are both gitignored; `backups/` holds production table dumps).

   `api/index.py` is a thin WSGI-ish entry that imports backend.main:app and
   surfaces import failures instead of returning a silent 500. It is the
   serverless adapter and nothing more.

   There is still no Dockerfile, systemd unit, nginx/Caddy config,
   vercel.json or CI workflow checked in.

   To stand it up on any other host you need, out of band:
     * a Python host running uvicorn against backend.main:app
     * the public/ directory served by the same origin (main.py mounts it at /)
     * .env populated as in section 2
     * the schema applied (section 3)

   NOTE: main.py mounts public/ itself. If a proxy serves public/ separately
   it will shadow the API — serve only the app process.

--------------------------------------------------------------------------------
7. KNOWN GAPS
--------------------------------------------------------------------------------
   * Rate limiting covers auth plus the two Groq-spending endpoints:
     login 15/min, register 10/min, change-password 5/min, AI 10/min
     (env-overridable: RATE_LIMIT_LOGIN / RATE_LIMIT_REGISTER /
     RATE_LIMIT_CHANGE_PASSWORD / RATE_LIMIT_AI; 0 disables one endpoint,
     RATE_LIMIT_DISABLED=true disables all).
     Auth buckets key on client address — those requests carry no token yet.
     AI buckets key on the bearer token, so users behind one office NAT do
     not share a budget, and both AI routes share a single per-account
     bucket so total Groq spend is capped rather than doubled per route.
     Limits are in-process: running more than one worker makes each worker's
     window independent. X-Forwarded-For is trusted only from a loopback peer.
   * No automated tests beyond scripts/e2e_test.py and
     scripts/test_ratelimit.py (both need a live server).
   * Transient Supabase read failures are retried (3 attempts, reads only) and
     surface as 503 Unavailable; writes are never retried — a client that
     receives 503 on a write must decide whether replaying is safe.
   * Course card CSS still lives partly in styles.css rather than
     styles/modules/courses.css.
   * No browser is connected in this workspace, so changes have been verified
     statically (node --check, XML-parsing emitted SVG, the three check
     scripts) rather than by clicking through the UI.

================================================================================
END
================================================================================
