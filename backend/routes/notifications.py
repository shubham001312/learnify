"""
Notifications system.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
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


@router.get("/notifications/my")
async def my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user=Depends(_auth),
):
    if not db_available():
        return []
    client = get_client()
    q = (
        client.table("notifications")
        .select("id, type, title, message, entity_type, entity_id, is_read, created_at")
        .eq("user_id", user["uid"])
    )
    if unread_only:
        q = q.eq("is_read", False)
    q = q.order("created_at", desc=True).limit(limit)
    try:
        return q.execute().data or []
    except Exception:
        return []


@router.get("/notifications/unread-count")
async def unread_count(user=Depends(_auth)):
    if not db_available():
        return {"count": 0}
    client = get_client()
    try:
        result = (
            client.table("notifications")
            .select("id", count="exact")
            .eq("user_id", user["uid"])
            .eq("is_read", False)
            .execute()
        )
        return {"count": result.count or 0}
    except Exception:
        return {"count": 0}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    try:
        client.table("notifications").update({"is_read": True}).eq(
            "id", notification_id
        ).eq("user_id", user["uid"]).execute()
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/notifications/mark-all-read")
async def mark_all_read(user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    try:
        client.table("notifications").update({"is_read": True}).eq(
            "user_id", user["uid"]
        ).eq("is_read", False).execute()
    except Exception:
        pass
    return {"status": "ok"}


async def send_notification(
    client, user_id, ntype, title, message, entity_type=None, entity_id=None
):
    if not client:
        return
    try:
        _safe_insert(
            client,
            "notifications",
            {
                "user_id": user_id,
                "type": ntype,
                "title": title,
                "message": message,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "is_read": False,
            },
        )
    except Exception:
        pass
