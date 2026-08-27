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

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"
SECRET = os.environ.get("SUPABASE_SERVICE_KEY") or "learnify-dev-secret-change-me"
TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days


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
        "language": u.get("language", "English"),
        "grade": u.get("grade", ""),
        "premium": bool(u.get("premium", False)),
    }


def register(
    email: str,
    password: str,
    name: str = "",
    language: str = "English",
    grade: str = "",
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
        "language": language,
        "grade": grade,
        "premium": False,
        "salt": salt,
        "pw": _hash(password, salt),
        "sgpa": [],
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
    for key in ("name", "language", "grade", "premium"):
        if key in meta and meta[key] is not None:
            u[key] = meta[key]
    _save(db)
    return u


def list_sgpa(email: str) -> list:
    db = _load()
    u = db.get((email or "").lower().strip())
    return (u or {}).get("sgpa", [])


def add_sgpa(email: str, semester: str, sgpa) -> dict:
    db = _load()
    u = db.get((email or "").lower().strip())
    if not u:
        return {}
    entry = {"semester": semester, "sgpa": sgpa}
    u.setdefault("sgpa", []).append(entry)
    _save(db)
    return entry
