"""Questionnaires — practice with a deadline.

Master authors (manually or from AI drafts), sets a deadline and attempt
budget, submits for Supreme release. Alpha attempts within the window as many
times as `max_attempts` allows. Unlike assessments this never issues a
certificate — it is formative practice.

Status: DRAFT → PENDING_RELEASE → PUBLISHED → ENDED → ARCHIVED
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db, quiz

router = APIRouter(prefix="/questionnaires", tags=["questionnaires"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class CreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=2000)
    subject_id: str = ""
    topic_id: str = ""
    course_id: str = ""
    deadline_at: str = ""
    duration_minutes: int = Field(default=30, ge=1, le=480)
    max_attempts: int = Field(default=3, ge=1, le=10)


class UpdateIn(CreateIn):
    pass


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
    responses: list[dict] = Field(default=[], max_length=200)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


# ─── Visibility ────────────────────────────────────────────────────────────
def _get(container_id: str, user: dict, for_edit: bool = False) -> dict:
    row = db.first("questionnaires", "*", eq={"id": container_id})
    if not row:
        raise db.NotFound("Questionnaire not found")
    if for_edit:
        if user["role"] == SUPREME:
            return row
        if user["role"] != MASTER or row.get("trainer_id") != user["uid"]:
            raise db.Denied("You do not own this questionnaire.")
        return row
    # View
    if user["role"] in (SUPREME, MASTER):
        return row
    if row.get("status") not in ("PUBLISHED",):
        raise db.NotFound("Questionnaire not found")
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
        "question_count": quiz.question_count("QUESTIONNAIRE", row["id"]),
        "can_edit": bool(row.get("trainer_id") == user["uid"]
                         or user["role"] == SUPREME),
    }


# ─── CRUD ──────────────────────────────────────────────────────────────────
@router.get("")
def list_questionnaires(
    status: str = Query(default="", max_length=30),
    subject_id: str = Query(default="", max_length=60),
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
        # Supreme's "mine" means "authored by me" — without it Supreme would
        # be offered every test in the portal when picking a publish target.
        eq["trainer_id"] = user["uid"]
    if status:
        eq["status"] = status
    if subject_id:
        eq["subject_id"] = subject_id

    rows, total = db.select("questionnaires", "*", eq=eq or None,
                            order=("created_at", True), limit=limit, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r.get("title", "") or "").lower()]
    out = []
    for r in rows:
        p = _public(r, user)
        if user["role"] == ALPHA:
            p["attempts_used"] = _attempts_used(r["id"], user["uid"])
            p["has_live"] = bool(quiz.active_attempt("QUESTIONNAIRE", r["id"], user["uid"]))
        out.append(p)
    return db.ok(out, meta={"total": total or len(out)})


def _attempts_used(qid: str, uid: str) -> int:
    _, total = db.select("questionnaire_attempts", "id",
                         eq={"questionnaire_id": qid, "trainee_id": uid},
                         count=True)
    return total


@router.get("/{qid}")
def get_questionnaire(qid: str, user=Depends(_auth)):
    row = _get(qid, user)
    p = _public(row, user)
    if user["role"] == ALPHA:
        p["attempts_used"] = _attempts_used(qid, user["uid"])
        p["has_live"] = bool(quiz.active_attempt("QUESTIONNAIRE", qid, user["uid"]))
        p["overdue"] = quiz.is_past(row.get("deadline_at"))
    return db.ok(p)


@router.post("")
def create(payload: CreateIn, user=Depends(require_role(MASTER, SUPREME))):
    row = db.insert("questionnaires", {
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "subject_id": payload.subject_id or None,
        "topic_id": payload.topic_id or None,
        "course_id": payload.course_id or None,
        "trainer_id": user["uid"],
        "deadline_at": payload.deadline_at or None,
        "duration_minutes": payload.duration_minutes,
        "max_attempts": payload.max_attempts,
        "status": "DRAFT",
    })
    db.audit(user["uid"], "questionnaire.create", "questionnaire", row.get("id"))
    return db.ok(row)


@router.put("/{qid}")
def update(qid: str, payload: UpdateIn, user=Depends(_auth)):
    row = _get(qid, user, for_edit=True)
    if row["status"] in ("PUBLISHED", "ENDED", "ARCHIVED"):
        raise db.Rejected(f"Cannot edit a {row['status']} questionnaire.")
    rows = db.update("questionnaires", {
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "subject_id": payload.subject_id or None,
        "topic_id": payload.topic_id or None,
        "course_id": payload.course_id or None,
        "deadline_at": payload.deadline_at or None,
        "duration_minutes": payload.duration_minutes,
        "max_attempts": payload.max_attempts,
        "updated_at": "now()",
    }, id=qid)
    return db.ok(rows[0] if rows else None)


@router.delete("/{qid}")
def delete(qid: str, user=Depends(_auth)):
    row = _get(qid, user, for_edit=True)
    if row["status"] == "PUBLISHED" and user["role"] != SUPREME:
        raise db.Rejected("Supreme must archive a published questionnaire first.")
    db.delete("questionnaires", id=qid)
    db.audit(user["uid"], "questionnaire.delete", "questionnaire", qid)
    return db.ok({"deleted": True})


# ─── Questions ─────────────────────────────────────────────────────────────
@router.get("/{qid}/questions")
def list_questions(qid: str, user=Depends(_auth)):
    _get(qid, user)
    return db.ok(quiz.load_questions("QUESTIONNAIRE", qid))


@router.post("/{qid}/questions")
def add_question(qid: str, payload: QuestionIn, user=Depends(_auth)):
    _get(qid, user, for_edit=True)
    _, total = db.select("questionnaire_questions", "id",
                         eq={"questionnaire_id": qid}, count=True)
    row = quiz.add_question("QUESTIONNAIRE", qid, {
        **payload.model_dump(), "sort_order": total,
    })
    return db.ok(row)


@router.post("/{qid}/questions/bulk")
def add_questions_bulk(qid: str, payload: dict, user=Depends(_auth)):
    """Insert many at once — the path AI drafts take after review."""
    _get(qid, user, for_edit=True)
    items = (payload or {}).get("questions") or []
    if len(items) > 100:
        raise db.Rejected("Bulk insert is capped at 100 questions.")
    _, total = db.select("questionnaire_questions", "id",
                         eq={"questionnaire_id": qid}, count=True)
    added, errors = 0, []
    for i, item in enumerate(items):
        try:
            quiz.add_question("QUESTIONNAIRE", qid,
                              {**item, "sort_order": total + i})
            added += 1
        except db.Rejected as e:
            errors.append({"index": i, "error": e.detail})
    return db.ok({"added": added, "errors": errors})


@router.delete("/{qid}/questions/{question_id}")
def remove_question(qid: str, question_id: str, user=Depends(_auth)):
    _get(qid, user, for_edit=True)
    quiz.delete_question("QUESTIONNAIRE", question_id)
    return db.ok({"deleted": True})


@router.put("/{qid}/questions-order")
def reorder(qid: str, payload: dict, user=Depends(_auth)):
    _get(qid, user, for_edit=True)
    quiz.retype_questions("QUESTIONNAIRE", qid, (payload or {}).get("order") or [])
    return db.ok({"order": (payload or {}).get("order") or []})


# ─── Release ───────────────────────────────────────────────────────────────
@router.post("/{qid}/submit")
def submit(qid: str, user=Depends(_auth)):
    row = _get(qid, user, for_edit=True)
    if row["status"] not in ("DRAFT", "PENDING_RELEASE"):
        raise db.Rejected(f"Cannot submit a {row['status']} questionnaire.")
    if quiz.question_count("QUESTIONNAIRE", qid) == 0:
        raise db.Rejected("Add at least one question before submitting.")
    db.update("questionnaires", {"status": "PENDING_RELEASE"}, id=qid)
    _notify_supreme(row, "questionnaire")
    db.audit(user["uid"], "questionnaire.submit", "questionnaire", qid)
    return db.ok({"status": "PENDING_RELEASE"})


@router.post("/{qid}/release")
def release(qid: str, user=Depends(require_role(SUPREME))):
    row = _get(qid, user, for_edit=True)
    if row["status"] not in ("PENDING_RELEASE", "ENDED", "ARCHIVED"):
        raise db.Rejected(f"Cannot release from status {row['status']}.")
    db.update("questionnaires", {"status": "PUBLISHED"}, id=qid)
    db.audit(user["uid"], "questionnaire.release", "questionnaire", qid)
    return db.ok({"status": "PUBLISHED"})


@router.post("/{qid}/reject")
def reject(qid: str, user=Depends(require_role(SUPREME))):
    row = _get(qid, user, for_edit=True)
    if row["status"] != "PENDING_RELEASE":
        raise db.Rejected("Only submitted questionnaires can be sent back.")
    db.update("questionnaires", {"status": "DRAFT"}, id=qid)
    return db.ok({"status": "DRAFT"})


@router.post("/{qid}/end")
def end_now(qid: str, user=Depends(require_role(SUPREME))):
    """Close the window and force-submit anyone still in progress."""
    row = _get(qid, user, for_edit=True)
    db.update("questionnaires", {"status": "ENDED"}, id=qid)
    n = _force_submit_open_attempts(qid, user["uid"])
    db.audit(user["uid"], "questionnaire.end", "questionnaire", qid,
             {"force_submitted": n})
    return db.ok({"status": "ENDED", "force_submitted": n})


@router.post("/{qid}/reopen")
def reopen(qid: str, payload: dict, user=Depends(require_role(SUPREME))):
    """Extend or re-open the window (deadline may be pushed forward)."""
    row = _get(qid, user, for_edit=True)
    updates = {"status": "PUBLISHED"}
    deadline = (payload or {}).get("deadline_at")
    if deadline:
        updates["deadline_at"] = deadline
    db.update("questionnaires", updates, id=qid)
    db.audit(user["uid"], "questionnaire.reopen", "questionnaire", qid,
             {"deadline_at": deadline})
    return db.ok({"status": "PUBLISHED", "deadline_at": deadline})


# ─── Attempts ──────────────────────────────────────────────────────────────
@router.post("/{qid}/start")
def start(qid: str, payload: StartIn, user=Depends(require_role(ALPHA))):
    row = _get(qid, user)
    live = quiz.require_attemptable(row, "QUESTIONNAIRE", user["uid"])
    if live:
        return db.ok({"attempt": live, "resumed": True,
                      "questions": _safe_questions(live)})

    attempt_no = quiz.attempt_number("QUESTIONNAIRE", qid, user["uid"])
    attempt = db.insert("questionnaire_attempts", {
        "questionnaire_id": qid, "trainee_id": user["uid"],
        "attempt_no": attempt_no, "status": "IN_PROGRESS",
        "max_score": _max_score(qid), "responses": [],
    })
    return db.ok({"attempt": attempt, "resumed": False,
                  "questions": _safe_questions(attempt)})


def _max_score(qid: str) -> float:
    qs = quiz.load_questions("QUESTIONNAIRE", qid)
    return round(sum(float(q.get("points") or 1) for q in qs), 2)


def _safe_questions(attempt: dict) -> list[dict]:
    """Questions WITHOUT the answer key — the trainee must not see it."""
    qs = quiz.load_questions("QUESTIONNAIRE", attempt["questionnaire_id"])
    return [{
        "id": q["id"], "text": q["text"], "difficulty": q.get("difficulty"),
        "points": q.get("points", 1), "sort_order": q.get("sort_order", 0),
        "options": [{"id": o["id"], "text": o["text"]}
                    for o in q.get("options", [])],
    } for q in qs]


@router.get("/{qid}/attempts/mine")
def my_attempts(qid: str, user=Depends(require_role(ALPHA))):
    rows, _ = db.select("questionnaire_attempts", "*",
                        eq={"questionnaire_id": qid, "trainee_id": user["uid"]},
                        order=("attempt_no", True), limit=20)
    return db.ok(rows)


@router.post("/{qid}/submit-attempt")
def submit_attempt(qid: str, payload: SubmitIn,
                   user=Depends(require_role(ALPHA))):
    """Grade and record. Re-sending the same attempt is idempotent."""
    row = _get(qid, user)
    attempt = quiz.active_attempt("QUESTIONNAIRE", qid, user["uid"])
    if not attempt:
        raise db.Rejected("No attempt is in progress. Start one first.")

    graded = quiz.score_responses("QUESTIONNAIRE", qid, payload.responses)
    responses = [
        {"question_id": d["question_id"], "option_id":
         next((r.get("option_id") for r in payload.responses
               if r.get("question_id") == d["question_id"]), None),
         "is_correct": d["correct"], "topic_id": d["topic_id"]}
        for d in graded["detail"]
    ]
    status = "SUBMITTED"
    if row.get("deadline_at") and quiz.is_past(row["deadline_at"]):
        status = "EXPIRED"

    db.update("questionnaire_attempts", {
        "submitted_at": "now()", "status": status,
        "score": graded["score"], "max_score": graded["max_score"],
        "percentage": graded["percentage"], "responses": responses,
    }, id=attempt["id"])

    db.audit(user["uid"], "questionnaire.attempt", "questionnaire", qid,
             {"pct": graded["percentage"]})
    return db.ok({
        "attempt_id": attempt["id"],
        "score": graded["score"], "max_score": graded["max_score"],
        "percentage": graded["percentage"],
        "passed": None,
        "detail": graded["detail"],
        "by_topic": list(graded["by_topic"].values()),
        "by_difficulty": list(graded["by_difficulty"].values()),
    })


@router.post("/{qid}/attempts/{attempt_id}/void")
def void_attempt(qid: str, attempt_id: str, payload: dict,
                 user=Depends(require_role(MASTER, SUPREME))):
    """Void a trainee's attempt (cheating / technical fault). Reversible by
    Supreme re-opening; the attempt is excluded from results."""
    row = _get(qid, user, for_edit=True)
    attempt = db.first("questionnaire_attempts", "*",
                       eq={"id": attempt_id, "questionnaire_id": qid})
    if not attempt:
        raise db.NotFound("Attempt not found")
    db.update("questionnaire_attempts",
              {"status": "VOIDED", "ended_by": user["uid"]}, id=attempt_id)
    db.audit(user["uid"], "questionnaire.void", "questionnaire", qid,
             {"attempt": attempt_id, "trainee": attempt.get("trainee_id")})
    return db.ok({"status": "VOIDED"})


@router.get("/{qid}/attempts")
def all_attempts(qid: str, status: str = "",
                 limit: int = Query(default=200, ge=1, le=500),
                 user=Depends(require_role(MASTER, SUPREME))):
    """Trainer/Supreme review of every attempt on this questionnaire."""
    _get(qid, user, for_edit=True)
    eq = {"questionnaire_id": qid}
    if status:
        eq["status"] = status
    rows, total = db.select(
        "questionnaire_attempts",
        "id, trainee_id, attempt_no, started_at, submitted_at, score, "
        "max_score, percentage, status, responses, users!trainee_id(name, email)",
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


@router.get("/{qid}/live")
def live_attempts(qid: str, user=Depends(require_role(MASTER, SUPREME))):
    """Watch who is working on this practice set right now.

    Mirrors the assessment screen: a trainer watching a deadline wants the
    same view whether the test is a formal exam or a practice set, and the
    player calls this through `${base}` for both kinds.
    """
    _get(qid, user, for_edit=True)
    rows, _ = db.select(
        "questionnaire_attempts",
        "id, trainee_id, attempt_no, started_at, status, "
        "users!trainee_id(name, email, department)",
        eq={"questionnaire_id": qid, "status": "IN_PROGRESS"},
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


def _elapsed(started) -> int:
    """Seconds since the attempt began, or 0 when it cannot be parsed."""
    if not started:
        return 0
    try:
        from datetime import datetime, timezone
        s = started if isinstance(started, datetime) else datetime.fromisoformat(
            str(started).replace("Z", "+00:00"))
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - s).total_seconds()))
    except Exception:
        return 0


@router.post("/{qid}/progress")
def save_progress(qid: str, payload: SubmitIn,
                  user=Depends(require_role(ALPHA))):
    """Persist in-progress answers so a refresh does not lose them.

    Questionnaires keep responses inline as jsonb on the attempt row; the
    assessment screen writes one row per question instead (see the response
    storage contract). Grading always recomputes correctness from the answer
    key, so only the picked option is worth storing here.
    """
    attempt = quiz.active_attempt("QUESTIONNAIRE", qid, user["uid"])
    if not attempt:
        raise db.Rejected("No attempt is in progress.")
    clean = [{"question_id": r.get("question_id"), "option_id": r.get("option_id")}
             for r in (payload.responses or []) if r.get("question_id")]
    db.update("questionnaire_attempts", {"responses": clean},
              id=attempt["id"])
    return db.ok({"saved": len(clean)})


def _force_submit_open_attempts(qid: str, ended_by: str) -> int:
    rows, _ = db.select("questionnaire_attempts", "id",
                        eq={"questionnaire_id": qid, "status": "IN_PROGRESS"})
    n = 0
    for r in rows:
        # Grade whatever was answered before the window slammed shut.
        attempt = db.first("questionnaire_attempts", "*", eq={"id": r["id"]})
        responses = attempt.get("responses") or [] if attempt else []
        graded = quiz.score_responses("QUESTIONNAIRE", qid, responses)
        db.update("questionnaire_attempts", {
            "status": "EXPIRED", "submitted_at": "now", "ended_by": ended_by,
            "score": graded["score"], "max_score": graded["max_score"],
            "percentage": graded["percentage"],
        }, id=r["id"])
        n += 1
    return n


def _notify_supreme(row: dict, noun: str):
    from backend.routes.notifications import notify_many
    sup, _ = db.select("users", "id", eq={"role": SUPREME, "status": "ACTIVE"},
                       limit=50)
    notify_many(db.client_or_none(), [s["id"] for s in sup],
                ntype="RELEASE",
                title=f"{noun.capitalize()} awaiting release",
                message=f"“{row.get('title','')}” is waiting for your approval.",
                link=f"/{noun}s/{row.get('id')}",
                metadata={"id": row.get("id")})
