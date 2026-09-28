"""Assessments — formal subject-wise MCQ examinations.

Passing issues a certificate automatically (see `certificates`). Unlike
questionnaires this is summative: one attempt per trainee, a deadline, and a
passing score.

Status: DRAFT → PENDING_RELEASE → PUBLISHED → ENDED → ARCHIVED
Attempt: IN_PROGRESS → SUBMITTED | EXPIRED | VOIDED

Supreme's six exam controls live here (plus suspend in admin.py):
  1 delete   — hard delete, prior results become orphaned-but-visible
  2 live     — watch in-progress attempts in real time
  3 end now  — close and force-submit everyone still sitting
  4 reopen   — extend / re-open the deadline
  5 void     — void a single trainee's attempt
  6 suspend  — see routes/admin.py
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db, quiz

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class CreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=2000)
    subject_id: str = ""
    course_id: str = ""
    duration_minutes: int = Field(default=30, ge=1, le=480)
    max_score: int = Field(default=100, ge=1, le=1000)
    passing_score: int = Field(default=60, ge=0, le=100)
    deadline_at: str = ""


class QuestionIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    explanation: str = Field(default="", max_length=2000)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    topic_id: str = ""
    points: float = Field(default=1, gt=0, le=100)
    options: list[dict] = Field(default=[], max_length=6)


class StartIn(BaseModel):
    pass


class SubmitIn(BaseModel):
    responses: list[dict] = Field(default=[], max_length=300)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


# ─── Access ────────────────────────────────────────────────────────────────
def _get(aid: str, user: dict, for_edit: bool = False) -> dict:
    row = db.first("assessments", "*", eq={"id": aid})
    if not row:
        raise db.NotFound("Assessment not found")
    if for_edit:
        if user["role"] == SUPREME:
            return row
        if user["role"] != MASTER or row.get("trainer_id") != user["uid"]:
            raise db.Denied("You do not own this assessment.")
        return row
    if user["role"] in (SUPREME, MASTER):
        return row
    if row.get("status") != "PUBLISHED":
        raise db.NotFound("Assessment not found")
    return row


def _public(row: dict, user: dict) -> dict:
    subject = db.first("subjects", "id, code, name",
                       eq={"id": row.get("subject_id")}) if row.get("subject_id") else None
    trainer = db.first("users", "id, name, designation",
                       eq={"id": row.get("trainer_id")}) or {}
    return {
        **row,
        "subject_name": (subject or {}).get("name", ""),
        "trainer_name": trainer.get("name", ""),
        "question_count": quiz.question_count("ASSESSMENT", row["id"]),
        "can_edit": bool(row.get("trainer_id") == user["uid"]
                         or user["role"] == SUPREME),
    }


# ─── List / detail ─────────────────────────────────────────────────────────
@router.get("")
def list_assessments(
    status: str = Query(default="", max_length=30),
    subject_id: str = Query(default="", max_length=60),
    course_id: str = Query(default="", max_length=60),
    mine: bool = False,
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=60, ge=1, le=200),
    user=Depends(_auth),
):
    eq: dict = {}
    if user["role"] == ALPHA:
        eq["status"] = "PUBLISHED"
    elif user["role"] == MASTER:
        eq["trainer_id"] = user["uid"]
    elif mine:
        # Supreme's "mine" means "authored by me", not "everything I can see".
        eq["trainer_id"] = user["uid"]
    if status:
        eq["status"] = status
    if subject_id:
        eq["subject_id"] = subject_id
    if course_id:
        eq["course_id"] = course_id

    rows, total = db.select("assessments", "*", eq=eq or None,
                            order=("created_at", True), limit=limit, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r.get("title", "") or "").lower()]

    out = []
    for r in rows:
        p = _public(r, user)
        if user["role"] == ALPHA:
            p["my_attempts"] = _mine(r["id"], user["uid"])
            p["has_live"] = bool(quiz.active_attempt("ASSESSMENT", r["id"], user["uid"]))
            p["overdue"] = quiz.is_past(r.get("deadline_at"))
        out.append(p)
    return db.ok(out, meta={"total": total or len(out)})


def _mine(aid: str, uid: str) -> list[dict]:
    rows, _ = db.select("assessment_attempts", "*",
                        eq={"assessment_id": aid, "trainee_id": uid},
                        order=("attempt_no", True), limit=10)
    return [{k: v for k, v in r.items() if k != "responses"} for r in rows]


@router.get("/{aid}")
def get_assessment(aid: str, user=Depends(_auth)):
    row = _get(aid, user)
    p = _public(row, user)
    if user["role"] == ALPHA:
        p["my_attempts"] = _mine(aid, user["uid"])
        p["has_live"] = bool(quiz.active_attempt("ASSESSMENT", aid, user["uid"]))
        p["overdue"] = quiz.is_past(row.get("deadline_at"))
    return db.ok(p)


# ─── Authoring ─────────────────────────────────────────────────────────────
@router.post("")
def create(payload: CreateIn, user=Depends(require_role(MASTER, SUPREME))):
    if payload.passing_score > payload.max_score:
        raise db.Rejected("Passing score cannot exceed the maximum score.")
    row = db.insert("assessments", {
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "subject_id": payload.subject_id or None,
        "course_id": payload.course_id or None,
        "trainer_id": user["uid"],
        "duration_minutes": payload.duration_minutes,
        "max_score": payload.max_score,
        "passing_score": payload.passing_score,
        "deadline_at": payload.deadline_at or None,
        "status": "DRAFT",
    })
    db.audit(user["uid"], "assessment.create", "assessment", row.get("id"))
    return db.ok(row)


@router.put("/{aid}")
def update(aid: str, payload: CreateIn, user=Depends(_auth)):
    row = _get(aid, user, for_edit=True)
    if row["status"] in ("PUBLISHED", "ENDED", "ARCHIVED"):
        raise db.Rejected(f"Cannot edit a {row['status']} assessment.")
    if payload.passing_score > payload.max_score:
        raise db.Rejected("Passing score cannot exceed the maximum score.")
    rows = db.update("assessments", {
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "subject_id": payload.subject_id or None,
        "course_id": payload.course_id or None,
        "duration_minutes": payload.duration_minutes,
        "max_score": payload.max_score,
        "passing_score": payload.passing_score,
        "deadline_at": payload.deadline_at or None,
        "updated_at": "now()",
    }, id=aid)
    return db.ok(rows[0] if rows else None)


@router.delete("/{aid}")
def delete(aid: str, user=Depends(require_role(SUPREME))):
    """Control 1 — hard delete.

    Result rows are removed with the exam; the platform keeps a tombstone in
    the audit log, and any certificate issued from it is marked REVOKED rather
    than destroyed so a trainee's record never silently disappears.
    """
    row = _get(aid, user, for_edit=True)
    certs, _ = db.select("certificates", "id",
                         eq={"assessment_id": aid, "status": "VALID"})
    for c in certs:
        db.update("certificates", {"status": "REVOKED"}, id=c["id"])
    db.delete("assessments", id=aid)
    db.audit(user["uid"], "assessment.delete", "assessment", aid,
             {"title": row.get("title"), "certificates_revoked": len(certs),
              "orphaned_results": True})
    return db.ok({"deleted": True, "certificates_revoked": len(certs)})


# ─── Questions ─────────────────────────────────────────────────────────────
@router.get("/{aid}/questions")
def list_questions(aid: str, user=Depends(_auth)):
    _get(aid, user)
    return db.ok(quiz.load_questions("ASSESSMENT", aid))


@router.post("/{aid}/questions")
def add_question(aid: str, payload: QuestionIn, user=Depends(_auth)):
    _get(aid, user, for_edit=True)
    if not payload.topic_id:
        raise db.Rejected(
            "Every assessment question needs a topic tag — it powers the "
            "weak-point analysis in the Veda report.")
    _, total = db.select("assessment_questions", "id",
                         eq={"assessment_id": aid}, count=True)
    row = quiz.add_question("ASSESSMENT", aid,
                            {**payload.model_dump(), "sort_order": total})
    return db.ok(row)


@router.post("/{aid}/questions/bulk")
def add_questions_bulk(aid: str, payload: dict, user=Depends(_auth)):
    _get(aid, user, for_edit=True)
    items = (payload or {}).get("questions") or []
    if len(items) > 100:
        raise db.Rejected("Bulk insert is capped at 100 questions.")
    _, total = db.select("assessment_questions", "id",
                         eq={"assessment_id": aid}, count=True)
    added, errors = 0, []
    for i, item in enumerate(items):
        if not item.get("topic_id"):
            errors.append({"index": i, "error": "Topic tag required."})
            continue
        try:
            quiz.add_question("ASSESSMENT", aid, {**item, "sort_order": total + i})
            added += 1
        except db.Rejected as e:
            errors.append({"index": i, "error": e.detail})
    return db.ok({"added": added, "errors": errors})


@router.delete("/{aid}/questions/{question_id}")
def remove_question(aid: str, question_id: str, user=Depends(_auth)):
    _get(aid, user, for_edit=True)
    quiz.delete_question("ASSESSMENT", question_id)
    return db.ok({"deleted": True})


@router.put("/{aid}/questions-order")
def reorder(aid: str, payload: dict, user=Depends(_auth)):
    _get(aid, user, for_edit=True)
    quiz.retype_questions("ASSESSMENT", aid, (payload or {}).get("order") or [])
    return db.ok({"order": (payload or {}).get("order") or []})


# ─── Release ───────────────────────────────────────────────────────────────
@router.post("/{aid}/submit")
def submit(aid: str, user=Depends(_auth)):
    row = _get(aid, user, for_edit=True)
    if row["status"] not in ("DRAFT", "PENDING_RELEASE"):
        raise db.Rejected(f"Cannot submit a {row['status']} assessment.")
    n = quiz.question_count("ASSESSMENT", aid)
    if n == 0:
        raise db.Rejected("Add at least one question before submitting.")
    untagged = _untagged(aid)
    if untagged:
        raise db.Rejected(
            f"{untagged} question(s) still lack a topic tag. Tag them all "
            "before submitting — reports depend on it.")
    db.update("assessments", {"status": "PENDING_RELEASE"}, id=aid)
    _notify_supreme(row, "assessment")
    db.audit(user["uid"], "assessment.submit", "assessment", aid)
    return db.ok({"status": "PENDING_RELEASE"})


def _untagged(aid: str) -> int:
    rows, total = db.select("assessment_questions", "topic_id",
                            eq={"assessment_id": aid}, limit=500)
    return sum(1 for r in rows if not r.get("topic_id"))


@router.post("/{aid}/release")
def release(aid: str, user=Depends(require_role(SUPREME))):
    row = _get(aid, user, for_edit=True)
    if row["status"] not in ("PENDING_RELEASE", "ENDED", "ARCHIVED"):
        raise db.Rejected(f"Cannot release from status {row['status']}.")
    if quiz.question_count("ASSESSMENT", aid) == 0:
        raise db.Rejected("This assessment has no questions.")
    db.update("assessments", {"status": "PUBLISHED"}, id=aid)
    db.audit(user["uid"], "assessment.release", "assessment", aid)
    return db.ok({"status": "PUBLISHED"})


@router.post("/{aid}/reject")
def reject(aid: str, user=Depends(require_role(SUPREME))):
    row = _get(aid, user, for_edit=True)
    if row["status"] != "PENDING_RELEASE":
        raise db.Rejected("Only submitted assessments can be sent back.")
    db.update("assessments", {"status": "DRAFT"}, id=aid)
    return db.ok({"status": "DRAFT"})


# ─── Supreme exam controls ─────────────────────────────────────────────────
@router.post("/{aid}/end")
def end_now(aid: str, user=Depends(require_role(SUPREME))):
    """Control 3 — close the exam and force-submit anyone still sitting."""
    row = _get(aid, user, for_edit=True)
    db.update("assessments", {"status": "ENDED"}, id=aid)
    n = _force_submit(aid, user["uid"])
    db.audit(user["uid"], "assessment.end", "assessment", aid,
             {"force_submitted": n})
    return db.ok({"status": "ENDED", "force_submitted": n})


@router.post("/{aid}/reopen")
def reopen(aid: str, payload: dict, user=Depends(require_role(SUPREME))):
    """Control 4 — extend or re-open the deadline."""
    row = _get(aid, user, for_edit=True)
    updates = {"status": "PUBLISHED"}
    deadline = (payload or {}).get("deadline_at")
    if deadline is not None:
        updates["deadline_at"] = deadline or None
    db.update("assessments", updates, id=aid)
    db.audit(user["uid"], "assessment.reopen", "assessment", aid,
             {"deadline_at": deadline})
    return db.ok({"status": "PUBLISHED", "deadline_at": updates.get("deadline_at")})


@router.get("/{aid}/live")
def live_attempts(aid: str, user=Depends(require_role(MASTER, SUPREME))):
    """Control 2 — watch in-progress attempts (who is sitting right now)."""
    _get(aid, user, for_edit=True)
    rows, _ = db.select(
        "assessment_attempts",
        "id, trainee_id, attempt_no, started_at, status, "
        "users!trainee_id(name, email, department)",
        eq={"assessment_id": aid, "status": "IN_PROGRESS"},
        order=("started_at", False), limit=200)
    out = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        out.append({
            "attempt_id": r["id"], "trainee_id": r["trainee_id"],
            "name": u.get("name", ""), "email": u.get("email", ""),
            "department": u.get("department", ""),
            "started_at": r.get("started_at"),
            "elapsed_seconds": _elapsed(r.get("started_at")),
        })
    return db.ok(out, meta={"live": len(out)})


def _elapsed(started: Optional[str]) -> int:
    if not started:
        return 0
    try:
        from datetime import datetime, timezone
        s = str(started).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    except Exception:
        return 0


@router.post("/{aid}/attempts/{attempt_id}/void")
def void_attempt(aid: str, attempt_id: str, user=Depends(require_role(MASTER, SUPREME))):
    """Control 5 — void a trainee's attempt (excluded from all results)."""
    row = _get(aid, user, for_edit=True)
    attempt = db.first("assessment_attempts", "*",
                       eq={"id": attempt_id, "assessment_id": aid})
    if not attempt:
        raise db.NotFound("Attempt not found")
    db.update("assessment_attempts",
              {"status": "VOIDED", "ended_by": user["uid"]}, id=attempt_id)
    # Any certificate earned from this attempt goes with it.
    certs, _ = db.select("certificates", "id",
                         eq={"attempt_id": attempt_id, "status": "VALID"})
    for c in certs:
        db.update("certificates", {"status": "REVOKED"}, id=c["id"])
    db.audit(user["uid"], "assessment.void", "assessment", aid,
             {"attempt": attempt_id, "trainee": attempt.get("trainee_id"),
              "certs_revoked": len(certs)})
    return db.ok({"status": "VOIDED", "certificates_revoked": len(certs)})


@router.get("/{aid}/attempts")
def all_attempts(aid: str, status: str = "",
                 limit: int = Query(default=200, ge=1, le=500),
                 user=Depends(require_role(MASTER, SUPREME))):
    _get(aid, user, for_edit=True)
    eq = {"assessment_id": aid}
    if status:
        eq["status"] = status
    rows, total = db.select(
        "assessment_attempts",
        "id, trainee_id, attempt_no, started_at, submitted_at, score, "
        "max_score, percentage, passed, status, users!trainee_id(name, email)",
        eq=eq, order=("submitted_at", True), limit=limit, count=True)
    out = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        r["name"] = u.get("name", "")
        r["email"] = u.get("email", "")
        r.pop("users", None)
        out.append(r)
    return db.ok(out, meta={"total": total or len(out)})


# ─── Attempts (trainee side) ───────────────────────────────────────────────
@router.post("/{aid}/start")
def start(aid: str, payload: StartIn, user=Depends(require_role(ALPHA))):
    row = _get(aid, user)
    live = quiz.require_attemptable(row, "ASSESSMENT", user["uid"])
    if live:
        return db.ok({"attempt": live, "resumed": True,
                      "questions": _safe(live), "assessment": _public(row, user)})

    attempt = db.insert("assessment_attempts", {
        "assessment_id": aid, "trainee_id": user["uid"], "attempt_no": 1,
        "status": "IN_PROGRESS", "max_score": _max(aid), "score": 0,
    })
    db.audit(user["uid"], "assessment.start", "assessment", aid)
    return db.ok({"attempt": attempt, "resumed": False,
                  "questions": _safe(attempt), "assessment": _public(row, user)})


def _max(aid: str) -> float:
    qs = quiz.load_questions("ASSESSMENT", aid)
    return round(sum(float(q.get("points") or 1) for q in qs), 2)


def _safe(attempt: dict) -> list[dict]:
    """Questions with no answer key — the exam must not leak solutions."""
    qs = quiz.load_questions("ASSESSMENT", attempt["assessment_id"])
    return [{
        "id": q["id"], "text": q["text"], "difficulty": q.get("difficulty"),
        "points": q.get("points", 1), "sort_order": q.get("sort_order", 0),
        "topic_id": q.get("topic_id"),
        "options": [{"id": o["id"], "text": o["text"]}
                    for o in q.get("options", [])],
    } for q in qs]


@router.post("/{aid}/progress")
def save_progress(aid: str, payload: SubmitIn,
                  user=Depends(require_role(ALPHA))):
    """Persist in-progress answers so a refresh or force-submit keeps them."""
    attempt = quiz.active_attempt("ASSESSMENT", aid, user["uid"])
    if not attempt:
        raise db.Rejected("No attempt is in progress.")
    # Stored per-row (not as jsonb on the attempt) — see quiz's table mapping.
    saved = quiz.save_responses("ASSESSMENT", attempt, payload.responses)
    return db.ok({"saved": saved})


@router.get("/{aid}/attempts/mine")
def my_attempts(aid: str, user=Depends(require_role(ALPHA))):
    return db.ok(_mine(aid, user["uid"]))


@router.post("/{aid}/submit-attempt")
def submit_attempt(aid: str, payload: SubmitIn,
                   user=Depends(require_role(ALPHA))):
    """Grade, record, and issue the certificate on a pass."""
    row = _get(aid, user)
    attempt = quiz.active_attempt("ASSESSMENT", aid, user["uid"])
    if not attempt:
        raise db.Rejected("No attempt is in progress. Start one first.")

    graded = quiz.score_responses("ASSESSMENT", aid, payload.responses)

    # Persist every answer — blanks graded as incorrect — as the audit trail.
    quiz.save_responses("ASSESSMENT", attempt, payload.responses, complete=True)

    # Pass/fail is judged against the assessment's own passing score, scaled
    # to the question total so partial papers are still graded fairly.
    max_total = graded["max_score"] or 1
    declared_max = float(row.get("max_score") or 100)
    scaled_score = round(graded["score"] / max_total * declared_max, 2) \
        if max_total else 0.0
    pct = graded["percentage"]
    passing_pct = (float(row.get("passing_score") or 60) / declared_max * 100) \
        if declared_max else 60.0
    passed = pct >= passing_pct

    expired = bool(row.get("deadline_at") and quiz.is_past(row["deadline_at"]))
    status = "EXPIRED" if expired else "SUBMITTED"

    db.update("assessment_attempts", {
        "submitted_at": "now()", "status": status,
        "score": scaled_score, "max_score": declared_max,
        "percentage": pct, "passed": passed,
    }, id=attempt["id"])

    cert = None
    if passed:
        cert = _issue_certificate(row, attempt, user, scaled_score, pct)

    # Veda report — deterministic base is always produced; AI layer is
    # populated by routes/reports.py (works without a Groq key).
    _build_report(row, attempt, user, scaled_score, pct, passed, graded)

    db.audit(user["uid"], "assessment.submit", "assessment", aid,
             {"pct": pct, "passed": passed})
    return db.ok({
        "attempt_id": attempt["id"],
        "score": scaled_score, "max_score": declared_max,
        "percentage": pct, "passed": passed,
        "passing_pct": round(passing_pct, 1),
        "certificate": cert,
        "detail": graded["detail"],
        "by_topic": list(graded["by_topic"].values()),
        "by_difficulty": list(graded["by_difficulty"].values()),
    })


def _issue_certificate(row: dict, attempt: dict, user: dict,
                       score: float, pct: float) -> Optional[dict]:
    """Auto-issue on pass. Idempotent per attempt."""
    existing = db.first("certificates", "*", eq={"attempt_id": attempt["id"]})
    if existing:
        if existing.get("status") == "REVOKED":
            db.update("certificates", {"status": "VALID"}, id=existing["id"])
        return existing

    code = f"CC-{uuid.uuid4().hex[:10].upper()}"
    cert = db.insert("certificates", {
        "code": code, "trainee_id": user["uid"],
        "assessment_id": row["id"], "attempt_id": attempt["id"],
        "title": row.get("title", ""),
        "subject_id": row.get("subject_id"),
        "score": score, "percentage": pct,
        "issued_by": "AUTO", "status": "VALID",
    })

    from backend.routes.notifications import notify
    notify(db.client_or_none(), user["uid"],
           ntype="ACHIEVEMENT", title="Certificate earned",
           message=f"You passed “{row.get('title','')}” with {pct:.1f}%.",
           link=f"/certificates/{cert.get('code', code)}",
           metadata={"certificate_code": cert.get("code", code)})

    _announce_achievement(user, row, pct)
    return cert


def _announce_achievement(user: dict, row: dict, pct: float):
    """Post the pass to the home feed as an ACHIEVEMENT item."""
    name = db.first("users", "name", eq={"id": user["uid"]}) or {}
    db.insert("home_posts", {
        "type": "ACHIEVEMENT",
        "title": f"{name.get('name','A trainee')} earned a certificate",
        "body": f"Passed “{row.get('title','')}” with {pct:.1f}%.",
        "target_roles": ["ALPHA", "MASTER", "SUPREME"],
        "published": True, "pinned": False,
    })


def _build_report(row, attempt, user, score, pct, passed, graded):
    """Persist the deterministic report skeleton (AI insights fill later)."""
    weak, strong = quiz.topics_ranked(graded["by_topic"], "ASSESSMENT")
    try:
        db.insert("performance_reports", {
            "attempt_id": attempt["id"], "attempt_kind": "ASSESSMENT",
            "trainee_id": user["uid"], "subject_id": row.get("subject_id"),
            "score": score, "percentage": pct, "passed": passed,
            "weak_topics": weak, "strong_topics": strong,
            "difficulty_breakdown": graded["by_difficulty"],
            "benchmark": _benchmark(row.get("subject_id")),
            "ai_insights": {}, "ai_generated": False,
        })
    except db.Rejected:
        # Report already exists for this attempt — refresh the numbers.
        try:
            db.update("performance_reports", {
                "score": score, "percentage": pct, "passed": passed,
                "weak_topics": weak, "strong_topics": strong,
                "difficulty_breakdown": graded["by_difficulty"],
            }, attempt_id=attempt["id"], attempt_kind="ASSESSMENT")
        except db.Rejected:
            pass


def _benchmark(subject_id: Optional[str]) -> dict:
    if not subject_id:
        return {}
    rows, _ = db.select(
        "subject_benchmarks",
        "industry_standard, expected_proficiency, subject_topics(name)",
        eq={"subject_id": subject_id}, limit=200)
    out = []
    for r in rows:
        t = r.get("subject_topics") or {}
        if isinstance(t, list):
            t = t[0] if t else {}
        out.append({"topic": t.get("name", ""),
                    "standard": r.get("industry_standard", ""),
                    "expected": r.get("expected_proficiency", 60)})
    return {"subject_id": subject_id, "topics": out}


def _force_submit(aid: str, ended_by: str) -> int:
    rows, _ = db.select("assessment_attempts", "id",
                        eq={"assessment_id": aid, "status": "IN_PROGRESS"})
    n = 0
    for r in rows:
        attempt = db.first("assessment_attempts", "*", eq={"id": r["id"]})
        responses = quiz.load_responses("ASSESSMENT", attempt or {})
        graded = quiz.score_responses("ASSESSMENT", aid, responses)
        row = db.first("assessments", "max_score, passing_score, subject_id, title",
                       eq={"id": aid}) or {}
        declared_max = float(row.get("max_score") or 100)
        max_total = graded["max_score"] or 1
        scaled = round(graded["score"] / max_total * declared_max, 2) \
            if max_total else 0.0
        pct = graded["percentage"]
        passing_pct = (float(row.get("passing_score") or 60) / declared_max * 100) \
            if declared_max else 60.0
        passed = pct >= passing_pct

        db.update("assessment_attempts", {
            "status": "EXPIRED", "submitted_at": "now()", "ended_by": ended_by,
            "score": scaled, "percentage": pct, "passed": passed,
        }, id=r["id"])
        n += 1
    return n


def _notify_supreme(row: dict, noun: str):
    from backend.routes.notifications import notify_many
    sup, _ = db.select("users", "id", eq={"role": SUPREME, "status": "ACTIVE"},
                       limit=50)
    notify_many(db.client_or_none(), [s["id"] for s in sup],
                ntype="RELEASE",
                title="Assessment awaiting release",
                message=f"“{row.get('title','')}” is waiting for your approval.",
                link=f"/assessments/{row.get('id')}",
                metadata={"id": row.get("id")})
