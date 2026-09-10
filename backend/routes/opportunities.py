"""
Opportunities routes: listing, matching, applying.

Uses Supabase client (same pattern as existing routes).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.middleware.rbac import _extract_user
from backend.database.client import db_available, get_client
from backend.services.skill_matching import (
    match_student_opportunity,
    rank_opportunities,
)
from backend.services.cache import (
    get as cache_get,
    set as cache_set,
    invalidate_pattern,
)

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(
    client, table, columns="*", filters=None, order=None, limit=None, offset=None
):
    """Safe Supabase select that returns [] on error."""
    if not client:
        return []
    try:
        q = client.table(table).select(columns)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "like":
                    q = q.like(col, val)
                elif op == "gte":
                    q = q.gte(col, val)
                elif op == "lte":
                    q = q.lte(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if offset is not None and limit:
            q = q.range(offset, offset + limit - 1)
        elif limit:
            q = q.limit(limit)
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def _safe_count(client, table, filters=None):
    if not client:
        return 0
    try:
        q = client.table(table).select("id", count="exact")
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "like":
                    q = q.like(col, val)
        result = q.execute()
        return result.count or 0
    except Exception:
        return 0


def _safe_insert(client, table, data):
    if not client:
        return None
    try:
        result = client.table(table).insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


@router.get("/opportunities")
async def list_opportunities(
    q: str = Query(None),
    location: str = Query(None),
    opp_type: str = Query(None),
    remote: bool = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    if not db_available():
        return {"items": [], "total": 0, "page": page, "limit": limit, "pages": 0}

    client = get_client()

    filters = [("status", "eq", "OPEN")]
    if q:
        filters.append(("title", "like", f"%{q}%"))
    if location:
        filters.append(("location", "like", f"%{location}%"))
    if opp_type:
        filters.append(("type", "eq", opp_type))
    if remote is not None:
        filters.append(("remote_allowed", "eq", remote))

    total = _safe_count(client, "opportunities", filters)
    offset = (page - 1) * limit
    rows = _safe(
        client,
        "opportunities",
        "id, title, description, type, location, remote_allowed, stipend, duration_weeks, deadline, created_at, organization_id",
        filters,
        order=("created_at", True),
        limit=limit,
        offset=offset,
    )

    skills_map = {}
    opp_ids = [r["id"] for r in rows]
    if opp_ids:
        skill_rows = _safe(
            client,
            "opportunity_skills",
            "opportunity_id, skill_id",
            [("opportunity_id", "in_", opp_ids)],
        )
        skill_ids = list(set(r["skill_id"] for r in skill_rows))
        skill_names = (
            _safe(client, "skills", "id, name, category_id", [("id", "in_", skill_ids)])
            if skill_ids
            else []
        )
        name_map = {s["id"]: s for s in skill_names}
        for sr in skill_rows:
            sid = sr["opportunity_id"]
            if sid not in skills_map:
                skills_map[sid] = []
            s = name_map.get(sr["skill_id"], {})
            skills_map[sid].append(
                {"name": s.get("name", ""), "category_id": s.get("category_id")}
            )

    org_ids = list(
        set(r.get("organization_id") for r in rows if r.get("organization_id"))
    )
    org_map = {}
    if org_ids:
        orgs = _safe(
            client, "organizations", "id, name, logo_url", [("id", "in_", org_ids)]
        )
        org_map = {o["id"]: o for o in orgs}

    items = []
    for r in rows:
        org = org_map.get(r.get("organization_id"), {})
        items.append(
            {
                "id": r["id"],
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "type": r.get("type", ""),
                "location": r.get("location", ""),
                "remote_allowed": r.get("remote_allowed", False),
                "stipend": r.get("stipend"),
                "duration_weeks": r.get("duration_weeks"),
                "deadline": r.get("deadline"),
                "created_at": r.get("created_at"),
                "organization_name": org.get("name", ""),
                "logo_url": org.get("logo_url"),
                "required_skills": skills_map.get(r["id"], []),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }


@router.get("/opportunities/{opp_id}")
async def get_opportunity(opp_id: int):
    if not db_available():
        raise HTTPException(status_code=404, detail="Opportunity not found")

    client = get_client()
    rows = _safe(
        client,
        "opportunities",
        "id, title, description, type, location, remote_allowed, stipend, duration_weeks, deadline, created_at, organization_id",
        [("id", "eq", opp_id)],
        limit=1,
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    r = rows[0]

    skills = _safe(
        client,
        "opportunity_skills",
        "skill_id, importance_weight",
        [("opportunity_id", "eq", opp_id)],
    )
    skill_ids = [s["skill_id"] for s in skills]
    skill_names = (
        _safe(client, "skills", "id, name, category_id", [("id", "in_", skill_ids)])
        if skill_ids
        else []
    )
    name_map = {s["id"]: s for s in skill_names}

    org = _safe(
        client,
        "organizations",
        "name, logo_url",
        [("id", "eq", r.get("organization_id"))],
        limit=1,
    )

    return {
        "id": r["id"],
        "title": r.get("title", ""),
        "description": r.get("description", ""),
        "type": r.get("type", ""),
        "location": r.get("location", ""),
        "remote_allowed": r.get("remote_allowed", False),
        "stipend": r.get("stipend"),
        "duration_weeks": r.get("duration_weeks"),
        "deadline": r.get("deadline"),
        "created_at": r.get("created_at"),
        "organization_name": org[0]["name"] if org else "",
        "logo_url": org[0]["logo_url"] if org else None,
        "required_skills": [
            {
                "name": name_map.get(s["skill_id"], {}).get("name", ""),
                "category_id": name_map.get(s["skill_id"], {}).get("category_id"),
                "importance_weight": s.get("importance_weight", 1.0),
            }
            for s in skills
        ],
    }


@router.get("/opportunities/{opp_id}/match")
async def match_opportunity(opp_id: int, user=Depends(_auth)):
    return match_student_opportunity(user["uid"], opp_id)


@router.get("/me/rankings")
async def my_rankings(limit: int = Query(10, ge=1, le=50), user=Depends(_auth)):
    return rank_opportunities(user["uid"], limit)


@router.post("/opportunities/{opp_id}/apply")
async def apply_opportunity(opp_id: int, user=Depends(_auth)):
    user_id = user["uid"]
    if not db_available():
        raise HTTPException(status_code=503, detail="Database not available")

    client = get_client()

    existing = _safe(
        client,
        "applications",
        "id",
        [("user_id", "eq", user_id), ("opportunity_id", "eq", opp_id)],
        limit=1,
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already applied")

    opp = _safe(client, "opportunities", "status", [("id", "eq", opp_id)], limit=1)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp[0].get("status") != "OPEN":
        raise HTTPException(status_code=400, detail="Opportunity is not open")

    result = _safe_insert(
        client,
        "applications",
        {
            "user_id": user_id,
            "opportunity_id": opp_id,
            "status": "SUBMITTED",
        },
    )

    if result:
        invalidate_pattern(f"opp_applications:{user_id}")
        return {"status": "ok", "message": "Application submitted"}

    raise HTTPException(status_code=500, detail="Failed to submit application")


@router.get("/me/applications")
async def my_applications(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user=Depends(_auth),
):
    if not db_available():
        return {"items": [], "total": 0, "page": page, "limit": limit, "pages": 0}

    client = get_client()
    user_id = user["uid"]

    filters = [("user_id", "eq", user_id)]
    if status:
        filters.append(("status", "eq", status))

    total = _safe_count(client, "applications", filters)
    offset = (page - 1) * limit

    rows = _safe(
        client,
        "applications",
        "id, status, applied_at, updated_at, opportunity_id",
        filters,
        order=("applied_at", True),
        limit=limit,
        offset=offset,
    )

    opp_ids = list(
        set(r.get("opportunity_id") for r in rows if r.get("opportunity_id"))
    )
    opp_map = {}
    if opp_ids:
        opps = _safe(
            client,
            "opportunities",
            "id, title, type, organization_id",
            [("id", "in_", opp_ids)],
        )
        org_ids = list(
            set(o.get("organization_id") for o in opps if o.get("organization_id"))
        )
        orgs = (
            _safe(client, "organizations", "id, name", [("id", "in_", org_ids)])
            if org_ids
            else []
        )
        org_map = {o["id"]: o["name"] for o in orgs}
        opp_map = {
            o["id"]: {**o, "org_name": org_map.get(o.get("organization_id"), "")}
            for o in opps
        }

    items = []
    for r in rows:
        opp = opp_map.get(r.get("opportunity_id"), {})
        items.append(
            {
                "id": r["id"],
                "status": r.get("status", ""),
                "applied_at": r.get("applied_at"),
                "updated_at": r.get("updated_at"),
                "opportunity_title": opp.get("title", ""),
                "opportunity_type": opp.get("type", ""),
                "organization": opp.get("org_name", ""),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }


@router.get("/me/applications/stats")
async def my_application_stats(user=Depends(_auth)):
    if not db_available():
        return {}

    client = get_client()
    user_id = user["uid"]

    rows = _safe(
        client,
        "applications",
        "status",
        [("user_id", "eq", user_id)],
    )
    stats = {}
    for r in rows:
        s = r.get("status", "UNKNOWN")
        stats[s] = stats.get(s, 0) + 1
    return stats
