"""
Student portfolio: skill evidence, projects, work samples.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from backend.middleware.rbac import _extract_user
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


# ─── Get my portfolio ────────────────────────────────────────
@router.get("/portfolio/my")
async def my_portfolio(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "portfolio_items",
        "id, title, description, category, file_url, thumbnail_url, skills_used, internship_id, visibility, created_at",
        [("student_id", "eq", user["uid"])],
        order=("created_at", True),
    )
    return rows


# ─── Add portfolio item ──────────────────────────────────────
@router.post("/portfolio/add")
async def add_portfolio_item(data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    result = _safe_insert(
        client,
        "portfolio_items",
        {
            "student_id": user["uid"],
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "category": data.get("category", "PROJECT"),
            "file_url": data.get("file_url"),
            "thumbnail_url": data.get("thumbnail_url"),
            "skills_used": data.get("skills_used", []),
            "internship_id": data.get("internship_id"),
            "visibility": data.get("visibility", "PUBLIC"),
        },
    )
    if result:
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to add portfolio item")


# ─── Update portfolio item ───────────────────────────────────
@router.patch("/portfolio/{item_id}")
async def update_portfolio_item(item_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    allowed = {
        "title",
        "description",
        "category",
        "file_url",
        "thumbnail_url",
        "skills_used",
        "visibility",
    }
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if updates:
        _safe_update(
            client,
            "portfolio_items",
            updates,
            [("id", "eq", item_id), ("student_id", "eq", user["uid"])],
        )
    return {"status": "ok"}


# ─── Delete portfolio item ───────────────────────────────────
@router.delete("/portfolio/{item_id}")
async def delete_portfolio_item(item_id: str, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    try:
        client.table("portfolio_items").delete().eq("id", item_id).eq(
            "student_id", user["uid"]
        ).execute()
    except Exception:
        pass
    return {"status": "ok"}


# ─── View someone's public portfolio ─────────────────────────
@router.get("/portfolio/{student_id}")
async def view_portfolio(student_id: str):
    if not db_available():
        return []
    client = get_client()
    return _safe(
        client,
        "portfolio_items",
        "id, title, description, category, file_url, thumbnail_url, skills_used, created_at",
        [("student_id", "eq", student_id), ("visibility", "eq", "PUBLIC")],
        order=("created_at", True),
    )
