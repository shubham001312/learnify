"""AI drafting: generate → queue → edit → publish.

Nothing AI-produced ever reaches a trainee directly. Generation writes into
`draft_questions` (status DRAFT); a Master edits, then explicitly publishes
them into a questionnaire/assessment. Discarding is always available.

Topics: every draft carries a topic tag. If the model omits or mismatches one,
the route resolves it against the subject's curated topic list before saving —
so the weak-point analysis downstream is never starved of data.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import MASTER, SUPREME, _extract_user, require_role
from backend.services import db, quiz
from backend.services import ai as ai_svc

router = APIRouter(prefix="/ai", tags=["ai"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class GenerateIn(BaseModel):
    subject_id: str = ""
    topic_ids: list[str] = Field(default=[], max_length=40)
    count: int = Field(default=8, ge=1, le=40)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    kind: str = Field(default="QUESTIONNAIRE", pattern="^(QUESTIONNAIRE|ASSESSMENT)$")
    context: str = Field(default="", max_length=1200)


class DraftEdit(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0, le=5)
    explanation: str = Field(default="", max_length=1500)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    topic_id: str = Field(default="", max_length=60)


class PublishIn(BaseModel):
    target_id: str = Field(min_length=1, max_length=60)


class ToManual(BaseModel):
    """A single draft promoted straight into a container's question list."""

    target_id: str = Field(min_length=1, max_length=60)
    sort_order: int = Field(default=0, ge=0, le=5000)


# ─── Capability ────────────────────────────────────────────────────────────
@router.get("/status")
def ai_status(user=Depends(_auth)):
    """Lets the UI show AI controls as enabled/disabled without guessing."""
    return db.ok(ai_svc.available())


# ─── Generation ────────────────────────────────────────────────────────────
@router.post("/generate-questions")
def generate(payload: GenerateIn, user=Depends(require_role(MASTER, SUPREME))):
    """Generate drafts into the queue. Returns them for on-screen editing."""
    subject = None
    if payload.subject_id:
        subject = db.first("subjects", "id, code, name",
                           eq={"id": payload.subject_id})
        if not subject:
            raise db.NotFound("Subject not found")

    topic_rows, _ = db.select(
        "subject_topics", "id, name, subject_id",
        in_={"subject_id": [payload.subject_id]} if payload.subject_id
        else {"subject_id": [""]}, limit=500)
    topics_by_id = {t["id"]: t for t in topic_rows}

    selected_names = []
    selected_ids = []
    for tid in payload.topic_ids:
        t = topics_by_id.get(tid)
        if t:
            selected_ids.append(tid)
            selected_names.append(t["name"])
    # Fall back to the whole curated list when the caller picked nothing.
    if not selected_names:
        selected_names = [t["name"] for t in topic_rows]
        selected_ids = [t["id"] for t in topic_rows]

    subject_name = (subject or {}).get("name") or "General training"

    try:
        drafts = ai_svc.generate_questions(
            subject=subject_name,
            topics=selected_names,
            count=payload.count,
            difficulty=payload.difficulty,
            kind=payload.kind,
            extra_context=payload.context,
        )
    except ai_svc.AIUnavailable as e:
        raise _unavailable(str(e))
    except ai_svc.AIInvalid as e:
        raise db.Rejected(f"The model returned unusable output: {e}")

    # Resolve each draft's topic string back to an id (or None).
    name_to_id = {t["name"].lower(): t["id"] for t in topic_rows}
    saved = []
    for d in drafts:
        tid = _topic_id_for(d.get("topic", ""), name_to_id, selected_ids)
        correct_index = d["correct_index"]
        choices = [{"text": t, "is_correct": i == correct_index}
                   for i, t in enumerate(d["options"])]
        row = db.insert("draft_questions", {
            "owner_id": user["uid"],
            "target_type": payload.kind,
            "target_id": None,
            "text": d["text"],
            "choices": choices,
            "correct_index": correct_index,
            "explanation": d.get("explanation", ""),
            "difficulty": d.get("difficulty", payload.difficulty),
            "topic_id": tid,
            "source": "AI",
            "status": "DRAFT",
            "sort_order": len(saved),
        })
        row["topic_name"] = _topic_name(tid, topics_by_id)
        saved.append(row)

    db.audit(user["uid"], "ai.generate", "draft_questions", "",
             {"n": len(saved), "kind": payload.kind,
              "subject": subject_name})
    return db.ok(saved, meta={"count": len(saved),
                              "model": ai_svc.DEFAULT_MODEL})


def _unavailable(msg: str):
    from fastapi import HTTPException
    return HTTPException(status_code=503, detail=msg)


def _topic_id_for(name: str, name_to_id: dict, fallback: list[str]) -> Optional[str]:
    n = (name or "").strip().lower()
    if n and n in name_to_id:
        return name_to_id[n]
    # partial match
    for k, v in name_to_id.items():
        if n and (n in k or k in n):
            return v
    if not n and len(fallback) == 1:
        return fallback[0]  # single topic selected → unambiguous
    return fallback[0] if (not n and fallback) else None


def _topic_name(tid: Optional[str], topics_by_id: dict) -> str:
    if not tid:
        return ""
    t = topics_by_id.get(tid)
    if t:
        return t["name"]
    row = db.first("subject_topics", "name", eq={"id": tid})
    return (row or {}).get("name", "")


# ─── Draft queue ───────────────────────────────────────────────────────────
@router.get("/drafts")
def list_drafts(
    kind: str = Query(default="", max_length=20),
    status: str = Query(default="DRAFT", max_length=20),
    limit: int = Query(default=100, ge=1, le=300),
    user=Depends(require_role(MASTER, SUPREME)),
):
    """The queue — the trainer's review surface before anything is published."""
    eq = {"owner_id": user["uid"]}
    if status:
        eq["status"] = status
    if kind:
        eq["target_type"] = kind
    rows, total = db.select("draft_questions", "*", eq=eq,
                            order=("created_at", True), limit=limit, count=True)
    # Resolve topic names in one pass.
    topic_ids = sorted({r["topic_id"] for r in rows if r.get("topic_id")})
    names = {}
    if topic_ids:
        trows, _ = db.select("subject_topics", "id, name",
                             in_={"id": topic_ids}, limit=500)
        names = {t["id"]: t["name"] for t in trows}
    for r in rows:
        r["topic_name"] = names.get(r.get("topic_id"), "")
    return db.ok(rows, meta={"total": total or len(rows)})


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, user=Depends(require_role(MASTER, SUPREME))):
    row = db.first("draft_questions", "*", eq={"id": draft_id})
    if not row:
        raise db.NotFound("Draft not found")
    if user["role"] != SUPREME and row.get("owner_id") != user["uid"]:
        raise db.Denied("That draft belongs to another trainer.")
    row["topic_name"] = _single_topic_name(row)
    return db.ok(row)


@router.put("/drafts/{draft_id}")
def edit_draft(draft_id: str, payload: DraftEdit,
               user=Depends(require_role(MASTER, SUPREME))):
    """The 'edit' step — a trainer fixes wording, answer or topic."""
    row = db.first("draft_questions", "*", eq={"id": draft_id})
    if not row:
        raise db.NotFound("Draft not found")
    if user["role"] != SUPREME and row.get("owner_id") != user["uid"]:
        raise db.Denied("That draft belongs to another trainer.")
    if row.get("status") == "PUBLISHED":
        raise db.Rejected("This draft has already been published.")

    options = [str(o).strip() for o in payload.options][:6]
    if len(options) < 2:
        raise db.Rejected("A question needs at least two options.")
    if payload.correct_index >= len(options):
        raise db.Rejected("The correct answer must be one of the options.")

    # drop blanks and re-point the correct index if the list shrank
    kept = [(i, o) for i, o in enumerate(options) if o]
    if len(kept) < 2:
        raise db.Rejected("At least two options must be non-empty.")
    correct_text = options[payload.correct_index]
    clean_opts = [o for _, o in kept]
    new_ci = clean_opts.index(correct_text) if correct_text in clean_opts else 0

    choices = [{"text": t, "is_correct": i == new_ci}
               for i, t in enumerate(clean_opts)]

    rows = db.update("draft_questions", {
        "text": payload.text.strip(),
        "choices": choices,
        "correct_index": new_ci,
        "explanation": payload.explanation.strip(),
        "difficulty": payload.difficulty,
        "topic_id": payload.topic_id or None,
    }, id=draft_id)
    out = rows[0] if rows else row
    out["topic_name"] = _single_topic_name(out)
    return db.ok(out)


@router.delete("/drafts/{draft_id}")
def discard_draft(draft_id: str, user=Depends(require_role(MASTER, SUPREME))):
    row = db.first("draft_questions", "*", eq={"id": draft_id})
    if not row:
        raise db.NotFound("Draft not found")
    if user["role"] != SUPREME and row.get("owner_id") != user["uid"]:
        raise db.Denied("That draft belongs to another trainer.")
    db.delete("draft_questions", id=draft_id)
    return db.ok({"deleted": True})


@router.post("/drafts/bulk-publish")
def bulk_publish(payload: PublishIn, user=Depends(require_role(MASTER, SUPREME))):
    """Move every pending draft for a target into the real question bank."""
    return _publish(user, payload.target_id, draft_ids=None)


@router.post("/drafts/{draft_id}/publish")
def publish_one(draft_id: str, payload: ToManual,
                user=Depends(require_role(MASTER, SUPREME))):
    return _publish(user, payload.target_id, draft_ids=[draft_id])


@router.post("/drafts/publish-selected")
def publish_selected(payload: dict, user=Depends(require_role(MASTER, SUPREME))):
    """Publish a hand-picked subset — the usual 'take 6 of 8' flow."""
    ids = (payload or {}).get("draft_ids") or []
    target = (payload or {}).get("target_id") or ""
    if not ids:
        raise db.Rejected("Select at least one draft.")
    if not target:
        raise db.Rejected("Choose where to publish these questions.")
    return _publish(user, target, draft_ids=[str(i) for i in ids[:100]])


def _publish(user: dict, target_id: str, draft_ids: Optional[list]) -> dict:
    kind = _target_kind(target_id)
    t = quiz.tables(kind)
    container = db.first(t["container"], "id, trainer_id, status",
                         eq={"id": target_id})
    if not container:
        raise db.NotFound("Target not found.")
    if user["role"] != SUPREME and container.get("trainer_id") != user["uid"]:
        raise db.Denied("That test belongs to another trainer.")
    if container.get("status") in ("PUBLISHED", "ENDED", "ARCHIVED"):
        raise db.Rejected("Cannot add questions to a released test. Ask Supreme "
                          "to re-open it first.")

    eq = {"owner_id": user["uid"], "target_type": kind, "status": "DRAFT"}
    if draft_ids:
        eq["id"] = draft_ids
    drafts, total = db.select("draft_questions", "*", eq=eq,
                              order=("sort_order", False), limit=300)
    if not drafts:
        raise db.Rejected("No pending drafts to publish.")

    _, existing = db.select(t["questions"], "id",
                            eq={t["fk"]: target_id}, count=True)

    published, skipped = [], []
    for i, d in enumerate(drafts):
        choices = d.get("choices") or []
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            opts = [{"text": c.get("text", ""),
                     "is_correct": bool(c.get("is_correct"))} for c in choices]
        else:
            ci = int(d.get("correct_index") or 0)
            opts = [{"text": str(c), "is_correct": j == ci}
                    for j, c in enumerate(choices or [])]
        correct = [j for j, o in enumerate(opts) if o["is_correct"]]
        if len(opts) < 2 or len(correct) != 1:
            skipped.append({"id": d["id"], "reason": "invalid options"})
            continue
        # topic is mandatory for assessments
        if kind == "ASSESSMENT" and not d.get("topic_id"):
            skipped.append({"id": d["id"], "reason": "missing topic tag"})
            continue
        try:
            quiz.add_question(kind, target_id, {
                "text": d.get("text", ""),
                "explanation": d.get("explanation", ""),
                "difficulty": d.get("difficulty", "medium"),
                "topic_id": d.get("topic_id"),
                "points": 1,
                "sort_order": existing + i,
                "options": opts,
            })
            db.update("draft_questions",
                      {"status": "PUBLISHED", "target_id": target_id},
                      id=d["id"])
            published.append(d["id"])
        except db.Rejected as e:
            skipped.append({"id": d["id"], "reason": e.detail})

    db.audit(user["uid"], "ai.publish", t["container"], target_id,
             {"published": len(published), "skipped": len(skipped)})
    return db.ok({"published": len(published), "skipped": skipped,
                  "target_id": target_id})


def _target_kind(target_id: str) -> str:
    """Which container type an id belongs to (questionnaire vs assessment)."""
    if db.first("questionnaires", "id", eq={"id": target_id}):
        return "QUESTIONNAIRE"
    if db.first("assessments", "id", eq={"id": target_id}):
        return "ASSESSMENT"
    raise db.NotFound("Target not found.")


def _single_topic_name(row: dict) -> str:
    tid = row.get("topic_id")
    if not tid:
        return ""
    r = db.first("subject_topics", "name", eq={"id": tid})
    return (r or {}).get("name", "")


# ─── Report personalisation ────────────────────────────────────────────────
class ReportIn(BaseModel):
    report_id: str = Field(min_length=1, max_length=60)


@router.post("/personalise-report")
def personalise(payload: ReportIn, user=Depends(_auth)):
    """Add the AI layer to an existing deterministic Veda report.

    The caller already has scores/ranks/benchmarks persisted, so a Groq failure
    simply leaves `ai_generated=false` — the report still renders fully.
    """
    report = db.first("performance_reports", "*", eq={"id": payload.report_id})
    if not report:
        raise db.NotFound("Report not found")

    # Own report, their trainee, or Supreme.
    allowed = report.get("trainee_id") == user["uid"] or user["role"] == SUPREME
    if not allowed and user["role"] == MASTER:
        allowed = _is_my_trainee(report.get("trainee_id"), user["uid"])
    if not allowed:
        raise db.Denied("You cannot view this report.")

    trainee = db.first("users", "name", eq={"id": report.get("trainee_id")}) or {}
    subject = db.first("subjects", "name",
                       eq={"id": report.get("subject_id")}) if report.get("subject_id") else None
    benchmarks = (report.get("benchmark") or {}).get("topics") or []

    try:
        insights = ai_svc.personalise_report(
            trainee_name=trainee.get("name", "the learner"),
            subject=(subject or {}).get("name") or "this subject",
            percentage=float(report.get("percentage") or 0),
            passed=bool(report.get("passed")),
            weak_topics=report.get("weak_topics") or [],
            strong_topics=report.get("strong_topics") or [],
            difficulty=report.get("difficulty_breakdown") or {},
            benchmarks=benchmarks,
            attempt_kind=report.get("attempt_kind", "ASSESSMENT"),
        )
    except ai_svc.AIUnavailable as e:
        raise _unavailable(str(e))
    except ai_svc.AIInvalid as e:
        raise db.Rejected(f"Could not personalise: {e}")

    db.update("performance_reports", {
        "ai_insights": insights, "ai_generated": True,
        "ai_model": ai_svc.DEFAULT_MODEL,
    }, id=payload.report_id)
    return db.ok({"ai_insights": insights, "ai_generated": True,
                  "ai_model": ai_svc.DEFAULT_MODEL})


def _is_my_trainee(trainee_id: Optional[str], master_id: str) -> bool:
    if not trainee_id:
        return False
    # A Master is linked to trainees through courses they own.
    rows, _ = db.select("courses", "id", eq={"trainer_id": master_id}, limit=500)
    course_ids = [r["id"] for r in rows]
    if not course_ids:
        return False
    enr, _ = db.select("enrollments", "id",
                       in_={"course_id": course_ids},
                       eq={"trainee_id": trainee_id}, limit=1)
    return bool(enr)
