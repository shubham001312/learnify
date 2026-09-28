"""Verify every intended router is reachable by walking the OpenAPI schema.

Note: newer FastAPI wraps each include_router() in a `_IncludedRouter` object
with `path=None`, so iterating `app.routes` cannot see the endpoints. The
generated OpenAPI document flattens everything, making it the reliable check.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from backend.main import app  # noqa: E402

EXPECTED = {
    "auth": "/api/auth",
    "notifications": "/api/v1/notifications",
    "profiles": "/api/v1/profiles",
    "subjects": "/api/v1/subjects",
    "competency": "/api/v1/competency",
    "courses": "/api/v1/courses",
    "questionnaires": "/api/v1/questionnaires",
    "assessments": "/api/v1/assessments",
    "ai": "/api/v1/ai",
    "library": "/api/v1/library",
    "feedback": "/api/v1/feedback",
    "feed": "/api/v1/feed",
    "reports": "/api/v1/reports",
    "admin": "/api/v1/admin",
    "participation": "/api/v1/participation",
}

spec = app.openapi()
paths = sorted(spec.get("paths", {}).keys())
methods = set()
for p, ops in spec.get("paths", {}).items():
    for m in ops:
        methods.add(f"{m.upper()} {p}")

print(f"total endpoints: {len(methods)}  ({len(paths)} paths)\n")

print("router coverage:")
missing_routers = []
for name, prefix in EXPECTED.items():
    hits = [p for p in paths if p.startswith(prefix)]
    if not hits:
        missing_routers.append(name)
    print(f"  [{'OK  ' if hits else 'MISS'}] {name:16} "
          f"{len(hits):3} endpoints under {prefix}")

print("\nmissing routers:", ", ".join(missing_routers) if missing_routers else "NONE")

# ── required endpoint spot-checks ──────────────────────────────────────────
REQUIRED = [
    "POST /api/auth/register",
    "POST /api/auth/login",
    "GET  /api/auth/me",
    "POST /api/v1/courses",
    "POST /api/v1/courses/{course_id}/submit",
    "POST /api/v1/courses/{course_id}/release",
    "POST /api/v1/questionnaires",
    "POST /api/v1/questionnaires/{qid}/start",
    "POST /api/v1/assessments",
    "POST /api/v1/assessments/{aid}/start",
    "POST /api/v1/assessments/{aid}/end",
    "POST /api/v1/assessments/{aid}/reopen",
    "GET  /api/v1/assessments/{aid}/live",
    "POST /api/v1/ai/generate-questions",
    "POST /api/v1/ai/drafts/bulk-publish",
    "POST /api/v1/ai/personalise-report",
    "GET  /api/v1/admin/dashboard",
    "POST /api/v1/admin/suspend",
    # Account approval queue — Administrator sign-up is invite-only and
    # Trainee/Trainer sign-ups are held here, so these are load-bearing.
    "GET  /api/v1/admin/pending",
    "POST /api/v1/admin/approve",
    "POST /api/v1/admin/reject",
    "GET  /api/v1/admin/invites",
    "POST /api/v1/admin/invites",
    "DELETE /api/v1/admin/invites/{token}",
    "GET  /api/v1/reports",
    "GET  /api/v1/reports/stats/weak-topics",
    "POST /api/v1/library/upload",
    "POST /api/v1/participation/progress",
    "GET  /api/v1/feed",
    "GET  /api/v1/competency/trainers/{subject_id}",
    "POST /api/v1/feedback/course",
    "GET  /api/v1/notifications/my",
]
print("\nrequired endpoints:")
missing_eps = []
for r in REQUIRED:
    parts = r.split()
    m, p = parts[0], parts[1]
    ok = p in spec.get("paths", {}) and m.lower() in spec["paths"][p]
    if not ok:
        missing_eps.append(r)
    print(f"  [{'OK  ' if ok else 'MISS'}] {r}")
print("\nmissing endpoints:", ", ".join(missing_eps) if missing_eps else "NONE")

# ── legacy Learnify surface must be gone ───────────────────────────────────
LEGACY = ["college", "scholarship", "career", "veda", "premium", "razorpay",
          "resume", "planner", "ocr", "internship", "mentor", "milestone",
          "portfolio", "sgpa", "document", "subscription", "skill",
          "opportun", "evaluat", "analytics"]
legacy_hits = [p for p in paths
               if any(l in p.lower() for l in LEGACY)]
print(f"\nlegacy Learnify endpoints still present: {legacy_hits or 'NONE'}")

# ── security: traceback must never appear in a schema-level response ──────
bad = [p for p, ops in spec.get("paths", {}).items()
       for m, op in ops.items()
       if "traceback" in str(op).lower()]
print(f"endpoints advertising a 'traceback' field: {bad or 'NONE'}")

print("\n" + ("ALL CHECKS PASSED"
              if not missing_routers and not missing_eps and not legacy_hits
              else "FAILURES PRESENT"))
