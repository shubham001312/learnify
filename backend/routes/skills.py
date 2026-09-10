"""
Skill taxonomy CRUD routes.

GET  /api/v1/skills              — list all skills (with categories)
GET  /api/v1/skills/categories   — list categories
GET  /api/v1/skills/{id}         — get skill with aliases and parent
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.database.client import db_available, get_client

router = APIRouter()


def _get_user(authorization: Optional[str]):
    from backend.routes.auth import _current_app_user

    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return cu


# ───────────────────────── PUBLIC ENDPOINTS ─────────────────────────


@router.get("/skills")
def list_skills(
    category: Optional[str] = None,
    search: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """List all skills, optionally filtered by category or search term."""
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        query = client.table("skills").select(
            "id, name, description, difficulty, demand_score, category_id, parent_skill_id"
        )
        if category:
            query = query.eq("category_id", category)
        if search:
            query = query.ilike("name", f"%{search}%")
        res = query.order("name").execute()
        skills = res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {e}")

    return {"skills": skills, "total": len(skills)}


@router.get("/skills/categories")
def list_categories(authorization: Optional[str] = Header(None)):
    """List all skill categories."""
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        res = (
            client.table("skill_categories")
            .select("id, name, description")
            .order("name")
            .execute()
        )
        return {"categories": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load categories: {e}")


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str, authorization: Optional[str] = Header(None)):
    """Get a single skill with its aliases and parent info."""
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        res = client.table("skills").select("*").eq("id", skill_id).limit(1).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Skill not found")
        skill = res.data[0]

        # Get aliases
        alias_res = (
            client.table("skill_aliases")
            .select("alias")
            .eq("skill_id", skill_id)
            .execute()
        )
        skill["aliases"] = [a["alias"] for a in (alias_res.data or [])]

        # Get parent if exists
        if skill.get("parent_skill_id"):
            parent_res = (
                client.table("skills")
                .select("id, name")
                .eq("id", skill["parent_skill_id"])
                .limit(1)
                .execute()
            )
            skill["parent"] = parent_res.data[0] if parent_res.data else None

        return {"skill": skill}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skill: {e}")


# ───────────────────────── ADMIN ENDPOINTS ─────────────────────────


@router.post("/skills")
def create_skill(
    name: str,
    category_id: Optional[str] = None,
    parent_skill_id: Optional[str] = None,
    description: str = "",
    difficulty: str = "intermediate",
    aliases: list[str] = [],
    authorization: Optional[str] = Header(None),
):
    """Create a new skill (admin only)."""
    _get_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    row = {
        "name": name,
        "description": description,
        "difficulty": difficulty,
    }
    if category_id:
        row["category_id"] = category_id
    if parent_skill_id:
        row["parent_skill_id"] = parent_skill_id

    try:
        res = client.table("skills").insert(row).execute()
        skill_id = res.data[0]["id"]

        # Insert aliases
        for alias in aliases:
            try:
                client.table("skill_aliases").insert(
                    {"skill_id": skill_id, "alias": alias}
                ).execute()
            except Exception:
                pass

        return {"skill": res.data[0], "message": "Skill created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create skill: {e}")


@router.put("/skills/{skill_id}")
def update_skill(
    skill_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    difficulty: Optional[str] = None,
    demand_score: Optional[float] = None,
    authorization: Optional[str] = Header(None),
):
    """Update a skill (admin only)."""
    _get_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    updates = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if difficulty is not None:
        updates["difficulty"] = difficulty
    if demand_score is not None:
        updates["demand_score"] = demand_score

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        client.table("skills").update(updates).eq("id", skill_id).execute()
        return {"message": "Skill updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update skill: {e}")


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: str, authorization: Optional[str] = Header(None)):
    """Delete a skill (admin only)."""
    _get_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        client.table("skill_aliases").delete().eq("skill_id", skill_id).execute()
        client.table("skills").delete().eq("id", skill_id).execute()
        return {"message": "Skill deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete skill: {e}")
