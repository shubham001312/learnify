from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.database.client import db_available, get_client
from backend.routes.auth import resolve_uid

router = APIRouter()


class ScannedIn(BaseModel):
    data_type: str = "note"
    title: str = ""
    content: str = ""
    source: str = ""
    meta: dict = {}


class ScannedOut(BaseModel):
    id: str
    user_id: str
    data_type: str
    title: str
    content: str
    source: str
    created_at: str


@router.get("/scanned")
def list_scanned(
    authorization: Optional[str] = Header(None), limit: int = 100, offset: int = 0
):
    uid = resolve_uid(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if db_available():
        client = get_client()
        res = (
            client.table("scanned_data")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
            .execute()
        )
        rows = res.data or []
        return {"items": rows, "user_id": uid}

    # Local fallback
    try:
        from backend.database import local_db

        rows = local_db.list_scanned(uid, limit, offset)
    except Exception:
        rows = []
    return {"items": rows, "user_id": uid}


@router.post("/scanned", response_model=dict)
def add_scanned(payload: ScannedIn, authorization: Optional[str] = Header(None)):
    uid = resolve_uid(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    record = {
        "user_id": uid,
        "data_type": payload.data_type,
        "title": payload.title,
        "content": payload.content,
        "source": payload.source,
        "meta": payload.meta,
    }

    if db_available():
        client = get_client()
        res = client.table("scanned_data").insert(record).execute()
        rows = res.data or []
        return {"item": rows[0] if rows else record}

    # Local fallback
    try:
        from backend.database import local_db

        item = local_db.add_scanned(record)
        return {"item": item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scanned/{item_id}")
def delete_scanned(item_id: str, authorization: Optional[str] = Header(None)):
    uid = resolve_uid(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if db_available():
        client = get_client()
        client.table("scanned_data").delete().eq("id", item_id).eq(
            "user_id", uid
        ).execute()
        return {"ok": True}

    try:
        from backend.database import local_db

        local_db.delete_scanned(uid, item_id)
    except Exception:
        pass
    return {"ok": True}
