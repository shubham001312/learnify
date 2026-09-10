"""
Role-based access control middleware.

Provides dependency-injection helpers for FastAPI routes to enforce
role-based authorization.
"""

from typing import Optional

from fastapi import Header, HTTPException

from backend.database.client import db_available, get_client
from backend.routes.auth import _current_app_user


# ─── Role Constants ──────────────────────────────────────────────────────
STUDENT = "STUDENT"
INDUSTRY = "INDUSTRY"
ACADEMICIAN = "ACADEMICIAN"
INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
SUPER_ADMIN = "SUPER_ADMIN"

ALL_ROLES = [STUDENT, INDUSTRY, ACADEMICIAN, INSTITUTION_ADMIN, SUPER_ADMIN]


def get_user_role(user_id: str) -> Optional[str]:
    """Get the primary role for a user from the database."""
    if not db_available():
        return STUDENT  # Default to student if no DB

    client = get_client()
    try:
        res = (
            client.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["role"]

        # Fallback: check users table role column
        res = client.table("users").select("role").eq("id", user_id).limit(1).execute()
        if res.data and res.data[0].get("role"):
            return res.data[0]["role"]
    except Exception:
        pass

    return STUDENT  # Default


def get_user_roles(user_id: str) -> list[str]:
    """Get all roles for a user (a user can have multiple)."""
    if not db_available():
        return [STUDENT]

    client = get_client()
    try:
        res = client.table("user_roles").select("role").eq("user_id", user_id).execute()
        roles = [r["role"] for r in (res.data or [])]
        return roles if roles else [STUDENT]
    except Exception:
        return [STUDENT]


def require_role(*allowed_roles: str):
    """Decorator factory for route handlers that require specific roles.

    Usage:
        @router.get("/admin/dashboard")
        def admin_dashboard(user=Depends(require_role(SUPER_ADMIN, INSTITUTION_ADMIN))):
            ...
    """

    def dependency(authorization: Optional[str] = Header(None)):
        cu = _current_app_user(authorization)
        if not cu:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        role = get_user_role(cu["uid"])
        if role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}",
            )
        return {"uid": cu["uid"], "email": cu["email"], "role": role}

    return dependency


def optional_role(*allowed_roles: str):
    """Like require_role but returns None if no auth instead of raising."""

    def dependency(authorization: Optional[str] = Header(None)):
        cu = _current_app_user(authorization)
        if not cu:
            return None

        role = get_user_role(cu["uid"])
        if role not in allowed_roles:
            return None
        return {"uid": cu["uid"], "email": cu["email"], "role": role}

    return dependency


def _extract_user(authorization: Optional[str]):
    """Extract current user from authorization header."""
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    role = get_user_role(cu["uid"])
    return {"uid": cu["uid"], "email": cu["email"], "role": role}


# ─── Convenience Functions ────────────────────────────────────────────────


def require_student(authorization: Optional[str] = Header(None)):
    """Require STUDENT role."""
    return require_role(STUDENT)(authorization)


def require_industry(authorization: Optional[str] = Header(None)):
    """Require INDUSTRY role."""
    return require_role(INDUSTRY)(authorization)


def require_academician(authorization: Optional[str] = Header(None)):
    """Require ACADEMICIAN role."""
    return require_role(ACADEMICIAN)(authorization)


def require_institution_admin(authorization: Optional[str] = Header(None)):
    """Require INSTITUTION_ADMIN role."""
    return require_role(INSTITUTION_ADMIN)(authorization)


def require_super_admin(authorization: Optional[str] = Header(None)):
    """Require SUPER_ADMIN role."""
    return require_role(SUPER_ADMIN)(authorization)
