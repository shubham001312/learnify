"""In-app notifications (bell panel).

Schema (backend/database/schema.sql → notifications):
    id, user_id, type, title, message, link, read, metadata, created_at
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.database.client import db_available, get_client
from backend.middleware.rbac import _extract_user

router = APIRouter()

SELECT_COLS = "id, type, title, message, link, read, metadata, created_at"


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def notify(
    client,
    user_id: str,
    title: str,
    message: str = "",
    ntype: str = "SYSTEM",
    link: str = None,
    metadata: dict = None,
):
    """Insert a notification. Best-effort: never raises into the caller."""
    if not client or not user_id:
        return None
    try:
        row = {
            "user_id": user_id,
            "type": ntype,
            "title": title,
            "message": message,
            "link": link,
            "read": False,
            "metadata": metadata or {},
        }
        res = client.table("notifications").insert(row).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def notify_many(client, user_ids, **kw):
    for uid in user_ids or []:
        notify(client, uid, **kw)


@router.get("/notifications/my")
def my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user=Depends(_auth),
):
    limit = max(1, min(limit, 200))
    if not db_available():
        return {"items": []}
    client = get_client()
    try:
        q = (
            client.table("notifications")
            .select(SELECT_COLS)
            .eq("user_id", user["uid"])
        )
        if unread_only:
            q = q.eq("read", False)
        rows = q.order("created_at", desc=True).limit(limit).execute().data or []
        return {"items": rows}
    except Exception:
        return {"items": []}


@router.get("/notifications/unread-count")
def unread_count(user=Depends(_auth)):
    if not db_available():
        return {"count": 0}
    client = get_client()
    try:
        result = (
            client.table("notifications")
            .select("id", count="exact")
            .eq("user_id", user["uid"])
            .eq("read", False)
            .execute()
        )
        return {"count": result.count or 0}
    except Exception:
        return {"count": 0}


@router.patch("/notifications/{notification_id}/read")
def mark_read(notification_id: str, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    try:
        # Scoped to the caller — a user can never mark someone else's read.
        client.table("notifications").update({"read": True}).eq(
            "id", notification_id
        ).eq("user_id", user["uid"]).execute()
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/notifications/mark-all-read")
def mark_all_read(user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    try:
        client.table("notifications").update({"read": True}).eq(
            "user_id", user["uid"]
        ).eq("read", False).execute()
    except Exception:
        pass
    return {"status": "ok"}
