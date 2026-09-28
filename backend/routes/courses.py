"""Courses: the 5-step resumable Master wizard + slot/curriculum management.

Step flow (persisted on `courses.draft_step`, so a wizard is resumable):
    1 BASICS      title, code, subject, level, description, cover
    2 CURRICULUM  modules (sections) and slots (lessons) within them
    3 CONTENT     per-slot video (upload|YouTube), body text, attachments
    4 TESTS       link a questionnaire/assessment to a slot
    5 REVIEW      summary → submit for SUPREME release  (status PENDING_RELEASE)

Status flow:  DRAFT → IN_PROGRESS → PENDING_RELEASE → PUBLISHED → ARCHIVED
Only SUPREME can move PENDING_RELEASE → PUBLISHED (and archive). A Master can
always return a course to DRAFT while it is not yet PUBLISHED.
"""

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/courses", tags=["courses"])

MAX_MB = 100                      # per-file video cap (Supabase free tier)
ALLOWED_VIDEO = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,20})"
)


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _slug(prefix: str = "CRS") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


# ─── Models ────────────────────────────────────────────────────────────────
class Step1(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    subject_id: str = ""
    level: str = Field(default="Beginner", max_length=40)
    description: str = Field(default="", max_length=4000)
    duration_hours: float = Field(default=0, ge=0, le=1000)
    cover_image_url: str = Field(default="", max_length=600)


class ModuleIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)


class ModuleReorder(BaseModel):
    order: list[str] = Field(default=[], max_length=100)


class SlotIn(BaseModel):
    module_id: str
    title: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="VIDEO", pattern="^(VIDEO|READING|LINK|TEST)$")


class SlotContent(BaseModel):
    title: str = Field(default="", max_length=160)
    kind: str = Field(default="VIDEO", pattern="^(VIDEO|READING|LINK|TEST)$")
    body: str = Field(default="", max_length=20000)
    video_source: str = Field(default="", pattern="^(UPLOAD|YOUTUBE)$")
    youtube_url: str = Field(default="", max_length=400)
    storage_path: str = Field(default="", max_length=600)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class LinkTest(BaseModel):
    linked_test_type: str = Field(default="", pattern="^(QUESTIONNAIRE|ASSESSMENT)$")
    linked_test_id: str = ""


class StatusChange(BaseModel):
    status: str = Field(pattern="^(DRAFT|IN_PROGRESS|PENDING_RELEASE|PUBLISHED|ARCHIVED)$")


# ─── Visibility helpers ────────────────────────────────────────────────────
def _visible_filter(user: dict) -> dict:
    """Which courses this caller may see at list level."""
    if user["role"] == SUPREME:
        return {}
    if user["role"] == MASTER:
        return {"trainer_id": user["uid"]}
    return {"status": "PUBLISHED"}          # ALPHA: only released courses


def _can_view(course: dict, user: dict) -> bool:
    if user["role"] in (SUPREME, MASTER):
        return True
    return course.get("status") == "PUBLISHED"


def _can_edit(course: dict, user: dict) -> bool:
    if user["role"] == SUPREME:
        return True
    return user["role"] == MASTER and course.get("trainer_id") == user["uid"]


def _get(course_id: str, user: dict, *, for_edit: bool = False) -> dict:
    row = db.first("courses", "*", eq={"id": course_id})
    if not row:
        raise db.NotFound("Course not found")
    if for_edit:
        if not _can_edit(row, user):
            raise db.Denied("You do not own this course.")
    elif not _can_view(row, user):
        raise db.NotFound("Course not found")
    return row


def _public(course: dict, user: dict) -> dict:
    trainer = db.first("users", "id, name, designation, avatar_url",
                       eq={"id": course.get("trainer_id")}) or {}
    subject = db.first("subjects", "id, code, name, category",
                       eq={"id": course.get("subject_id")}) if course.get("subject_id") else None
    out = {
        **course,
        "trainer_name": trainer.get("name", ""),
        "trainer_designation": trainer.get("designation", ""),
        "trainer_avatar": trainer.get("avatar_url", ""),
        "subject_name": (subject or {}).get("name", ""),
        "subject_code": (subject or {}).get("code", ""),
        "subject_category": (subject or {}).get("category", ""),
    }
    out["can_edit"] = _can_edit(course, user)
    return out


def _slots_of(course_id: str) -> list[dict]:
    """All slots belonging to a course, via its modules (never unscoped)."""
    mods, _ = db.select("course_modules", "id", eq={"course_id": course_id},
                        limit=100)
    module_ids = [m["id"] for m in mods]
    if not module_ids:
        return []
    rows, _ = db.select(
        "course_slots",
        "id, module_id, body, video_source, storage_path, youtube_id, linked_test_id",
        in_={"module_id": module_ids}, limit=500)
    return rows


def _counts(course_id: str) -> dict:
    mods, mod_total = db.select("course_modules", "id",
                                eq={"course_id": course_id}, count=True)
    slot_rows = _slots_of(course_id)
    return {
        "modules": mod_total,
        "slots": len(slot_rows),
        "with_video": sum(1 for s in slot_rows
                          if s.get("storage_path") or s.get("youtube_id")),
        "with_test": sum(1 for s in slot_rows if s.get("linked_test_id")),
        "with_body": sum(1 for s in slot_rows if (s.get("body") or "").strip()),
    }


# ─── List / detail ─────────────────────────────────────────────────────────
@router.get("")
def list_courses(
    status: str = Query(default="", max_length=30),
    subject_id: str = Query(default="", max_length=60),
    q: str = Query(default="", max_length=80),
    mine: bool = False,
    limit: int = Query(default=60, ge=1, le=200),
    user=Depends(_auth),
):
    eq = _visible_filter(user)
    in_f = None
    if mine:
        if user["role"] == ALPHA:
            # A trainee's "mine" is their enrolments — without this an ALPHA
            # has no way at all to list the courses they are actually on.
            enr, _ = db.select("enrollments", "course_id",
                               eq={"trainee_id": user["uid"]}, limit=1000)
            ids = sorted({e.get("course_id") for e in enr if e.get("course_id")})
            if not ids:
                return db.ok([], meta={"total": 0})
            in_f = {"id": ids}
        else:
            eq["trainer_id"] = user["uid"]
    if status:
        eq["status"] = status
    if subject_id:
        eq["subject_id"] = subject_id

    rows, total = db.select("courses", "*", eq=eq or None, in_=in_f,
                            order=("created_at", True), limit=limit, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows
                if ql in (r.get("title", "") or "").lower()
                or ql in (r.get("description", "") or "").lower()]
    out = [_public(r, user) for r in rows]
    if user["role"] == ALPHA and out:
        # Carry the caller's enrolment onto each row so a course card can show
        # progress without a second round-trip per card.
        enr, _ = db.select("enrollments", "course_id, status, progress_pct",
                           in_={"course_id": [r["id"] for r in out]},
                           limit=1000)
        by_course = {e.get("course_id"): e for e in enr}
        for p, r in zip(out, rows):
            e = by_course.get(r["id"])
            if e:
                p["enrolled"] = True
                p["enrollment_status"] = e.get("status")
                p["progress_pct"] = float(e.get("progress_pct") or 0)
            else:
                p["enrolled"] = False
    elif user["role"] in (MASTER, SUPREME) and out:
        # One batched query for the whole page — a trainer needs to see at a
        # glance which courses have a roster and which are still empty.
        enr, _ = db.select("enrollments", "course_id, status",
                           in_={"course_id": [r["id"] for r in out]},
                           limit=5000)
        per: dict = {}
        for e in enr:
            cid = e.get("course_id")
            bucket = per.setdefault(cid, {"enrolled": 0, "completed": 0})
            bucket["enrolled"] += 1
            if e.get("status") == "COMPLETED":
                bucket["completed"] += 1
        for p in out:
            p.update(per.get(p["id"], {"enrolled": 0, "completed": 0}))
    return db.ok(out, meta={"total": total or len(out)})


@router.get("/{course_id}")
def get_course(course_id: str, user=Depends(_auth)):
    return db.ok(_public(_get(course_id, user), user))


@router.get("/{course_id}/outline")
def course_outline(course_id: str, user=Depends(_auth)):
    """Modules → slots tree (what the player and wizard both render)."""
    course = _get(course_id, user)
    mods, _ = db.select("course_modules", "*", eq={"course_id": course_id},
                        order=("sort_order", False), limit=100)
    slot_rows, _ = db.select("course_slots", "*",
                             in_={"module_id": [m["id"] for m in mods]} if mods
                             else {"module_id": [""]},
                             order=("sort_order", False), limit=500)
    by_mod: dict[str, list] = {}
    for s in slot_rows:
        by_mod.setdefault(s["module_id"], []).append(s)

    can_edit = _can_edit(course, user)
    tree = []
    for m in mods:
        slots = []
        for s in by_mod.get(m["id"], []):
            slots.append({
                "id": s["id"], "title": s["title"], "kind": s["kind"],
                "sort_order": s.get("sort_order", 0),
                "has_video": bool(s.get("storage_path") or s.get("youtube_id")),
                "video_source": s.get("video_source"),
                "duration_seconds": s.get("duration_seconds", 0),
                "linked_test_type": s.get("linked_test_type"),
                "linked_test_id": s.get("linked_test_id"),
                "is_preview": bool(s.get("is_preview")),
            })
        tree.append({"id": m["id"], "title": m["title"],
                     "description": m.get("description", ""),
                     "sort_order": m.get("sort_order", 0), "slots": slots})

    # enrollment + progress summary for the viewer (ALPHA mostly)
    enrollment = None
    progress = None
    if user["role"] == ALPHA:
        enrollment = db.first("enrollments", "*",
                              eq={"course_id": course_id, "trainee_id": user["uid"]})
        slot_ids = [s["id"] for m in tree for s in m["slots"]]
        done, _ = db.select("slot_progress", "slot_id",
                            in_={"slot_id": slot_ids} if slot_ids else {"slot_id": [""]},
                            eq={"trainee_id": user["uid"], "completed": True})
        progress = {"completed_slots": len(done), "total_slots": len(slot_ids)}

    return db.ok({"course": _public(course, user), "modules": tree,
                  "counts": _counts(course_id),
                  "enrollment": enrollment, "progress": progress})


@router.get("/{course_id}/slots/{slot_id}")
def get_slot(course_id: str, slot_id: str, user=Depends(_auth)):
    """Full slot record — the outline only carries a summary per slot.

    The player and the wizard's content step need `body`, `storage_path`,
    `youtube_id` and `youtube_url`, none of which the tree exposes.
    """
    _get(course_id, user)
    slot = db.first("course_slots", "*", eq={"id": slot_id})
    if not slot or not _slot_in_course(slot, course_id):
        raise db.NotFound("Slot not found")
    return db.ok(slot)


# ─── Wizard: create + step updates ─────────────────────────────────────────
@router.post("")
def create_course(payload: Step1, user=Depends(require_role(MASTER, SUPREME))):
    """Step 1 — open a new draft (resumable from here on)."""
    code = _slug()
    row = db.insert("courses", {
        "code": code, "title": payload.title.strip(),
        "subject_id": payload.subject_id or None,
        "level": payload.level, "description": payload.description.strip(),
        "duration_hours": payload.duration_hours,
        "cover_image_url": payload.cover_image_url,
        "trainer_id": user["uid"], "status": "DRAFT", "draft_step": 1,
    })
    db.audit(user["uid"], "course.create", "course", row.get("id"))
    return db.ok(row)


@router.put("/{course_id}/step1")
def update_step1(course_id: str, payload: Step1, user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    if course["status"] not in ("DRAFT", "IN_PROGRESS"):
        raise db.Rejected("Only drafts can be edited. Ask Supreme to re-open it.")
    row = db.update("courses", {
        "title": payload.title.strip(),
        "subject_id": payload.subject_id or None,
        "level": payload.level, "description": payload.description.strip(),
        "duration_hours": payload.duration_hours,
        "cover_image_url": payload.cover_image_url,
        "draft_step": 1, "updated_at": "now()",
    }, id=course_id)
    _promote(course_id, course, 1)
    return db.ok(row[0] if row else None)


@router.post("/{course_id}/modules")
def add_module(course_id: str, payload: ModuleIn, user=Depends(_auth)):
    """Step 2 — add a module (section)."""
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    mods, total = db.select("course_modules", "id",
                            eq={"course_id": course_id}, count=True)
    row = db.insert("course_modules", {
        "course_id": course_id, "title": payload.title.strip(),
        "description": payload.description.strip(), "sort_order": total,
    })
    _promote(course_id, course, 2)
    return db.ok(row)


@router.put("/{course_id}/modules/{module_id}")
def update_module(course_id: str, module_id: str, payload: ModuleIn,
                  user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    if not db.first("course_modules", "id",
                    eq={"id": module_id, "course_id": course_id}):
        raise db.NotFound("Module not found")
    rows = db.update("course_modules",
                     {"title": payload.title.strip(),
                      "description": payload.description.strip()},
                     id=module_id)
    return db.ok(rows[0] if rows else None)


@router.put("/{course_id}/modules-order")
def reorder_modules(course_id: str, payload: ModuleReorder, user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    for i, mid in enumerate(payload.order):
        if db.first("course_modules", "id", eq={"id": mid, "course_id": course_id}):
            db.update("course_modules", {"sort_order": i}, id=mid)
    return db.ok({"order": payload.order})


@router.delete("/{course_id}/modules/{module_id}")
def delete_module(course_id: str, module_id: str, user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    db.delete("course_modules", id=module_id, course_id=course_id)
    return db.ok({"deleted": True})


@router.post("/{course_id}/slots")
def add_slot(course_id: str, payload: SlotIn, user=Depends(_auth)):
    """Step 2/3 — add a lesson slot to a module."""
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    if not db.first("course_modules", "id",
                    eq={"id": payload.module_id, "course_id": course_id}):
        raise db.NotFound("Module not found")
    _, total = db.select("course_slots", "id",
                         eq={"module_id": payload.module_id}, count=True)
    row = db.insert("course_slots", {
        "module_id": payload.module_id, "title": payload.title.strip(),
        "kind": payload.kind, "sort_order": total,
    })
    _promote(course_id, course, 2)
    return db.ok(row)


@router.put("/{course_id}/slots/{slot_id}")
def update_slot(course_id: str, slot_id: str, payload: SlotContent,
                user=Depends(_auth)):
    """Step 3 — attach video / body text to a slot."""
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    slot = db.first("course_slots", "*", eq={"id": slot_id})
    if not slot or not _slot_in_course(slot, course_id):
        raise db.NotFound("Slot not found")

    # NB: course_slots has no updated_at column, so none is written here.
    body: dict = {
        "kind": payload.kind,
        "body": payload.body,
        "duration_seconds": payload.duration_seconds,
    }
    if payload.title.strip():
        body["title"] = payload.title.strip()

    # Video source handling — exactly one of upload / youtube / none.
    if payload.video_source == "YOUTUBE":
        vid = extract_youtube_id(payload.youtube_url)
        if not vid:
            raise db.Rejected(
                "That does not look like a YouTube link. Paste a full "
                "watch/shorts/youtu.be URL.")
        body.update({"video_source": "YOUTUBE", "youtube_id": vid,
                     "youtube_url": payload.youtube_url, "storage_path": None})
    elif payload.video_source == "UPLOAD":
        if not payload.storage_path:
            raise db.Rejected("Upload the video first, then save the slot.")
        body.update({"video_source": "UPLOAD", "storage_path": payload.storage_path,
                     "youtube_id": None, "youtube_url": None})
    elif payload.video_source == "":
        body.update({"video_source": None, "youtube_id": None,
                     "youtube_url": None, "storage_path": None})

    rows = db.update("course_slots", body, id=slot_id)
    _promote(course_id, course, 3)
    return db.ok(rows[0] if rows else None)


@router.delete("/{course_id}/slots/{slot_id}")
def delete_slot(course_id: str, slot_id: str, user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    db.delete("course_slots", id=slot_id)
    return db.ok({"deleted": True})


@router.put("/{course_id}/slots/{slot_id}/link-test")
def link_test(course_id: str, slot_id: str, payload: LinkTest,
              user=Depends(_auth)):
    """Step 4 — attach a questionnaire or assessment to a slot."""
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    if not db.first("course_slots", "id", eq={"id": slot_id}):
        raise db.NotFound("Slot not found")

    if not payload.linked_test_id:
        db.update("course_slots",
                  {"linked_test_type": None, "linked_test_id": None},
                  id=slot_id)
        return db.ok({"linked": False})

    table = ("questionnaires" if payload.linked_test_type == "QUESTIONNAIRE"
             else "assessments")
    test = db.first(table, "id, trainer_id, title",
                    eq={"id": payload.linked_test_id})
    if not test:
        raise db.NotFound("Test not found")
    if user["role"] != SUPREME and test.get("trainer_id") != user["uid"]:
        raise db.Denied("That test belongs to another trainer.")

    db.update("course_slots",
              {"linked_test_type": payload.linked_test_type,
               "linked_test_id": payload.linked_test_id},
              id=slot_id)
    _promote(course_id, course, 4)
    return db.ok({"linked": True, "title": test.get("title", "")})


# ─── Status transitions ────────────────────────────────────────────────────
@router.post("/{course_id}/submit")
def submit_for_release(course_id: str, user=Depends(_auth)):
    """Step 5 — Master hands the course to Supreme for release."""
    course = _get(course_id, user, for_edit=True)
    if course["status"] not in ("DRAFT", "IN_PROGRESS"):
        raise db.Rejected(f"Course is {course['status']}; it cannot be submitted.")
    c = _counts(course_id)
    if c["modules"] == 0 or c["slots"] == 0:
        raise db.Rejected("Add at least one module and one lesson before submitting.")
    if c["with_video"] == 0 and c["with_body"] == 0:
        raise db.Rejected("Add at least one video or reading before submitting.")

    db.update("courses", {"status": "PENDING_RELEASE", "draft_step": 5,
                          "updated_at": "now()"}, id=course_id)
    _notify_supreme(course, "submitted for release")
    db.audit(user["uid"], "course.submit", "course", course_id)
    return db.ok({"status": "PENDING_RELEASE"})


@router.post("/{course_id}/release")
def release_course(course_id: str, user=Depends(require_role(SUPREME))):
    """Supreme publishes — this is the only path to PUBLISHED."""
    course = _get(course_id, user, for_edit=True)
    if course["status"] not in ("PENDING_RELEASE", "IN_PROGRESS", "ARCHIVED"):
        raise db.Rejected(
            f"Cannot release a course in status {course['status']}. "
            "It must be submitted by its trainer first.")
    db.update("courses", {
        "status": "PUBLISHED", "released_by": user["uid"],
        "released_at": "now()", "updated_at": "now()"}, id=course_id)
    db.audit(user["uid"], "course.release", "course", course_id)
    return db.ok({"status": "PUBLISHED"})


@router.post("/{course_id}/reject")
def reject_course(course_id: str, payload: StatusChange, user=Depends(require_role(SUPREME))):
    """Supreme sends it back to the trainer as DRAFT (with a note in feed)."""
    course = _get(course_id, user, for_edit=True)
    if course["status"] != "PENDING_RELEASE":
        raise db.Rejected("Only submitted courses can be sent back.")
    db.update("courses", {"status": "DRAFT", "draft_step": 5,
                          "updated_at": "now()"}, id=course_id)
    db.audit(user["uid"], "course.reject", "course", course_id)
    return db.ok({"status": "DRAFT"})


@router.post("/{course_id}/status")
def set_status(course_id: str, payload: StatusChange,
               user=Depends(require_role(SUPREME))):
    """Supreme: archive / restore / un-publish."""
    course = _get(course_id, user, for_edit=True)
    allowed = {"DRAFT", "IN_PROGRESS", "PENDING_RELEASE", "PUBLISHED", "ARCHIVED"}
    if payload.status not in allowed:
        raise db.Rejected("Unknown status.")
    updates = {"status": payload.status, "updated_at": "now()"}
    if payload.status != "PUBLISHED":
        updates.update({"released_by": None, "released_at": None})
    db.update("courses", updates, id=course_id)
    db.audit(user["uid"], "course.status", "course", course_id,
             {"to": payload.status})
    return db.ok({"status": payload.status})


@router.get("/{course_id}/wizard")
def wizard_state(course_id: str, user=Depends(_auth)):
    """Everything the wizard needs to restore its exact position."""
    course = _get(course_id, user, for_edit=True)
    c = _counts(course_id)
    step = int(course.get("draft_step") or 1)

    # A step only counts as complete when its data actually exists.
    s1 = bool(course.get("title")) and bool(course.get("description") or
                                            course.get("subject_id"))
    s2 = c["modules"] > 0 and c["slots"] > 0
    s3 = c["with_video"] > 0
    s4 = c["with_test"] > 0
    s5 = course.get("status") in ("PENDING_RELEASE", "PUBLISHED")

    # Auto-derive the furthest genuinely-complete step.
    done_through = 1 if s1 else 0
    if s2:
        done_through = 2
    if s3:
        done_through = 3
    if s4:
        done_through = 4
    if s5:
        done_through = 5

    step = max(step, min(done_through, 5)) if done_through else 1
    return db.ok({
        "course": _public(course, user),
        "counts": c,
        "step": max(1, step),
        "max_step": max(1, done_through),
        "complete": {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5},
        "can_submit": s1 and s2 and s3 and course["status"] in ("DRAFT", "IN_PROGRESS"),
    })


@router.post("/{course_id}/step/{n}")
def goto_step(course_id: str, n: int, user=Depends(_auth)):
    """Explicitly park the cursor at a step (so the wizard resumes there)."""
    course = _get(course_id, user, for_edit=True)
    if n < 1 or n > 5:
        raise db.Rejected("Steps run 1–5.")
    db.update("courses", {"draft_step": n}, id=course_id)
    return db.ok({"step": n})


# ─── Enrollment ────────────────────────────────────────────────────────────
@router.post("/{course_id}/enroll")
def enroll(course_id: str, user=Depends(require_role(ALPHA))):
    course = _get(course_id, user)
    if course["status"] != "PUBLISHED":
        raise db.Rejected("This course is not open for enrolment yet.")
    existing = db.first("enrollments", "id, status",
                        eq={"course_id": course_id, "trainee_id": user["uid"]})
    if existing:
        if existing["status"] == "DROPPED":
            db.update("enrollments", {"status": "ENROLLED"}, id=existing["id"])
            return db.ok({"enrolled": True, "rejoined": True})
        return db.ok({"enrolled": True, "already": True})
    row = db.insert("enrollments", {
        "course_id": course_id, "trainee_id": user["uid"], "status": "ENROLLED"})
    db.audit(user["uid"], "course.enroll", "course", course_id)
    return db.ok({"enrolled": True, "id": row.get("id")})


@router.post("/{course_id}/leave")
def leave(course_id: str, user=Depends(require_role(ALPHA))):
    db.update("enrollments", {"status": "DROPPED"},
              course_id=course_id, trainee_id=user["uid"])
    return db.ok({"left": True})


@router.get("/{course_id}/enrollments")
def list_enrollments(course_id: str,
                     limit: int = Query(default=100, ge=1, le=500),
                     user=Depends(require_role(MASTER, SUPREME))):
    """Who is on this course + their progress (for the trainer view)."""
    _get(course_id, user, for_edit=True)
    rows, total = db.select(
        "enrollments",
        "id, trainee_id, status, progress_pct, enrolled_at, completed_at, "
        "users(name, email, avatar_url, department)",
        eq={"course_id": course_id}, order=("enrolled_at", True),
        limit=limit, count=True)
    flat = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        flat.append({
            "id": r["id"], "trainee_id": r["trainee_id"],
            "name": u.get("name", ""), "email": u.get("email", ""),
            "avatar_url": u.get("avatar_url", ""),
            "department": u.get("department", ""),
            "status": r["status"], "progress_pct": r.get("progress_pct", 0),
            "enrolled_at": r.get("enrolled_at"),
            "completed_at": r.get("completed_at"),
        })
    return db.ok(flat, meta={"total": total or len(flat)})


# ─── Attachments (per-slot files) ──────────────────────────────────────────
class AttachmentIn(BaseModel):
    storage_path: str = Field(max_length=600)
    filename: str = Field(min_length=1, max_length=260)
    mime: str = Field(default="", max_length=140)
    size_bytes: int = Field(default=0, ge=0, le=52_428_800)
    library_item_id: str = Field(default="", max_length=60)


@router.post("/{course_id}/slots/{slot_id}/attachments")
def add_attachment(course_id: str, slot_id: str, payload: AttachmentIn,
                   user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    if not db.first("course_slots", "id", eq={"id": slot_id}):
        raise db.NotFound("Slot not found")
    row = db.insert("slot_attachments", {
        "slot_id": slot_id, "storage_path": payload.storage_path,
        "filename": payload.filename, "mime": payload.mime,
        "size_bytes": payload.size_bytes,
        "library_item_id": payload.library_item_id or None,
    })
    return db.ok(row)


@router.get("/{course_id}/slots/{slot_id}/attachments")
def list_attachments(course_id: str, slot_id: str, user=Depends(_auth)):
    _get(course_id, user)
    if not db.first("course_slots", "id", eq={"id": slot_id}):
        raise db.NotFound("Slot not found")
    rows, _ = db.select("slot_attachments", "*",
                        eq={"slot_id": slot_id}, order=("created_at", False))
    return db.ok(rows)


@router.delete("/{course_id}/attachments/{attachment_id}")
def delete_attachment(course_id: str, attachment_id: str, user=Depends(_auth)):
    course = _get(course_id, user, for_edit=True)
    _assert_editable(course)
    db.delete("slot_attachments", id=attachment_id)
    return db.ok({"deleted": True})


# ─── Shared utilities ──────────────────────────────────────────────────────
def _assert_editable(course: dict):
    if course["status"] not in ("DRAFT", "IN_PROGRESS"):
        raise db.Rejected(
            f"Course is {course['status']} — only Supreme can change it now.")


def _promote(course_id: str, course: dict, step: int):
    """Move DRAFT → IN_PROGRESS once real content exists (keeps it resumable)."""
    if course.get("status") == "DRAFT":
        db.update("courses", {"status": "IN_PROGRESS", "draft_step": step,
                              "updated_at": "now()"}, id=course_id)
    else:
        db.update("courses", {"draft_step": max(int(course.get("draft_step") or 1), step),
                              "updated_at": "now()"}, id=course_id)


def _slot_in_course(slot: dict, course_id: str) -> bool:
    mod = db.first("course_modules", "course_id", eq={"id": slot.get("module_id")})
    return bool(mod and mod.get("course_id") == course_id)


def extract_youtube_id(url: str) -> str:
    if not url:
        return ""
    m = YOUTUBE_RE.search(url.strip())
    return m.group(1) if m else ""


def _notify_supreme(course: dict, reason: str):
    """Tell every Supreme that something is waiting on them."""
    from backend.routes.notifications import notify_many
    sup, _ = db.select("users", "id", eq={"role": SUPREME, "status": "ACTIVE"},
                       limit=50)
    notify_many(db.client_or_none(), [s["id"] for s in sup],
                ntype="RELEASE", title="Course awaiting release",
                message=f"“{course.get('title','')}” {reason}.",
                link=f"/courses/{course.get('id')}",
                metadata={"course_id": course.get("id")})
