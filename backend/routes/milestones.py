"""
Milestones, tasks, and deliverables for internships.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from backend.middleware.rbac import _extract_user, require_role, INDUSTRY
from backend.database.client import db_available, get_client
from backend.services.cache import invalidate_pattern

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(client, table, columns="*", filters=None, order=None, limit=None):
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
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    except Exception:
        return []


def _safe_insert(client, table, data):
    if not client:
        return None
    try:
        r = client.table(table).insert(data).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def _safe_update(client, table, data, filters):
    if not client:
        return False
    try:
        q = client.table(table).update(data)
        for col, op, val in filters:
            if op == "eq":
                q = q.eq(col, val)
        q.execute()
        return True
    except Exception:
        return False


def _recalc_completion(client, internship_id):
    tasks = _safe(
        client, "internship_tasks", "status", [("internship_id", "eq", internship_id)]
    )
    if not tasks:
        return
    done = sum(1 for t in tasks if t.get("status") == "DONE")
    pct = int(done / len(tasks) * 100)
    _safe_update(
        client, "internships", {"completion_pct": pct}, [("id", "eq", internship_id)]
    )


# ─── Get milestones for an internship ────────────────────────
@router.get("/internships/{internship_id}/milestones")
async def get_milestones(internship_id: str, user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "milestones",
        "id, title, description, due_date, status, weight, internship_id",
        [("internship_id", "eq", internship_id)],
        order=("due_date", False),
    )
    return rows


# ─── Create milestone (industry/mentor) ──────────────────────
@router.post("/internships/{internship_id}/milestones")
async def create_milestone(
    internship_id: str, data: dict, user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    result = _safe_insert(
        client,
        "milestones",
        {
            "internship_id": internship_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "due_date": data.get("due_date"),
            "status": "PENDING",
            "weight": data.get("weight", 1),
            "created_by": user["uid"],
        },
    )
    if result:
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to create milestone")


# ─── Update milestone status ─────────────────────────────────
@router.patch("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    allowed = {"status", "title", "description", "due_date"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if updates:
        _safe_update(client, "milestones", updates, [("id", "eq", milestone_id)])
    return {"status": "ok"}


# ─── Get tasks for milestone ─────────────────────────────────
@router.get("/milestones/{milestone_id}/tasks")
async def get_tasks(milestone_id: str, user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    return _safe(
        client,
        "internship_tasks",
        "id, title, description, status, priority, due_date, assigned_to, internship_id, milestone_id",
        [("milestone_id", "eq", milestone_id)],
        order=("due_date", False),
    )


# ─── Create task ─────────────────────────────────────────────
@router.post("/internships/{internship_id}/tasks")
async def create_task(
    internship_id: str, data: dict, user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    result = _safe_insert(
        client,
        "internship_tasks",
        {
            "internship_id": internship_id,
            "milestone_id": data.get("milestone_id"),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "status": "TODO",
            "priority": data.get("priority", "MEDIUM"),
            "due_date": data.get("due_date"),
            "assigned_to": data.get("assigned_to"),
        },
    )
    if result:
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to create task")


# ─── Update task ─────────────────────────────────────────────
@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    allowed = {"status", "title", "description", "priority", "due_date", "assigned_to"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if updates:
        _safe_update(client, "internship_tasks", updates, [("id", "eq", task_id)])
        task = _safe(
            client,
            "internship_tasks",
            "internship_id, status",
            [("id", "eq", task_id)],
            limit=1,
        )
        if task:
            _recalc_completion(client, task[0]["internship_id"])
    return {"status": "ok"}


# ─── Submit deliverable ──────────────────────────────────────
@router.post("/tasks/{task_id}/deliverables")
async def submit_deliverable(task_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    result = _safe_insert(
        client,
        "deliverables",
        {
            "task_id": task_id,
            "internship_id": data.get("internship_id"),
            "student_id": user["uid"],
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "file_url": data.get("file_url"),
            "status": "SUBMITTED",
        },
    )
    if result:
        _safe_update(
            client, "internship_tasks", {"status": "REVIEW"}, [("id", "eq", task_id)]
        )
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to submit deliverable")


# ─── Get deliverables for task ───────────────────────────────
@router.get("/tasks/{task_id}/deliverables")
async def get_deliverables(task_id: str, user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    return _safe(
        client,
        "deliverables",
        "id, title, description, file_url, status, submitted_at, reviewed_at, feedback",
        [("task_id", "eq", task_id)],
        order=("submitted_at", True),
    )
