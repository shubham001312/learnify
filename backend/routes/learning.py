"""
Learning resources: curated recommendations linked to skills and gaps.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, Query
from backend.middleware.rbac import _extract_user
from backend.database.client import db_available, get_client

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
                elif op == "like":
                    q = q.like(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    except Exception:
        return []


# ─── Browse learning resources ───────────────────────────────
@router.get("/learning-resources")
async def list_resources(
    skill: str = Query(None),
    category: str = Query(None),
    difficulty: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user=Depends(_auth),
):
    if not db_available():
        return {"items": [], "total": 0}
    client = get_client()

    filters = []
    if skill:
        filters.append(("skill_name", "like", f"%{skill}%"))
    if category:
        filters.append(("category", "eq", category))
    if difficulty:
        filters.append(("difficulty", "eq", difficulty))

    try:
        q = client.table("learning_resources").select(
            "id, title, description, url, provider, category, difficulty, duration_minutes, skill_name, rating, enrollment_count"
        )
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "like":
                    q = q.like(col, val)
        q = q.order("rating", desc=True)
        q = q.range((page - 1) * limit, (page - 1) * limit + limit - 1)
        rows = q.execute().data or []
    except Exception:
        rows = []

    return {"items": rows, "total": len(rows), "page": page, "limit": limit}


# ─── Get resources for specific skill ────────────────────────
@router.get("/learning-resources/skill/{skill_name}")
async def resources_for_skill(skill_name: str, limit: int = 10, user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    return _safe(
        client,
        "learning_resources",
        "id, title, description, url, provider, category, difficulty, duration_minutes, rating",
        [("skill_name", "like", f"%{skill_name}%")],
        order=("rating", True),
        limit=limit,
    )


# ─── Get recommended resources based on gaps ─────────────────
@router.get("/learning-resources/recommended")
async def recommended_resources(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    uid = user["uid"]

    try:
        skills = (
            client.table("user_skills")
            .select("skill_id, proficiency")
            .eq("user_id", uid)
            .execute()
            .data
            or []
        )
        weak = [s["skill_id"] for s in skills if (s.get("proficiency") or 0) < 7]
        if not weak:
            weak = [s["skill_id"] for s in skills]

        skill_map_result = (
            client.table("skills").select("id, name").in_("id", weak).execute()
        )
        skill_names = {s["id"]: s["name"] for s in (skill_map_result.data or [])}

        resources = []
        for skill_id, skill_name in skill_names.items():
            res = (
                client.table("learning_resources")
                .select(
                    "id, title, description, url, provider, difficulty, duration_minutes, rating"
                )
                .eq("skill_name", skill_name)
                .order("rating", desc=True)
                .limit(3)
                .execute()
            )
            for r in res.data or []:
                r["recommended_for"] = skill_name
                resources.append(r)

        resources.sort(key=lambda x: x.get("rating", 0), reverse=True)
        return resources[:20]
    except Exception:
        return []


# ─── Learning progress tracking ──────────────────────────────
@router.get("/learning-progress/my")
async def my_learning_progress(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    try:
        rows = (
            client.table("learning_progress")
            .select(
                "id, resource_id, status, progress_pct, started_at, completed_at, notes"
            )
            .eq("user_id", user["uid"])
            .order("started_at", desc=True)
            .execute()
        )
        return rows.data or []
    except Exception:
        return []


@router.post("/learning-progress/{resource_id}/start")
async def start_learning(resource_id: str, user=Depends(_auth)):
    if not db_available():
        return {"status": "ok"}
    client = get_client()
    try:
        existing = (
            client.table("learning_progress")
            .select("id")
            .eq("user_id", user["uid"])
            .eq("resource_id", resource_id)
            .execute()
        )
        if existing.data:
            return {"status": "ok", "id": existing.data[0]["id"]}

        result = (
            client.table("learning_progress")
            .insert(
                {
                    "user_id": user["uid"],
                    "resource_id": resource_id,
                    "status": "IN_PROGRESS",
                    "progress_pct": 0,
                }
            )
            .execute()
        )
        return {"status": "ok", "id": result.data[0]["id"] if result.data else None}
    except Exception:
        return {"status": "ok"}


@router.patch("/learning-progress/{resource_id}/update")
async def update_progress(resource_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        return {"status": "ok"}
    client = get_client()
    try:
        updates = {}
        if "progress_pct" in data:
            updates["progress_pct"] = data["progress_pct"]
        if "status" in data:
            updates["status"] = data["status"]
            if data["status"] == "COMPLETED":
                updates["completed_at"] = "now()"
        if updates:
            client.table("learning_progress").update(updates).eq(
                "user_id", user["uid"]
            ).eq("resource_id", resource_id).execute()
    except Exception:
        pass
    return {"status": "ok"}
