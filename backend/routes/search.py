from fastapi import APIRouter, Query

from backend.services.search import google_scholarship_search

router = APIRouter()


@router.get("/search")
def search(q: str = Query(..., min_length=2), num: int = 10):
    results, meta = google_scholarship_search(q, num=num)
    return {"query": q, "results": results, "meta": meta}
