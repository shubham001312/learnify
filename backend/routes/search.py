from fastapi import APIRouter, Query

from backend.services.search import google_scholarship_search, smart_global_search
from backend.services.ai import chat
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
    """Typo-tolerant, relevance-ranked search across careers, companies and
    colleges. When nothing in the database matches, an AI-generated answer is
    returned so the user never hits a dead end."""
    res = smart_global_search(q, num=num)
    careers = [
        {
            "id": c["id"],
            "title": c["title"],
            "category": c["category"],
            "tagline": c.get("tagline"),
        }
        for c in res["careers"]
    ][:num]
    companies = [
        {
            "id": co["id"],
            "name": co["name"],
            "sector": co["sector"],
            "headquarters": co.get("headquarters"),
        }
        for co in res["companies"]
    ][:num]
    colleges = res["colleges"][:num]

    total = len(careers) + len(companies) + len(colleges)
    ai_answer = None
    if total == 0:
        try:
            ai_answer = chat(
                [
                    {
                        "role": "system",
                        "content": "You are Veda, a concise career guide for Indian students. "
                        "Answer the query in 2-3 short, factual sentences. No markdown headings, no emojis.",
                    },
                    {"role": "user", "content": q},
                ]
            )
        except Exception:
            ai_answer = None

    return {
        "query": q,
        "careers": careers,
        "companies": companies,
        "colleges": colleges,
        "suggestion": res["suggestion"],
        "ai_answer": ai_answer,
    }
