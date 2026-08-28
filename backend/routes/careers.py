from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database.seed_careers import (
    list_careers,
    get_career,
    list_categories,
    list_domains,
    list_streams,
    list_classes,
)
from backend.database.seed_companies import (
    list_companies,
    get_company,
    list_sectors,
)

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("")
def get_careers(
    category: Optional[str] = None,
    cls: Optional[str] = None,
    stream: Optional[str] = None,
    domain: Optional[str] = None,
    q: Optional[str] = None,
):
    """List career paths with optional class / stream / domain / text filters."""
    careers = list_careers(category, cls, stream, domain, q)
    slim = [
        {
            "id": c["id"],
            "title": c["title"],
            "category": c["category"],
            "icon": c["icon"],
            "tagline": c["tagline"],
            "classes": c.get("classes", []),
            "streams": c.get("streams", []),
            "domains": c.get("domains", []),
        }
        for c in careers
    ]
    return {
        "careers": slim,
        "categories": list_categories(),
        "domains": list_domains(),
        "streams": list_streams(),
        "classes": list_classes(),
    }


@router.get("/filters")
def get_filters():
    return {
        "categories": list_categories(),
        "domains": list_domains(),
        "streams": list_streams(),
        "classes": list_classes(),
    }


@router.get("/companies")
def get_companies(
    career: Optional[str] = None,
    q: Optional[str] = None,
    sector: Optional[str] = None,
):
    slim = [
        {
            "id": c["id"],
            "name": c["name"],
            "sector": c["sector"],
            "website": c["website"],
        }
        for c in list_companies(career=career, q=q, sector=sector)
    ]
    return {"companies": slim, "sectors": list_sectors()}


@router.get("/companies/{company_id}")
def get_company_detail(company_id: str):
    co = get_company(company_id)
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")
    related = [
        {"id": c["id"], "title": c["title"], "category": c["category"]}
        for c in list_careers()
        if c["category"] in co.get("careers", [])
    ]
    return {"company": {**co, "related_careers": related}}


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
    companies = [
        {"id": co["id"], "name": co["name"], "sector": co["sector"]}
        for co in list_companies(career=c["category"])
    ]
    return {"career": {**c, "related_careers": related, "companies": companies}}
