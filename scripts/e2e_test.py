"""End-to-end smoke test for the Learnify API.

Exercises the whole product surface against a running server, in the order a
real organisation would use it:

    auth (3 roles) -> subject/topics -> competency -> course wizard -> release
    -> AI drafts -> publish -> questionnaire -> assessment -> trainee attempt
    -> certificate -> Veda report -> feedback -> feed -> admin controls

Response envelopes
    auth routes return the body as-is:        {"user": ..., "session": ...}
    every db.ok() route wraps it:             {"success": true, "data": ...}
`step()` unwraps both, so call sites always receive the payload itself.

    python scripts/e2e_test.py [base_url]     # default http://127.0.0.1:8021
"""
import datetime
import json
import pathlib
import secrets
import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8021").rstrip("/")
ROOT = pathlib.Path(__file__).resolve().parents[1]

FAILURES = []
STAMP = str(int(time.time()))[-6:]

ALPHA = {"email": f"e2e.alpha{STAMP}@gmail.com", "password": "TestPass123!",
         "name": "Asha Trainee", "role": "ALPHA"}
MASTER = {"email": f"e2e.master{STAMP}@gmail.com", "password": "TestPass123!",
          "name": "Ravi Trainer", "role": "MASTER"}
SUPREME = {"email": f"e2e.supreme{STAMP}@gmail.com", "password": "TestPass123!",
           "name": "Meera Admin", "role": "SUPREME"}

TOKENS = {}
UIDS = {}
INVITE_TOKENS = []


def step(label, resp, expect=200, key=None, quiet=False):
    """Assert status (and optionally a key), returning the unwrapped payload."""
    ok = resp.status_code == expect
    try:
        body = resp.json()
    except Exception:
        body = {}

    # Unwrap db.ok() envelopes; leave auth bodies untouched.
    data = body
    if isinstance(body, dict) and "success" in body and "data" in body:
        data = body["data"]

    if ok and key is not None:
        if isinstance(data, dict):
            ok = key in data
        else:
            ok = data is not None

    if not ok:
        detail = (f"  got {resp.status_code} want {expect}"
                  + (f" missing '{key}'" if key else "")
                  + f" :: {str(body)[:240]}")
        FAILURES.append(label + detail)
        print(f"  [FAIL] {label}{detail}")
    elif not quiet:
        print(f"  [PASS] {label}")

    # Never hand back None: a failed step degrades to an empty dict so one
    # bad call cannot abort the whole run with an AttributeError.
    return data if data is not None else {}


def H(role=None, extra=None):
    h = {"Content-Type": "application/json"}
    if role and role in TOKENS:
        h["Authorization"] = f"Bearer {TOKENS[role]}"
    if extra:
        h.update(extra)
    return h


def P(path, payload=None, role=None, expect=200, key=None, quiet=False, params=None):
    r = requests.post(BASE + path, json=payload if payload is not None else {},
                      headers=H(role), params=params, timeout=60)
    return step(f"POST {path}", r, expect, key, quiet)


def G(path, role=None, expect=200, key=None, quiet=False, params=None):
    r = requests.get(BASE + path, headers=H(role), params=params, timeout=60)
    return step(f"GET  {path}", r, expect, key, quiet)


def U(path, payload, role, expect=200, key=None, quiet=True):
    r = requests.put(BASE + path, json=payload, headers=H(role), timeout=60)
    return step(f"PUT  {path}", r, expect, key, quiet)


def raw(method, path, payload=None, role=None):
    """Response object, for asserting on a status the helper would fail on."""
    return requests.request(method, BASE + path,
                            json=payload if payload is not None else {},
                            headers=H(role), timeout=60)


def as_list(x):
    return x if isinstance(x, list) else []


def _supabase():
    """A service client for the database, or None if it is not configured."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        import os
        url = os.environ.get("SUPABASE_URL")
        key = (os.environ.get("SUPABASE_SERVICE_KEY")
               or os.environ.get("SUPABASE_PAT"))
        if not url or not key:
            return None
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        print(f"    [warn] supabase client unavailable: {exc}")
        return None


def provision_invite(email="", note="e2e_test.py"):
    """Mint an Administrator invite straight in the database.

    The API only gives out invites to an existing SUPREME, and on a database
    that already has administrators the bootstrap path is closed — so there is
    nobody for a test to ask. The harness writes its own row (it already holds
    the service key) and then spends it through the real `/auth/register`
    route, which is the thing actually under test. Nothing about the check
    itself is bypassed: a registration without a token still gets 403.
    """
    token = secrets.token_urlsafe(24)
    client = _supabase()
    if client is None:
        FAILURES.append("could not provision an administrator invite "
                        "(SUPABASE_URL / SUPABASE_SERVICE_KEY missing)")
        return ""
    expires = (datetime.datetime.now(datetime.timezone.utc)
               + datetime.timedelta(hours=6)).isoformat()
    try:
        client.table("admin_invites").insert({
            "token": token,
            # Bound to an address, so the "issued to someone else" branch of
            # the check gets covered as well as the bare no-token one.
            "email": email,
            "note": note,
            "expires_at": expires,
            "max_uses": 1,
            "used_count": 0,
        }).execute()
        INVITE_TOKENS.append(token)
        return token
    except Exception as exc:
        FAILURES.append(f"could not provision an invite: {exc}")
        return ""


def release_invites():
    """Drop every invite row this run created. Best-effort teardown."""
    if not INVITE_TOKENS:
        return
    client = _supabase()
    if client is None:
        return
    for token in INVITE_TOKENS:
        try:
            client.table("admin_invites").delete().eq("token", token).execute()
        except Exception as exc:
            print(f"    [warn] could not remove a test invite: {exc}")


def _env(name):
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        import os
        return os.environ.get(name) or ""
    except Exception:
        return ""


def teardown_run():
    """Undo everything the run wrote, so re-runs stop piling up.

    The suite points at a real database, so each run otherwise leaves four
    accounts and all of their content behind for good. Only rows owned by an
    `e2e.*` account are touched — content is selected by owner, never by
    title, so a real trainer's course can never be caught in the sweep.

    Five columns point back at a user *without* `on delete cascade`
    (`audit_logs.actor_id`, `courses.released_by`, `*_attempts.ended_by`,
    `home_posts.published_by`, `trainer_competencies.verified_by`, plus
    `users.created_by`/`suspended_by`). Those are cleared rather than
    deleted: nulling the reference preserves any row that belongs to
    somebody else, while making the e2e account removable.
    """
    problems = []
    client = _supabase()
    if client is None:
        print("    [warn] teardown skipped: no database client")
        return

    def drop(table, column, values):
        if not values:
            return
        try:
            client.table(table).delete().in_(column, values).execute()
        except Exception as exc:
            problems.append(f"delete {table}.{column}: {exc}")

    def ids_of(table, column, values):
        """Primary keys of rows matched by `column` in `values`."""
        if not values:
            return set()
        try:
            rows = client.table(table).select("id").in_(column, values).execute().data
            return {r["id"] for r in rows if r.get("id")}
        except Exception as exc:
            problems.append(f"list {table} by {column}: {exc}")
            return set()

    def clear(table, column, values):
        if not values:
            return
        try:
            client.table(table).update({column: None}).in_(column, values).execute()
        except Exception as exc:
            problems.append(f"clear {table}.{column}: {exc}")

    try:
        everyone = client.table("users").select("id,email").limit(2000).execute().data
    except Exception as exc:
        print(f"    [warn] teardown could not read users: {exc}")
        return

    # Everything the suite has ever created, not just this run: the emails are
    # namespaced (`e2e.alpha<stamp>@…`), so the sweep also clears the accounts
    # earlier runs abandoned before teardown existed.
    uids = sorted({u["id"] for u in everyone
                   if str(u.get("email") or "").lower().startswith("e2e.")})
    if not uids:
        print("    teardown: no e2e accounts left over")
        return

    asm_ids = ids_of("assessments", "trainer_id", uids)
    qn_ids = ids_of("questionnaires", "trainer_id", uids)
    # Attempts are owned either by an e2e trainee or by an e2e assessment —
    # never merely *ended* by an e2e admin, which only gets nulled below.
    attempt_ids = (ids_of("assessment_attempts", "assessment_id", asm_ids)
                   | ids_of("assessment_attempts", "trainee_id", uids))

    # Results first: they hang off attempts, and attempts point at users.
    drop("assessment_responses", "attempt_id", attempt_ids)
    drop("assessment_attempts", "assessment_id", asm_ids)
    drop("assessment_attempts", "trainee_id", uids)
    drop("questionnaire_attempts", "questionnaire_id", qn_ids)
    drop("questionnaire_attempts", "trainee_id", uids)
    drop("certificates", "trainee_id", uids)
    drop("performance_reports", "trainee_id", uids)

    # Engagement and ownership. These mostly cascade from users anyway; doing
    # them explicitly means a failure shows up here instead of as a blocked
    # account delete later.
    for table, column in (
        ("slot_progress", "trainee_id"), ("enrollments", "trainee_id"),
        ("course_feedback", "trainee_id"), ("content_feedback", "trainee_id"),
        ("participation_logs", "user_id"), ("notifications", "user_id"),
        ("profiles", "user_id"), ("draft_questions", "owner_id"),
        ("library_items", "trainer_id"), ("audit_logs", "actor_id"),
        ("trainer_competencies", "trainer_id"),
    ):
        drop(table, column, uids)

    # Competencies the suite invents each run ("Network Design <stamp>").
    try:
        comps = client.table("competencies").select("id,name").limit(2000).execute().data
        comp_ids = sorted({c["id"] for c in comps
                           if str(c.get("name") or "").startswith("Network Design ")})
    except Exception as exc:
        problems.append(f"list competencies: {exc}")
        comp_ids = []
    drop("competencies", "id", comp_ids)

    # Authored content. Subjects and topics are deliberately left alone: they
    # are reused between runs and are not owned by any single account.
    drop("questionnaires", "trainer_id", uids)
    drop("assessments", "trainer_id", uids)
    drop("courses", "trainer_id", uids)
    drop("home_posts", "published_by", uids)

    # References that survive on rows we keep. Nulling is the whole point:
    # a real trainer's course released by a test admin must stay, just
    # unattributed.
    clear("courses", "released_by", uids)
    clear("assessment_attempts", "ended_by", uids)
    clear("questionnaire_attempts", "ended_by", uids)
    clear("trainer_competencies", "verified_by", uids)
    clear("home_posts", "published_by", uids)
    clear("users", "created_by", uids)
    clear("users", "suspended_by", uids)

    # Anything still standing means the accounts cannot go.
    for table in ("courses", "questionnaires", "assessments", "library_items"):
        try:
            left = client.table(table).select("id").in_("trainer_id", uids).execute().data
            if left:
                problems.append(f"{len(left)} {table} row(s) still owned after the sweep")
        except Exception as exc:
            problems.append(f"recheck {table}: {exc}")

    try:
        client.table("users").delete().in_("id", uids).execute()
    except Exception as exc:
        problems.append(f"delete users: {exc}")

    # GoTrue has no foreign key into the app, so its rows survive an app-side
    # delete and would otherwise grow by four every run.
    url, key = _env("SUPABASE_URL"), _env("SUPABASE_SERVICE_KEY")
    if url and key:
        for uid in uids:
            try:
                requests.delete(f"{url}/auth/v1/admin/users/{uid}",
                                headers={"apikey": key,
                                         "Authorization": f"Bearer {key}"},
                                timeout=30)
            except Exception as exc:
                problems.append(f"auth delete {uid}: {exc}")
    else:
        problems.append("SUPABASE_SERVICE_KEY missing; auth users left behind")

    try:
        survivors = client.table("users").select("id").in_("id", uids).execute().data
    except Exception as exc:
        problems.append(f"could not verify teardown: {exc}")
        survivors = [{"id": "?"}]

    if survivors:
        FAILURES.append(f"teardown left {len(survivors)} e2e account(s) in the "
                        "database (P0: they are production rows)")
        print(f"    [FAIL] teardown left {len(survivors)} e2e account(s)")
    else:
        print(f"    teardown: removed {len(uids)} e2e account(s) and their content")

    for p in problems:
        print(f"    [warn] teardown: {p}")


# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 1. AUTH · SIGN-UP APPROVAL ════════════════════════════════")

# Administrator sign-up is never public, and a test has no administrator to
# ask for an invite — so it mints one itself and then spends it through the
# real registration route.
INVITE = provision_invite(email=SUPREME["email"])
WRONG_INVITE = provision_invite(email="someone.else@example.com",
                                note="bound to a different address")

for who in (ALPHA, MASTER, SUPREME):
    payload = dict(who)
    if who["role"] == "SUPREME":
        payload["invite"] = INVITE
    b = P("/api/auth/register", payload, expect=200, key="session")
    tok = (b.get("session") or {}).get("access_token")
    status = (b.get("user") or {}).get("status")
    if tok:
        TOKENS[who["role"]] = tok
        print(f"    registered {who['role']}: token ok, status={status}")
    else:
        FAILURES.append(f"register {who['role']} produced no token")

    # Trainees and trainers queue for approval; an accepted Administrator
    # invite is approved on the spot because the invite is the credential.
    want = "ACTIVE" if who["role"] == "SUPREME" else "PENDING"
    if status != want:
        FAILURES.append(f"register {who['role']}: status {status} != {want}")
        print(f"    [FAIL] {who['role']} registered as {status}, wanted {want}")

# ── the gate ───────────────────────────────────────────────────────────────
step("SUPREME sign-up with no invite -> 403",
     raw("POST", "/api/auth/register",
         {"email": f"e2e.intruder{STAMP}@gmail.com", "password": "TestPass123!",
          "name": "No Invite", "role": "SUPREME"}), 403)

# Same address, token already spent — refuses without creating anything.
step("SUPREME sign-up reusing an exhausted invite -> 403",
     raw("POST", "/api/auth/register",
         {"email": SUPREME["email"], "password": "TestPass123!",
          "name": "Reuse", "role": "SUPREME", "invite": INVITE}), 403)

# A live token issued to somebody else is no better than no token.
step("SUPREME sign-up with an invite issued elsewhere -> 403",
     raw("POST", "/api/auth/register",
         {"email": f"e2e.notme{STAMP}@gmail.com", "password": "TestPass123!",
          "name": "Wrong Address", "role": "SUPREME",
          "invite": WRONG_INVITE}), 403)

for who in (ALPHA, MASTER, SUPREME):
    b = P("/api/auth/login", {"email": who["email"], "password": who["password"]},
          expect=200, key="user")
    role = (b.get("user") or {}).get("role")
    uid = (b.get("user") or {}).get("id")
    if role != who["role"]:
        FAILURES.append(f"login {who['email']}: role {role} != {who['role']}")
        print(f"    [FAIL] login {who['role']} role={role}")
    else:
        print(f"    [PASS] login {who['role']} -> {role}")
    if uid:
        UIDS[who["role"]] = uid
    tok = (b.get("session") or {}).get("access_token")
    if tok:
        TOKENS[who["role"]] = tok

# ── a queued account can reach nothing until an Administrator agrees ──────
r = raw("GET", "/api/v1/assessments", role="ALPHA")
step("PENDING trainee on a gated route -> 403", r, 403)
try:
    detail = (r.json() or {}).get("detail")
except Exception:
    detail = None
if detail != "ACCOUNT_PENDING_APPROVAL":
    FAILURES.append(f"pending refusal said {detail!r}, want "
                    "'ACCOUNT_PENDING_APPROVAL'")
else:
    print("    [PASS] refusal names ACCOUNT_PENDING_APPROVAL")

q = as_list(G("/api/v1/admin/pending", role="SUPREME"))
queued = {u.get("id") for u in q if isinstance(u, dict)}
absent = [w["role"] for w in (ALPHA, MASTER)
          if UIDS.get(w["role"]) not in queued]
if absent:
    FAILURES.append("approval queue is missing " + ", ".join(absent))
else:
    print("    [PASS] both sign-ups are waiting in /admin/pending")

for who in (ALPHA, MASTER):
    a = P("/api/v1/admin/approve", {"user_id": UIDS[who["role"]]},
          role="SUPREME", expect=200, key="status")
    if a.get("status") != "ACTIVE":
        FAILURES.append(f"approve {who['role']} returned {a.get('status')}")
    else:
        print(f"    [PASS] approved {who['role']}")

step("approved trainee on a gated route -> 200",
     raw("GET", "/api/v1/assessments", role="ALPHA"), 200)

q = as_list(G("/api/v1/admin/pending", role="SUPREME"))
still = {u.get("id") for u in q if isinstance(u, dict)}
if {UIDS.get("ALPHA"), UIDS.get("MASTER")} & still:
    FAILURES.append("approved accounts are still in /admin/pending")
else:
    print("    [PASS] the queue drains as accounts are approved")

# ── rejection: refused, told why, and reversible on record ───────────────
REJECTED = {"email": f"e2e.rejected{STAMP}@gmail.com", "password": "TestPass123!",
            "name": "Rejected Applicant", "role": "ALPHA"}
rb = P("/api/auth/register", REJECTED, expect=200, key="session")
REJECTED_UID = (rb.get("user") or {}).get("id") or ""

rj = P("/api/v1/admin/reject",
       {"user_id": REJECTED_UID, "reason": "E2E coverage of the reject path."},
       role="SUPREME", expect=200, key="status")
if rj.get("status") != "SUSPENDED":
    FAILURES.append(f"reject returned {rj.get('status')}, want SUSPENDED")
else:
    print("    [PASS] rejected account is suspended, not deleted")

step("rejected account cannot sign in -> 403",
     raw("POST", "/api/auth/login",
         {"email": REJECTED["email"], "password": REJECTED["password"]}), 403)

me = G("/api/auth/me", role="ALPHA", key="user")
if (me.get("user") or {}).get("email") != ALPHA["email"]:
    FAILURES.append("/api/auth/me returned the wrong user")
else:
    print("    [PASS] /me resolved the right account")

r = raw("POST", "/api/auth/login",
        {"email": ALPHA["email"], "password": "wrongpass"})
step("login with wrong password -> 401", r, 401)

step("admin dashboard with no token -> 401",
     raw("GET", "/api/v1/admin/dashboard"), 401)
step("ALPHA hitting admin dashboard -> 403",
     raw("GET", "/api/v1/admin/dashboard", role="ALPHA"), 403)
step("MASTER can list assessments -> 200",
     raw("GET", "/api/v1/assessments", role="MASTER"), 200)

# An approved account must not still read as pending anywhere.
me_status = (G("/api/auth/me", role="MASTER", quiet=True).get("user") or {}
             ).get("status")
if me_status != "ACTIVE":
    FAILURES.append(f"approved trainer reports status={me_status}")
else:
    print("    [PASS] approved account reports ACTIVE")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 2. SUBJECT + TOPICS + BENCHMARKS ════════════════════════")
# Subject names are unique now (subjects_name_uk), so reuse the seeded
# "Computer Networks" row when it already exists instead of inserting another
# duplicate on every re-run.
existing = as_list(G("/api/v1/subjects", role="SUPREME", quiet=True))
found = next((s for s in existing
              if (s.get("name") or "").strip().lower() == "computer networks"),
             None)
if found:
    SUBJ = found.get("id")
    print(f"    subject reused: {SUBJ} (code {found.get('code')})")
else:
    subj = P("/api/v1/subjects",
             {"code": f"CN{STAMP}", "name": "Computer Networks",
              "category": "Engineering",
              "description": "OSI, TCP/IP and routing fundamentals."},
             role="SUPREME", expect=200, key="id")
    SUBJ = subj.get("id")
    print(f"    subject {SUBJ}")

if not SUBJ:
    FAILURES.append("cannot continue without a subject id")
    print("\nABORTING: subject creation failed")
    sys.exit(1)

topics = P(f"/api/v1/subjects/{SUBJ}/topics/bulk",
           {"names": ["OSI Model", "TCP/IP Suite", "Routing",
                      "Transport Layer", "DNS"]},
           role="SUPREME", expect=200, key="added")
print(f"    topics seeded: {topics.get('count')}")

TOPICS = as_list(G(f"/api/v1/subjects/{SUBJ}/topics", role="MASTER"))
TOPIC_IDS = [t["id"] for t in TOPICS if t.get("id")]
print(f"    topics readable: {len(TOPIC_IDS)}")
if len(TOPIC_IDS) < 5:
    FAILURES.append(f"expected 5 topics, got {len(TOPIC_IDS)}")

bm = U(f"/api/v1/reports/benchmarks/{SUBJ}",
       {"topic_id": TOPIC_IDS[0] if TOPIC_IDS else "",
        "industry_standard": "Should be able to explain all 7 OSI layers and "
                             "map common protocols to them.",
        "expected_proficiency": 70},
       "SUPREME", expect=200, key="id")
print(f"    benchmark id: {bm.get('id')}")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 3. COMPETENCY ═══════════════════════════════════════════")
comp = P("/api/v1/subjects/competencies",
         {"name": f"Network Design {STAMP}", "description": "L2/L3 design"},
         role="SUPREME", expect=200, key="id")
COMP = comp.get("id")
print(f"    competency {COMP}")

if COMP:
    P(f"/api/v1/subjects/{SUBJ}/competencies",
      {"competency_id": COMP, "required_weight": 1.5},
      role="SUPREME", expect=200, quiet=True)

    selfass = U("/api/v1/competency/mine",
                {"items": [{"competency_id": COMP, "proficiency": 85,
                            "evidence": "Built campus networks for 3 years"}]},
                "MASTER", expect=200, key="count")
    print(f"    master self-assessed: {selfass.get('count')}")

    verify = P("/api/v1/competency/verify",
               {"trainer_id": UIDS.get("MASTER"), "competency_id": COMP,
                "verified": True},
               role="SUPREME", expect=200)
    print(f"    verified: {bool(verify)}")

ranked = as_list(G(f"/api/v1/competency/trainers/{SUBJ}", role="ALPHA"))
print(f"    ranked trainers for subject: {len(ranked)}")
if ranked:
    top = ranked[0]
    print(f"    top: {top.get('name')} score={top.get('score')} "
          f"coverage={top.get('coverage')}%")
    if "explanation" not in top:
        FAILURES.append("ranked trainer lacks an explanation field")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 4. COURSE 5-STEP WIZARD ═════════════════════════════════")
c1 = P("/api/v1/courses",
       {"title": f"Networking Foundations {STAMP}", "subject_id": SUBJ,
        "level": "Beginner",
        "description": "A practical introduction to how networks actually "
                       "move data, from cabling to routing.",
        "duration_hours": 12},
       role="MASTER", expect=200, key="id")
COURSE = c1.get("id")
print(f"    step1 created course {COURSE}")

U(f"/api/v1/courses/{COURSE}/step1",
  {"title": f"Networking Foundations {STAMP}", "subject_id": SUBJ,
   "level": "Beginner",
   "description": "A practical introduction to how networks actually move "
                  "data, from cabling to routing.",
   "duration_hours": 12},
  "MASTER", expect=200, key="id", quiet=False)

mod = P(f"/api/v1/courses/{COURSE}/modules",
        {"title": "Module 1 - Models & Layers",
         "description": "How to think about network layers."},
        role="MASTER", expect=200, key="id")
MOD = mod.get("id")
print(f"    step2 module {MOD}")

slot1 = P(f"/api/v1/courses/{COURSE}/slots",
          {"module_id": MOD, "title": "The OSI model in practice",
           "kind": "READING"},
          role="MASTER", expect=200, key="id")
SLOT1 = slot1.get("id")
slot2 = P(f"/api/v1/courses/{COURSE}/slots",
          {"module_id": MOD, "title": "Why TCP handshakes matter",
           "kind": "VIDEO"},
          role="MASTER", expect=200, key="id")
SLOT2 = slot2.get("id")
print(f"    step2 slots {SLOT1}, {SLOT2}")

U(f"/api/v1/courses/{COURSE}/slots/{SLOT1}",
  {"kind": "READING",
   "body": "The OSI model has seven layers. Each layer does one job and "
           "hides the detail from the layer above. When troubleshooting, "
           "name the layer first - it tells you which tool to reach for.",
   "duration_seconds": 0},
  "MASTER", expect=200, key="id")

U(f"/api/v1/courses/{COURSE}/slots/{SLOT2}",
  {"kind": "VIDEO",
   "body": "A short walkthrough of the three-way handshake.",
   "video_source": "YOUTUBE",
   "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
   "duration_seconds": 420},
  "MASTER", expect=200, key="id")
print("    step3 content written (body + youtube)")

step("invalid YouTube URL -> 400",
     raw("PUT", f"/api/v1/courses/{COURSE}/slots/{SLOT2}",
         {"kind": "VIDEO", "video_source": "YOUTUBE",
          "youtube_url": "https://example.com/not-youtube",
          "body": "", "duration_seconds": 0}, role="MASTER"), 400)

wz = G(f"/api/v1/courses/{COURSE}/wizard", role="MASTER") or {}
print(f"    wizard step={wz.get('step')} max={wz.get('max_step')} "
      f"complete={wz.get('complete')}")
if not (wz.get("complete") or {}).get("s3"):
    FAILURES.append("wizard did not register step 3 as complete")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 5. AI DRAFTS → QUEUE → PUBLISH ══════════════════════════")
stat = G("/api/v1/ai/status", role="MASTER") or {}
print(f"    groq configured: {stat.get('configured')}")

gen = P("/api/v1/ai/generate-questions",
        {"subject_id": SUBJ, "topic_ids": TOPIC_IDS[:3], "count": 3,
         "difficulty": "medium", "kind": "ASSESSMENT",
         "context": "Introductory level, first module."},
        role="MASTER", expect=200, key="added" if False else None)
DRAFTS = as_list(gen)
print(f"    generated drafts: {len(DRAFTS)}")
if not DRAFTS:
    FAILURES.append("AI generated no drafts")
for d in DRAFTS[:3]:
    print(f"      topic={d.get('topic_name') or '(untagged)'} "
          f"diff={d.get('difficulty')} :: {(d.get('text') or '')[:70]}")

queue = as_list(G("/api/v1/ai/drafts", role="MASTER"))
print(f"    queue size: {len(queue)}")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 6. ASSESSMENT (formal exam) ═════════════════════════════")
asm = P("/api/v1/assessments",
        {"title": f"Networking Basics Exam {STAMP}",
         "description": "Formal assessment covering the OSI model and TCP.",
         "subject_id": SUBJ, "course_id": COURSE,
         "duration_minutes": 30, "max_score": 100, "passing_score": 60},
        role="MASTER", expect=200, key="id")
ASM = asm.get("id")
print(f"    assessment {ASM}")

step("untagged assessment question -> 400",
     raw("POST", f"/api/v1/assessments/{ASM}/questions",
         {"text": "Which layer is the transport layer?", "topic_id": "",
          "options": [{"text": "Layer 3", "is_correct": False},
                      {"text": "Layer 4", "is_correct": True}]},
         role="MASTER"), 400)

manual = P(f"/api/v1/assessments/{ASM}/questions",
           {"text": "In the OSI model, which layer is responsible for "
                    "end-to-end delivery?",
            "topic_id": TOPIC_IDS[0] if TOPIC_IDS else "",
            "difficulty": "medium",
            "explanation": "Layer 4 (transport) provides end-to-end delivery.",
            "options": [{"text": "Network", "is_correct": False},
                        {"text": "Transport", "is_correct": True},
                        {"text": "Data Link", "is_correct": False},
                        {"text": "Session", "is_correct": False}]},
           role="MASTER", expect=200, key="id")
print(f"    manual question {manual.get('id')}")

if DRAFTS:
    pub = P("/api/v1/ai/drafts/bulk-publish", {"target_id": ASM},
            role="MASTER", expect=200, key="published")
    print(f"    published: {pub.get('published')}, "
          f"skipped: {len(pub.get('skipped') or [])}")

QUESTIONS = as_list(G(f"/api/v1/assessments/{ASM}/questions", role="MASTER"))
print(f"    exam now has {len(QUESTIONS)} questions")
if len(QUESTIONS) < 2:
    FAILURES.append(f"exam has only {len(QUESTIONS)} questions")

P(f"/api/v1/assessments/{ASM}/submit", {}, role="MASTER", expect=200,
  key="status", quiet=True)
rel = P(f"/api/v1/assessments/{ASM}/release", {}, role="SUPREME",
        expect=200, key="status")
print(f"    released: {rel.get('status')}")

alist = as_list(G("/api/v1/assessments", role="ALPHA"))
visible = [a for a in alist if a.get("id") == ASM]
if not visible:
    FAILURES.append("released assessment not visible to ALPHA")
else:
    print(f"    visible to ALPHA: {visible[0].get('title')} "
          f"({visible[0].get('question_count')} questions)")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 7. QUESTIONNAIRE (practice, deadline) ════════════════════")
qn = P("/api/v1/questionnaires",
       {"title": f"OSI Practice Set {STAMP}",
        "description": "Timed practice on the first module.",
        "subject_id": SUBJ, "duration_minutes": 15, "max_attempts": 3,
        "deadline_at": "2030-01-01T00:00:00+00:00"},
       role="MASTER", expect=200, key="id")
QN = qn.get("id")
print(f"    questionnaire {QN}")

qmanual = P(f"/api/v1/questionnaires/{QN}/questions",
            {"text": "Which topology connects every node to a single hub?",
             "topic_id": TOPIC_IDS[1] if len(TOPIC_IDS) > 1 else "",
             "difficulty": "easy",
             "options": [{"text": "Mesh", "is_correct": False},
                         {"text": "Star", "is_correct": True},
                         {"text": "Ring", "is_correct": False},
                         {"text": "Bus", "is_correct": False}]},
            role="MASTER", expect=200, key="id")
print(f"    question {qmanual.get('id')}")

P(f"/api/v1/questionnaires/{QN}/submit", {}, role="MASTER", expect=200,
  key="status", quiet=True)
qrel = P(f"/api/v1/questionnaires/{QN}/release", {}, role="SUPREME",
         expect=200, key="status")
print(f"    released: {qrel.get('status')}")

# ── release the course too: a trainee may only enrol in PUBLISHED work ──────
csub = P(f"/api/v1/courses/{COURSE}/submit", {}, role="MASTER",
         expect=200, key="status")
print(f"    course submitted: {csub.get('status')}")
crel = P(f"/api/v1/courses/{COURSE}/release", {}, role="SUPREME",
         expect=200, key="status")
print(f"    course released: {crel.get('status')}")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 8. TRAINEE: enroll → attempt → certificate ═══════════════")
enr = P(f"/api/v1/courses/{COURSE}/enroll", {}, role="ALPHA", expect=200,
        key="enrolled")
print(f"    enrolled: {enr.get('enrolled')}")

start = P(f"/api/v1/assessments/{ASM}/start", {}, role="ALPHA", expect=200)
ATTEMPT = (start.get("attempt") or {}).get("id")
exam_qs = as_list(start.get("questions"))
print(f"    attempt {ATTEMPT}, {len(exam_qs)} questions handed out")

leak = any("is_correct" in (o or {})
           for q in exam_qs for o in as_list(q.get("options")))
if leak:
    FAILURES.append("SECURITY: answer key exposed to trainee in start payload")
else:
    print("    [PASS] answer key not exposed in start payload")

responses = []
for q in exam_qs:
    key_row = next((x for x in QUESTIONS if x.get("id") == q["id"]), None)
    if not key_row:
        continue
    correct = next((o for o in as_list(key_row.get("options"))
                    if o.get("is_correct")), None)
    if correct:
        responses.append({"question_id": q["id"], "option_id": correct["id"]})
print(f"    answering {len(responses)}/{len(exam_qs)} correctly")

sub = P(f"/api/v1/assessments/{ASM}/submit-attempt",
        {"responses": responses, "duration_seconds": 120},
        role="ALPHA", expect=200)
print(f"    score {sub.get('score')}/{sub.get('max_score')} "
      f"= {sub.get('percentage')}% passed={sub.get('passed')}")
CERT = (sub.get("certificate") or {}).get("code")
if sub.get("passed") and not CERT:
    FAILURES.append("passed but no certificate issued")
if CERT:
    print(f"    CERTIFICATE: {CERT}")
if not sub.get("passed"):
    FAILURES.append("answering every question correctly did not pass")

step("second attempt refused -> 400",
     raw("POST", f"/api/v1/assessments/{ASM}/start", {}, role="ALPHA"), 400)

qstart = P(f"/api/v1/questionnaires/{QN}/start", {}, role="ALPHA", expect=200)
qat = (qstart.get("attempt") or {}).get("id")
qq = as_list(qstart.get("questions"))
qresp = [{"question_id": q["id"],
          "option_id": (as_list(q.get("options"))[0] or {}).get("id")}
         for q in qq if as_list(q.get("options"))]
qsub = P(f"/api/v1/questionnaires/{QN}/submit-attempt",
         {"responses": qresp, "duration_seconds": 60},
         role="ALPHA", expect=200)
print(f"    practice attempt {qsub.get('attempt_id')} "
      f"scored {qsub.get('percentage')}%")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 9. VEDA REPORTS ═════════════════════════════════════════")
RPTS = as_list(G("/api/v1/reports", role="ALPHA"))
print(f"    reports for ALPHA: {len(RPTS)}")
if not RPTS:
    FAILURES.append("no performance report was produced")
RID = (RPTS[0] or {}).get("id") if RPTS else None

if RID:
    rd = G(f"/api/v1/reports/{RID}", role="ALPHA") or {}
    print(f"    verdict: {rd.get('verdict')}")
    print(f"    weak topics: {[t.get('topic') for t in as_list(rd.get('weak_topics'))]}")
    print(f"    next steps: {len(as_list(rd.get('next_steps')))}")
    if not rd.get("next_steps"):
        FAILURES.append("report has no deterministic next_steps")
    if not rd.get("source"):
        FAILURES.append("report has no source attempt reference")

    ai = P("/api/v1/ai/personalise-report", {"report_id": RID},
           role="ALPHA", expect=200, key="ai_insights")
    ins = ai.get("ai_insights") or {}
    print(f"    AI sections: {list(ins.keys())}")
    for k in ("weak_points", "improve", "industry", "learn_next"):
        if not ins.get(k):
            FAILURES.append(f"AI report missing section '{k}'")

    summ = G("/api/v1/reports/stats/summary", role="SUPREME") or {}
    print(f"    platform summary: {json.dumps(summ)[:120]}")
    wt = as_list(G("/api/v1/reports/stats/weak-topics", role="SUPREME"))
    print(f"    weak-topic ranking entries: {len(wt)}")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 10. PARTICIPATION (90% rule) ════════════════════════════")
pr = P("/api/v1/participation/progress",
       {"slot_id": SLOT1, "position_seconds": 30,
        "duration_seconds": 600, "watched_delta": 30},
       role="ALPHA", expect=200)
print(f"    5% watched -> completed={pr.get('completed')} "
      f"pct={pr.get('progress_pct')}")
if pr.get("completed"):
    FAILURES.append("slot completed at only 5% watched")

step("complete before 90% -> 400",
     raw("POST", "/api/v1/participation/complete", {"slot_id": SLOT1},
         role="ALPHA"), 400)

pr2 = P("/api/v1/participation/progress",
        {"slot_id": SLOT1, "position_seconds": 570,
         "duration_seconds": 600, "watched_delta": 540},
        role="ALPHA", expect=200)
print(f"    95% watched -> completed={pr2.get('completed')} "
      f"pct={pr2.get('progress_pct')}")
if not pr2.get("completed"):
    FAILURES.append("90% completion rule did not trigger at 95%")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 11. FEEDBACK ════════════════════════════════════════════")
fb = P("/api/v1/feedback/course",
       {"course_id": COURSE, "rating": 5,
        "comment": "Clear explanations and the diagrams really helped."},
       role="ALPHA", expect=200, key="id")
print(f"    course rating saved: {bool(fb.get('id'))}")

cfb = P("/api/v1/feedback/content",
        {"content_type": "SLOT", "content_id": SLOT1, "rating": 4,
         "comment": "Concise."},
        role="ALPHA", expect=200, key="id")
print(f"    content rating saved: {bool(cfb.get('id'))}")

agg = G(f"/api/v1/feedback/course/{COURSE}", role="MASTER") or {}
print(f"    aggregate: avg={agg.get('average')} count={agg.get('count')}")
if agg.get("average") != 5:
    FAILURES.append(f"expected average 5.0, got {agg.get('average')}")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 12. FEED ════════════════════════════════════════════════")
post = P("/api/v1/feed",
         {"type": "ANNOUNCEMENT",
          "title": f"Welcome to Learnify {STAMP}",
          "body": "Term one begins Monday. Check your course list.",
          "target_roles": ["ALPHA", "MASTER", "SUPREME"], "pinned": True},
         role="SUPREME", expect=200, key="id")
POST = post.get("id")
ftop = as_list(G("/api/v1/feed", role="ALPHA"))
print(f"    feed items for ALPHA: {len(ftop)}")
if not ftop:
    FAILURES.append("feed is empty for ALPHA despite an announcement")
elif not ftop[0].get("pinned"):
    FAILURES.append("pinned post is not first in the feed")
else:
    print(f"    first item pinned: {(ftop[0].get('title') or '')[:50]}")

P("/api/v1/feed", {"type": "NOTIFICATION", "title": "Admin only note",
                   "target_roles": ["SUPREME"]},
  role="SUPREME", expect=200, quiet=True)
falpha2 = as_list(G("/api/v1/feed", role="ALPHA"))
if [x for x in falpha2 if x.get("title") == "Admin only note"]:
    FAILURES.append("SECURITY: SUPREME-only feed post leaked to ALPHA")
else:
    print("    [PASS] role-targeted post correctly hidden from ALPHA")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 13. ADMIN: dashboard, suspension, audit ═════════════════")
dd = G("/api/v1/admin/dashboard", role="SUPREME") or {}
print(f"    counts: {json.dumps(dd.get('counts'))[:150]}")
print(f"    pending queue: {len(as_list(dd.get('pending')))}")
print(f"    activity: {len(as_list(dd.get('activity')))} entries")
print(f"    certificates: {dd.get('certificates')}")
if not dd.get("counts"):
    FAILURES.append("admin dashboard returned no counts")

ULIST = as_list(G("/api/v1/admin/users", role="SUPREME"))
print(f"    users listed: {len(ULIST)}")
ALPHA_ID = next((u["id"] for u in ULIST
                 if (u.get("email") or "").lower() == ALPHA["email"]), None)
if not ALPHA_ID:
    FAILURES.append("could not find the ALPHA account in admin/user list")

sus = P("/api/v1/admin/suspend",
        {"user_id": ALPHA_ID, "reason": "E2E test suspension"},
        role="SUPREME", expect=200, key="status")
print(f"    suspended: {sus.get('status')}")

step("suspended login -> 403",
     raw("POST", "/api/auth/login",
         {"email": ALPHA["email"], "password": ALPHA["password"]}), 403)
step("suspended /me -> 403",
     raw("GET", "/api/auth/me", role="ALPHA"), 403)

P("/api/v1/admin/unsuspend", {"user_id": ALPHA_ID}, role="SUPREME",
  expect=200, key="status")
r = raw("POST", "/api/auth/login",
        {"email": ALPHA["email"], "password": ALPHA["password"]})
step("unsuspended login -> 200", r, 200)
if r.status_code == 200:
    tok = (r.json().get("session") or {}).get("access_token")
    if tok:
        TOKENS["ALPHA"] = tok

aud = as_list(G("/api/v1/admin/audit", role="SUPREME"))
print(f"    audit entries: {len(aud)}")
if not aud:
    FAILURES.append("audit log is empty after a full session")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 14. SUPREME EXAM CONTROLS ═══════════════════════════════")
live = as_list(G(f"/api/v1/assessments/{ASM}/live", role="SUPREME"))
print(f"    live in-progress attempts: {len(live)}")

ext = P(f"/api/v1/assessments/{ASM}/reopen",
        {"deadline_at": "2031-06-30T00:00:00+00:00"},
        role="SUPREME", expect=200, key="status")
print(f"    extended deadline -> {ext.get('status')}")

end = P(f"/api/v1/assessments/{ASM}/end", {}, role="SUPREME", expect=200,
        key="status")
print(f"    ended -> {end.get('status')}, "
      f"force-submitted {end.get('force_submitted')}")

step("MASTER ending an exam -> 403",
     raw("POST", f"/api/v1/assessments/{ASM}/end", {}, role="MASTER"), 403)

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 15. PROFILES ════════════════════════════════════════════")
pd = U("/api/v1/profiles/me",
       {"education": [{"degree": "B.Tech CSE", "institution": "NIT",
                       "year": "2024", "grade": "8.2"}],
        "skills": [{"name": "TCP/IP", "level": 80},
                   {"name": "Wireshark", "level": 65}],
        "interests": ["Networking", "Security"],
        "qualifications": [{"title": "CCNA", "issuer": "Cisco", "year": "2025"}],
        "experience": [{"role": "Network Intern", "org": "XYZ Ltd",
                        "from": "2023", "to": "2024",
                        "summary": "Maintained campus LAN."}],
        "certificates": [{"name": "Networking Foundations",
                          "issuer": "Learnify", "year": "2026", "url": ""}]},
       "ALPHA", expect=200, key="skills")
print(f"    skills={len(as_list(pd.get('skills')))} "
      f"education={len(as_list(pd.get('education')))} "
      f"interests={len(as_list(pd.get('interests')))} "
      f"certs={len(as_list(pd.get('certificates')))}")
if not (pd.get("skills") and pd.get("education")):
    FAILURES.append("profile did not persist education/skills")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══ 16. LIBRARY ═════════════════════════════════════════════")
lib = P("/api/v1/library",
        {"title": f"Routing Deep Dive {STAMP}",
         "description": "Recorded session on distance-vector routing.",
         "file_type": "RECORDED_LECTURE", "subject_id": SUBJ,
         "youtube_url": "https://youtu.be/abcdefghijk",
         "duration_seconds": 1500},
        role="MASTER", expect=200, key="id")
LIB = lib.get("id")
print(f"    library item {LIB} (YouTube)")

step("ALPHA creating library item -> 403",
     raw("POST", "/api/v1/library",
         {"title": "nope", "file_type": "STUDY_MATERIAL"}, role="ALPHA"), 403)

llist = as_list(G("/api/v1/library", role="ALPHA"))
print(f"    library visible to ALPHA: {len(llist)}")

# ═══════════════════════════════════════════════════════════════════════════
# Teardown before the verdict: this suite shares a database with production,
# so leaving accounts behind is a real leak, not untidy output.
teardown_run()
release_invites()
print("\n" + "═" * 60)
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILURE(S)")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
