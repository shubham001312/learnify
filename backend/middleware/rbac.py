"""Role-based access control for Learnify.

Roles
    SUPREME  — platform admin: approvals, releases, dashboards, publishing
    MASTER   — trainer: courses, questionnaires, assessments, library
    ALPHA    — trainee: enroll, learn, attempt, give feedback

Design rules
    * Fail-CLOSED. If the role cannot be determined the request is rejected.
      (The previous implementation defaulted to a permissive role on error.)
    * A SUSPENDED account is refused regardless of role.
    * A PENDING account is refused with ACCOUNT_PENDING_APPROVAL until an
      Administrator approves it — it never inherits SUSPENDED's meaning.
    * Authorization is enforced server-side only — the frontend is never trusted.
"""

from typing import Optional

from fastapi import Header, HTTPException

from backend.database.client import db_available, get_client
from backend.routes.auth import _current_app_user

# ─── Role constants ───────────────────────────────────────────────────────
SUPREME = "SUPREME"
MASTER = "MASTER"
ALPHA = "ALPHA"

ALL_ROLES = [SUPREME, MASTER, ALPHA]
DEFAULT_ROLE = ALPHA  # only applied when the DB is genuinely unreachable

# Coarse permission tiers: higher tier includes the lower one's read access.
_ROLE_RANK = {ALPHA: 0, MASTER: 1, SUPREME: 2}


class AuthError(HTTPException):
    """401 — identity could not be established."""


class Forbidden(HTTPException):
    """403 — identity known but not permitted / account suspended."""


def get_user_role(user_id: str) -> Optional[str]:
    """Primary role for a user, or None if it cannot be determined.

    Never guesses: returns None on any failure so callers can fail closed.
    """
    if not db_available():
        return None
    client = get_client()
    if client is None:
        return None
    try:
        res = (
            client.table("users")
            .select("role,status")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        _refuse_if_not_active(row.get("status") or "ACTIVE")
        role = row.get("role")
        return role if role in ALL_ROLES else None
    except Forbidden:
        raise
    except Exception:
        return None


def _refuse_if_not_active(status: str) -> None:
    """Raise the 403 that matches this account state, or return for ACTIVE.

    PENDING and SUSPENDED are deliberately different codes: the UI has to tell
    "waiting for an administrator" apart from "your account was taken away",
    and a shared message would make the first look like the second.
    """
    if status == "ACTIVE":
        return
    if status == "PENDING":
        raise Forbidden(status_code=403, detail="ACCOUNT_PENDING_APPROVAL")
    raise Forbidden(status_code=403, detail="ACCOUNT_SUSPENDED")


def get_user_status(user_id: str) -> Optional[str]:
    if not db_available():
        return None
    client = get_client()
    if client is None:
        return None
    try:
        res = (
            client.table("users").select("status").eq("id", user_id).limit(1).execute()
        )
        rows = res.data or []
        return rows[0].get("status") if rows else None
    except Exception:
        return None


def _identity(authorization: Optional[str]) -> dict:
    """Resolve {uid,email,role,status} or raise (fail-closed)."""
    cu = _current_app_user(authorization)
    if not cu:
        raise AuthError(status_code=401, detail="Invalid or expired token")

    uid = cu["uid"]
    role = get_user_role(uid)
    if role is None:
        # Distinguish "unknown user / no role" from "db down".
        if get_user_status(uid) is None:
            raise Forbidden(
                status_code=403, detail="Account is not provisioned on this platform."
            )
        raise AuthError(status_code=401, detail="Invalid or expired token")
    return {"uid": uid, "email": cu["email"], "role": role}


def require_role(*allowed_roles: str):
    """FastAPI dependency restricting a route to specific roles.

        @router.get("/x")
        def x(user=Depends(require_role(MASTER, SUPREME))): ...
    """

    def dependency(authorization: Optional[str] = Header(None)) -> dict:
        user = _identity(authorization)
        if user["role"] not in allowed_roles:
            raise Forbidden(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}",
            )
        return user

    return dependency


def optional_role(*allowed_roles: str):
    """Like require_role but returns None instead of raising when unauthenticated.

    Rejected roles still raise — a logged-in Alpha must never silently gain
    access to a page meant for someone else.
    """

    def dependency(authorization: Optional[str] = Header(None)) -> Optional[dict]:
        if not authorization:
            return None
        user = _identity(authorization)
        if user["role"] not in allowed_roles:
            raise Forbidden(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}",
            )
        return user

    return dependency


def _extract_user(authorization: Optional[str] = Header(None)) -> dict:
    """Any authenticated user, role unchecked (for 'my own data' routes)."""
    return _identity(authorization)


# ─── Convenience wrappers ──────────────────────────────────────────────────
def require_alpha(authorization: Optional[str] = Header(None)) -> dict:
    return require_role(ALPHA)(authorization)


def require_master(authorization: Optional[str] = Header(None)) -> dict:
    return require_role(MASTER)(authorization)


def require_supreme(authorization: Optional[str] = Header(None)) -> dict:
    return require_role(SUPREME)(authorization)


def at_least(user: dict, role: str) -> bool:
    """True when the user's role rank is >= `role`'s rank."""
    return _ROLE_RANK.get(user.get("role"), -1) >= _ROLE_RANK.get(role, 99)


def ensure_owner_or_above(user: dict, owner_id: str, minimum: str = MASTER) -> None:
    """Allow the resource owner, or anyone at/above `minimum`."""
    if user.get("uid") == owner_id or at_least(user, minimum):
        return
    raise Forbidden(status_code=403, detail="Access denied.")
