"""
Student skill profile routes.

GET    /api/v1/students/me/skill-profile          — get own skill profile
POST   /api/v1/students/me/skills                  — add/update a skill
DELETE /api/v1/students/me/skills/{skill_id}        — remove a skill
PUT    /api/v1/students/me/profile                  — update profile fields (role, career_goal, etc.)
GET    /api/v1/students/{student_id}/skill-profile  — view another student's profile (admin/industry)
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.database.client import db_available, get_client
from backend.routes.auth import _current_app_user
from backend.services.cache import (
    get as cache_get,
    set as cache_set,
    invalidate_pattern,
)

router = APIRouter()


class SkillAddReq(BaseModel):
    skill_id: str
    level: float = 0
    source: str = "SELF_REPORTED"


class ProfileUpdateReq(BaseModel):
    career_goal: str = ""
    headline: str = ""
    bio: str = ""
    stream: str = ""


def _require_user(authorization: Optional[str]):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return cu


# ───────────────────────── GET SKILL PROFILE ─────────────────────────


@router.get("/students/me/skill-profile")
def get_my_skill_profile(authorization: Optional[str] = Header(None)):
    """Get the authenticated student's skill profile."""
    cu = _require_user(authorization)
    return _get_skill_profile(cu["uid"])


@router.get("/students/{student_id}/skill-profile")
def get_student_skill_profile(
    student_id: str, authorization: Optional[str] = Header(None)
):
    """View a student's skill profile (admin/industry/academician)."""
    _require_user(authorization)
    return _get_skill_profile(student_id)


def _get_skill_profile(user_id: str):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Check cache
    cache_key = f"learnify:user:{user_id}:skills"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    try:
        # Get user skills with skill info
        res = (
            client.table("user_skills")
            .select(
                "skill_id, level, source, verified, confidence, last_assessed_at, skills(name, category_id, difficulty)"
            )
            .eq("user_id", user_id)
            .execute()
        )
        user_skills = res.data or []

        # Get categories for grouping
        cat_res = client.table("skill_categories").select("id, name").execute()
        categories = {c["id"]: c["name"] for c in (cat_res.data or [])}

        # Build skill profile
        skills = []
        for us in user_skills:
            skill_info = us.get("skills") or {}
            skills.append(
                {
                    "skill_id": us["skill_id"],
                    "name": skill_info.get("name", "Unknown"),
                    "category": categories.get(skill_info.get("category_id"), "Other"),
                    "difficulty": skill_info.get("difficulty", "intermediate"),
                    "level": us.get("level", 0),
                    "source": us.get("source", "SELF_REPORTED"),
                    "verified": us.get("verified", False),
                    "confidence": us.get("confidence", 0),
                    "last_assessed_at": us.get("last_assessed_at"),
                }
            )

        # Group by category
        by_category = {}
        for s in skills:
            cat = s["category"]
            by_category.setdefault(cat, []).append(s)

        # Calculate stats
        levels = [s["level"] for s in skills]
        avg_level = sum(levels) / len(levels) if levels else 0
        verified_count = sum(1 for s in skills if s["verified"])
        total = len(skills)

        result = {
            "user_id": user_id,
            "skills": skills,
            "by_category": by_category,
            "stats": {
                "total_skills": total,
                "avg_level": round(avg_level, 1),
                "verified_count": verified_count,
                "sources": {
                    s: sum(1 for sk in skills if sk["source"] == s)
                    for s in set(sk["source"] for sk in skills)
                },
            },
        }

        # Cache for 5 minutes
        cache_set(cache_key, result, ttl_seconds=300)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load skill profile: {e}"
        )


# ───────────────────────── ADD/UPDATE SKILL ─────────────────────────


@router.post("/students/me/skills")
def add_or_update_skill(req: SkillAddReq, authorization: Optional[str] = Header(None)):
    """Add or update a skill in the student's profile."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()

    # Verify skill exists
    try:
        skill_res = (
            client.table("skills")
            .select("id, name")
            .eq("id", req.skill_id)
            .limit(1)
            .execute()
        )
        if not skill_res.data:
            raise HTTPException(status_code=404, detail="Skill not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill lookup failed: {e}")

    # Upsert user skill
    row = {
        "user_id": cu["uid"],
        "skill_id": req.skill_id,
        "level": max(0, min(100, req.level)),
        "source": req.source,
    }

    try:
        existing = (
            client.table("user_skills")
            .select("id")
            .eq("user_id", cu["uid"])
            .eq("skill_id", req.skill_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            client.table("user_skills").update(row).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            client.table("user_skills").insert(row).execute()

        # Invalidate cache
        invalidate_pattern(f"learnify:user:{cu['uid']}")

        # Increment profile version
        client.table("users").update(
            {"skill_profile_version": "skill_profile_version + 1"}
        ).eq("id", cu["uid"]).execute()

        return {"message": "Skill updated", "skill": skill_res.data[0]["name"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update skill: {e}")


# ───────────────────────── REMOVE SKILL ─────────────────────────


@router.delete("/students/me/skills/{skill_id}")
def remove_skill(skill_id: str, authorization: Optional[str] = Header(None)):
    """Remove a skill from the student's profile."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        client.table("user_skills").delete().eq("user_id", cu["uid"]).eq(
            "skill_id", skill_id
        ).execute()

        invalidate_pattern(f"learnify:user:{cu['uid']}")
        return {"message": "Skill removed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to remove skill: {e}")


# ───────────────────────── UPDATE PROFILE ─────────────────────────


@router.put("/students/me/profile")
def update_student_profile(
    req: ProfileUpdateReq, authorization: Optional[str] = Header(None)
):
    """Update student profile fields (career_goal, headline, bio, stream)."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    updates = {}
    if req.career_goal:
        updates["career_goal"] = req.career_goal
    if req.headline:
        updates["headline"] = req.headline
    if req.bio:
        updates["bio"] = req.bio
    if req.stream:
        updates["stream"] = req.stream

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        client.table("users").update(updates).eq("id", cu["uid"]).execute()
        invalidate_pattern(f"learnify:user:{cu['uid']}")
        return {"message": "Profile updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update profile: {e}")
