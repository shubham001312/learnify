import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from backend.services.uid import generate_uid

DATA_DIR = Path(__file__).resolve().parent.parent / "users_data"
USERS_FILE = DATA_DIR / "users.json"
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days


def _secret() -> str:
    """Token-signing secret (returned as a string — the sign/verify helpers
    call `.encode()` on it).

    Prefer an explicit APP_TOKEN_SECRET, then the Supabase service key (which
    is already private to this server). The previous implementation fell back
    to a publicly-known literal, allowing anyone to forge sessions.
    """
    explicit = os.environ.get("APP_TOKEN_SECRET")
    if explicit:
        return explicit
    service = os.environ.get("SUPABASE_SERVICE_KEY")
    if service:
        return service
    if os.environ.get("ENV", "development").lower() in ("production", "prod"):
        raise RuntimeError(
            "APP_TOKEN_SECRET or SUPABASE_SERVICE_KEY must be set in production."
        )
    # Development-only ephemeral secret: random per process, so tokens from a
    # previous run are rejected rather than forged.
    import warnings

    warnings.warn(
        "local_auth: no APP_TOKEN_SECRET/SUPABASE_SERVICE_KEY — using an "
        "ephemeral dev secret; sessions will not survive a restart.",
        RuntimeWarning,
        stacklevel=2,
    )
    return secrets.token_hex(32)


SECRET = _secret()  # resolved once at import; used by sign/verify


def _load() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(db: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(db, indent=2), encoding="utf-8")


def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()


def public_user(u: dict) -> dict:
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "name": u.get("name"),
        "role": u.get("role", "ALPHA"),
        "status": u.get("status", "ACTIVE"),
        "language": u.get("language", "English"),
        "department": u.get("department", ""),
        "designation": u.get("designation", ""),
        "headline": u.get("headline", ""),
        "bio": u.get("bio", ""),
        "phone": u.get("phone", ""),
        "avatar_url": u.get("avatar_url", ""),
        "must_change_password": bool(u.get("must_change_password", False)),
    }


def register(
    email: str,
    password: str,
    name: str = "",
    language: str = "English",
    role: str = "ALPHA",
) -> dict:
    db = _load()
    email = (email or "").lower().strip()
    if not email or not password:
        raise ValueError("Email and password are required.")
    if email in db:
        raise ValueError("An account with this email already exists.")
    taken = lambda uid: any(u.get("id") == uid for u in db.values())
    uid = generate_uid(taken)
    salt = secrets.token_hex(8)
    db[email] = {
        "id": uid,
        "email": email,
        "name": name or email.split("@")[0],
        "role": role if role in ("SUPREME", "MASTER", "ALPHA") else "ALPHA",
        # Mirrors the Supabase path: only an Administrator is usable the
        # moment it exists; everyone else waits for approval.
        "status": "ACTIVE" if role == "SUPREME" else "PENDING",
        "language": language,
        "department": "",
        "designation": "",
        "must_change_password": False,
        "salt": salt,
        "pw": _hash(password, salt),
    }
    _save(db)
    return db[email]


def verify(email: str, password: str) -> Optional[dict]:
    db = _load()
    email = (email or "").lower().strip()
    u = db.get(email)
    if not u:
        return None
    if u.get("pw") != _hash(password, u.get("salt", "")):
        return None
    return u


def _sign(email: str, uid: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"uid": uid, "email": email, "exp": int(time.time()) + TOKEN_TTL}
        ).encode()
    ).decode()
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig


def issue_token(user: dict) -> str:
    return _sign(user["email"], user["id"])


def sign_app_token(email: str, uid: str) -> str:
    """Issue a signed, refresh-free app session token (used even when Supabase
    is the credential store, so the app never depends on Supabase token expiry)."""
    return _sign(email, uid)


def decode_token(token: Optional[str]) -> Optional[dict]:
    """Verify and decode an app token without any DB lookup. Returns
    {uid, email, exp} or None if invalid/expired."""
    if not token:
        return None
    try:
        payload, sig = token.split(".")
    except Exception:
        return None
    if not hmac.compare_digest(
        sig, hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    ):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return {"uid": data.get("uid"), "email": data.get("email"), "exp": data.get("exp")}


def get_user_by_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        payload, sig = token.split(".")
    except Exception:
        return None
    if not hmac.compare_digest(
        sig, hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    ):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    db = _load()
    return db.get(data.get("email"))


def update_user(email: str, meta: dict) -> Optional[dict]:
    db = _load()
    u = db.get((email or "").lower().strip())
    if not u:
        return None
    # `role`/`status` are protected — only the profile endpoint writes them.
    for key in ("name", "language", "department", "designation",
                "headline", "bio", "phone", "avatar_url"):
        if key in meta and meta[key] is not None:
            u[key] = meta[key]
    _save(db)
    return u

