from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.database.client import db_available, get_anon_client, get_client
from backend.services import local_auth
from backend.services.uid import generate_uid

router = APIRouter()


class RegisterReq(BaseModel):
    email: str
    password: str
    name: str
    language: str = "English"
    grade: str = ""


class ProfileReq(BaseModel):
    name: str = ""
    language: str = ""
    grade: str = ""


class LoginReq(BaseModel):
    email: str
    password: str


class SgpaReq(BaseModel):
    semester: str
    sgpa: float


def _token(authorization: Optional[str]) -> str:
    return (authorization or "").replace("Bearer ", "").strip()


def _email_from_token(authorization: Optional[str]) -> Optional[str]:
    u = local_auth.get_user_by_token(_token(authorization))
    return u["email"] if u else None


def _require_client():
    if not db_available():
        raise HTTPException(
            status_code=503,
            detail="Auth service unavailable: Supabase is not configured. "
            "Set SUPABASE_URL and SUPABASE_ANON_KEY in .env.",
        )
    return get_anon_client()


def _ensure_users_row(client, uid, email, name="", language="English", grade=""):
    try:
        client.table("users").upsert(
            {
                "id": uid,
                "email": email,
                "name": name,
                "language": language,
                "grade": grade,
            },
            on_conflict="id",
        ).execute()
    except Exception:
        pass


def _admin_confirm_email(email: str):
    """Best-effort: mark a user's email confirmed via the service-role admin API
    so newly registered (or previously unconfirmed) accounts can sign in immediately."""
    try:
        svc = get_client()
        target = None
        try:
            resp = svc.auth.admin.get_user_by_email(email)
            target = getattr(resp, "user", None)
        except Exception:
            target = None
        if not target:
            try:
                listing = svc.auth.admin.list_users()
                for u in getattr(listing, "users", []) or []:
                    if (getattr(u, "email", "") or "").lower() == email.lower():
                        target = u
                        break
            except Exception:
                target = None
        if target:
            uid = getattr(target, "id", None)
            if uid:
                svc.auth.admin.update_user_by_id(uid, {"email_confirm": True})
    except Exception:
        pass


def _our_uid(client, email, name="", language="English", grade=""):
    """Resolve our app-level unique id (exactly 7 chars) for a user.

    Looks up the existing row by email; if missing, generates a fresh,
    non-repeating id and creates the users row. Uses the service client so
    row-level security on `users` doesn't block the upsert.
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
    _ensure_users_row(svc, uid, email, name, language, grade)
    return uid


def resolve_uid(authorization: Optional[str]):
    """Return the app-level unique id (7 chars) for the bearer of `authorization`."""
    token = _token(authorization)
    if not token:
        return None
    if db_available():
        try:
            client = _require_client()
            user_resp = client.auth.get_user(token)
            user = getattr(user_resp, "user", None)
            if user:
                return _our_uid(
                    client,
                    getattr(user, "email", ""),
                    getattr(user, "user_metadata", {}).get("name", ""),
                )
        except Exception:
            return None
        return None
    u = local_auth.get_user_by_token(token)
    return u.get("id") if u else None


@router.post("/register")
def register(req: RegisterReq):
    if db_available():
        client = _require_client()
        svc = get_client()
        email = req.email
        user = None
        try:
            resp = client.auth.sign_up(
                {
                    "email": email,
                    "password": req.password,
                    "options": {
                        "data": {
                            "name": req.name,
                            "language": req.language,
                            "grade": req.grade,
                        }
                    },
                }
            )
            user = resp.user
        except Exception as e:
            msg = str(e).lower()
            if "already registered" in msg or "already exists" in msg:
                # Account exists: confirm it (if needed) and sign in like a login.
                _admin_confirm_email(email)
                try:
                    sess = client.auth.sign_in_with_password(
                        {"email": email, "password": req.password}
                    ).session
                except Exception:
                    sess = None
                if sess:
                    uid = _our_uid(client, email, req.name, req.language, req.grade)
                    return {
                        "user": {"id": uid, "email": email, "name": req.name},
                        "session": {"access_token": sess.access_token},
                    }
                raise HTTPException(
                    status_code=401, detail="Account exists but password is incorrect."
                )
            if "rate limit" in msg or "email rate" in msg:
                # Supabase's free-tier email hourly quota is exhausted. Fall back
                # to an admin-created, already-confirmed account so signup never
                # blocks the user (no confirmation email is sent in this path).
                try:
                    user = svc.auth.admin.create_user(
                        {
                            "email": email,
                            "password": req.password,
                            "email_confirm": True,
                            "user_metadata": {
                                "name": req.name,
                                "language": req.language,
                                "grade": req.grade,
                            },
                        }
                    ).user
                except Exception:
                    user = None
            if user is None:
                raise HTTPException(
                    status_code=400, detail="Registration failed: " + str(e)
                )
        if not user:
            raise HTTPException(status_code=400, detail="Registration failed")
        email = getattr(user, "email", email)
        _admin_confirm_email(email)
        uid = _our_uid(client, email, req.name, req.language, req.grade)
        out = {
            "user": {
                "id": uid,
                "email": email,
                "name": req.name,
            }
        }
        try:
            sess = client.auth.sign_in_with_password(
                {"email": email, "password": req.password}
            ).session
        except Exception:
            sess = None
        if sess:
            out["session"] = {"access_token": sess.access_token}
        return out

    # Local fallback (Supabase not configured)
    try:
        u = local_auth.register(
            req.email, req.password, req.name, req.language, req.grade
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = local_auth.issue_token(u)
    return {"session": {"access_token": token}, "user": local_auth.public_user(u)}


@router.post("/login")
def login(req: LoginReq):
    if db_available():
        client = _require_client()
        try:
            resp = client.auth.sign_in_with_password(
                {"email": req.email, "password": req.password}
            )
        except Exception as e:
            msg = str(e).lower()
            if "not confirmed" in msg or "email not confirm" in msg:
                _admin_confirm_email(req.email)
                resp = client.auth.sign_in_with_password(
                    {"email": req.email, "password": req.password}
                )
            else:
                raise HTTPException(status_code=401, detail="Invalid email or password")
        session = resp.session
        user = resp.user
        if not session or not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        email = getattr(user, "email", req.email)
        uid = _our_uid(client, email)
        return {
            "session": {"access_token": session.access_token},
            "user": {
                "id": uid,
                "email": email,
                "name": getattr(user, "user_metadata", {}).get("name", "User"),
            },
        }

    u = local_auth.verify(req.email, req.password)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = local_auth.issue_token(u)
    return {"session": {"access_token": token}, "user": local_auth.public_user(u)}


@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if db_available():
        token = _token(authorization)
        client = _require_client()
        try:
            user_resp = client.auth.get_user(token)
            user = user_resp.user
        except Exception:
            user = None
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        email = getattr(user, "email", "")
        uid = _our_uid(
            client, email, getattr(user, "user_metadata", {}).get("name", "")
        )
        return {
            "user": {
                "id": uid,
                "email": email,
                "name": getattr(user, "user_metadata", {}).get("name", "User"),
            }
        }

    u = local_auth.get_user_by_token(_token(authorization))
    if not u:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user": local_auth.public_user(u)}


@router.put("/profile")
def update_profile(req: ProfileReq, authorization: Optional[str] = Header(None)):
    meta = {}
    if req.name:
        meta["name"] = req.name
    if req.language:
        meta["language"] = req.language
    if req.grade:
        meta["grade"] = req.grade

    if db_available():
        client = _require_client()
        token = _token(authorization)
        try:
            resp = client.auth.update_user({"data": meta})
            user = resp.user
            uid = getattr(user, "id", None)
            if uid:
                try:
                    client.table("users").update(meta).eq("id", uid).execute()
                except Exception:
                    pass
            return {
                "user": {
                    "email": getattr(user, "email", ""),
                    "name": getattr(user, "user_metadata", {}).get("name", req.name),
                    "language": getattr(user, "user_metadata", {}).get(
                        "language", req.language
                    ),
                    "grade": getattr(user, "user_metadata", {}).get("grade", req.grade),
                }
            }
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Could not update profile: " + str(e)
            )

    email = _email_from_token(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    u = local_auth.update_user(email, meta)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": local_auth.public_user(u)}


@router.get("/sgpa")
def list_sgpa(authorization: Optional[str] = Header(None)):
    if db_available():
        client = _require_client()
        token = _token(authorization)
        try:
            uid = client.auth.get_user(token).user.id
            res = client.table("sgpa_entries").select("*").eq("user_id", uid).execute()
            return {"entries": res.data or []}
        except Exception as e:
            raise HTTPException(
                status_code=401, detail="Could not load SGPA: " + str(e)
            )

    email = _email_from_token(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"entries": local_auth.list_sgpa(email)}


@router.post("/sgpa")
def add_sgpa(req: SgpaReq, authorization: Optional[str] = Header(None)):
    if db_available():
        client = _require_client()
        token = _token(authorization)
        try:
            uid = client.auth.get_user(token).user.id
            res = (
                client.table("sgpa_entries")
                .insert(
                    {
                        "user_id": uid,
                        "semester": req.semester,
                        "sgpa": req.sgpa,
                    }
                )
                .execute()
            )
            return {"entry": (res.data or [{}])[0]}
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Could not save SGPA: " + str(e)
            )

    email = _email_from_token(authorization)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    entry = local_auth.add_sgpa(email, req.semester, req.sgpa)
    return {"entry": entry}
