from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database.seed_careers import (
    list_careers,
    get_career,
    list_categories,
)

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("")
def get_careers(category: Optional[str] = None):
    """List all career paths (optionally filtered by category)."""
    careers = list_careers(category)
    # Trim heavy fields for the list view to keep payloads small.
    slim = [
        {
            "id": c["id"],
            "title": c["title"],
            "category": c["category"],
            "icon": c["icon"],
            "tagline": c["tagline"],
        }
        for c in careers
    ]
    return {"careers": slim, "categories": list_categories()}


@router.get("/categories")
def get_categories():
    return {"categories": list_categories()}


@router.get("/{career_id}")
def get_career_detail(career_id: str):
    c = get_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")
    # Resolve related careers to slim cards for navigation.
    related = [
        {
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "icon": r["icon"],
        }
        for r in list_careers()
        if r["id"] in c.get("related", [])
    ]
    return {"career": {**c, "related_careers": related}}
