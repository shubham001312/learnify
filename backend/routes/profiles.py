"""Professional profiles: qualifications, work experience, interests, skills,
certificates, education.

Every user owns exactly one profile row (created lazily on first read/write).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from backend.middleware.rbac import _extract_user
from backend.services import db

router = APIRouter(prefix="/profiles", tags=["profiles"])

LIST_MAX = 60          # cap any repeating section
TEXT_MAX = 400         # per-item text cap


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


# ─── Item shapes (validated, capped) ───────────────────────────────────────
class Education(BaseModel):
    degree: str = Field(default="", max_length=160)
    institution: str = Field(default="", max_length=160)
    year: str = Field(default="", max_length=20)
    grade: str = Field(default="", max_length=40)


class Qualification(BaseModel):
    title: str = Field(default="", max_length=160)
    issuer: str = Field(default="", max_length=160)
    year: str = Field(default="", max_length=20)


class Experience(BaseModel):
    role: str = Field(default="", max_length=160)
    org: str = Field(default="", max_length=160)
    from_year: str = Field(default="", max_length=20, alias="from")
    to_year: str = Field(default="", max_length=20, alias="to")
    summary: str = Field(default="", max_length=TEXT_MAX)

    class Config:
        populate_by_name = True


class Skill(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    level: int = Field(default=50, ge=0, le=100)


class Certificate(BaseModel):
    name: str = Field(default="", max_length=160)
    issuer: str = Field(default="", max_length=160)
    year: str = Field(default="", max_length=20)
    url: str = Field(default="", max_length=400)


class ProfileIn(BaseModel):
    education: list[Education] = []
    qualifications: list[Qualification] = []
    experience: list[Experience] = []
    interests: list[str] = []
    skills: list[Skill] = []
    certificates: list[Certificate] = []


def _clean(items: list, limit: int = LIST_MAX) -> list:
    """Cap list size; drop entries that are entirely blank."""
    out = []
    for it in items[:limit]:
        d = it.model_dump(by_alias=True) if hasattr(it, "model_dump") else (
            it if isinstance(it, dict) else {"name": str(it)}
        )
        if isinstance(d, str):
            d = {"name": d}
        if any(str(v).strip() for v in d.values() if isinstance(v, (str, int))):
            out.append(d)
    return out


def _normalize(payload: dict) -> dict:
    """Apply caps and coercion to a raw profile payload."""
    norm = {}
    for key in ("education", "qualifications", "experience", "skills",
                "certificates"):
        if key in payload and payload[key] is not None:
            norm[key] = _clean(payload[key])
    if "interests" in payload and payload["interests"] is not None:
        seen, interests = set(), []
        for raw in payload["interests"][:LIST_MAX]:
            s = str(raw).strip()[:80]
            if s and s.lower() not in seen:
                seen.add(s.lower())
                interests.append(s)
        norm["interests"] = interests
    norm["updated_at"] = "now()"
    return norm


def _get_or_create(user_id: str) -> dict:
    row = db.first("profiles", "*", eq={"user_id": user_id})
    if row:
        return row
    try:
        return db.upsert("profiles", {"user_id": user_id}, "user_id")
    except db.Rejected:
        return {"user_id": user_id, "education": [], "qualifications": [],
                "experience": [], "interests": [], "skills": [], "certificates": []}


def public_profile(user_id: str, viewer: dict) -> dict:
    """Profile + the owning user's public identity."""
    prof = _get_or_create(user_id)
    user = db.first("users",
                    "id, name, role, department, designation, headline, bio, "
                    "avatar_url, created_at",
                    eq={"id": user_id})
    if not user:
        raise db.NotFound("User not found")
    is_self = viewer and viewer.get("uid") == user_id
    out = {
        "user": user,
        "education": prof.get("education") or [],
        "qualifications": prof.get("qualifications") or [],
        "experience": prof.get("experience") or [],
        "interests": prof.get("interests") or [],
        "skills": prof.get("skills") or [],
        "certificates": prof.get("certificates") or [],
        "updated_at": prof.get("updated_at"),
        "is_self": is_self,
    }
    return out


@router.get("/me")
def my_profile(user=Depends(_auth)):
    return db.ok(public_profile(user["uid"], user))


@router.put("/me")
def update_my_profile(payload: ProfileIn, user=Depends(_auth)):
    _get_or_create(user["uid"])
    body = _normalize(payload.model_dump(by_alias=True))
    row = db.upsert("profiles", {**body, "user_id": user["uid"]}, "user_id")
    db.audit(user["uid"], "profile.update", "profile", user["uid"])
    return db.ok({**row, "is_self": True})


@router.get("/{user_id}")
def view_profile(user_id: str, user=Depends(_auth)):
    """Any authenticated user may view another's professional profile.

    Email/phone are never exposed — only the public identity block.
    """
    return db.ok(public_profile(user_id, user))
