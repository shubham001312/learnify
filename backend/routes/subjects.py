"""Subjects, topics and competency taxonomy.

Subjects are the backbone: courses, questionnaires, assessments, benchmarks
and competency mapping all key off them.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/subjects", tags=["subjects"])


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class SubjectIn(BaseModel):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=1000)


class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class TopicBulk(BaseModel):
    names: list[str] = Field(default=[], max_length=100)


class CompetencyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class LinkCompetency(BaseModel):
    competency_id: str
    required_weight: float = Field(default=1.0, gt=0, le=10)


@router.get("")
def list_subjects(
    q: str = Query(default="", max_length=80),
    active_only: bool = True,
    user=Depends(_auth),
):
    filters = {"is_active": True} if active_only else {}
    rows, total = db.select("subjects", "*", eq=filters or None, order=("name", False),
                            limit=500, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows
                if ql in (r.get("name", "") or "").lower()
                or ql in (r.get("code", "") or "").lower()
                or ql in (r.get("category", "") or "").lower()]
    return db.ok(rows, meta={"total": total or len(rows)})


@router.get("/with-topics")
def subjects_with_topics(user=Depends(_auth)):
    """All subjects plus their curated topic lists — used by the question
    builders so every question can carry a topic tag."""
    subjects, _ = db.select("subjects", "*", eq={"is_active": True},
                            order=("name", False), limit=500)
    topics, _ = db.select("subject_topics", "*", order=("sort_order", False),
                          limit=2000)
    by_subject: dict[str, list] = {}
    for t in topics:
        by_subject.setdefault(t["subject_id"], []).append(t)
    for s in subjects:
        s["topics"] = by_subject.get(s["id"], [])
    return db.ok(subjects)


def _name_taken(name: str, except_id: str = "") -> bool:
    """Case-insensitive duplicate check against subjects.name (trimmed).

    PostgREST cannot filter on lower(name), so the (small) subject list is
    scanned in Python — the same way list_subjects() searches it.
    """
    needle = (name or "").strip().lower()
    if not needle:
        return False
    rows, _ = db.select("subjects", "id, name", limit=1000)
    return any((r.get("name") or "").strip().lower() == needle
               and r.get("id") != except_id
               for r in rows)


@router.post("")
def create_subject(payload: SubjectIn, user=Depends(require_role(MASTER, SUPREME))):
    code = payload.code.strip().upper()
    if db.first("subjects", "id", eq={"code": code}):
        raise db.Rejected(f"Subject code '{code}' already exists.")
    name = payload.name.strip()
    if _name_taken(name):
        raise db.Rejected(f"A subject named '{name}' already exists.")
    row = db.insert("subjects", {
        "code": code, "name": name,
        "category": payload.category.strip(),
        "description": payload.description.strip(), "is_active": True,
    })
    db.audit(user["uid"], "subject.create", "subject", row.get("id"))
    return db.ok(row)


@router.put("/{subject_id}")
def update_subject(subject_id: str, payload: SubjectIn,
                   user=Depends(require_role(MASTER, SUPREME))):
    db.first("subjects", "id", eq={"id": subject_id}) or (_raise_404())
    name = payload.name.strip()
    if _name_taken(name, except_id=subject_id):
        raise db.Rejected(f"A subject named '{name}' already exists.")
    row = db.update("subjects", {
        "code": payload.code.strip().upper(), "name": name,
        "category": payload.category.strip(),
        "description": payload.description.strip(),
    }, id=subject_id)
    db.audit(user["uid"], "subject.update", "subject", subject_id)
    return db.ok(row[0] if row else None)


@router.delete("/{subject_id}")
def delete_subject(subject_id: str, user=Depends(require_role(SUPREME))):
    """Archive rather than hard-delete: courses/assessments may reference it."""
    db.update("subjects", {"is_active": False}, id=subject_id)
    db.audit(user["uid"], "subject.archive", "subject", subject_id)
    return db.ok({"archived": True})


def _raise_404():
    raise db.NotFound("Subject not found")


# ─── Topics ────────────────────────────────────────────────────────────────
@router.get("/{subject_id}/topics")
def list_topics(subject_id: str, user=Depends(_auth)):
    rows, _ = db.select("subject_topics", "*", eq={"subject_id": subject_id},
                        order=("sort_order", False), limit=200)
    return db.ok(rows)


@router.post("/{subject_id}/topics")
def add_topic(subject_id: str, payload: TopicIn,
              user=Depends(require_role(MASTER, SUPREME))):
    if not db.first("subjects", "id", eq={"id": subject_id}):
        raise db.NotFound("Subject not found")
    if db.first("subject_topics", "id",
                eq={"subject_id": subject_id, "name": payload.name.strip()}):
        raise db.Rejected("Topic already exists for this subject.")
    rows, _ = db.select("subject_topics", "id", eq={"subject_id": subject_id})
    row = db.insert("subject_topics", {
        "subject_id": subject_id, "name": payload.name.strip(),
        "description": payload.description.strip(), "sort_order": len(rows),
    })
    return db.ok(row)


@router.post("/{subject_id}/topics/bulk")
def add_topics_bulk(subject_id: str, payload: TopicBulk,
                    user=Depends(require_role(MASTER, SUPREME))):
    """Seed a curated topic list in one call (used by the setup wizard)."""
    if not db.first("subjects", "id", eq={"id": subject_id}):
        raise db.NotFound("Subject not found")
    existing, _ = db.select("subject_topics", "name",
                            eq={"subject_id": subject_id})
    # PostgREST returns row objects even for a single-column select, so each
    # entry is {"name": ...} — reading it as a bare string raises on a subject
    # that already has topics.
    seen = {(r.get("name") or "").strip().lower() for r in existing}
    rows, _ = db.select("subject_topics", "id", eq={"subject_id": subject_id})
    order = len(rows)
    added = []
    for raw in payload.names[:100]:
        name = str(raw).strip()[:120]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        db.insert("subject_topics", {"subject_id": subject_id, "name": name,
                                     "description": "", "sort_order": order})
        order += 1
        added.append(name)
    return db.ok({"added": added, "count": len(added)})


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str, user=Depends(require_role(MASTER, SUPREME))):
    db.delete("subject_topics", id=topic_id)
    return db.ok({"deleted": True})


# ─── Competencies ──────────────────────────────────────────────────────────
@router.get("/{subject_id}/competencies")
def list_subject_competencies(subject_id: str, user=Depends(_auth)):
    rows, _ = db.select(
        "subject_competencies",
        "subject_id, competency_id, required_weight, competencies(name, description)",
        eq={"subject_id": subject_id},
    )
    # PostgREST embeds rows as `competencies`; flatten for the UI.
    flat = []
    for r in rows:
        emb = r.get("competencies") or {}
        if isinstance(emb, list):
            emb = emb[0] if emb else {}
        flat.append({
            "competency_id": r["competency_id"],
            "required_weight": r.get("required_weight", 1),
            "name": emb.get("name", ""),
            "description": emb.get("description", ""),
        })
    return db.ok(flat)


@router.post("/competencies")
def create_competency(payload: CompetencyIn,
                      user=Depends(require_role(MASTER, SUPREME))):
    name = payload.name.strip()
    if db.first("competencies", "id", eq={"name": name}):
        raise db.Rejected(f"Competency '{name}' already exists.")
    row = db.insert("competencies", {"name": name,
                                     "description": payload.description.strip()})
    return db.ok(row)


@router.post("/{subject_id}/competencies")
def link_competency(subject_id: str, payload: LinkCompetency,
                    user=Depends(require_role(MASTER, SUPREME))):
    if not db.first("subjects", "id", eq={"id": subject_id}):
        raise db.NotFound("Subject not found")
    row = db.upsert("subject_competencies", {
        "subject_id": subject_id, "competency_id": payload.competency_id,
        "required_weight": payload.required_weight,
    }, "subject_id,competency_id")
    return db.ok(row)


@router.delete("/{subject_id}/competencies/{competency_id}")
def unlink_competency(subject_id: str, competency_id: str,
                      user=Depends(require_role(MASTER, SUPREME))):
    db.delete("subject_competencies", subject_id=subject_id,
              competency_id=competency_id)
    return db.ok({"deleted": True})
