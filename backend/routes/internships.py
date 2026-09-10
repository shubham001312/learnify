"""
Internship lifecycle management.

States: APPLIED → SHORTLISTED → INTERVIEW → SELECTED → ACTIVE → COMPLETED
        Any state can also go to REJECTED or CANCELLED.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from backend.middleware.rbac import (
    _extract_user,
    require_role,
    INDUSTRY,
    INSTITUTION_ADMIN,
)
from backend.database.client import db_available, get_client
from backend.services.cache import (
    get as cache_get,
    set as cache_set,
    invalidate_pattern,
)

router = APIRouter()

VALID_TRANSITIONS = {
    "APPLIED": ["SHORTLISTED", "REJECTED", "CANCELLED"],
    "SHORTLISTED": ["INTERVIEW", "REJECTED", "CANCELLED"],
    "INTERVIEW": ["SELECTED", "REJECTED", "CANCELLED"],
    "SELECTED": ["ACTIVE", "CANCELLED"],
    "ACTIVE": ["COMPLETED", "CANCELLED"],
    "COMPLETED": [],
    "REJECTED": [],
    "CANCELLED": [],
}


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(
    client, table, columns="*", filters=None, order=None, limit=None, offset=None
):
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


def _safe_insert(client, table, data):
    if not client:
        return None
    try:
        result = client.table(table).insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def _safe_update(client, table, data, filters):
    if not client:
        return False
    try:
        q = client.table(table).update(data)
        for col, op, val in filters:
            if op == "eq":
                q = q.eq(col, val)
        q.execute()
        return True
    except Exception:
        return False


def _transition_application(client, application_id, new_status, changed_by, notes=None):
    app_rows = _safe(
        client, "applications", "status", [("id", "eq", application_id)], limit=1
    )
    if not app_rows:
        raise HTTPException(status_code=404, detail="Application not found")

    current = app_rows[0]["status"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400, detail=f"Cannot transition from {current} to {new_status}"
        )

    _safe_update(
        client,
        "applications",
        {"status": new_status, "updated_at": "now()"},
        [("id", "eq", application_id)],
    )

    _safe_insert(
        client,
        "application_events",
        {
            "application_id": application_id,
            "from_status": current,
            "to_status": new_status,
            "changed_by": changed_by,
            "notes": notes,
        },
    )


# ─── Student: Apply ──────────────────────────────────────────
@router.post("/internships/apply/{opp_id}")
async def apply_internship(opp_id: str, user=Depends(_auth)):
    user_id = user["uid"]
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    existing = _safe(
        client,
        "applications",
        "id",
        [("student_id", "eq", user_id), ("opportunity_id", "eq", opp_id)],
        limit=1,
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already applied")

    opp = _safe(
        client,
        "opportunities",
        "status, organization_id",
        [("id", "eq", opp_id)],
        limit=1,
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp[0].get("status") not in ("ACTIVE", "OPEN"):
        raise HTTPException(
            status_code=400, detail="Opportunity not accepting applications"
        )

    result = _safe_insert(
        client,
        "applications",
        {
            "student_id": user_id,
            "opportunity_id": opp_id,
            "status": "APPLIED",
        },
    )

    if result:
        invalidate_pattern(f"opp_applications:{user_id}")
        return {"status": "ok", "application_id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to submit application")


# ─── Student: My applications ────────────────────────────────
@router.get("/internships/my-applications")
async def my_applications(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user=Depends(_auth),
):
    if not db_available():
        return {"items": [], "total": 0}
    client = get_client()
    user_id = user["uid"]

    filters = [("student_id", "eq", user_id)]
    if status:
        filters.append(("status", "eq", status))

    rows = _safe(
        client,
        "applications",
        "id, status, applied_at, updated_at, opportunity_id, match_score",
        filters,
        order=("applied_at", True),
        limit=limit,
        offset=(page - 1) * limit,
    )

    opp_ids = list(
        set(r.get("opportunity_id") for r in rows if r.get("opportunity_id"))
    )
    opp_map = {}
    if opp_ids:
        opps = _safe(
            client,
            "opportunities",
            "id, title, type, organization_id, location",
            [("id", "in_", opp_ids)],
        )
        org_ids = list(
            set(o.get("organization_id") for o in opps if o.get("organization_id"))
        )
        orgs = (
            _safe(
                client, "organizations", "id, name, logo_url", [("id", "in_", org_ids)]
            )
            if org_ids
            else []
        )
        org_map = {o["id"]: o for o in orgs}
        opp_map = {
            o["id"]: {**o, "org": org_map.get(o.get("organization_id"), {})}
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
                "match_score": r.get("match_score"),
                "opportunity_title": opp.get("title", ""),
                "opportunity_type": opp.get("type", ""),
                "organization": opp.get("org", {}).get("name", ""),
                "location": opp.get("location", ""),
            }
        )

    return {"items": items, "total": len(items), "page": page, "limit": limit}


# ─── Industry: Shortlist candidate ───────────────────────────
@router.post("/internships/applications/{app_id}/shortlist")
async def shortlist_candidate(
    app_id: str, notes: str = "", user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    _transition_application(client, app_id, "SHORTLISTED", user["uid"], notes)
    return {"status": "ok"}


# ─── Industry: Schedule interview ────────────────────────────
@router.post("/internships/applications/{app_id}/interview")
async def schedule_interview(
    app_id: str, notes: str = "", user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    _transition_application(client, app_id, "INTERVIEW", user["uid"], notes)
    return {"status": "ok"}


# ─── Industry: Select candidate → creates internship ─────────
@router.post("/internships/applications/{app_id}/select")
async def select_candidate(
    app_id: str, notes: str = "", user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    _transition_application(client, app_id, "SELECTED", user["uid"], notes)

    app_rows = _safe(
        client,
        "applications",
        "student_id, opportunity_id",
        [("id", "eq", app_id)],
        limit=1,
    )
    if app_rows:
        a = app_rows[0]
        opp = _safe(
            client,
            "opportunities",
            "title, organization_id, id",
            [("id", "eq", a.get("opportunity_id"))],
            limit=1,
        )
        if opp:
            _safe_insert(
                client,
                "internships",
                {
                    "application_id": app_id,
                    "student_id": a["student_id"],
                    "organization_id": opp[0].get("organization_id"),
                    "opportunity_id": a.get("opportunity_id"),
                    "title": opp[0].get("title", "Internship"),
                    "status": "ACTIVE",
                },
            )

    return {"status": "ok"}


# ─── Industry: Reject candidate ──────────────────────────────
@router.post("/internships/applications/{app_id}/reject")
async def reject_candidate(
    app_id: str, notes: str = "", user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    _transition_application(client, app_id, "REJECTED", user["uid"], notes)
    return {"status": "ok"}


# ─── Student: My active internships ──────────────────────────
@router.get("/internships/active")
async def my_active_internships(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "internships",
        "id, title, status, start_date, end_date, completion_pct, organization_id, mentor_id",
        [("student_id", "eq", user["uid"]), ("status", "in_", ["ACTIVE", "COMPLETED"])],
        order=("created_at", True),
    )
    org_ids = list(
        set(r.get("organization_id") for r in rows if r.get("organization_id"))
    )
    orgs = (
        _safe(client, "organizations", "id, name, logo_url", [("id", "in_", org_ids)])
        if org_ids
        else []
    )
    org_map = {o["id"]: o for o in orgs}
    for r in rows:
        org = org_map.get(r.get("organization_id"), {})
        r["organization_name"] = org.get("name", "")
        r["logo_url"] = org.get("logo_url")
    return rows


# ─── Get internship detail ───────────────────────────────────
@router.get("/internships/{internship_id}")
async def get_internship(internship_id: str, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    rows = _safe(client, "internships", "*", [("id", "eq", internship_id)], limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Internship not found")
    return rows[0]


# ─── Industry: View applicants for my opportunities ──────────
@router.get("/internships/applicants")
async def list_applicants(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user=Depends(require_role(INDUSTRY)),
):
    if not db_available():
        return {"items": [], "total": 0}
    client = get_client()

    org = _safe(
        client,
        "user_roles",
        "organization_id",
        [("user_id", "eq", user["uid"]), ("role", "eq", "INDUSTRY")],
        limit=1,
    )
    if not org:
        return {"items": [], "total": 0}

    opps = _safe(
        client,
        "opportunities",
        "id",
        [("organization_id", "eq", org[0]["organization_id"])],
    )
    opp_ids = [o["id"] for o in opps]
    if not opp_ids:
        return {"items": [], "total": 0}

    filters = [("opportunity_id", "in_", opp_ids)]
    if status:
        filters.append(("status", "eq", status))

    rows = _safe(
        client,
        "applications",
        "id, student_id, status, applied_at, match_score, opportunity_id",
        filters,
        order=("applied_at", True),
        limit=limit,
        offset=(page - 1) * limit,
    )

    student_ids = list(set(r.get("student_id") for r in rows if r.get("student_id")))
    students = (
        _safe(
            client, "users", "id, name, email, avatar_url", [("id", "in_", student_ids)]
        )
        if student_ids
        else []
    )
    student_map = {s["id"]: s for s in students}

    opp_ids2 = list(
        set(r.get("opportunity_id") for r in rows if r.get("opportunity_id"))
    )
    opps2 = (
        _safe(client, "opportunities", "id, title", [("id", "in_", opp_ids2)])
        if opp_ids2
        else []
    )
    opp_map = {o["id"]: o["title"] for o in opps2}

    items = []
    for r in rows:
        s = student_map.get(r.get("student_id"), {})
        items.append(
            {
                "id": r["id"],
                "student_id": r.get("student_id"),
                "student_name": s.get("name", ""),
                "student_email": s.get("email", ""),
                "student_avatar": s.get("avatar_url"),
                "status": r.get("status", ""),
                "applied_at": r.get("applied_at"),
                "match_score": r.get("match_score"),
                "opportunity_title": opp_map.get(r.get("opportunity_id"), ""),
            }
        )

    return {"items": items, "total": len(items), "page": page, "limit": limit}
