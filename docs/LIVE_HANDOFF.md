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
     SUPREME_SIGNUP_OPEN                 (set false once your admins exist)

   There is NO hard-coded bootstrap account. The first SUPREME registers
   through the normal signup form; role is a signup field.

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
   python scripts/check_frontend.py    16 route modules, 24 handler exports,
                                       imports resolve, 59 icons, 118 frontend
                                       API paths matched against 162 contract ops
   python scripts/verify_routes.py     mounted routes vs docs/API.md, and the
                                       deleted surface must still be absent
   python scripts/e2e_test.py          full three-role flow against a live
                                       server (default http://127.0.0.1:8021)
   python scripts/dump_api.py          regenerate docs/API.md

   Last run: ALL of the above PASSED.

   check_frontend.py is the fastest early signal — it catches a broken named
   import or an API path the contract does not know about before you start
   the server.

--------------------------------------------------------------------------------
5. FRONTEND CONVENTIONS
--------------------------------------------------------------------------------
   * No build step. public/index.html links styles/modules/*.css at ?v=61;
     JS imports each other at ?v=60. Bump both when deploying.
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
   NOT scripted in this repository — there is no Dockerfile, systemd unit,
   nginx/Caddy config, vercel.json or CI workflow checked in.

   api/index.py is a thin WSGI-ish entry that imports backend.main:app and
   surfaces import failures instead of returning a silent 500. It is the
   serverless adapter and nothing more.

   To deploy you currently need, out of band:
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
