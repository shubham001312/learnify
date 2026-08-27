from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database.client import db_available, get_client
from backend.database.local_db import (
    db_available as local_db_available,
    query_colleges as local_query_colleges,
    get_college as local_get_college,
    list_states as local_list_states,
    get_reviews as local_get_reviews,
    add_review as local_add_review,
)
from backend.database import supabase_db
from pydantic import BaseModel
from backend.database.seed import SEED_COLLEGES, SEED_SCHOLARSHIPS

router = APIRouter()


def _colleges_source():
    """Return 'supabase' | 'local' | 'seed' in order of preference."""
    if db_available():
        return "supabase"
    if local_db_available():
        return "local"
    return "seed"


def _as_str(v) -> str:
    return v if isinstance(v, str) else ""


@router.get("/colleges")
def list_colleges(
    type: Optional[str] = None,
    state: Optional[str] = None,
    q: Optional[str] = None,
    stream: Optional[str] = None,
    top: bool = False,
    min_rank: Optional[int] = None,
    min_package: Optional[float] = None,
    sort: str = "default",
    limit: int = 60,
    offset: int = 0,
):
    try:
        if db_available():
            rows, total = supabase_db.query_colleges(
                type=type,
                state=state,
                q=q,
                stream=stream,
                top=top,
                min_rank=min_rank,
                min_package=min_package,
                sort=sort,
                limit=limit,
                offset=offset,
            )
            return {"colleges": rows, "total": total, "limit": limit, "offset": offset}
    except Exception:
        pass
    try:
        if local_db_available():
            rows, total = local_query_colleges(
                type=type,
                state=state,
                q=q,
                stream=stream,
                top=top,
                min_rank=min_rank,
                min_package=min_package,
                sort=sort,
                limit=limit,
                offset=offset,
            )
            return {"colleges": rows, "total": total, "limit": limit, "offset": offset}
    except Exception:
        pass

    colleges = SEED_COLLEGES
    if type:
        colleges = [c for c in colleges if c.get("type") == type]
    if state:
        colleges = [c for c in colleges if c.get("state") == state]
    if q:
        ql = q.lower()
        colleges = [c for c in colleges if ql in c.get("name", "").lower()]
    if top:
        colleges = [c for c in colleges if c.get("nirf_rank") is not None]
        colleges.sort(key=lambda c: c.get("nirf_rank") or 9999)
    total = len(colleges)
    page = colleges[offset : offset + limit]
    return {"colleges": page, "total": total, "limit": limit, "offset": offset}


@router.get("/colleges/states")
def states():
    try:
        if db_available():
            return {"states": supabase_db.list_states()}
    except Exception:
        pass
    try:
        if local_db_available():
            return {"states": local_list_states()}
    except Exception:
        pass
    states = sorted({c.get("state") for c in SEED_COLLEGES if c.get("state")})
    return {"states": states}


@router.get("/colleges/{college_id}")
def get_college(college_id: int):
    try:
        if db_available():
            c = supabase_db.get_college(college_id)
            if c:
                return c
    except Exception:
        pass
    try:
        if local_db_available():
            c = local_get_college(college_id)
            if c:
                return c
    except Exception:
        pass
    for c in SEED_COLLEGES:
        if c.get("id") == college_id:
            return c
    raise HTTPException(status_code=404, detail="College not found")


class ReviewIn(BaseModel):
    author: str = "Anonymous"
    rating: float = 0
    text: str = ""
    pros: str = ""
    cons: str = ""


@router.get("/colleges/{college_id}/reviews")
def college_reviews(college_id: int):
    try:
        if db_available():
            return {"reviews": supabase_db.get_reviews(college_id)}
    except Exception:
        pass
    try:
        if local_db_available():
            return {"reviews": local_get_reviews(college_id)}
    except Exception:
        pass
    return {"reviews": []}


@router.post("/colleges/{college_id}/reviews")
def post_college_review(college_id: int, payload: ReviewIn):
    if not (db_available() or local_db_available()):
        raise HTTPException(status_code=400, detail="Reviews storage unavailable")
    author = (payload.author or "Anonymous").strip()[:60] or "Anonymous"
    rating = max(0.0, min(5.0, float(payload.rating or 0)))
    text = (payload.text or "").strip()[:2000]
    pros = (payload.pros or "").strip()[:500]
    cons = (payload.cons or "").strip()[:500]
    if not text and not pros and not cons:
        raise HTTPException(status_code=400, detail="Review cannot be empty")
    try:
        if db_available():
            supabase_db.add_review(college_id, author, rating, text, pros, cons)
            return {"ok": True}
    except Exception:
        pass
    if local_db_available():
        local_add_review(college_id, author, rating, text, pros, cons)
    return {"ok": True}


@router.get("/scholarships")
def list_scholarships(
    category: Optional[str] = None,
    state: Optional[str] = None,
    q: Optional[str] = None,
):
    if db_available():
        try:
            data = supabase_db.list_scholarships(category=category, state=state, q=q)
        except Exception:
            data = None
    else:
        data = None

    if not data:
        data = SEED_SCHOLARSHIPS
        if category:
            data = [
                s
                for s in data
                if _as_str(s.get("category")).lower() == category.lower()
            ]
        if state:
            data = [s for s in data if _as_str(s.get("state")).lower() == state.lower()]
        if q:
            qq = q.lower()
            data = [
                s
                for s in data
                if (
                    _as_str(s.get("name"))
                    + " "
                    + _as_str(s.get("eligibility"))
                    + " "
                    + _as_str(s.get("state"))
                )
                .lower()
                .find(qq)
                != -1
            ]
    return {"scholarships": data}
