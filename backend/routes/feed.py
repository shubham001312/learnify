"""Home feed — 4 post types, published by Supreme.

    NOTIFICATION   operational notices
    ANNOUNCEMENT   general broadcast
    ACHIEVEMENT    certificates / completions (also written by assessments.py)
    NEW_CONTENT    a course, questionnaire, assessment or library item released

Posts carry `target_roles` so Supreme can address one role or all three, and
`pinned` puts an item at the top of every eligible feed.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/feed", tags=["feed"])

POST_TYPES = ("NOTIFICATION", "ANNOUNCEMENT", "ACHIEVEMENT", "NEW_CONTENT")
ALL_ROLES = ["SUPREME", "MASTER", "ALPHA"]


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class PostIn(BaseModel):
    type: str = Field(pattern="^(NOTIFICATION|ANNOUNCEMENT|ACHIEVEMENT|NEW_CONTENT)$")
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(default="", max_length=4000)
    link: str = Field(default="", max_length=400)
    image_url: str = Field(default="", max_length=600)
    target_roles: list[str] = Field(default=ALL_ROLES, max_length=3)
    pinned: bool = False
    published: bool = True


class PostUpdate(PostIn):
    pass


# ─── Read ──────────────────────────────────────────────────────────────────
@router.get("")
def my_feed(
    post_type: str = Query(default="", max_length=30),
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=5000),
    user=Depends(_auth),
):
    """Pinned first, then newest — filtered to this caller's role."""
    if not db.db_available():
        return db.ok([], meta={"total": 0})

    rows, total = db.select(
        "home_posts", "*", eq={"published": True},
        order=("published_at", True), limit=1000, count=True)

    visible = []
    for r in rows:
        roles = r.get("target_roles") or ALL_ROLES
        if user["role"] not in roles:
            continue
        if post_type and r.get("type") != post_type:
            continue
        if q:
            ql = q.lower()
            if ql not in (r.get("title", "") or "").lower() \
                    and ql not in (r.get("body", "") or "").lower():
                continue
        visible.append(r)

    # Newest first, but anything pinned jumps to the top of its own group.
    visible.sort(key=lambda r: _ts(r.get("published_at")), reverse=True)
    visible.sort(key=lambda r: 0 if r.get("pinned") else 1)

    page = visible[offset:offset + limit]
    return db.ok(page, meta={"total": len(visible),
                             "for_role": user["role"]})


def _ts(value: Optional[str]) -> float:
    """Epoch seconds for ordering; unknown/absent timestamps sort last."""
    if not value:
        return 0.0
    try:
        from datetime import datetime
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


@router.get("/types")
def post_types(user=Depends(_auth)):
    return db.ok(list(POST_TYPES))


@router.get("/{post_id}")
def get_post(post_id: str, user=Depends(_auth)):
    row = db.first("home_posts", "*", eq={"id": post_id})
    if not row:
        raise db.NotFound("Post not found")
    roles = row.get("target_roles") or ALL_ROLES
    if user["role"] not in roles and user["role"] != SUPREME:
        raise db.NotFound("Post not found")
    return db.ok(row)


# ─── Write (Supreme only) ──────────────────────────────────────────────────
@router.post("")
def create_post(payload: PostIn, user=Depends(require_role(SUPREME))):
    roles = [r for r in (payload.target_roles or ALL_ROLES)
             if r in ALL_ROLES] or ALL_ROLES
    row = db.insert("home_posts", {
        "type": payload.type,
        "title": payload.title.strip(),
        "body": payload.body.strip(),
        "link": payload.link.strip() or None,
        "image_url": payload.image_url.strip() or None,
        "target_roles": roles,
        "pinned": payload.pinned,
        "published": payload.published,
        "published_by": user["uid"],
        "published_at": "now()",
    })
    db.audit(user["uid"], "feed.create", "home_post", row.get("id"),
             {"type": payload.type, "roles": roles, "pinned": payload.pinned})
    return db.ok(row)


@router.put("/{post_id}")
def update_post(post_id: str, payload: PostUpdate,
                user=Depends(require_role(SUPREME))):
    if not db.first("home_posts", "id", eq={"id": post_id}):
        raise db.NotFound("Post not found")
    roles = [r for r in (payload.target_roles or ALL_ROLES)
             if r in ALL_ROLES] or ALL_ROLES
    rows = db.update("home_posts", {
        "type": payload.type,
        "title": payload.title.strip(),
        "body": payload.body.strip(),
        "link": payload.link.strip() or None,
        "image_url": payload.image_url.strip() or None,
        "target_roles": roles,
        "pinned": payload.pinned,
        "published": payload.published,
    }, id=post_id)
    db.audit(user["uid"], "feed.update", "home_post", post_id)
    return db.ok(rows[0] if rows else None)


@router.delete("/{post_id}")
def delete_post(post_id: str, user=Depends(require_role(SUPREME))):
    if not db.first("home_posts", "id", eq={"id": post_id}):
        raise db.NotFound("Post not found")
    db.delete("home_posts", id=post_id)
    db.audit(user["uid"], "feed.delete", "home_post", post_id)
    return db.ok({"deleted": True})


@router.post("/{post_id}/pin")
def toggle_pin(post_id: str, user=Depends(require_role(SUPREME))):
    row = db.first("home_posts", "id, pinned", eq={"id": post_id})
    if not row:
        raise db.NotFound("Post not found")
    rows = db.update("home_posts", {"pinned": not row.get("pinned")}, id=post_id)
    return db.ok({"pinned": bool((rows[0] if rows else {}).get("pinned"))})


# ─── Management ────────────────────────────────────────────────────────────
@router.get("/all/manage")
def manage_list(
    post_type: str = Query(default="", max_length=30),
    limit: int = Query(default=100, ge=1, le=300),
    user=Depends(require_role(SUPREME)),
):
    """Supreme's own view — includes drafts and every role target."""
    eq: dict = {}
    if post_type:
        eq["type"] = post_type
    rows, total = db.select("home_posts", "*", eq=eq or None,
                            order=("published_at", True), limit=limit,
                            count=True)
    return db.ok(rows, meta={"total": total or len(rows)})


def announce_new_content(title: str, body: str, link: str = "",
                         roles: Optional[list] = None) -> None:
    """Convenience used by release flows (courses/tests/library)."""
    try:
        db.insert("home_posts", {
            "type": "NEW_CONTENT", "title": title[:200], "body": body[:4000],
            "link": link or None,
            "target_roles": roles or ALL_ROLES,
            "published": True, "pinned": False,
            "published_by": None, "published_at": "now()",
        })
    except db.Rejected:
        pass
