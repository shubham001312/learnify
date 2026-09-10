"""
Analytics: institution dashboard, industry insights, policymaker metrics.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, Query
from backend.middleware.rbac import (
    _extract_user,
    require_role,
    INDUSTRY,
    INSTITUTION_ADMIN,
    ACADEMICIAN,
)
from backend.database.client import db_available, get_client

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(client, table, columns="*", filters=None, order=None, limit=None):
    if not client:
        return []
    try:
        q = client.table(table).select(columns)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    except Exception:
        return []


# ─── Institution: My institution analytics ───────────────────
@router.get("/analytics/institution")
async def institution_analytics(user=Depends(require_role(INSTITUTION_ADMIN))):
    if not db_available():
        return _empty_analytics()
    client = get_client()

    org = _safe(
        client,
        "user_roles",
        "organization_id",
        [("user_id", "eq", user["uid"]), ("role", "eq", "INSTITUTION_ADMIN")],
        limit=1,
    )
    if not org:
        return _empty_analytics()
    org_id = org[0]["organization_id"]

    students = _safe(client, "users", "id", [("organization_id", "eq", org_id)])
    total_students = len(students)

    opps = _safe(
        client, "opportunities", "id, type, status", [("organization_id", "eq", org_id)]
    )
    total_opps = len(opps)
    active_opps = sum(1 for o in opps if o.get("status") in ("ACTIVE", "OPEN"))

    student_ids = [s["id"] for s in students]
    if student_ids:
        skills = _safe(
            client,
            "user_skills",
            "skill_id, proficiency",
            [("user_id", "in_", student_ids)],
        )
        assessments = _safe(
            client,
            "assessment_attempts",
            "score, skill_id",
            [("user_id", "in_", student_ids)],
        )
        applications = _safe(
            client, "applications", "status", [("student_id", "in_", student_ids)]
        )
    else:
        skills = []
        assessments = []
        applications = []

    avg_score = 0
    if assessments:
        scores = [a.get("score", 0) for a in assessments if a.get("score") is not None]
        avg_score = round(sum(scores) / max(len(scores), 1), 1)

    placement_rate = 0
    if applications:
        placed = sum(
            1
            for a in applications
            if a.get("status") in ("SELECTED", "COMPLETED", "ACTIVE")
        )
        placement_rate = round(placed / max(len(applications), 1) * 100, 1)

    return {
        "total_students": total_students,
        "total_opportunities": total_opps,
        "active_opportunities": active_opps,
        "total_skills_tracked": len(skills),
        "avg_assessment_score": avg_score,
        "placement_rate": placement_rate,
        "total_applications": len(applications),
    }


# ─── Industry: Hiring analytics ──────────────────────────────
@router.get("/analytics/industry")
async def industry_analytics(user=Depends(require_role(INDUSTRY))):
    if not db_available():
        return _empty_industry()
    client = get_client()

    org = _safe(
        client,
        "user_roles",
        "organization_id",
        [("user_id", "eq", user["uid"]), ("role", "eq", "INDUSTRY")],
        limit=1,
    )
    if not org:
        return _empty_industry()
    org_id = org[0]["organization_id"]

    opps = _safe(
        client, "opportunities", "id, type, status", [("organization_id", "eq", org_id)]
    )
    opp_ids = [o["id"] for o in opps]

    if opp_ids:
        apps = _safe(
            client,
            "applications",
            "status, match_score, applied_at",
            [("opportunity_id", "in_", opp_ids)],
        )
    else:
        apps = []

    total = len(apps)
    shortlisted = sum(
        1
        for a in apps
        if a.get("status")
        in ("SHORTLISTED", "INTERVIEW", "SELECTED", "ACTIVE", "COMPLETED")
    )
    hired = sum(
        1 for a in apps if a.get("status") in ("SELECTED", "ACTIVE", "COMPLETED")
    )
    avg_match = 0
    if apps:
        scores = [
            a.get("match_score", 0) for a in apps if a.get("match_score") is not None
        ]
        avg_match = round(sum(scores) / max(len(scores), 1) * 100, 1)

    return {
        "total_opportunities": len(opps),
        "total_applications": total,
        "shortlisted": shortlisted,
        "hired": hired,
        "avg_match_score": avg_match,
        "conversion_rate": round(hired / max(total, 1) * 100, 1),
    }


# ─── Acadianian: Research analytics ──────────────────────────
@router.get("/analytics/research")
async def research_analytics(user=Depends(require_role(ACADEMICIAN))):
    if not db_available():
        return {}
    client = get_client()
    return {
        "total_projects": 0,
        "active_collaborations": 0,
        "publications_linked": 0,
        "industry_partners": 0,
    }


# ─── Student: My analytics ───────────────────────────────────
@router.get("/analytics/student")
async def student_analytics(user=Depends(_auth)):
    if not db_available():
        return _empty_student()
    client = get_client()
    uid = user["uid"]

    skills = _safe(
        client, "user_skills", "id, skill_id, proficiency", [("user_id", "eq", uid)]
    )
    attempts = _safe(
        client,
        "assessment_attempts",
        "id, score, completed_at",
        [("user_id", "eq", uid)],
    )
    apps = _safe(
        client,
        "applications",
        "id, status, applied_at, match_score",
        [("student_id", "eq", uid)],
    )
    creds = _safe(
        client, "credentials", "id, status, final_score", [("student_id", "eq", uid)]
    )

    avg_score = 0
    if attempts:
        scores = [a.get("score", 0) for a in attempts if a.get("score") is not None]
        avg_score = round(sum(scores) / max(len(scores), 1), 1)

    return {
        "skills_count": len(skills),
        "assessments_taken": len(attempts),
        "avg_score": avg_score,
        "applications": len(apps),
        "placed": sum(
            1 for a in apps if a.get("status") in ("SELECTED", "ACTIVE", "COMPLETED")
        ),
        "credentials": len([c for c in creds if c.get("status") == "ISSUED"]),
    }


# ─── Skill demand analytics (public) ────────────────────────
@router.get("/analytics/skill-demand")
async def skill_demand():
    if not db_available():
        return []
    client = get_client()

    try:
        apps = (
            client.table("applications").select("id, opportunity_id").execute().data
            or []
        )
        opp_ids = list(
            set(a.get("opportunity_id") for a in apps if a.get("opportunity_id"))
        )
        if not opp_ids:
            return []

        opp_skills = (
            client.table("opportunity_skills")
            .select("skill_id, skill_name, weight")
            .in_("opportunity_id", opp_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    skill_counts = {}
    for os in opp_skills:
        sid = os.get("skill_id") or os.get("skill_name", "")
        if sid:
            if sid not in skill_counts:
                skill_counts[sid] = {
                    "skill_id": sid,
                    "skill_name": os.get("skill_name", ""),
                    "count": 0,
                    "total_weight": 0,
                }
            skill_counts[sid]["count"] += 1
            skill_counts[sid]["total_weight"] += os.get("weight", 1)

    ranked = sorted(skill_counts.values(), key=lambda x: x["count"], reverse=True)
    return ranked[:20]


def _empty_analytics():
    return {
        "total_students": 0,
        "total_opportunities": 0,
        "active_opportunities": 0,
        "total_skills_tracked": 0,
        "avg_assessment_score": 0,
        "placement_rate": 0,
        "total_applications": 0,
    }


def _empty_industry():
    return {
        "total_opportunities": 0,
        "total_applications": 0,
        "shortlisted": 0,
        "hired": 0,
        "avg_match_score": 0,
        "conversion_rate": 0,
    }


def _empty_student():
    return {
        "skills_count": 0,
        "assessments_taken": 0,
        "avg_score": 0,
        "applications": 0,
        "placed": 0,
        "credentials": 0,
    }
