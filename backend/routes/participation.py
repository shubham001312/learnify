"""Participation tracking: video progress + slot completion.

Rules
  * Watch progress is checkpointed so a refresh resumes exactly where it was.
  * A slot is complete at >= 90% watched (readings at 90% scrolled/rendered).
  * A course completes when every slot is complete → enrollment COMPLETED.
  * All writes are idempotent and scoped to the caller — a trainee can never
    post progress against someone else's id.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/participation", tags=["participation"])

COMPLETE_AT = 90          # percent watched
HEARTBEAT_MIN = 5         # seconds between meaningful checkpoints
MAX_WATCH_PER_BEAT = 120  # guard against absurd deltas / clock skew


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class ProgressIn(BaseModel):
    slot_id: str = Field(min_length=1, max_length=60)
    position_seconds: int = Field(ge=0, le=86400)
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    watched_delta: int = Field(default=0, ge=0, le=3600)


class CompleteIn(BaseModel):
    slot_id: str = Field(min_length=1, max_length=60)


# ─── Helpers ───────────────────────────────────────────────────────────────
def _slot_context(slot_id: str):
    """slot → module → course, plus the course status. None when missing."""
    slot = db.first("course_slots", "*", eq={"id": slot_id})
    if not slot:
        raise db.NotFound("Lesson not found")
    mod = db.first("course_modules", "id, course_id, title",
                   eq={"id": slot.get("module_id")})
    if not mod:
        raise db.NotFound("Lesson not found")
    course = db.first("courses", "id, title, status, trainer_id",
                      eq={"id": mod.get("course_id")})
    if not course:
        raise db.NotFound("Course not found")
    return slot, mod, course


def _assert_reachable(course: dict, user: dict, *, writing: bool):
    """A trainee may only touch progress on a published, enrolled course."""
    if user["role"] in (SUPREME, MASTER):
        return
    if course.get("status") != "PUBLISHED":
        raise db.NotFound("Course not found")
    enr = db.first("enrollments", "id, status",
                   eq={"course_id": course["id"], "trainee_id": user["uid"]})
    if not enr:
        if writing:
            raise db.Rejected("Enrol in this course before tracking progress.")
        return
    if enr.get("status") == "DROPPED" and writing:
        raise db.Rejected("You left this course — rejoin to continue.")


def _pct(position: int, duration: int) -> float:
    if duration <= 0:
        return 0.0
    return round(min(100.0, max(0.0, position / duration * 100.0)), 2)


# ─── Write ─────────────────────────────────────────────────────────────────
@router.post("/progress")
def save_progress(payload: ProgressIn, user=Depends(require_role(ALPHA))):
    """Heartbeat from the player. Cheap, idempotent, never 500s on bad data."""
    slot, mod, course = _slot_context(payload.slot_id)
    _assert_reachable(course, user, writing=True)

    duration = payload.duration_seconds or int(slot.get("duration_seconds") or 0)
    pct = _pct(payload.position_seconds, duration)
    delta = min(payload.watched_delta, MAX_WATCH_PER_BEAT)

    existing = db.first("slot_progress", "*",
                        eq={"slot_id": payload.slot_id,
                            "trainee_id": user["uid"]})
    completed = bool(existing and existing.get("completed"))
    watch = int(existing.get("watch_seconds") or 0) if existing else 0
    if delta:
        watch += delta
    # Completion is judged on position, not accumulated watch time, so
    # scrubbing forward to 90% still counts as having seen the lesson.
    if not completed and pct >= COMPLETE_AT:
        completed = True

    fields = {
        "slot_id": payload.slot_id, "trainee_id": user["uid"],
        "watch_seconds": watch,
        "progress_pct": max(pct, float(existing.get("progress_pct") or 0)
                            if existing else 0),
        "last_position_seconds": payload.position_seconds,
        "completed": completed,
        "updated_at": "now()",
    }
    if completed and not (existing and existing.get("completed_at")):
        fields["completed_at"] = "now()"
    elif not completed:
        fields["completed_at"] = None

    row = db.upsert("slot_progress", fields, "slot_id,trainee_id")

    if completed and not (existing and existing.get("completed")):
        _log(user["uid"], "slot_complete", payload.slot_id,
             {"course_id": course["id"], "seconds": payload.position_seconds})
        _sync_enrollment(course["id"], user["uid"])
    else:
        _log(user["uid"], "slot_progress", payload.slot_id,
             {"pct": fields["progress_pct"], "course_id": course["id"]})

    return db.ok({
        "progress_pct": fields["progress_pct"],
        "watch_seconds": watch,
        "completed": completed,
        "completed_at": fields.get("completed_at"),
        "course_complete": _course_complete(course["id"], user["uid"]),
    })


@router.post("/complete")
def complete_slot(payload: CompleteIn, user=Depends(require_role(ALPHA))):
    """Explicit 'mark as done' — only honoured if the 90% bar was met."""
    slot, mod, course = _slot_context(payload.slot_id)
    _assert_reachable(course, user, writing=True)

    existing = db.first("slot_progress", "*",
                        eq={"slot_id": payload.slot_id,
                            "trainee_id": user["uid"]})
    pct = float(existing.get("progress_pct") or 0) if existing else 0.0
    if pct < COMPLETE_AT:
        raise db.Rejected(
            f"Watch at least {COMPLETE_AT}% of this lesson before marking it "
            f"complete (currently {pct:.0f}%).")

    db.upsert("slot_progress", {
        "slot_id": payload.slot_id, "trainee_id": user["uid"],
        "progress_pct": max(pct, 100.0),
        "completed": True, "completed_at": "now()", "updated_at": "now()",
    }, "slot_id,trainee_id")

    _log(user["uid"], "slot_complete", payload.slot_id,
         {"course_id": course["id"], "manual": True})
    done = _sync_enrollment(course["id"], user["uid"])
    return db.ok({"completed": True, "course_complete": done})


@router.post("/enrollment/{course_id}/sync")
def sync_enrollment(course_id: str, user=Depends(require_role(ALPHA))):
    """Recompute a course's completion from slot progress."""
    db.first("courses", "id", eq={"id": course_id}) or _raise_404()
    return db.ok({"completed": _sync_enrollment(course_id, user["uid"])})


def _raise_404():
    raise db.NotFound("Not found")


# ─── Completion engine ─────────────────────────────────────────────────────
def _course_slots(course_id: str) -> list[dict]:
    mods, _ = db.select("course_modules", "id", eq={"course_id": course_id},
                        limit=100)
    ids = [m["id"] for m in mods]
    if not ids:
        return []
    slots, _ = db.select("course_slots", "id, kind",
                         in_={"module_id": ids}, limit=500)
    return slots


def _course_complete(course_id: str, trainee_id: str) -> bool:
    slots = _course_slots(course_id)
    if not slots:
        return False
    ids = [s["id"] for s in slots]
    done, _ = db.select("slot_progress", "slot_id",
                        in_={"slot_id": ids},
                        eq={"trainee_id": trainee_id, "completed": True},
                        limit=500)
    return len({d["slot_id"] for d in done}) >= len(ids)


def _sync_enrollment(course_id: str, trainee_id: str) -> bool:
    """Update enrollment progress; flip to COMPLETED when every slot is done."""
    enr = db.first("enrollments", "id, status",
                   eq={"course_id": course_id, "trainee_id": trainee_id})
    if not enr:
        return False

    slots = _course_slots(course_id)
    total = len(slots)
    if not total:
        return False
    ids = [s["id"] for s in slots]
    done_rows, _ = db.select("slot_progress", "slot_id",
                             in_={"slot_id": ids},
                             eq={"trainee_id": trainee_id, "completed": True},
                             limit=500)
    done_ids = {d["slot_id"] for d in done_rows}
    pct = round(len(done_ids) / total * 100, 1)
    complete = len(done_ids) >= total

    updates = {"progress_pct": pct}
    if complete and enr.get("status") != "COMPLETED":
        updates.update({"status": "COMPLETED", "completed_at": "now()"})
    elif not complete and enr.get("status") in ("ENROLLED", "COMPLETED"):
        updates["status"] = "IN_PROGRESS"
        updates["completed_at"] = None

    db.update("enrollments", updates, id=enr["id"])

    if updates.get("status") == "COMPLETED":
        _announce_completion(course_id, trainee_id, pct)
    return bool(updates.get("status") == "COMPLETED")


def _announce_completion(course_id: str, trainee_id: str, pct: float):
    """Feed achievement + certificate-of-completion style notification."""
    course = db.first("courses", "title", eq={"id": course_id}) or {}
    who = db.first("users", "name", eq={"id": trainee_id}) or {}
    name = who.get("name", "A trainee")
    title = course.get("title", "a course")

    from backend.routes.notifications import notify
    notify(db.client_or_none(), trainee_id, ntype="ACHIEVEMENT",
           title="Course completed",
           message=f"You have completed “{title}”.",
           link=f"/courses/{course_id}",
           metadata={"course_id": course_id})

    try:
        db.insert("home_posts", {
            "type": "ACHIEVEMENT",
            "title": f"{name} completed a course",
            "body": f"Finished “{title}”.",
            "link": f"/courses/{course_id}",
            "target_roles": ["MASTER", "SUPREME", "ALPHA"],
            "published": True, "pinned": False, "published_at": "now()",
        })
    except db.Rejected:
        pass


def _log(user_id: str, action: str, item_id: str, metadata: Optional[dict] = None):
    try:
        db.insert("participation_logs", {
            "user_id": user_id, "item_type": "SLOT", "item_id": item_id,
            "action": action, "metadata": metadata or {},
        })
    except db.Rejected:
        pass


# ─── Read ──────────────────────────────────────────────────────────────────
@router.get("/course/{course_id}")
def course_progress(course_id: str, user=Depends(_auth)):
    """Per-slot state for one course (drives the player's checkmarks)."""
    course = db.first("courses", "*", eq={"id": course_id})
    if not course:
        raise db.NotFound("Course not found")
    if user["role"] == ALPHA:
        _assert_reachable(course, user, writing=False)

    slots = _course_slots(course_id)
    ids = [s["id"] for s in slots]
    if ids:
        rows, _ = db.select(
            "slot_progress",
            "slot_id, progress_pct, watch_seconds, completed, "
            "last_position_seconds, completed_at",
            in_={"slot_id": ids},
            eq={"trainee_id": user["uid"]}, limit=500)
    else:
        rows = []

    by_slot = {r["slot_id"]: r for r in rows}
    total = len(slots)
    done = sum(1 for r in rows if r.get("completed"))

    enr = db.first("enrollments", "*",
                   eq={"course_id": course_id, "trainee_id": user["uid"]}) \
        if user["role"] == ALPHA else None

    return db.ok({
        "slots": {s["id"]: by_slot.get(s["id"], {
            "slot_id": s["id"], "progress_pct": 0, "watch_seconds": 0,
            "completed": False, "last_position_seconds": 0, "completed_at": None,
        }) for s in slots},
        "summary": {
            "total_slots": total, "completed_slots": done,
            "progress_pct": round(done / total * 100, 1) if total else 0,
            "at_or_above_90": done >= total > 0,
        },
        "enrollment": enr,
    })


@router.get("/slot/{slot_id}")
def slot_progress(slot_id: str, user=Depends(_auth)):
    """Resume point for one lesson."""
    slot, mod, course = _slot_context(slot_id)
    if user["role"] == ALPHA:
        _assert_reachable(course, user, writing=False)

    row = db.first("slot_progress", "*",
                   eq={"slot_id": slot_id, "trainee_id": user["uid"]})
    return db.ok({
        "slot_id": slot_id,
        "progress_pct": float((row or {}).get("progress_pct") or 0),
        "watch_seconds": int((row or {}).get("watch_seconds") or 0),
        "completed": bool((row or {}).get("completed")),
        "completed_at": (row or {}).get("completed_at"),
        "last_position_seconds": int((row or {}).get("last_position_seconds") or 0),
        "resume_from": int((row or {}).get("last_position_seconds") or 0),
        "complete_at": COMPLETE_AT,
        "duration_seconds": int(slot.get("duration_seconds") or 0),
    })


@router.get("/my")
def my_activity(
    limit: int = Query(default=60, ge=1, le=200),
    user=Depends(_auth),
):
    """Recent participation log for the caller (dashboard 'continue learning')."""
    target = user["uid"]
    if user["role"] == SUPREME:
        rows, _ = db.select(
            "participation_logs",
            "id, user_id, item_type, item_id, action, created_at, users(name)",
            order=("created_at", True), limit=limit)
    else:
        rows, _ = db.select(
            "participation_logs",
            "id, user_id, item_type, item_id, action, created_at, users(name)",
            eq={"user_id": target}, order=("created_at", True), limit=limit)
    out = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        out.append({**r, "user_name": u.get("name", ""), "users": None})
    return db.ok(out)


@router.get("/stats")
def my_stats(user=Depends(_auth)):
    """Headline learning numbers for the caller's dashboard."""
    uid = user["uid"]
    if user["role"] == ALPHA:
        enr, enr_total = db.select("enrollments", "id, status, progress_pct",
                                   eq={"trainee_id": uid}, count=True, limit=1000)
        done = [e for e in enr if e.get("status") == "COMPLETED"]
        certs, cert_total = db.select("certificates", "id",
                                      eq={"trainee_id": uid, "status": "VALID"},
                                      count=True, limit=1000)
        attempts, att_total = db.select(
            "assessment_attempts", "id, passed, percentage",
            eq={"trainee_id": uid, "status": "SUBMITTED"}, count=True, limit=1000)
        passed = [a for a in attempts if a.get("passed")]
        slots_done, _ = db.select("slot_progress", "id",
                                  eq={"trainee_id": uid, "completed": True},
                                  limit=5000)
        return db.ok({
            "enrolled": enr_total, "completed_courses": len(done),
            "avg_progress": round(sum(float(e.get("progress_pct") or 0)
                                      for e in enr) / len(enr), 1) if enr else 0,
            "certificates": cert_total,
            "lessons_completed": len(slots_done),
            "exams_taken": att_total,
            "exams_passed": len(passed),
            "avg_score": round(sum(float(a.get("percentage") or 0)
                                   for a in attempts) / len(attempts), 1)
            if attempts else 0,
        })

    if user["role"] == MASTER:
        courses, course_total = db.select("courses", "id",
                                          eq={"trainer_id": uid}, count=True)
        ids = [c["id"] for c in courses]
        enr, enr_total = (db.select("enrollments", "id",
                                    in_={"course_id": ids} if ids
                                    else {"course_id": [""]},
                                    count=True, limit=5000)
                          if ids else ([], 0))
        tests, test_total = db.select("questionnaires", "id",
                                      eq={"trainer_id": uid}, count=True)
        exams, exam_total = db.select("assessments", "id",
                                      eq={"trainer_id": uid}, count=True)
        lib, lib_total = db.select("library_items", "id",
                                   eq={"trainer_id": uid}, count=True)
        return db.ok({
            "courses": course_total, "trainees": enr_total,
            "questionnaires": test_total, "assessments": exam_total,
            "library_items": lib_total,
            "pending_release": db.count("courses", trainer_id=uid,
                                        status="PENDING_RELEASE"),
        })

    # SUPREME — quick totals
    return db.ok({
        "users": db.count("users"), "courses": db.count("courses"),
        "assessments": db.count("assessments"),
        "certificates": db.count("certificates", status="VALID"),
    })
