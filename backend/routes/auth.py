"""Learnify authentication.

Roles: SUPREME · MASTER · ALPHA.  Signup is intentionally minimal
(email, password, name, role) — the profile page completes qualifications,
experience, interests, skills and certificates afterwards.

Issues its own 7-day signed app token so the API never depends on Supabase
token expiry. Falls back to a local JSON store when Supabase is unreachable.
"""

import concurrent.futures as _cf
import datetime
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from backend.database.client import db_available, get_anon_client, get_client
from backend.services import local_auth
from backend.services.uid import generate_uid

router = APIRouter()

AUTH_TIMEOUT = 8  # seconds — fail fast rather than hang on a slow auth backend
VALID_ROLES = ("SUPREME", "MASTER", "ALPHA")


def _call_limited(fn, timeout: int = AUTH_TIMEOUT):
    """Run a network call in a worker thread and raise on timeout."""
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except _cf.TimeoutError:
            raise RuntimeError("Auth service timed out")


# ─── Request models (minimal signup) ──────────────────────────────────────
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    role: str = "ALPHA"
    language: str = "English"
    # Administrator sign-up only: the token from the invite link an existing
    # Administrator shared. Ignored for Trainee and Trainer registrations.
    invite: str = Field(default="", max_length=200)


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileReq(BaseModel):
    # Optional (not "") so the endpoint can tell "leave this alone" from
    # "clear it" — every field used to default to "" and empty strings were
    # then discarded, so nobody could ever blank a headline or a bio.
    name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    language: Optional[str] = None


SITE_URL = os.environ.get("SITE_URL", "https://learnify.hosteler.shop/")

# Edits to these are refused for non-SUPREME callers (privilege self-escalation).
_PROTECTED_FIELDS = ("role", "status", "must_change_password")


def _token(authorization: Optional[str]) -> str:
    return (authorization or "").replace("Bearer ", "").strip()


def _issue_app_token(uid: str, email: str) -> str:
    return local_auth.sign_app_token(email, uid)


def _require_client():
    if not db_available():
        raise HTTPException(
            status_code=503,
            detail="Auth service unavailable: Supabase is not configured.",
        )
    return get_anon_client()


def _current_app_user(authorization: Optional[str]) -> Optional[dict]:
    """Resolve {uid, email} from our signed app token, falling back to a
    Supabase access token or a legacy local token. None when invalid."""
    token = _token(authorization)
    if not token:
        return None
    dec = local_auth.decode_token(token)
    if dec and dec.get("uid"):
        return {"uid": dec["uid"], "email": dec["email"]}
    u = local_auth.get_user_by_token(token)
    if u:
        return {"uid": u.get("id"), "email": u.get("email")}
    if db_available():
        try:
            client = _require_client()
            ur = _call_limited(lambda: client.auth.get_user(token))
            user = getattr(ur, "user", None)
            if user:
                email = getattr(user, "email", "")
                uid = _our_uid(
                    client, email, getattr(user, "user_metadata", {}).get("name", "")
                )
                return {"uid": uid, "email": email}
        except Exception:
            pass
    return None


def _our_uid(client, email, name="", role="ALPHA", status="PENDING") -> str:
    """Resolve (or create) the app-level 7-char id for a user.

    Uses the service client so RLS on `users` cannot block the upsert.

    `status` only reaches a row that does not exist yet; it defaults to
    PENDING so an account materialised outside a sign-up (a lost row, a token
    that outlived it) never comes back already approved.
    """
    svc = get_client()
    try:
        res = svc.table("users").select("id").eq("email", email).limit(1).execute()
        rows = res.data or []
        if rows:
            return rows[0]["id"]
    except Exception:
        pass

    def taken(u):
        try:
            r = svc.table("users").select("id").eq("id", u).limit(1).execute()
            return bool(r.data)
        except Exception:
            return False

    uid = generate_uid(taken)
    _ensure_users_row(svc, uid, email, name, role, status=status)
    return uid


def _ensure_users_row(client, uid, email, name="", role="ALPHA", language="English",
                      status="PENDING"):
    """Create the app row for a brand-new account.

    `status` is passed explicitly rather than left to the column default so the
    approval state is decided by one visible rule: Administrators are usable the
    moment their invite is accepted, Trainees are usable the moment they
    register, and only Trainers wait for an approval decision.
    """
    try:
        row = {"id": uid, "email": email, "name": name or email.split("@")[0],
               "role": role, "language": language, "status": status}
        client.table("users").upsert(row, on_conflict="id").execute()
    except Exception:
        pass


def _ensure_profile_row(client, uid):
    try:
        client.table("profiles").upsert({"user_id": uid}, on_conflict="user_id").execute()
    except Exception:
        pass


def _age_from_dob(dob):
    if not dob:
        return None
    try:
        d = datetime.date.fromisoformat(str(dob)[:10])
        today = datetime.date.today()
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        return None


def _profile_from_row(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "email": row.get("email"),
        "name": row.get("name") or "",
        "role": row.get("role") or "ALPHA",
        "status": row.get("status") or "ACTIVE",
        "department": row.get("department") or "",
        "designation": row.get("designation") or "",
        "headline": row.get("headline") or "",
        "bio": row.get("bio") or "",
        "phone": row.get("phone") or "",
        "avatar_url": row.get("avatar_url") or "",
        "language": row.get("language") or "English",
        "must_change_password": bool(row.get("must_change_password")),
        "created_at": row.get("created_at") or "",
    }


def _full_user(client, uid, email_fallback="", name_fallback="") -> dict:
    try:
        res = client.table("users").select("*").eq("id", uid).limit(1).execute()
        if res.data:
            return _profile_from_row(res.data[0])
    except Exception:
        pass
    return {"id": uid, "email": email_fallback, "name": name_fallback,
            "role": "ALPHA", "status": "ACTIVE"}


def _supabase_signin(client, email: str, password: str, errors: list = None):
    """Validate credentials → {uid, email, session} or None.

    When `errors` is provided, the raw GoTrue error code is appended so the
    caller can tell "wrong password" from "email not confirmed" without
    guessing.
    """
    try:
        resp = _call_limited(
            lambda: client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        )
    except Exception as e:
        if errors is not None:
            code = getattr(e, "error_code", None) or getattr(e, "code", None) \
                or type(e).__name__
            errors.append(str(code))
        return None
    sess = getattr(resp, "session", None)
    user = getattr(resp, "user", None)
    if not sess or not user:
        return None
    uid = _our_uid(
        client, email, getattr(user, "user_metadata", {}).get("name", "ALPHA")
    )
    return {"uid": uid, "email": email,
            "session": {"access_token": _issue_app_token(uid, email)}}


def _assert_active(client, uid):
    """Refuse a suspended account at the auth boundary.

    PENDING deliberately passes through: an unapproved person still has to be
    able to sign in and reach the "waiting for approval" screen, and telling
    them "suspended" would be both wrong and alarming. Every other route is
    shut by backend.middleware.rbac, which does tell the two states apart.
    """
    try:
        res = (
            client.table("users").select("status").eq("id", uid).limit(1).execute()
        )
        rows = res.data or []
        if not rows:
            return
        status = rows[0].get("status") or "ACTIVE"
        if status == "PENDING":
            return
        if status != "ACTIVE":
            raise HTTPException(status_code=403, detail="ACCOUNT_SUSPENDED")
    except HTTPException:
        raise
    except Exception:
        pass


def resolve_uid(authorization: Optional[str]) -> Optional[str]:
    cu = _current_app_user(authorization)
    return cu["uid"] if cu else None


# ─── Administrator invitations ─────────────────────────────────────────────
# Creating an account with role SUPREME is never a public act: an existing
# Administrator mints a token and shares the link, and the registration only
# goes through when that token is presented.
#
# Two doors exist and both close themselves:
#   * SUPREME_SIGNUP_OPEN=true is an explicit operator opt-in for a fresh
#     install — it is read as "closed" unless positively enabled.
#   * the bootstrap: while no Administrator exists there is nobody to send an
#     first invite, so one sign-up is allowed. The moment it succeeds the
#     condition is false and every later one needs an invite.
#
# Neither door applies to MASTER or ALPHA — they self-register without one. A
# Trainee is active immediately; a Trainer still waits in the approval queue.

INVITE_TABLE = "admin_invites"


def _supreme_signup_open() -> bool:
    """True only when the operator has positively enabled public sign-up."""
    return os.environ.get("SUPREME_SIGNUP_OPEN", "false").lower() in (
        "1", "true", "yes", "on"
    )


def _bootstrap_available(client) -> bool:
    """True when no Administrator account exists yet.

    Anything that goes wrong answers False — if the state cannot be read the
    safe reading is "do not open the door".
    """
    if client is None:
        return False
    try:
        res = client.table("users").select("id").eq("role", "SUPREME") \
                           .limit(1).execute()
        return not (res.data or [])
    except Exception:
        return False


def _reserve_invite(client, token: str, email: str) -> None:
    """Validate an Administrator invite and claim one of its uses.

    Raises HTTPException(403) when the token is unknown, revoked, expired,
    bound to a different address, or already used up. The claim is an
    optimistic compare-and-set on `used_count`: exactly one of two racing
    registrations matches the row it read, so a single-use link cannot admit
    two Administrators.

    A use is spent before the account exists, so a sign-up that fails part way
    through burns it — an Administrator can always mint another one, whereas a
    use handed back after the fact is how tokens get reused behind your back.
    """
    if client is None:
        raise HTTPException(status_code=403,
                            detail="Administrator sign-up is unavailable.")
    token = (token or "").strip()
    if not token:
        raise HTTPException(
            status_code=403,
            detail="Administrator sign-up is by invitation only. Ask an "
                   "administrator to send you a link.")
    try:
        res = client.table(INVITE_TABLE).select("*").eq("token", token) \
                    .limit(1).execute()
    except Exception:
        # Cannot confirm the invite is real, so it is not treated as real.
        raise HTTPException(status_code=403,
                            detail="That invite link could not be verified.")
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=403,
                            detail="That invite link is not valid.")
    inv = rows[0]

    if inv.get("revoked_at"):
        raise HTTPException(status_code=403,
                            detail="That invite link has been revoked.")
    exp = inv.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            if exp_dt <= datetime.datetime.now(datetime.timezone.utc):
                raise HTTPException(status_code=403,
                                    detail="That invite link has expired.")
        except HTTPException:
            raise
        except Exception:
            pass

    want = (inv.get("email") or "").strip().lower()
    if want and want != (email or "").lower().strip():
        raise HTTPException(status_code=403,
                            detail="That invite link was issued to a "
                                   "different email address.")

    if int(inv.get("used_count") or 0) >= int(inv.get("max_uses") or 1):
        raise HTTPException(status_code=403,
                            detail="That invite link has already been used.")

    try:
        claimed = (
            client.table(INVITE_TABLE)
            .update({"used_count": int(inv.get("used_count") or 0) + 1})
            .eq("token", token)
            .eq("used_count", int(inv.get("used_count") or 0))
            .is_("revoked_at", "null")
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=403,
                            detail="That invite link could not be used.")
    if not (claimed.data or []):
        # Someone else claimed it between the read and the write.
        raise HTTPException(status_code=403,
                            detail="That invite link has already been used.")


# ─── Routes ────────────────────────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterReq):
    role = (req.role or "ALPHA").upper().strip()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role.")

    # Administrator sign-up is never a public act. An invite token (or, while
    # no Administrator exists at all, the bootstrap) is required, and it is
    # checked before a single row is written. Trainee and trainer sign-ups
    # stay open — they are held in the approval queue instead.
    email = req.email.lower().strip()

    if db_available():
        client = _require_client()
        svc = get_client()
        if role == "SUPREME" and not _supreme_signup_open():
            if not _bootstrap_available(svc):
                _reserve_invite(svc, req.invite, email)
        payload = {
            "email": email,
            "password": req.password,
            "options": {
                "emailRedirectTo": SITE_URL,
                "data": {"name": req.name, "role": role, "language": req.language},
            },
        }
        user = None
        try:
            resp = _call_limited(lambda: client.auth.sign_up(payload))
            user = resp.user
        except Exception as e:
            msg = str(e).lower()
            if "already registered" in msg or "already exists" in msg:
                # Account exists. It may be an address whose confirmation never
                # landed, so repair it first — otherwise a person retrying a
                # sign-up that half-completed is locked out for good.
                _admin_confirm_email(email)
                sin = _supabase_signin(client, email, req.password)
                if not sin:
                    raise HTTPException(
                        status_code=401,
                        detail="An account with this email already exists.",
                    )
                _assert_active(client, sin["uid"])
                return {"session": sin["session"],
                        "user": _full_user(client, sin["uid"], email, req.name)}
            if "rate limit" in msg or "email rate" in msg:
                # Free-tier email quota exhausted — create a confirmed account
                # directly so signup is never blocked.
                try:
                    user = svc.auth.admin.create_user(
                        {"email": email, "password": req.password,
                         "email_confirm": True,
                         "user_metadata": {"name": req.name, "role": role}}
                    ).user
                except Exception:
                    user = None
            if user is None:
                raise HTTPException(status_code=400,
                                    detail="Registration failed: " + str(e))

        if not user:
            raise HTTPException(status_code=400, detail="Registration failed")

        email = getattr(user, "email", email) or email
        # Confirm immediately so the user is never blocked on an email link.
        # Pass the GoTrue id straight through — no lookup, no ambiguity.
        if not _admin_confirm_email(email, getattr(user, "id", "") or ""):
            import logging
            logging.getLogger("learnify.auth").warning(
                "sign-up for %s could not be auto-confirmed; login will retry", email)
        # A Trainee needs no one's permission: the account is usable the
        # moment it exists. An Administrator gets here only after its invite
        # (or the bootstrap) was validated above, for the same reason. A
        # Trainer is the one sign-up that still waits in the approval queue
        # until an Administrator acts — authoring content is a privilege.
        uid = _our_uid(client, email, req.name, role,
                       status="ACTIVE" if role in ("SUPREME", "ALPHA")
                       else "PENDING")
        _ensure_profile_row(client, uid)
        return {"session": {"access_token": _issue_app_token(uid, email)},
                "user": _full_user(client, uid, email, req.name)}

    # Local fallback (Supabase unreachable)
    try:
        u = local_auth.register(email, req.password, req.name, req.language, role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = local_auth.issue_token(u)
    return {"session": {"access_token": token}, "user": local_auth.public_user(u)}


@router.post("/login")
def login(req: LoginReq):
    email = req.email.lower().strip()
    if db_available():
        client = _require_client()
        errs: list = []
        sin = _supabase_signin(client, email, req.password, errs)
        if not sin and errs and "not_confirmed" in errs[-1]:
            # Repair the address, then retry once. Only unconfirmed accounts
            # pay for this round trip — a wrong password never does.
            _admin_confirm_email(email)
            sin = _supabase_signin(client, email, req.password, errs)
        if not sin:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        _assert_active(client, sin["uid"])
        return {"session": sin["session"],
                "user": _full_user(client, sin["uid"], email)}

    u = local_auth.verify(email, req.password)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if u.get("status", "ACTIVE") not in ("ACTIVE", "PENDING"):
        # Same rule as `_assert_active`: a pending account can still sign in,
        # so the app can show it the waiting screen. Only a suspension stops it.
        raise HTTPException(status_code=403, detail="ACCOUNT_SUSPENDED")
    token = local_auth.issue_token(u)
    return {"session": {"access_token": token}, "user": local_auth.public_user(u)}


@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if db_available():
        client = _require_client()
        _assert_active(client, cu["uid"])
        return {"user": _full_user(client, cu["uid"], cu["email"])}
    u = local_auth.get_user_by_token(_token(authorization))
    if not u:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user": local_auth.public_user(u)}


@router.put("/profile")
def update_profile(req: ProfileReq, authorization: Optional[str] = Header(None)):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    meta = {k: v for k, v in req.dict().items() if v is not None}
    # Never allow these through the generic profile endpoint.
    for f in _PROTECTED_FIELDS:
        meta.pop(f, None)
    # A blank name renders as an anonymous account; refuse to write it.
    if meta.get("name", "x") == "":
        meta.pop("name", None)

    if db_available():
        client = _require_client()
        _assert_active(client, cu["uid"])
        if meta:
            try:
                client.table("users").update(meta).eq("id", cu["uid"]).execute()
            except Exception:
                # Swallowing here would report a save that never happened.
                raise HTTPException(
                    status_code=400, detail="Could not save your profile.")
        return {"user": _full_user(client, cu["uid"], cu["email"])}

    u = local_auth.update_user(cu["email"], meta)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": local_auth.public_user(u)}


@router.post("/change-password")
def change_password(req: ChangePasswordReq,
                    authorization: Optional[str] = Header(None)):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not db_available():
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    client = _require_client()
    svc = get_client()
    # Verify the current password first.
    if not _supabase_signin(client, cu["email"], req.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    try:
        _call_limited(
            lambda: svc.auth.update_user_by_id(cu["uid"], {"password": req.new_password})
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not change password: " + str(e))

    try:
        svc.table("users").update({"must_change_password": False}).eq(
            "id", cu["uid"]
        ).execute()
    except Exception:
        pass

    return {"ok": True, "message": "Password updated."}


@router.get("/confirm")
def confirm(code: Optional[str] = None, access_token: Optional[str] = None):
    """Complete email confirmation and return a session (auto-login)."""
    if not db_available():
        raise HTTPException(status_code=503, detail="Auth unavailable")
    client = _require_client()
    user = None
    try:
        if code:
            res = _call_limited(
                lambda: client.auth.exchange_code_for_session({"code": code})
            )
            user = getattr(res, "user", None)
        elif access_token:
            ur = _call_limited(lambda: client.auth.get_user(access_token))
            user = getattr(ur, "user", None)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Confirmation failed: " + str(e))
    if not user:
        raise HTTPException(status_code=400, detail="Confirmation incomplete")
    email = getattr(user, "email", "")
    name = getattr(user, "user_metadata", {}).get("name", "") or ""
    _admin_confirm_email(email)
    uid = _our_uid(client, email, name)
    _ensure_profile_row(client, uid)
    return {"session": {"access_token": _issue_app_token(uid, email)},
            "user": _full_user(client, uid, email, name)}


def _admin_confirm_email(email: str, auth_uid: str = "") -> bool:
    """Mark the email confirmed so the account can sign in immediately.

    Returns True only when GoTrue reports the address as confirmed. Callers
    treat False as meaningful: handing back a session for an account that
    still cannot password-login is worse than saying so.

    Two client-API traps live here, both of which used to fail silently:
      * this supabase-py has no `auth.admin.get_user_by_email`, and
      * `auth.admin.list_users()` returns a plain list, not an object with a
        `.users` attribute — reading `.users` always yielded nothing, so the
        confirmation update was never issued and sign-up produced accounts
        that could register but never log in.
    """
    wanted = (email or "").lower()

    def _do() -> bool:
        svc = get_client()
        if svc is None:
            return False

        target_id = auth_uid or ""
        if not target_id:
            for u in _list_gotrue_users(svc):
                if (getattr(u, "email", "") or "").lower() == wanted:
                    target_id = getattr(u, "id", "") or ""
                    break
        if not target_id:
            return False

        updated = svc.auth.admin.update_user_by_id(target_id, {"email_confirm": True})
        # Some versions return the updated User, others wrap it — accept either.
        probe = updated if getattr(updated, "email_confirmed_at", None) else (
            getattr(updated, "user", None) or updated)
        if getattr(probe, "email_confirmed_at", None):
            return True
        # Fall back to a re-read when the return value carried no confirmation.
        for u in _list_gotrue_users(svc):
            if getattr(u, "id", None) == target_id:
                return bool(getattr(u, "email_confirmed_at", None))
        return False

    try:
        return bool(_call_limited(_do, timeout=AUTH_TIMEOUT))
    except Exception:
        import logging
        logging.getLogger("learnify.auth").warning(
            "email confirmation failed for %s", email, exc_info=True)
        return False


def _list_gotrue_users(svc, per_page: int = 100) -> list:
    """Every GoTrue account, paginated to the end."""
    out: list = []
    page = 1
    while page <= 50:                       # projects are small; hard stop anyway
        try:
            batch = svc.auth.admin.list_users(page=page, per_page=per_page) or []
        except Exception:
            break
        if not isinstance(batch, list):
            batch = getattr(batch, "users", None) or []
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return out
