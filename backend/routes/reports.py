"""Veda performance reports.

Every attempt produces a report with two layers:

  1. Deterministic base — always present, computed at submit time from the
     stored responses: scores, weak/strong topics, difficulty split, and the
     curated industry benchmark for the subject.
  2. AI personalisation — optional, layered on by routes/ai.py. If Groq is
     unavailable the report still renders completely.

Audience rule (enforced below):
    ALPHA   → own reports only
    MASTER  → reports for trainees on their courses
    SUPREME → aggregate weak-topic stats across the platform
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db, quiz

router = APIRouter(prefix="/reports", tags=["reports"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class GenerateIn(BaseModel):
    attempt_id: str = Field(min_length=1, max_length=60)
    attempt_kind: str = Field(default="ASSESSMENT",
                              pattern="^(ASSESSMENT|QUESTIONNAIRE)$")


# ─── Access ────────────────────────────────────────────────────────────────
def _my_trainees(master_id: str) -> set[str]:
    """Trainee ids linked to this Master through their courses."""
    courses, _ = db.select("courses", "id", eq={"trainer_id": master_id},
                           limit=500)
    ids = [c["id"] for c in courses]
    if not ids:
        return set()
    enr, _ = db.select("enrollments", "trainee_id",
                       in_={"course_id": ids}, limit=5000)
    return {e["trainee_id"] for e in enr if e.get("trainee_id")}


def _assert_can_view(report: dict, user: dict):
    if user["role"] == SUPREME:
        return
    if report.get("trainee_id") == user["uid"]:
        return
    if user["role"] == MASTER and report.get("trainee_id") in _my_trainees(user["uid"]):
        return
    raise db.Denied("You cannot view this report.")


def _public(row: dict, user: dict) -> dict:
    trainee = db.first("users", "id, name, designation, department, avatar_url",
                       eq={"id": row.get("trainee_id")}) or {}
    subject = db.first("subjects", "id, code, name",
                       eq={"id": row.get("subject_id")}) if row.get("subject_id") else None
    return {
        **row,
        "trainee_name": trainee.get("name", ""),
        "trainee_designation": trainee.get("designation", ""),
        "trainee_department": trainee.get("department", ""),
        "trainee_avatar": trainee.get("avatar_url", ""),
        "subject_name": (subject or {}).get("name", ""),
        "subject_code": (subject or {}).get("code", ""),
    }


# ─── List / read ───────────────────────────────────────────────────────────
@router.get("")
def list_reports(
    subject_id: str = Query(default="", max_length=60),
    kind: str = Query(default="", max_length=20),
    mine: bool = True,
    trainee_id: str = Query(default="", max_length=60),
    limit: int = Query(default=40, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=5000),
    user=Depends(_auth),
):
    eq: dict = {}
    if user["role"] == ALPHA:
        eq["trainee_id"] = user["uid"]
    elif user["role"] == MASTER:
        allowed = _my_trainees(user["uid"]) | {user["uid"]}
        if trainee_id:
            if trainee_id not in allowed:
                raise db.Denied("That trainee is not on any of your courses.")
            eq["trainee_id"] = trainee_id
        else:
            eq["trainee_id"] = sorted(allowed)   # multi-value via in_ below
    elif trainee_id:
        eq["trainee_id"] = trainee_id

    if subject_id:
        eq["subject_id"] = subject_id
    if kind:
        eq["attempt_kind"] = kind

    # PostgREST eq() takes one value; expand the Master's set with in_().
    multi = eq.pop("trainee_id", None) if isinstance(
        eq.get("trainee_id"), list) else None

    rows, total = db.select(
        "performance_reports", "id, trainee_id, attempt_id, attempt_kind, "
        "subject_id, score, percentage, passed, weak_topics, strong_topics, "
        "ai_generated, generated_at",
        eq=eq or None,
        in_={"trainee_id": multi} if multi else None,
        order=("generated_at", True), limit=limit, count=True)

    # Attach names efficiently (avoids N+1).
    tids = sorted({r["trainee_id"] for r in rows if r.get("trainee_id")})
    names = {}
    if tids:
        tr, _ = db.select("users", "id, name, avatar_url",
                          in_={"id": tids}, limit=500)
        names = {x["id"]: x for x in tr}
    sids = sorted({r["subject_id"] for r in rows if r.get("subject_id")})
    subjects = {}
    if sids:
        sr, _ = db.select("subjects", "id, code, name",
                          in_={"id": sids}, limit=500)
        subjects = {x["id"]: x for x in sr}

    out = []
    for r in rows:
        t = names.get(r.get("trainee_id"), {})
        s = subjects.get(r.get("subject_id"), {})
        out.append({
            **r,
            "trainee_name": t.get("name", ""),
            "trainee_avatar": t.get("avatar_url", ""),
            "subject_name": s.get("name", ""),
            "subject_code": s.get("code", ""),
            "weak_count": len(r.get("weak_topics") or []),
        })
    return db.ok(out, meta={"total": total or len(out)})


@router.get("/{report_id}")
def get_report(report_id: str, user=Depends(_auth)):
    row = db.first("performance_reports", "*", eq={"id": report_id})
    if not row:
        raise db.NotFound("Report not found")
    _assert_can_view(row, user)

    # Resolve the exam/practice it came from for the header.
    source = None
    if row.get("attempt_kind") == "ASSESSMENT":
        src = db.first("assessment_attempts", "id, assessment_id, started_at, "
                       "submitted_at, attempt_no, assessments(title, duration_minutes, "
                       "passing_score, max_score, subject_id)",
                       eq={"id": row.get("attempt_id")})
        if src:
            a = src.get("assessments") or {}
            if isinstance(a, list):
                a = a[0] if a else {}
            source = {"kind": "ASSESSMENT", "title": a.get("title", ""),
                      "attempt_no": src.get("attempt_no"),
                      "started_at": src.get("started_at"),
                      "submitted_at": src.get("submitted_at"),
                      "passing_score": a.get("passing_score"),
                      "max_score": a.get("max_score"),
                      "assessment_id": src.get("assessment_id")}
    else:
        src = db.first("questionnaire_attempts",
                       "id, questionnaire_id, started_at, submitted_at, "
                       "attempt_no, questionnaires(title, deadline_at)",
                       eq={"id": row.get("attempt_id")})
        if src:
            a = src.get("questionnaires") or {}
            if isinstance(a, list):
                a = a[0] if a else {}
            source = {"kind": "QUESTIONNAIRE", "title": a.get("title", ""),
                      "attempt_no": src.get("attempt_no"),
                      "started_at": src.get("started_at"),
                      "submitted_at": src.get("submitted_at"),
                      "deadline_at": a.get("deadline_at"),
                      "questionnaire_id": src.get("questionnaire_id")}

    # Certificate, if this was a pass.
    cert = None
    if row.get("attempt_kind") == "ASSESSMENT":
        cert = db.first("certificates", "id, code, title, status, issued_at",
                        eq={"attempt_id": row.get("attempt_id")})

    out = _public(row, user)
    out["source"] = source
    out["certificate"] = cert
    out["verdict"] = _verdict(row)
    out["next_steps"] = _next_steps(row)
    return db.ok(out)


def _verdict(row: dict) -> str:
    pct = float(row.get("percentage") or 0)
    passed = bool(row.get("passed"))
    if row.get("attempt_kind") == "QUESTIONNAIRE":
        if pct >= 80:
            return "Excellent command of the material."
        if pct >= 60:
            return "Solid practice run — a few gaps left to close."
        return "Worth another attempt after revisiting the weak topics."
    if passed and pct >= 85:
        return "Passed with distinction."
    if passed:
        return "Passed — certificate issued."
    return "Not cleared this time. Focus on the weakest topics below."


def _next_steps(row: dict) -> list[dict]:
    """Deterministic suggestions that work with no AI at all."""
    out = []
    for t in (row.get("weak_topics") or [])[:4]:
        pct = float(t.get("pct") or 0)
        if pct < 50:
            label = f"Rebuild “{t.get('topic','')}” from basics — scored {pct:.0f}%."
        elif pct < 70:
            label = f"Practise more questions on “{t.get('topic','')}” ({pct:.0f}%)."
        else:
            label = f"Keep “{t.get('topic','')}” sharp with a revision pass."
        out.append({"topic": t.get("topic"), "action": label, "priority":
                    "high" if pct < 50 else "medium"})
    if not out:
        out.append({"topic": None,
                    "action": "No weak topic recorded — move to advanced material.",
                    "priority": "low"})
    return out


# ─── Generate / refresh ────────────────────────────────────────────────────
@router.post("/generate")
def generate(payload: GenerateIn, user=Depends(_auth)):
    """Rebuild the deterministic base for an attempt (idempotent).

    Supremes and the owning trainer can trigger it for a trainee; a trainee
    for their own attempt. Used when a report was missing or needs refreshing.
    """
    if payload.attempt_kind == "ASSESSMENT":
        attempt = db.first("assessment_attempts", "*",
                           eq={"id": payload.attempt_id})
        if not attempt:
            raise db.NotFound("Attempt not found")
        if user["role"] == ALPHA and attempt.get("trainee_id") != user["uid"]:
            raise db.Denied("That attempt is not yours.")
        if user["role"] == MASTER and attempt.get("trainee_id") not in \
                _my_trainees(user["uid"]):
            raise db.Denied("That trainee is not on any of your courses.")

        exam = db.first("assessments", "*, trainer_id",
                        eq={"id": attempt.get("assessment_id")})
        if not exam:
            raise db.NotFound("Assessment not found")
        if user["role"] == MASTER and exam.get("trainer_id") != user["uid"] \
                and attempt.get("trainee_id") not in _my_trainees(user["uid"]):
            raise db.Denied("You cannot generate this report.")

        result = _rebuild_from_responses(
            "ASSESSMENT", attempt, exam, float(exam.get("max_score") or 100),
            float(exam.get("passing_score") or 60))
    else:
        attempt = db.first("questionnaire_attempts", "*",
                           eq={"id": payload.attempt_id})
        if not attempt:
            raise db.NotFound("Attempt not found")
        if user["role"] == ALPHA and attempt.get("trainee_id") != user["uid"]:
            raise db.Denied("That attempt is not yours.")
        exam = db.first("questionnaires", "*, trainer_id",
                        eq={"id": attempt.get("questionnaire_id")})
        if not exam:
            raise db.NotFound("Questionnaire not found")
        result = _rebuild_from_responses(
            "QUESTIONNAIRE", attempt, exam,
            float(exam.get("max_score") or attempt.get("max_score") or 0), None)

    db.audit(user["uid"], "report.generate", "performance_report",
             result.get("id"), {"kind": payload.attempt_kind})
    return db.ok(result)


def _rebuild_from_responses(kind: str, attempt: dict, container: dict,
                            declared_max: float, passing: Optional[float]) -> dict:
    """Recompute weak/strong topics from stored per-question responses."""
    responses = quiz.load_responses(kind, attempt)
    if responses:
        # Per-question detail was stored at submit time — reuse it.
        by_topic: dict[str, dict] = {}
        by_diff: dict[str, dict] = {}
        score, max_total = 0.0, 0.0
        for r in responses:
            pts = float(r.get("points") or 1)
            tid = r.get("topic_id") or ""
            key = tid or "__untagged__"
            b = by_topic.setdefault(key, {"topic_id": tid, "correct": 0,
                                          "total": 0, "points": 0.0,
                                          "max_points": 0.0})
            b["total"] += 1
            b["max_points"] += pts
            if r.get("is_correct"):
                b["correct"] += 1
                b["points"] += pts
                score += pts
            max_total += pts
            d = r.get("difficulty") or "medium"
            db2 = by_diff.setdefault(d, {"correct": 0, "total": 0,
                                         "points": 0.0, "max_points": 0.0})
            db2["total"] += 1
            db2["max_points"] += pts
            if r.get("is_correct"):
                db2["correct"] += 1
                db2["points"] += pts
        for bucket in list(by_topic.values()) + list(by_diff.values()):
            bucket["pct"] = round(bucket["points"] / bucket["max_points"] * 100, 1) \
                if bucket["max_points"] else 0.0
        pct = round(score / max_total * 100, 2) if max_total else \
            float(attempt.get("percentage") or 0)
    else:
        graded = quiz.score_responses(kind, container["id"], [])
        by_topic, by_diff = graded["by_topic"], graded["by_difficulty"]
        pct = float(attempt.get("percentage") or 0)
        max_total = graded["max_score"] or 1
        score = float(attempt.get("score") or 0)

    if declared_max and max_total:
        scaled = round(score / max_total * declared_max, 2)
    else:
        scaled = float(attempt.get("score") or 0)

    passed = bool(attempt.get("passed")) if kind == "ASSESSMENT" else None
    if kind == "ASSESSMENT" and passing is not None and declared_max:
        passed = pct >= (passing / declared_max * 100)

    weak, strong = quiz.topics_ranked(by_topic, kind)
    benchmark = _benchmarks(container.get("subject_id"))

    fields = {
        "attempt_id": attempt["id"], "attempt_kind": kind,
        "trainee_id": attempt.get("trainee_id"),
        "subject_id": container.get("subject_id"),
        "score": scaled, "percentage": pct,
        "passed": bool(passed) if passed is not None else False,
        "weak_topics": weak, "strong_topics": strong,
        "difficulty_breakdown": by_diff, "benchmark": benchmark,
        "generated_at": "now()",
    }
    existing = db.first("performance_reports", "id",
                        eq={"attempt_id": attempt["id"], "attempt_kind": kind})
    if existing:
        db.update("performance_reports", fields, id=existing["id"])
        return db.first("performance_reports", "*", eq={"id": existing["id"]})
    row = db.insert("performance_reports", {**fields, "ai_insights": {},
                                            "ai_generated": False})
    return row


def _benchmarks(subject_id: Optional[str]) -> dict:
    if not subject_id:
        return {}
    rows, _ = db.select(
        "subject_benchmarks",
        "industry_standard, expected_proficiency, topic_id, subject_topics(name)",
        eq={"subject_id": subject_id}, limit=300)
    out = []
    for r in rows:
        t = r.get("subject_topics") or {}
        if isinstance(t, list):
            t = t[0] if t else {}
        out.append({"topic": t.get("name", ""),
                    "standard": r.get("industry_standard", ""),
                    "expected": r.get("expected_proficiency", 60)})
    return {"subject_id": subject_id, "topics": out}


# ─── Benchmarks (curated static reference data) ────────────────────────────
class BenchmarkIn(BaseModel):
    topic_id: str = Field(default="", max_length=60)
    industry_standard: str = Field(min_length=3, max_length=800)
    expected_proficiency: int = Field(default=60, ge=0, le=100)
    notes: str = Field(default="", max_length=800)


@router.get("/benchmarks/{subject_id}")
def list_benchmarks(subject_id: str, user=Depends(_auth)):
    rows, _ = db.select(
        "subject_benchmarks",
        "id, topic_id, industry_standard, expected_proficiency, notes, "
        "subject_topics(name)",
        eq={"subject_id": subject_id}, limit=300)
    out = []
    for r in rows:
        t = r.get("subject_topics") or {}
        if isinstance(t, list):
            t = t[0] if t else {}
        out.append({**r, "topic_name": t.get("name", ""),
                    "subject_topics": None})
    return db.ok(out)


@router.put("/benchmarks/{subject_id}")
def upsert_benchmark(subject_id: str, payload: BenchmarkIn,
                     user=Depends(require_role(MASTER, SUPREME))):
    """Curate the industry-standard reference the AI then personalises."""
    if not db.first("subjects", "id", eq={"id": subject_id}):
        raise db.NotFound("Subject not found")
    tid = payload.topic_id or None
    if tid and not db.first("subject_topics", "id",
                            eq={"id": tid, "subject_id": subject_id}):
        raise db.Rejected("That topic does not belong to this subject.")

    existing = db.first("subject_benchmarks", "id",
                        eq={"subject_id": subject_id, "topic_id": tid}) \
        if tid else None
    fields = {
        "industry_standard": payload.industry_standard.strip(),
        "expected_proficiency": payload.expected_proficiency,
        "notes": payload.notes.strip(),
    }
    if existing:
        db.update("subject_benchmarks", fields, id=existing["id"])
        return db.ok({**existing, **fields})
    row = db.insert("subject_benchmarks", {
        "subject_id": subject_id, "topic_id": tid, **fields})
    db.audit(user["uid"], "benchmark.upsert", "subject", subject_id)
    return db.ok(row)


@router.delete("/benchmarks/{benchmark_id}")
def delete_benchmark(benchmark_id: str,
                     user=Depends(require_role(MASTER, SUPREME))):
    db.delete("subject_benchmarks", id=benchmark_id)
    return db.ok({"deleted": True})


# ─── Aggregate analytics ───────────────────────────────────────────────────
@router.get("/stats/weak-topics")
def weak_topics(
    subject_id: str = Query(default="", max_length=60),
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(require_role(MASTER, SUPREME)),
):
    """Platform-wide weak-topic ranking (Supreme) / subject-scoped (Master)."""
    eq = {"attempt_kind": "ASSESSMENT"}
    if subject_id:
        eq["subject_id"] = subject_id
    rows, _ = db.select("performance_reports", "weak_topics, subject_id",
                        eq=eq, limit=1000)

    agg: dict[str, dict] = {}
    for r in rows:
        for t in (r.get("weak_topics") or []):
            key = t.get("topic") or "General"
            b = agg.setdefault(key, {"topic": key, "appearances": 0,
                                     "pct_sum": 0.0, "learner_total": 0})
            b["appearances"] += 1
            b["pct_sum"] += float(t.get("pct") or 0)
            b["learner_total"] += int(t.get("total") or 0)

    ranked = []
    for v in agg.values():
        item = dict(v)
        item["avg_pct"] = round(v["pct_sum"] / v["appearances"], 1) \
            if v["appearances"] else 0.0
        ranked.append(item)
    # Lowest average score first — these are the platform's weak points.
    ranked.sort(key=lambda x: (x["avg_pct"], -x["appearances"]))
    return db.ok(ranked[:limit], meta={"subjects_scanned": len(rows)})


@router.get("/stats/summary")
def summary(subject_id: str = Query(default="", max_length=60),
            user=Depends(require_role(MASTER, SUPREME))):
    """Headline numbers for the Supreme dashboard."""
    eq: dict = {}
    if subject_id:
        eq["subject_id"] = subject_id
    rows, total = db.select("performance_reports",
                            "percentage, passed, attempt_kind, ai_generated, "
                            "subject_id",
                            eq=eq or None, limit=2000)
    if not rows:
        return db.ok({"reports": 0, "avg_pct": 0, "pass_rate": 0,
                      "ai_personalised": 0, "subjects": 0})

    assessed = [r for r in rows if r.get("attempt_kind") == "ASSESSMENT"]
    pcts = [float(r.get("percentage") or 0) for r in rows]
    passed = [r for r in assessed if r.get("passed")]
    subjects = {r.get("subject_id") for r in rows if r.get("subject_id")}
    return db.ok({
        "reports": total or len(rows),
        "avg_pct": round(sum(pcts) / len(pcts), 1),
        "assessments": len(assessed),
        "pass_rate": round(len(passed) / len(assessed) * 100, 1)
        if assessed else 0,
        "ai_personalised": sum(1 for r in rows if r.get("ai_generated")),
        "subjects": len(subjects),
    })
