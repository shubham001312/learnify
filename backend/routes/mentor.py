"""
Mentor system: assignment, feedback, dashboard.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from backend.middleware.rbac import _extract_user, require_role, INDUSTRY, ACADEMICIAN
from backend.database.client import db_available, get_client
from backend.services.cache import (
    get as cache_get,
    set as cache_set,
    invalidate_pattern,
)

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(
    client, table, columns="*", filters=None, order=None, limit=None, offset=None
):
    if not client:
        return []
    try:
        q = client.table(table).select(columns)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
                elif op == "like":
                    q = q.like(col, val)
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if offset is not None and limit:
            q = q.range(offset, offset + limit - 1)
        elif limit:
            q = q.limit(limit)
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def _safe_insert(client, table, data):
    if not client:
        return None
    try:
        result = client.table(table).insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


# ─── Assign mentor ───────────────────────────────────────────
@router.post("/internships/{internship_id}/assign-mentor")
async def assign_mentor(
    internship_id: str,
    mentor_id: str,
    mentor_type: str = "INDUSTRY",
    user=Depends(require_role(INDUSTRY, ACADEMICIAN)),
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    intern = _safe(
        client, "internships", "id, mentor_id", [("id", "eq", internship_id)], limit=1
    )
    if not intern:
        raise HTTPException(status_code=404, detail="Internship not found")

    _safe_insert(
        client,
        "mentor_assignments",
        {
            "mentor_id": mentor_id,
            "internship_id": internship_id,
            "mentor_type": mentor_type,
        },
    )

    from backend.services.cache import invalidate_pattern as inv

    client.table("internships").update({"mentor_id": mentor_id}).eq(
        "id", internship_id
    ).execute()

    return {"status": "ok"}


# ─── Mentor: My assigned internships ─────────────────────────
@router.get("/mentor/my-internships")
async def my_mentor_internships(user=Depends(require_role(INDUSTRY, ACADEMICIAN))):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "mentor_assignments",
        "id, internship_id, mentor_type, assigned_at",
        [("mentor_id", "eq", user["uid"])],
    )
    intern_ids = [r["internship_id"] for r in rows]
    if not intern_ids:
        return []

    interns = _safe(
        client,
        "internships",
        "id, title, student_id, status, completion_pct, organization_id",
        [("id", "in_", intern_ids)],
    )
    student_ids = list(set(i.get("student_id") for i in interns if i.get("student_id")))
    students = (
        _safe(
            client, "users", "id, name, email, avatar_url", [("id", "in_", student_ids)]
        )
        if student_ids
        else []
    )
    student_map = {s["id"]: s for s in students}

    for i in interns:
        s = student_map.get(i.get("student_id"), {})
        i["student_name"] = s.get("name", "")
        i["student_email"] = s.get("email", "")
        i["student_avatar"] = s.get("avatar_url")

    return interns


# ─── Mentor: Submit feedback ─────────────────────────────────
@router.post("/mentor/feedback")
async def submit_feedback(
    data: dict, user=Depends(require_role(INDUSTRY, ACADEMICIAN))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    internship_id = data.get("internship_id")
    student_id = data.get("student_id")

    if not internship_id or not student_id:
        raise HTTPException(
            status_code=400, detail="internship_id and student_id required"
        )

    result = _safe_insert(
        client,
        "mentor_feedback",
        {
            "internship_id": internship_id,
            "mentor_id": user["uid"],
            "student_id": student_id,
            "technical_skills": data.get("technical_skills", 0),
            "problem_solving": data.get("problem_solving", 0),
            "communication": data.get("communication", 0),
            "teamwork": data.get("teamwork", 0),
            "professionalism": data.get("professionalism", 0),
            "domain_knowledge": data.get("domain_knowledge", 0),
            "initiative": data.get("initiative", 0),
            "time_management": data.get("time_management", 0),
            "overall_rating": data.get("overall_rating", 0),
            "strengths": data.get("strengths", ""),
            "areas_for_improvement": data.get("areas_for_improvement", ""),
            "recommended_actions": data.get("recommended_actions", ""),
            "comments": data.get("comments", ""),
        },
    )

    if result:
        invalidate_pattern(f"mentor_feedback:{student_id}")
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to submit feedback")


# ─── Student: My feedback ────────────────────────────────────
@router.get("/mentor/my-feedback")
async def my_feedback(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "mentor_feedback",
        "id, internship_id, mentor_id, overall_rating, strengths, areas_for_improvement, comments, created_at",
        [("student_id", "eq", user["uid"])],
        order=("created_at", True),
    )
    mentor_ids = list(set(r.get("mentor_id") for r in rows if r.get("mentor_id")))
    mentors = (
        _safe(client, "users", "id, name, avatar_url", [("id", "in_", mentor_ids)])
        if mentor_ids
        else []
    )
    mentor_map = {m["id"]: m for m in mentors}
    for r in rows:
        m = mentor_map.get(r.get("mentor_id"), {})
        r["mentor_name"] = m.get("name", "")
        r["mentor_avatar"] = m.get("avatar_url")
    return rows


# ─── Mentor: Pending feedback requests ───────────────────────
@router.get("/mentor/pending-feedback")
async def pending_feedback(user=Depends(require_role(INDUSTRY, ACADEMICIAN))):
    if not db_available():
        return []
    client = get_client()
    assigned = _safe(
        client,
        "mentor_assignments",
        "internship_id",
        [("mentor_id", "eq", user["uid"])],
    )
    intern_ids = [a["internship_id"] for a in assigned]
    if not intern_ids:
        return []

    interns = _safe(
        client,
        "internships",
        "id, title, student_id, status",
        [("id", "in_", intern_ids), ("status", "eq", "ACTIVE")],
    )
    existing = _safe(
        client, "mentor_feedback", "internship_id", [("mentor_id", "eq", user["uid"])]
    )
    feedback_set = {e["internship_id"] for e in existing}

    pending = [i for i in interns if i["id"] not in feedback_set]
    student_ids = list(set(i.get("student_id") for i in pending if i.get("student_id")))
    students = (
        _safe(client, "users", "id, name, email", [("id", "in_", student_ids)])
        if student_ids
        else []
    )
    student_map = {s["id"]: s for s in students}
    for i in pending:
        s = student_map.get(i.get("student_id"), {})
        i["student_name"] = s.get("name", "")
        i["student_email"] = s.get("email", "")
    return pending
