import datetime
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
    school: str = ""
    board: str = ""
    college: str = ""
    dob: str = ""


class ProfileReq(BaseModel):
    language: str = ""
    grade: str = ""
    school: str = ""
    board: str = ""
    college: str = ""
    dob: str = ""


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


def _ensure_users_row(
    client,
    uid,
    email,
    name="",
    language="English",
    grade="",
    school="",
    board="",
    college="",
    dob="",
):
    try:
        row = {
            "id": uid,
            "email": email,
            "name": name,
            "language": language,
            "grade": grade,
        }
        if school:
            row["school"] = school
        if board:
            row["board"] = board
        if college:
            row["college"] = college
        if dob:
            row["dob"] = dob
        client.table("users").upsert(row, on_conflict="id").execute()
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


def _profile_from_row(row: dict, email_fallback="", name_fallback=""):
    name = row.get("name") or name_fallback
    dob = row.get("dob")
    premium_until = row.get("premium_until")
    is_premium = bool(row.get("premium"))
    if is_premium and premium_until:
        try:
            until = datetime.datetime.fromisoformat(str(premium_until)[:19])
            is_premium = until > datetime.datetime.utcnow()
        except Exception:
            pass
    return {
        "id": row.get("id"),
        "email": row.get("email") or email_fallback,
        "name": name,
        "language": row.get("language") or "English",
        "grade": row.get("grade") or "",
        "premium": is_premium,
        "premium_until": premium_until or "",
        "school": row.get("school") or "",
        "board": row.get("board") or "",
        "college": row.get("college") or "",
        "dob": dob or "",
        "age": _age_from_dob(dob),
    }


def _full_user(client, uid, email_fallback="", name_fallback=""):
    try:
        res = client.table("users").select("*").eq("id", uid).limit(1).execute()
        if res.data:
            return _profile_from_row(res.data[0], email_fallback, name_fallback)
    except Exception:
        pass
    return {
        "id": uid,
        "email": email_fallback,
        "name": name_fallback,
        "language": "English",
        "grade": "",
        "premium": False,
        "premium_until": "",
        "school": "",
        "board": "",
        "college": "",
        "dob": "",
        "age": None,
    }


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


def _our_uid(
    client,
    email,
    name="",
    language="English",
    grade="",
    school="",
    board="",
    college="",
    dob="",
):
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
            # ensure profile fields are filled in if previously missing
            existing = rows[0]["id"]
            _ensure_users_row(
                svc, existing, email, name, language, grade, school, board, college, dob
            )
            return existing
    except Exception:
        pass

    def taken(u):
        try:
            r = svc.table("users").select("id").eq("id", u).limit(1).execute()
            return bool(r.data)
        except Exception:
            return False

    uid = generate_uid(taken)
    _ensure_users_row(
        svc, uid, email, name, language, grade, school, board, college, dob
    )
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
                        "emailRedirectTo": "https://learnify.hosteler.shop/",
                        "data": {
                            "name": req.name,
                            "language": req.language,
                            "grade": req.grade,
                            "school": req.school,
                            "board": req.board,
                            "college": req.college,
                            "dob": req.dob,
                        },
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
                    uid = _our_uid(
                        client,
                        email,
                        req.name,
                        req.language,
                        req.grade,
                        req.school,
                        req.board,
                        req.college,
                        req.dob,
                    )
                    return {
                        "user": _full_user(client, uid, email, req.name),
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
                                "school": req.school,
                                "board": req.board,
                                "college": req.college,
                                "dob": req.dob,
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

        # If the account is already confirmed (e.g. rate-limit admin fallback),
        # sign in immediately. Otherwise require email confirmation.
        confirmed = bool(
            getattr(user, "email_confirmed_at", None)
            or getattr(user, "confirmed_at", None)
        )
        if confirmed:
            _admin_confirm_email(email)
            uid = _our_uid(
                client,
                email,
                req.name,
                req.language,
                req.grade,
                req.school,
                req.board,
                req.college,
                req.dob,
            )
            out = {"user": _full_user(client, uid, email, req.name)}
            try:
                sess = client.auth.sign_in_with_password(
                    {"email": email, "password": req.password}
                ).session
            except Exception:
                sess = None
            if sess:
                out["session"] = {"access_token": sess.access_token}
            return out

        # New, unconfirmed account — ask the user to confirm via email.
        return {
            "user": {
                "id": getattr(user, "id", ""),
                "email": email,
                "name": req.name,
            },
            "needs_confirmation": True,
        }

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
            "user": _full_user(
                client,
                uid,
                email,
                getattr(user, "user_metadata", {}).get("name", "User"),
            ),
        }

    u = local_auth.verify(req.email, req.password)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = local_auth.issue_token(u)
    return {"session": {"access_token": token}, "user": local_auth.public_user(u)}


@router.get("/confirm")
def confirm(
    code: Optional[str] = None,
    access_token: Optional[str] = None,
):
    """Complete email confirmation and return a session (auto-login).

    Supabase's confirm-email link redirects back to the app with ?code= (PKCE)
    or an implicit #access_token. We exchange it for a session here.
    """
    if not db_available():
        raise HTTPException(status_code=503, detail="Auth unavailable")
    client = _require_client()
    user = None
    token = None
    try:
        if code:
            res = client.auth.exchange_code_for_session({"code": code})
            sess = getattr(res, "session", None)
            user = getattr(res, "user", None)
            token = getattr(sess, "access_token", None) if sess else None
        elif access_token:
            ur = client.auth.get_user(access_token)
            user = getattr(ur, "user", None)
            token = access_token
    except Exception as e:
        raise HTTPException(status_code=400, detail="Confirmation failed: " + str(e))
    if not user or not token:
        raise HTTPException(status_code=400, detail="Confirmation incomplete")
    email = getattr(user, "email", "")
    name = getattr(user, "user_metadata", {}).get("name", "") or ""
    _admin_confirm_email(email)
    uid = _our_uid(client, email, name)
    return {
        "session": {"access_token": token},
        "user": _full_user(client, uid, email, name),
    }


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
            "user": _full_user(
                client,
                uid,
                email,
                getattr(user, "user_metadata", {}).get("name", "User"),
            )
        }

    u = local_auth.get_user_by_token(_token(authorization))
    if not u:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user": local_auth.public_user(u)}


@router.put("/profile")
def update_profile(req: ProfileReq, authorization: Optional[str] = Header(None)):
    meta = {}
    if req.language:
        meta["language"] = req.language
    if req.grade:
        meta["grade"] = req.grade
    if req.school:
        meta["school"] = req.school
    if req.board:
        meta["board"] = req.board
    if req.college:
        meta["college"] = req.college
    if req.dob:
        meta["dob"] = req.dob

    if db_available():
        client = _require_client()
        token = _token(authorization)
        uid = resolve_uid(authorization)
        email = ""
        try:
            email = getattr(client.auth.get_user(token).user, "email", "")
        except Exception:
            email = ""
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        try:
            client.table("users").update(meta).eq("id", uid).execute()
        except Exception:
            pass
        try:
            auth_meta = {k: meta[k] for k in ("language", "grade") if k in meta}
            if auth_meta:
                client.auth.update_user({"data": auth_meta})
        except Exception:
            pass
        return {"user": _full_user(client, uid, email)}

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
        uid = resolve_uid(authorization)
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        try:
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
        uid = resolve_uid(authorization)
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        try:
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
