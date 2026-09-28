"""Supreme administration: dashboards, user management, audit trail.

Suspension (exam control #6) blocks a user at the auth boundary *and* in the
RBAC dependency, so a suspended account cannot read anything even with a
still-valid token.
"""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALL_ROLES, ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/admin", tags=["admin"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class SuspendIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=60)
    reason: str = Field(default="", max_length=500)


class RoleChange(BaseModel):
    user_id: str = Field(min_length=1, max_length=60)
    role: str = Field(pattern="^(SUPREME|MASTER|ALPHA)$")


class UserFilter(BaseModel):
    pass


# ─── Dashboard ─────────────────────────────────────────────────────────────
@router.get("/dashboard")
def dashboard(user=Depends(require_role(SUPREME))):
    """Single call that fills the Supreme landing view."""
    counts = {}
    for table, key in (
        ("users", "users"), ("courses", "courses"),
        ("questionnaires", "questionnaires"), ("assessments", "assessments"),
        ("enrollments", "enrollments"), ("certificates", "certificates"),
        ("library_items", "library"), ("performance_reports", "reports"),
        ("subjects", "subjects"), ("home_posts", "posts"),
    ):
        counts[key] = db.count(table)

    by_role = {}
    pending_accounts = 0
    users, _ = db.select("users", "role, status", limit=5000)
    for u in users:
        r = u.get("role") or "ALPHA"
        s = (u.get("status") or "ACTIVE").upper()
        by_role.setdefault(r, {"total": 0, "active": 0, "suspended": 0,
                               "pending": 0})
        by_role[r]["total"] += 1
        # Anything the schema does not recognise still counts as active here —
        # it is a display bucket, not an authorisation decision.
        bucket = s if s in ("ACTIVE", "SUSPENDED", "PENDING") else "ACTIVE"
        by_role[r][bucket.lower()] += 1
        if s == "PENDING":
            pending_accounts += 1

    pending = _pending_queue()
    activity = _recent_activity()

    # Learning health across published work.
    enrs, _ = db.select("enrollments", "status, progress_pct", limit=5000)
    completed = sum(1 for e in enrs if e.get("status") == "COMPLETED")
    avg_progress = (round(sum(float(e.get("progress_pct") or 0) for e in enrs)
                          / len(enrs), 1) if enrs else 0)

    certs, _ = db.select("certificates", "id, status, percentage",
                         eq={"status": "VALID"}, limit=5000)
    _, revoked_total = db.select("certificates", "id",
                                 eq={"status": "REVOKED"}, count=True)

    return db.ok({
        "counts": counts,
        "users_by_role": by_role,
        # Accounts that can sign in but cannot reach anything yet — the number
        # the approval queue is built around.
        "pending_accounts": pending_accounts,
        "pending": pending,
        "activity": activity,
        "learning": {
            "enrollments": len(enrs),
            "completed": completed,
            "avg_progress": avg_progress,
            "completion_rate": round(completed / len(enrs) * 100, 1)
            if enrs else 0,
        },
        "certificates": {
            "valid": len(certs),
            "revoked": revoked_total,
            "avg_score": round(sum(float(c.get("percentage") or 0)
                                   for c in certs) / len(certs), 1)
            if certs else 0,
        },
    })


def _pending_queue() -> list[dict]:
    """Everything waiting on a Supreme decision, in one list."""
    out = []
    courses, _ = db.select(
        "courses", "id, title, status, created_at, updated_at, "
        "users!trainer_id(name), subjects(name)",
        eq={"status": "PENDING_RELEASE"}, order=("updated_at", False), limit=50)
    for c in courses:
        out.append(_flat(c, "course", "Awaiting release", "courses"))

    qnrs, _ = db.select(
        "questionnaires", "id, title, status, updated_at, users(name), subjects(name)",
        eq={"status": "PENDING_RELEASE"}, order=("updated_at", False), limit=50)
    for q in qnrs:
        out.append(_flat(q, "questionnaire", "Awaiting release", "questionnaires"))

    asms, _ = db.select(
        "assessments", "id, title, status, updated_at, users(name), subjects(name)",
        eq={"status": "PENDING_RELEASE"}, order=("updated_at", False), limit=50)
    for a in asms:
        out.append(_flat(a, "assessment", "Awaiting release", "assessments"))

    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return out


def _flat(row: dict, kind: str, action: str, path: str) -> dict:
    owner = row.get("users") or {}
    if isinstance(owner, list):
        owner = owner[0] if owner else {}
    subj = row.get("subjects") or {}
    if isinstance(subj, list):
        subj = subj[0] if subj else {}
    return {
        "kind": kind, "id": row.get("id"), "title": row.get("title", ""),
        "status": row.get("status"),
        "owner": owner.get("name", ""), "subject": subj.get("name", ""),
        "action": action, "path": f"/{path}/{row.get('id')}",
        "updated_at": row.get("updated_at"),
    }


def _recent_activity(limit: int = 30) -> list[dict]:
    rows, _ = db.select(
        "audit_logs",
        "id, actor_id, action, resource_type, resource_id, created_at, "
        "users(name, role)",
        order=("created_at", True), limit=limit)
    out = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        out.append({
            "id": r.get("id"), "actor": u.get("name", "system"),
            "actor_role": u.get("role", ""),
            "action": r.get("action", ""),
            "resource": r.get("resource_type", ""),
            "resource_id": r.get("resource_id", ""),
            "created_at": r.get("created_at"),
        })
    return out


# ─── Users ─────────────────────────────────────────────────────────────────
@router.get("/users")
def list_users(
    role: str = Query(default="", max_length=20),
    status: str = Query(default="", max_length=20),
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=10000),
    user=Depends(require_role(SUPREME)),
):
    eq: dict = {}
    if role in ALL_ROLES:
        eq["role"] = role
    if status in ("PENDING", "ACTIVE", "SUSPENDED"):
        eq["status"] = status

    rows, total = db.select("users",
                            "id, email, name, role, status, department, "
                            "designation, avatar_url, created_at, suspended_at",
                            eq=eq or None, order=("created_at", True),
                            limit=limit, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows
                if ql in (r.get("name", "") or "").lower()
                or ql in (r.get("email", "") or "").lower()
                or ql in (r.get("department", "") or "").lower()]

    # Enrich with per-user activity so the table is useful at a glance.
    ids = [r["id"] for r in rows]
    stats = _bulk_stats(ids)
    for r in rows:
        r.update(stats.get(r["id"], {"enrollments": 0, "courses": 0,
                                     "certificates": 0, "attempts": 0}))
    return db.ok(rows, meta={"total": total or len(rows)})


def _bulk_stats(ids: list[str]) -> dict:
    out = {i: {"enrollments": 0, "courses": 0, "certificates": 0, "attempts": 0}
           for i in ids}
    if not ids:
        return out
    enr, _ = db.select("enrollments", "trainee_id",
                       in_={"trainee_id": ids}, limit=5000)
    for e in enr:
        if e.get("trainee_id") in out:
            out[e["trainee_id"]]["enrollments"] += 1
    crs, _ = db.select("courses", "trainer_id",
                       in_={"trainer_id": ids}, limit=5000)
    for c in crs:
        if c.get("trainer_id") in out:
            out[c["trainer_id"]]["courses"] += 1
    certs, _ = db.select("certificates", "trainee_id",
                         in_={"trainee_id": ids}, limit=5000)
    for c in certs:
        if c.get("trainee_id") in out:
            out[c["trainee_id"]]["certificates"] += 1
    att, _ = db.select("assessment_attempts", "trainee_id",
                       in_={"trainee_id": ids}, limit=5000)
    for a in att:
        if a.get("trainee_id") in out:
            out[a["trainee_id"]]["attempts"] += 1
    return out


@router.get("/users/{user_id}")
def user_detail(user_id: str, user=Depends(require_role(SUPREME))):
    row = db.first("users", "*", eq={"id": user_id})
    if not row:
        raise db.NotFound("User not found")
    row.pop("password", None)

    profile = db.first("profiles", "*", eq={"user_id": user_id}) or {}
    stats = _bulk_stats([user_id]).get(user_id, {})

    enrollments, _ = db.select(
        "enrollments", "id, course_id, status, progress_pct, enrolled_at, "
        "courses(title)", eq={"trainee_id": user_id},
        order=("enrolled_at", True), limit=100)
    enr_out = []
    for e in enrollments:
        t = e.get("courses") or {}
        if isinstance(t, list):
            t = t[0] if t else {}
        enr_out.append({**{k: e[k] for k in ("id", "course_id", "status",
                                            "progress_pct", "enrolled_at")},
                        "title": t.get("title", "")})

    certs, _ = db.select("certificates",
                         "id, code, title, percentage, issued_at, status",
                         eq={"trainee_id": user_id},
                         order=("issued_at", True), limit=100)

    exams, _ = db.select("assessments", "id, title, status",
                         eq={"trainer_id": user_id},
                         order=("created_at", True), limit=100)

    return db.ok({
        "user": row,
        "profile": profile,
        "stats": stats,
        "enrollments": enr_out,
        "certificates": certs,
        "authored_assessments": exams,
    })


# ─── Suspension (exam control #6) ──────────────────────────────────────────
@router.post("/suspend")
def suspend(payload: SuspendIn, user=Depends(require_role(SUPREME))):
    """Suspend an account: blocked at login and in every RBAC check."""
    target = db.first("users", "id, role, status, name, email",
                      eq={"id": payload.user_id})
    if not target:
        raise db.NotFound("User not found")
    if payload.user_id == user["uid"]:
        raise db.Rejected("You cannot suspend your own account.")
    if target.get("role") == SUPREME and payload.user_id != user["uid"]:
        # Allowed (multiple admins) but must be a deliberate act.
        pass

    db.update("users", {"status": "SUSPENDED", "suspended_by": user["uid"],
                        "suspended_at": "now()"}, id=payload.user_id)
    db.audit(user["uid"], "user.suspend", "user", payload.user_id,
             {"reason": payload.reason.strip(),
              "name": target.get("name"), "email": target.get("email")})

    from backend.routes.notifications import notify
    notify(db.client_or_none(), payload.user_id, ntype="SYSTEM",
           title="Account suspended",
           message=(payload.reason.strip() or
                    "Your account has been suspended by an administrator."))
    return db.ok({"status": "SUSPENDED", "user": target.get("name", "")})


@router.post("/unsuspend")
def unsuspend(payload: dict, user=Depends(require_role(SUPREME))):
    uid = str((payload or {}).get("user_id") or "")
    target = db.first("users", "id, name", eq={"id": uid})
    if not target:
        raise db.NotFound("User not found")
    db.update("users", {"status": "ACTIVE", "suspended_by": None,
                        "suspended_at": None}, id=uid)
    db.audit(user["uid"], "user.unsuspend", "user", uid)
    from backend.routes.notifications import notify
    notify(db.client_or_none(), uid, ntype="SYSTEM",
           title="Account reactivated",
           message="Your account has been reactivated. Welcome back.")
    return db.ok({"status": "ACTIVE"})


@router.post("/role")
def change_role(payload: RoleChange, user=Depends(require_role(SUPREME))):
    """Promote/demote between the three roles."""
    target = db.first("users", "id, role, name", eq={"id": payload.user_id})
    if not target:
        raise db.NotFound("User not found")
    if payload.user_id == user["uid"] and payload.role != SUPREME:
        raise db.Rejected("You cannot demote yourself.")
    db.update("users", {"role": payload.role}, id=payload.user_id)
    db.audit(user["uid"], "user.role", "user", payload.user_id,
             {"from": target.get("role"), "to": payload.role})
    return db.ok({"role": payload.role})


@router.delete("/users/{user_id}")
def delete_user(user_id: str, user=Depends(require_role(SUPREME))):
    """Hard-delete an account: removes the auth user and the app row.

    Dependent rows cascade where the schema declares it; content the user
    authored (courses, assessments) is retained so learners keep their records.
    """
    target = db.first("users", "id, email, name, role", eq={"id": user_id})
    if not target:
        raise db.NotFound("User not found")
    if user_id == user["uid"]:
        raise db.Rejected("You cannot delete your own account.")

    # Remove from GoTrue first so the login cannot outlive the row.
    try:
        from backend.database.client import get_client
        client = get_client()
        if client is not None:
            listing = client.auth.admin.list_users()
            for u in getattr(listing, "users", []) or []:
                if (getattr(u, "email", "") or "").lower() == \
                        (target.get("email") or "").lower():
                    client.auth.admin.delete_user(u.id)
                    break
    except Exception:
        pass

    db.delete("users", id=user_id)
    db.audit(user["uid"], "user.delete", "user", user_id,
             {"email": target.get("email"), "role": target.get("role"),
              "content_retained": True})
    return db.ok({"deleted": True, "email": target.get("email")})


# ─── Account approval queue ───────────────────────────────────────────────
# A Trainer self-registers into `PENDING` and can sign in, but every
# role-gated route refuses them with ACCOUNT_PENDING_APPROVAL until an
# Administrator here says otherwise. Trainees are ACTIVE on registration, and
# Administrators never appear in this queue — they are admitted by invite
# instead.

class DecisionIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=60)
    reason: str = Field(default="", max_length=500)


@router.get("/pending")
def pending_users(user=Depends(require_role(SUPREME))):
    """Accounts waiting for a decision, oldest first."""
    rows, total = db.select(
        "users",
        "id, email, name, role, status, department, headline, created_at",
        eq={"status": "PENDING"}, order=("created_at", False),
        limit=200, count=True)
    return db.ok(rows, meta={"total": total or len(rows)})


@router.post("/approve")
def approve(payload: DecisionIn, user=Depends(require_role(SUPREME))):
    """Let a queued account in. The account becomes usable immediately."""
    target = db.first("users", "id, role, status, name, email",
                      eq={"id": payload.user_id})
    if not target:
        raise db.NotFound("User not found")
    if target.get("status") == "ACTIVE":
        raise db.Rejected("That account is already active.")
    if target.get("status") == "SUSPENDED":
        raise db.Rejected("That account is suspended — reactivate it instead.")

    db.update("users", {"status": "ACTIVE"}, id=payload.user_id)
    db.audit(user["uid"], "user.approve", "user", payload.user_id,
             {"name": target.get("name"), "email": target.get("email"),
              "role": target.get("role")})

    from backend.routes.notifications import notify
    notify(db.client_or_none(), payload.user_id, ntype="SYSTEM",
           title="Account approved",
           message="Your account has been approved. Welcome to Learnify.",
           link="/home")
    return db.ok({"status": "ACTIVE", "role": target.get("role")})


@router.post("/reject")
def reject_registration(payload: DecisionIn, user=Depends(require_role(SUPREME))):
    """Refuse a queued registration.

    The account is suspended rather than deleted: the decision stays in the
    audit trail and in `suspended_by`, and an Administrator can still reverse
    it if the person was turned away by mistake. A deletion would erase the
    reason along with the row.
    """
    target = db.first("users", "id, role, status, name, email",
                      eq={"id": payload.user_id})
    if not target:
        raise db.NotFound("User not found")
    if target.get("status") == "ACTIVE":
        raise db.Rejected("That account is already active — suspend it instead.")

    db.update("users", {"status": "SUSPENDED", "suspended_by": user["uid"],
                        "suspended_at": "now()"}, id=payload.user_id)
    db.audit(user["uid"], "user.reject", "user", payload.user_id,
             {"name": target.get("name"), "email": target.get("email"),
              "role": target.get("role"),
              "reason": payload.reason.strip()})

    from backend.routes.notifications import notify
    notify(db.client_or_none(), payload.user_id, ntype="SYSTEM",
           title="Registration not approved",
           message=(payload.reason.strip() or
                    "Your registration was not approved by an administrator. "
                    "Contact your administrator if you believe this is a mistake."))
    return db.ok({"status": "SUSPENDED"})


# ─── Administrator invitations ─────────────────────────────────────────────
# The only way to create another Administrator. An Administrator mints a
# token here and shares `#/supreme/signup?invite=<token>`; registration
# consumes one use of it (see backend/routes/auth.py::_reserve_invite).

class InviteIn(BaseModel):
    email: str = Field(default="", max_length=254)
    note: str = Field(default="", max_length=200)
    days: int = Field(default=7, ge=1, le=365)
    max_uses: int = Field(default=1, ge=1, le=500)


def _invite_state(inv: dict) -> str:
    """`active` · `exhausted` · `expired` · `revoked` — first match wins."""
    if inv.get("revoked_at"):
        return "revoked"
    exp = inv.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            if exp_dt <= datetime.datetime.now(datetime.timezone.utc):
                return "expired"
        except Exception:
            return "expired"
    if int(inv.get("used_count") or 0) >= int(inv.get("max_uses") or 1):
        return "exhausted"
    return "active"


@router.get("/invites")
def list_invites(user=Depends(require_role(SUPREME))):
    rows, total = db.select(
        "admin_invites",
        "token, email, note, created_by, created_at, expires_at, "
        "max_uses, used_count, revoked_at",
        order=("created_at", True), limit=200, count=True)
    out = [{**r, "state": _invite_state(r)} for r in rows]
    return db.ok(out, meta={"total": total or len(out)})


@router.post("/invites")
def create_invite(payload: InviteIn, user=Depends(require_role(SUPREME))):
    import secrets

    token = secrets.token_urlsafe(24)
    try:
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=payload.days)
        ).isoformat()
    except Exception:
        raise db.Rejected("Could not work out an expiry for that invite.")

    row = db.insert("admin_invites", {
        "token": token,
        "email": (payload.email or "").strip().lower(),
        "note": payload.note.strip(),
        "created_by": user["uid"],
        "expires_at": expires_at,
        "max_uses": payload.max_uses,
        "used_count": 0,
    })
    db.audit(user["uid"], "admin.invite.create", "admin_invite", token,
             {"email": row.get("email", ""), "max_uses": payload.max_uses,
              "days": payload.days})
    return db.ok({"token": row.get("token") or token,
                  "expires_at": row.get("expires_at") or expires_at,
                  "max_uses": payload.max_uses,
                  "email": row.get("email", "")})


@router.delete("/invites/{token}")
def revoke_invite(token: str, user=Depends(require_role(SUPREME))):
    """Kill a link that is out in the wild.

    Revoking is deliberately permanent — a token that can be un-revoked is a
    token an attacker can sit on until someone "revokes" it and then watches
    it come back.
    """
    existing = db.first("admin_invites", "token", eq={"token": token})
    if not existing:
        raise db.NotFound("Invite not found")
    db.update("admin_invites", {"revoked_at": "now()"}, token=token)
    db.audit(user["uid"], "admin.invite.revoke", "admin_invite", token)
    return db.ok({"revoked": True})


# ─── Notifications ─────────────────────────────────────────────────────────
# The console's "send a notification" screen.
#
# A notification is one row per recipient (`notifications.user_id`) rather
# than a single row with a NULL user: `/api/v1/notifications/my` filters on
# `user_id`, so a global row would be invisible to everybody and could never
# be marked read. Materialising the rows also buys per-person read state and
# `on delete cascade` — an account that goes away takes its notices with it.
#
# Two ways to choose who hears from you:
#   * an audience — a role/status filter resolved server-side, so the browser
#     never has to hold the whole user table to address "every trainee";
#   * `user_ids` — a hand-picked list, which wins over the audience. Exactly
#     who you picked is who gets it, whatever their status.

AUDIENCES = (
    ("ALL", "Everyone", "Every approved account, whatever the role."),
    ("ALPHA", "Trainees", "Approved trainees."),
    ("MASTER", "Trainers", "Approved trainers."),
    ("SUPREME", "Administrators", "Approved administrators."),
    ("PENDING", "Awaiting approval", "Accounts still waiting for a decision."),
)

# Matches TYPE_META in public/src/notifications.js — anything else would land
# on the recipient's bell with the generic "System" icon.
NOTIFY_TYPES = ("SYSTEM", "RELEASE", "ACHIEVEMENT", "FEEDBACK", "WARNING")

MAX_RECIPIENTS = 5000


class NotifyIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(default="", max_length=1000)
    link: str = Field(default="", max_length=300)
    # One source of truth for both the validation and the select options in
    # the composer: the pattern is derived from the same tuples the handler
    # reads, so a new audience cannot be added to one and forgotten in other.
    type: str = Field(default="SYSTEM",
                      pattern="^(" + "|".join(NOTIFY_TYPES) + ")$")
    audience: str = Field(default="ALL",
                          pattern="^(" + "|".join(a[0] for a in AUDIENCES) + ")$")
    # Typed, so a malformed entry is a 422 naming the field rather than a
    # stringified object quietly matching no one.
    user_ids: list[str] = Field(default_factory=list)


def _recipients(audience: str, user_ids: list) -> list[dict]:
    cols = "id, name, email, role, status"
    if user_ids:
        ids = list(dict.fromkeys(u for u in user_ids if u))
        rows, _ = db.select("users", cols, in_={"id": ids},
                            limit=MAX_RECIPIENTS)
        return rows
    eq = {"status": "PENDING"} if audience == "PENDING" else {"status": "ACTIVE"}
    if audience in ("ALPHA", "MASTER", "SUPREME"):
        eq["role"] = audience
    rows, _ = db.select("users", cols, eq=eq, limit=MAX_RECIPIENTS)
    return rows


@router.get("/notifications/audiences")
def notification_audiences(user=Depends(require_role(SUPREME))):
    """Reach of each audience, so the composer can say "this hits N people"
    before anything is written."""
    out = []
    for key, label, hint in AUDIENCES:
        if key == "ALL":
            n = db.count("users", status="ACTIVE")
        elif key == "PENDING":
            n = db.count("users", status="PENDING")
        else:
            n = db.count("users", role=key, status="ACTIVE")
        out.append({"key": key, "label": label, "hint": hint, "count": n})
    return db.ok(out)


@router.post("/notifications")
def send_notification(payload: NotifyIn, user=Depends(require_role(SUPREME))):
    """Fan a message out to an audience — or to the people you picked."""
    title = (payload.title or "").strip()
    message = (payload.message or "").strip()
    if not title:
        raise db.Rejected("A notification needs a title.")
    if not message:
        raise db.Rejected("A notification needs a message.")

    link = (payload.link or "").strip()
    if link and not (link.startswith(("/", "#/", "http://", "https://"))):
        raise db.Rejected(
            "The link must be a portal path such as /courses or an "
            "http(s) address.")

    ids = payload.user_ids or []
    if len(ids) > MAX_RECIPIENTS:
        raise db.Rejected(f"Pick at most {MAX_RECIPIENTS} people.")

    recipients = _recipients(payload.audience, ids)
    if not recipients:
        raise db.Rejected("Nobody matched that audience — nothing was sent.")

    target = "HAND_PICKED" if ids else payload.audience
    rows = [{
        "user_id": r["id"],
        "type": payload.type,
        "title": title,
        "message": message,
        "link": link or None,
        "read": False,
        "metadata": {"sent_by": user["uid"], "audience": target},
    } for r in recipients]

    sent = db.insert_many("notifications", rows)
    db.audit(user["uid"], "admin.notify.send", "notification", "",
             {"title": title, "type": payload.type, "audience": target,
              "sent": sent, "link": link})
    return db.ok({"sent": sent, "audience": target, "title": title,
                  "type": payload.type})


# ─── Audit ─────────────────────────────────────────────────────────────────
@router.get("/audit")
def audit_log(
    action: str = Query(default="", max_length=60),
    actor_id: str = Query(default="", max_length=60),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=10000),
    user=Depends(require_role(SUPREME)),
):
    eq: dict = {}
    if action:
        eq["action"] = action
    if actor_id:
        eq["actor_id"] = actor_id
    rows, total = db.select(
        "audit_logs",
        "id, actor_id, action, resource_type, resource_id, metadata, "
        "ip_address, created_at, users(name, email)",
        eq=eq or None, order=("created_at", True),
        limit=limit, count=True)
    out = []
    for r in rows:
        u = r.get("users") or {}
        if isinstance(u, list):
            u = u[0] if u else {}
        out.append({**r, "actor_name": u.get("name", ""),
                    "actor_email": u.get("email", ""), "users": None})
    return db.ok(out, meta={"total": total or len(out)})


@router.get("/stats")
def platform_stats(user=Depends(require_role(SUPREME))):
    """Lightweight numbers for widgets (separate from the big dashboard)."""
    result = {}
    for table, key in (("users", "users"), ("courses", "courses"),
                       ("assessments", "assessments"),
                       ("questionnaires", "questionnaires"),
                       ("certificates", "certificates"),
                       ("enrollments", "enrollments")):
        result[key] = db.count(table)
    return db.ok(result)
