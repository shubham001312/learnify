"""Feedback — star rating + comment, per course AND per content item.

One rating per user per target (upsert), so a trainee can revise their score
rather than stacking duplicates. Masters and Supreme see aggregates; trainees
only ever see their own comment back.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/feedback", tags=["feedback"])

CONTENT_TYPES = ("SLOT", "LIBRARY")


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class CourseFeedbackIn(BaseModel):
    course_id: str = Field(min_length=1, max_length=60)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ContentFeedbackIn(BaseModel):
    content_type: str = Field(pattern="^(SLOT|LIBRARY)$")
    content_id: str = Field(min_length=1, max_length=60)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


# ─── Course feedback ───────────────────────────────────────────────────────
@router.post("/course")
def rate_course(payload: CourseFeedbackIn,
                user=Depends(require_role(ALPHA))):
    """Requires an enrolment — you can only rate what you joined."""
    course = db.first("courses", "id, status, title", eq={"id": payload.course_id})
    if not course:
        raise db.NotFound("Course not found")
    if course.get("status") != "PUBLISHED":
        raise db.Rejected("You can only review published courses.")
    enr = db.first("enrollments", "id",
                   eq={"course_id": payload.course_id, "trainee_id": user["uid"]})
    if not enr:
        raise db.Rejected("Enrol in this course before reviewing it.")

    row = db.upsert("course_feedback", {
        "course_id": payload.course_id, "trainee_id": user["uid"],
        "rating": payload.rating, "comment": payload.comment.strip(),
    }, "course_id,trainee_id")
    db.audit(user["uid"], "feedback.course", "course", payload.course_id,
             {"rating": payload.rating})
    return db.ok(row)


@router.get("/course/{course_id}")
def course_feedback(course_id: str, user=Depends(_auth)):
    db.first("courses", "id", eq={"id": course_id}) or _raise_404()
    rows, _ = db.select("course_feedback", "*",
                        eq={"course_id": course_id},
                        order=("created_at", True), limit=300)
    return db.ok(_summarise(rows, user))


# ─── Content feedback ──────────────────────────────────────────────────────
@router.post("/content")
def rate_content(payload: ContentFeedbackIn,
                 user=Depends(require_role(ALPHA))):
    if payload.content_type not in CONTENT_TYPES:
        raise db.Rejected("Unknown content type.")
    _assert_visible(payload.content_type, payload.content_id, user)

    row = db.upsert("content_feedback", {
        "trainee_id": user["uid"],
        "content_type": payload.content_type,
        "content_id": payload.content_id,
        "rating": payload.rating, "comment": payload.comment.strip(),
    }, "trainee_id,content_type,content_id")
    db.audit(user["uid"], "feedback.content", payload.content_type.lower(),
             payload.content_id, {"rating": payload.rating})
    return db.ok(row)


@router.get("/content/{content_type}/{content_id}")
def content_feedback(content_type: str, content_id: str, user=Depends(_auth)):
    if content_type not in CONTENT_TYPES:
        raise db.Rejected("Unknown content type.")
    rows, _ = db.select("content_feedback", "*",
                        eq={"content_type": content_type, "content_id": content_id},
                        order=("created_at", True), limit=300)
    return db.ok(_summarise(rows, user))


def _assert_visible(content_type: str, content_id: str, user: dict):
    """A trainee may only rate content they can actually reach."""
    if user["role"] in (SUPREME, MASTER):
        return
    if content_type == "LIBRARY":
        item = db.first("library_items", "id", eq={"id": content_id})
        if not item:
            raise db.NotFound("Item not found")
        return
    # SLOT → walk slot → module → course → published + enrolled
    slot = db.first("course_slots", "id, module_id", eq={"id": content_id})
    if not slot:
        raise db.NotFound("Content not found")
    mod = db.first("course_modules", "course_id", eq={"id": slot["module_id"]})
    if not mod:
        raise db.NotFound("Content not found")
    course = db.first("courses", "status", eq={"id": mod["course_id"]})
    if not course or course.get("status") != "PUBLISHED":
        raise db.NotFound("Content not found")
    enr = db.first("enrollments", "id",
                   eq={"course_id": mod["course_id"], "trainee_id": user["uid"]})
    if not enr:
        raise db.Rejected("Enrol in this course before reviewing its content.")


# ─── Aggregates ────────────────────────────────────────────────────────────
def _summarise(rows: list[dict], user: dict) -> dict:
    mine = next((r for r in rows if r.get("trainee_id") == user["uid"]), None)
    ratings = [r["rating"] for r in rows if r.get("rating")]
    dist = {i: 0 for i in range(1, 6)}
    for r in ratings:
        dist[int(r)] = dist.get(int(r), 0) + 1
    return {
        "average": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        "count": len(ratings),
        "distribution": dist,
        "my_rating": (mine or {}).get("rating"),
        "my_comment": (mine or {}).get("comment", ""),
        "comments": [
            {"rating": r.get("rating"), "comment": (r.get("comment") or "")[:500],
             "created_at": r.get("created_at"),
             "mine": r.get("trainee_id") == user["uid"]}
            for r in rows if (r.get("comment") or "").strip()
        ][:30],
    }


@router.get("/my")
def my_feedback(limit: int = Query(default=60, ge=1, le=200),
                user=Depends(require_role(ALPHA))):
    """Everything this trainee has rated — powers their profile history."""
    courses, _ = db.select("course_feedback",
                           "id, course_id, rating, comment, created_at, courses(title)",
                           eq={"trainee_id": user["uid"]},
                           order=("created_at", True), limit=limit)
    contents, _ = db.select("content_feedback",
                            "id, content_type, content_id, rating, comment, created_at",
                            eq={"trainee_id": user["uid"]},
                            order=("created_at", True), limit=limit)

    out_courses = []
    for r in courses:
        t = r.get("courses") or {}
        if isinstance(t, list):
            t = t[0] if t else {}
        out_courses.append({
            "id": r["id"], "kind": "COURSE", "target_id": r["course_id"],
            "title": t.get("title", ""), "rating": r.get("rating"),
            "comment": r.get("comment", ""), "created_at": r.get("created_at"),
        })

    out_contents = []
    for r in contents:
        out_contents.append({
            "id": r["id"], "kind": r.get("content_type"),
            "target_id": r.get("content_id"),
            "title": _content_title(r.get("content_type"), r.get("content_id")),
            "rating": r.get("rating"), "comment": r.get("comment", ""),
            "created_at": r.get("created_at"),
        })

    merged = sorted(out_courses + out_contents,
                    key=lambda x: x.get("created_at") or "", reverse=True)
    return db.ok(merged[:limit])


def _content_title(content_type: Optional[str], content_id: Optional[str]) -> str:
    if not content_id:
        return ""
    if content_type == "SLOT":
        r = db.first("course_slots", "title", eq={"id": content_id})
        return (r or {}).get("title", "")
    if content_type == "LIBRARY":
        r = db.first("library_items", "title", eq={"id": content_id})
        return (r or {}).get("title", "")
    return ""


@router.get("/course/{course_id}/mine")
def my_course_feedback(course_id: str, user=Depends(_auth)):
    row = db.first("course_feedback", "*",
                   eq={"course_id": course_id, "trainee_id": user["uid"]})
    return db.ok(row)


def _raise_404():
    raise db.NotFound("Not found")
