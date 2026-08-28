from fastapi import APIRouter, Query

from backend.services.search import google_scholarship_search
from backend.database.seed_careers import list_careers
from backend.database.seed_companies import list_companies
from backend.database.client import db_available, get_client
from backend.database import supabase_db, local_db
from backend.database.seed import SEED_COLLEGES

router = APIRouter()


@router.get("/search")
def search(q: str = Query(..., min_length=2), num: int = 10):
    results, meta = google_scholarship_search(q, num=num)
    return {"query": q, "results": results, "meta": meta}


def _search_colleges(q, num):
    ql = q.lower()
    try:
        if db_available():
            res = (
                get_client()
                .table("colleges")
                .select("id,name,city,state,type")
                .ilike("name", f"%{q}%")
                .limit(num)
                .execute()
            )
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "city": r.get("city"),
                    "state": r.get("state"),
                    "type": r.get("type"),
                }
                for r in (res.data or [])
            ]
        if local_db.db_available():
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "city": r.get("city"),
                    "state": r.get("state"),
                    "type": r.get("type"),
                }
                for r in local_db.query_colleges(q=q)[:num]
            ]
    except Exception:
        pass
    return [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "city": r.get("city"),
            "state": r.get("state"),
            "type": r.get("type"),
        }
        for r in SEED_COLLEGES
        if ql in (r.get("name", "") or "").lower()
    ][:num]


@router.get("/search/global")
def global_search(q: str = Query(..., min_length=2), num: int = 8):
    """Search across careers, companies and colleges in one call."""
    careers = [
        {
            "id": c["id"],
            "title": c["title"],
            "category": c["category"],
            "tagline": c["tagline"],
        }
        for c in list_careers(q=q)
    ][:num]
    companies = [
        {"id": co["id"], "name": co["name"], "sector": co["sector"]}
        for co in list_companies(q=q)
    ][:num]
    colleges = _search_colleges(q, num)
    return {
        "query": q,
        "careers": careers,
        "companies": companies,
        "colleges": colleges,
    }
