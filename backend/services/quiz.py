"""Shared quiz logic for questionnaires and assessments.

Both features are MCQ-based with per-question topic tags. Keeping scoring,
topic attribution and deadline handling in one place guarantees that practice
and the formal exam agree on what "correct" and "overdue" mean.

Table mapping:
                    QUESTIONNAIRE          ASSESSMENT
  container         questionnaires         assessments
  questions         questionnaire_questions assessment_questions
  options           questionnaire_options   assessment_options
  attempts          questionnaire_attempts  assessment_attempts
  responses         (jsonb on attempt)      assessment_responses
"""

from datetime import datetime, timezone
from typing import Optional

from backend.services import db

KINDS = ("QUESTIONNAIRE", "ASSESSMENT")

_TABLES = {
    "QUESTIONNAIRE": {
        "container": "questionnaires",
        "questions": "questionnaire_questions",
        "options": "questionnaire_options",
        "attempts": "questionnaire_attempts",
        "fk": "questionnaire_id",
    },
    "ASSESSMENT": {
        "container": "assessments",
        "questions": "assessment_questions",
        "options": "assessment_options",
        "attempts": "assessment_attempts",
        "fk": "assessment_id",
    },
}


def tables(kind: str) -> dict:
    if kind not in _TABLES:
        raise ValueError(f"unknown quiz kind: {kind}")
    return _TABLES[kind]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_past(deadline: Optional[str]) -> bool:
    """True when a deadline string (ISO / PostgREST) has elapsed."""
    if not deadline:
        return False
    try:
        s = str(deadline).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= _now()
    except Exception:
        return False


# ─── Questions ─────────────────────────────────────────────────────────────
def load_questions(kind: str, container_id: str) -> list[dict]:
    """Questions with their options, in sort order, for the authoring view."""
    t = tables(kind)
    qs, _ = db.select(t["questions"], "*",
                      eq={t["fk"]: container_id},
                      order=("sort_order", False), limit=500)
    if not qs:
        return []
    opts, _ = db.select(t["options"], "*",
                        in_={"question_id": [q["id"] for q in qs]},
                        order=("sort_order", False), limit=3000)
    by_q: dict[str, list] = {}
    for o in opts:
        by_q.setdefault(o["question_id"], []).append(o)
    for q in qs:
        q["options"] = by_q.get(q["id"], [])
    return qs


def question_count(kind: str, container_id: str) -> int:
    t = tables(kind)
    _, total = db.select(t["questions"], "id", eq={t["fk"]: container_id},
                         count=True)
    return total


def add_question(kind: str, container_id: str, data: dict) -> dict:
    """Insert a question + its options in one shot.

    `data` = {text, explanation, difficulty, topic_id, points, options:[{text,is_correct}]}
    Exactly one option must be flagged correct.
    """
    t = tables(kind)
    options = data.get("options") or []
    if len(options) < 2:
        raise db.Rejected("A question needs at least two options.")
    correct = [i for i, o in enumerate(options) if o.get("is_correct")]
    if len(correct) != 1:
        raise db.Rejected("Mark exactly one option as correct.")
    if len(options) > 6:
        raise db.Rejected("A question may have at most six options.")

    qrow = db.insert(t["questions"], {
        t["fk"]: container_id,
        "text": (data.get("text") or "").strip(),
        "explanation": (data.get("explanation") or "").strip(),
        "difficulty": data.get("difficulty") or "medium",
        "topic_id": data.get("topic_id") or None,
        "points": float(data.get("points") or 1),
        "sort_order": int(data.get("sort_order") or 0),
    })
    qid = qrow["id"]
    for i, o in enumerate(options):
        db.insert(t["options"], {
            "question_id": qid,
            "text": (o.get("text") or "").strip(),
            "is_correct": bool(o.get("is_correct")),
            "sort_order": i,
        })
    return qrow


def delete_question(kind: str, question_id: str):
    t = tables(kind)
    db.delete(t["questions"], id=question_id)


def retype_questions(kind: str, container_id: str, order: list[str]):
    """Re-order questions after a drag or an insert."""
    t = tables(kind)
    for i, qid in enumerate(order):
        db.update(t["questions"], {"sort_order": i}, id=qid,
                  **{t["fk"]: container_id})


def topic_of(kind: str, question_id: str) -> Optional[dict]:
    t = tables(kind)
    q = db.first(t["questions"], "text, topic_id, difficulty",
                 eq={"id": question_id})
    if not q or not q.get("topic_id"):
        return None
    topic = db.first("subject_topics", "id, name, subject_id",
                     eq={"id": q["topic_id"]})
    return topic


# ─── Attempts ──────────────────────────────────────────────────────────────
def active_attempt(kind: str, container_id: str, user_id: str) -> Optional[dict]:
    t = tables(kind)
    return db.first(t["attempts"], "*",
                    eq={t["fk"]: container_id, "trainee_id": user_id,
                        "status": "IN_PROGRESS"})


def attempt_number(kind: str, container_id: str, user_id: str) -> int:
    t = tables(kind)
    rows, total = db.select(t["attempts"], "id",
                            eq={t["fk"]: container_id, "trainee_id": user_id})
    return max(total, len(rows)) + 1


def score_responses(kind: str, container_id: str,
                    responses: list[dict]) -> dict:
    """Grade a set of [{question_id, option_id}] against the answer key.

    Returns {score, max_score, percentage, detail:[{question_id, topic_id,
    difficulty, is_correct, points}], by_topic, by_difficulty}.
    """
    questions = load_questions(kind, container_id)
    picked = {r.get("question_id"): r.get("option_id") for r in responses or []}

    max_score = sum(float(q.get("points") or 1) for q in questions)
    score = 0.0
    detail = []
    by_topic: dict[str, dict] = {}
    by_diff: dict[str, dict] = {}

    for q in questions:
        pts = float(q.get("points") or 1)
        correct_opt = next((o for o in q.get("options", [])
                            if o.get("is_correct")), None)
        chosen = picked.get(q["id"])
        is_correct = bool(correct_opt and chosen and chosen == correct_opt["id"])
        if is_correct:
            score += pts

        tid = q.get("topic_id") or ""
        topic_bucket = by_topic.setdefault(
            tid or "__untagged__",
            {"topic_id": tid, "correct": 0, "total": 0, "points": 0.0,
             "max_points": 0.0})
        topic_bucket["total"] += 1
        topic_bucket["max_points"] += pts
        if is_correct:
            topic_bucket["correct"] += 1
            topic_bucket["points"] += pts

        d = q.get("difficulty") or "medium"
        diff_bucket = by_diff.setdefault(
            d, {"correct": 0, "total": 0, "points": 0.0, "max_points": 0.0})
        diff_bucket["total"] += 1
        diff_bucket["max_points"] += pts
        if is_correct:
            diff_bucket["correct"] += 1
            diff_bucket["points"] += pts

        detail.append({
            "question_id": q["id"],
            "topic_id": tid or None,
            "difficulty": d,
            "points": pts,
            "correct": is_correct,
        })

    pct = round((score / max_score * 100), 2) if max_score else 0.0
    for bucket in list(by_topic.values()) + list(by_diff.values()):
        bucket["pct"] = round(bucket["points"] / bucket["max_points"] * 100, 1) \
            if bucket["max_points"] else 0.0

    return {
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "percentage": pct,
        "detail": detail,
        "by_topic": by_topic,
        "by_difficulty": by_diff,
    }


def save_responses(kind: str, attempt: dict, responses: list[dict],
                   *, complete: bool = False) -> int:
    """Persist answers for an attempt, honouring the storage split above.

    QUESTIONNAIRE keeps the whole answer list inline as jsonb; ASSESSMENT
    writes one row per question to assessment_responses (upserted, so
    re-answering a question overwrites the earlier pick).

    `complete=True` records every question on the paper — including the ones
    left blank, graded as incorrect — which is what final grading wants.
    Otherwise only the questions actually touched are written, so a mid-exam
    autosave never looks like a page of wrong answers.
    """
    responses = responses or []
    t = tables(kind)

    if kind == "QUESTIONNAIRE":
        db.update(t["attempts"], {"responses": responses}, id=attempt["id"])
        return len(responses)

    graded = score_responses(kind, attempt.get("assessment_id") or "", responses)
    chosen = {r.get("question_id"): r.get("option_id") for r in responses}
    n = 0
    for d in graded["detail"]:
        qid = d["question_id"]
        if not complete and qid not in chosen:
            continue
        db.upsert("assessment_responses", {
            "attempt_id": attempt["id"], "question_id": qid,
            "option_id": chosen.get(qid), "is_correct": bool(d["correct"]),
        }, "attempt_id,question_id")
        n += 1
    return n


def load_responses(kind: str, attempt: dict) -> list[dict]:
    """Stored answers in the shape reports rebuild from:

        [{question_id, option_id, is_correct, topic_id, points, difficulty}]

    Reads whichever store the kind uses, then enriches each row from the
    question paper so a rebuilt report attributes topics, points and difficulty
    exactly as the original grading did.
    """
    if not attempt:
        return []
    if kind == "QUESTIONNAIRE":
        raw = attempt.get("responses") or []
        container = attempt.get("questionnaire_id") or ""
    else:
        raw, _ = db.select("assessment_responses",
                           "question_id, option_id, is_correct",
                           eq={"attempt_id": attempt["id"]})
        container = attempt.get("assessment_id") or ""

    if not raw:
        return []

    meta = {q["id"]: q for q in load_questions(kind, container)} if container else {}
    out = []
    for r in raw:
        q = meta.get(r.get("question_id")) or {}
        out.append({
            "question_id": r.get("question_id"),
            "option_id": r.get("option_id"),
            "is_correct": bool(r.get("is_correct")),
            "topic_id": r.get("topic_id") or q.get("topic_id"),
            "points": float(r.get("points") or q.get("points") or 1),
            "difficulty": r.get("difficulty") or q.get("difficulty") or "medium",
        })
    return out


def topics_ranked(by_topic: dict, kind: str = "") -> tuple[list, list]:
    """Split topic buckets into (weak, strong) lists with resolved names."""
    rows = []
    for tid, b in by_topic.items():
        if tid == "__untagged__":
            name = "General"
        else:
            topic = db.first("subject_topics", "name, subject_id", eq={"id": tid})
            name = (topic or {}).get("name") or "General"
        rows.append({
            "topic_id": None if tid == "__untagged__" else tid,
            "topic": name,
            "subject_id": (topic or {}).get("subject_id") if tid != "__untagged__" else None,
            "correct": b["correct"],
            "total": b["total"],
            "pct": b["pct"],
        })
    # Weak = worst percentage first; strong = best first. Skip buckets where
    # every question was right/wrong so the lists stay meaningful.
    weak = sorted([r for r in rows if r["pct"] < 70],
                  key=lambda r: (r["pct"], r["topic"]))[:8]
    strong = sorted([r for r in rows if r["pct"] >= 70],
                    key=lambda r: (-r["pct"], r["topic"]))[:8]
    return weak, strong


def require_open(container: dict, kind: str):
    """Raise unless a trainee may currently start an attempt."""
    status = container.get("status")
    if status in ("DRAFT", "PENDING_RELEASE"):
        raise db.Rejected("This test has not been released yet.")
    if status in ("ENDED", "ARCHIVED"):
        raise db.Rejected("This test is closed.")
    if container.get("deadline_at") and is_past(container["deadline_at"]):
        raise db.Rejected("The deadline for this test has passed.")


def require_attemptable(container: dict, kind: str, user_id: str):
    """Open a fresh attempt only if the attempt budget allows it."""
    t = tables(kind)
    live = active_attempt(kind, container["id"], user_id)
    if live:
        return live
    require_open(container, kind)
    rows, total = db.select(t["attempts"], "id",
                            eq={t["fk"]: container["id"], "trainee_id": user_id})
    max_attempts = int(container.get("max_attempts") or 1) \
        if kind == "QUESTIONNAIRE" else 1
    if total >= max_attempts > 0:
        raise db.Rejected("You have used all your attempts for this test.")
    return None
