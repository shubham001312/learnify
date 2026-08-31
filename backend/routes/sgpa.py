from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from pydantic import BaseModel

from backend.database.client import db_available, get_client
from backend.routes.auth import _current_app_user, _require_client, local_auth

router = APIRouter()


class SgpaReq(BaseModel):
    semester: str
    sgpa: float


@router.get("")
def list_sgpa(authorization: Optional[str] = Header(None)):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if db_available():
        client = _require_client()
        try:
            res = (
                client.table("sgpa_entries")
                .select("*")
                .eq("user_id", cu["uid"])
                .execute()
            )
            return {"entries": res.data or []}
        except Exception as e:
            raise HTTPException(
                status_code=401, detail="Could not load SGPA: " + str(e)
            )
    return {"entries": local_auth.list_sgpa(cu["email"])}


@router.post("")
def add_sgpa(req: SgpaReq, authorization: Optional[str] = Header(None)):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if db_available():
        client = _require_client()
        try:
            res = (
                client.table("sgpa_entries")
                .insert(
                    {"user_id": cu["uid"], "semester": req.semester, "sgpa": req.sgpa}
                )
                .execute()
            )
            return {"entry": (res.data or [{}])[0]}
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Could not save SGPA: " + str(e)
            )
    entry = local_auth.add_sgpa(cu["email"], req.semester, req.sgpa)
    return {"entry": entry}
