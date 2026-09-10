"""
Career intelligence routes: gaps, readiness, dashboard.

Uses Supabase client (same pattern as existing routes).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header

from backend.middleware.rbac import _extract_user
from backend.services.gap_analysis import (
    get_gaps,
    get_readiness_score,
    clear_gaps_cache,
)
from backend.services.cache import get as cache_get, set as cache_set

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


@router.get("/me/gaps")
async def my_gaps(user=Depends(_auth)):
    return get_gaps(user["uid"])


@router.get("/me/readiness")
async def my_readiness(user=Depends(_auth)):
    return get_readiness_score(user["uid"])


@router.get("/me/dashboard")
async def my_dashboard(user=Depends(_auth)):
    user_id = user["uid"]
    cached = cache_get(f"learnify:career_dashboard:{user_id}")
    if cached:
        return cached

    from backend.database.client import db_available, get_client

    if not db_available():
        return {"user_id": user_id, "skills": [], "applications": [], "assessments": []}

    client = get_client()

    def _safe(table, cols="*", filters=None, limit=None):
        try:
            q = client.table(table).select(cols)
            if filters:
                for col, op, val in filters:
                    if op == "eq":
                        q = q.eq(col, val)
            if limit:
                q = q.limit(limit)
            result = q.execute()
            return result.data or []
        except Exception:
            return []

    skills = _safe(
        "user_skills",
        "skill_id, level, confidence, last_assessed_at",
        [("user_id", "eq", user_id), ("is_active", "eq", True)],
    )

    skill_ids = [s["skill_id"] for s in skills]
    skill_names = _safe("skills", "id, name, category_id") if skill_ids else []
    name_map = {s["id"]: s for s in skill_names}

    skills_data = []
    for s in skills:
        info = name_map.get(s["skill_id"], {})
        skills_data.append(
            {
                "name": info.get("name", ""),
                "category_id": info.get("category_id"),
                "level": s.get("level", "BEGINNER"),
                "confidence": s.get("confidence", 0.0),
                "last_assessed_at": s.get("last_assessed_at"),
            }
        )

    applications = _safe(
        "applications",
        "status, applied_at, opportunity_id",
        [("user_id", "eq", user_id)],
        limit=5,
    )

    app_details = []
    for a in applications:
        opp = _safe(
            "opportunities",
            "title, type",
            [("id", "eq", a.get("opportunity_id"))],
            limit=1,
        )
        app_details.append(
            {
                "title": opp[0]["title"] if opp else "",
                "type": opp[0]["type"] if opp else "",
                "status": a.get("status", ""),
                "applied_at": a.get("applied_at"),
            }
        )

    attempts = _safe(
        "assessment_attempts",
        "assessment_id, score, completed_at",
        [("user_id", "eq", user_id)],
        limit=5,
    )

    attempt_details = []
    for a in attempts:
        assessment = _safe(
            "assessments", "title", [("id", "eq", a.get("assessment_id"))], limit=1
        )
        attempt_details.append(
            {
                "title": assessment[0]["title"] if assessment else "",
                "score": a.get("score", 0),
                "completed_at": a.get("completed_at"),
            }
        )

    result = {
        "skills_count": len(skills_data),
        "skills": skills_data,
        "applications": app_details,
        "assessments": attempt_details,
    }

    cache_set(f"learnify:career_dashboard:{user_id}", result, 600)
    return result


@router.post("/me/cache/clear")
async def clear_my_cache(user=Depends(_auth)):
    clear_gaps_cache(user["uid"])
    return {"status": "ok", "message": "Cache cleared"}
