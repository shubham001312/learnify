"""Competency mapping.

Deterministic, explainable trainer ranking per subject — no AI involved, so the
same inputs always produce the same order and the UI can show *why* a trainer
ranked where they did.

Ranking formula (all terms documented in `explanation`):
    score = Σ( weight_t × proficiency_t )  /  Σ( weight_t )        [0..100]
          + verified bonus (each verified competency: +2, capped +10)
          + evidence bonus (+1 if any competency carries evidence)
    coverage = matched_competencies / required_competencies
    rank is by score desc, then coverage desc, then trainer name asc.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from backend.middleware.rbac import MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/competency", tags=["competency"])

VERIFIED_BONUS = 2
VERIFIED_CAP = 10
EVIDENCE_BONUS = 1


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class SelfAssessIn(BaseModel):
    """Trainer declaring proficiency against one competency."""

    competency_id: str
    proficiency: int = Field(ge=0, le=100)
    evidence: str = Field(default="", max_length=400)


class SelfAssessBulk(BaseModel):
    items: list[SelfAssessIn] = Field(default=[], max_length=100)


class VerifyIn(BaseModel):
    trainer_id: str
    competency_id: str
    verified: bool = True


# ─── Ranking engine ────────────────────────────────────────────────────────
def rank_trainers(subject_id: str, limit: int = 20) -> list[dict]:
    """Rank trainers for a subject. Deterministic and fully explainable."""
    if not db.first("subjects", "id", eq={"id": subject_id}):
        raise db.NotFound("Subject not found")

    requirements, _ = db.select(
        "subject_competencies",
        "competency_id, required_weight",
        eq={"subject_id": subject_id},
    )
    if not requirements:
        # No declared requirements — fall back to a plain, stable ordering by
        # verified-competency count so the list is never empty or arbitrary.
        return _fallback_ranking(subject_id, limit)

    req_map = {r["competency_id"]: float(r.get("required_weight") or 1) for r in requirements}
    required_ids = list(req_map)
    total_weight = sum(req_map.values()) or 1.0

    trainers, _ = db.select(
        "users",
        "id, name, role, designation, department, headline, avatar_url",
        eq={"role": "MASTER", "status": "ACTIVE"},
        order=("name", False),
        limit=500,
    )
    profs, _ = db.select(
        "trainer_competencies",
        "trainer_id, competency_id, proficiency, evidence, verified_by, verified_at",
        eq=None,
        limit=5000,
    )

    by_trainer: dict[str, list[dict]] = {}
    for p in profs:
        by_trainer.setdefault(p["trainer_id"], []).append(p)

    ranked = []
    for t in trainers:
        entries = by_trainer.get(t["id"], [])
        mine = {e["competency_id"]: e for e in entries if e["competency_id"] in req_map}

        matched = 0
        weighted_sum = 0.0
        verified_count = 0
        has_evidence = False
        reasons = []

        for cid, weight in req_map.items():
            e = mine.get(cid)
            if not e:
                continue
            matched += 1
            prof = float(e.get("proficiency") or 0)
            weighted_sum += weight * prof
            if e.get("verified_by"):
                verified_count += 1
                reasons.append(f"{_cname(cid, subject_id)} verified")
            if (e.get("evidence") or "").strip():
                has_evidence = True

        coverage = matched / len(required_ids) if required_ids else 0.0
        base = weighted_sum / total_weight if total_weight else 0.0

        bonus = min(verified_count * VERIFIED_BONUS, VERIFIED_CAP)
        if has_evidence:
            bonus += EVIDENCE_BONUS
        score = min(100.0, round(base + bonus, 1))

        if coverage == 0:
            continue  # trainer has no overlap with this subject at all

        reasons.insert(
            0,
            f"{matched}/{len(required_ids)} required competencies "
            f"({coverage * 100:.0f}% coverage)",
        )
        if verified_count:
            reasons.append(f"{verified_count} verified (+{bonus} pts)")

        ranked.append({
            **t,
            "score": score,
            "coverage": round(coverage * 100, 1),
            "matched": matched,
            "required": len(required_ids),
            "verified": verified_count,
            "explanation": reasons,
        })

    ranked.sort(key=lambda r: (-r["score"], -r["coverage"], (r.get("name") or "").lower()))
    return ranked[:limit]


def _cname(cid: str, subject_id: str) -> str:
    row = db.first("competencies", "name", eq={"id": cid})
    if row:
        return row.get("name", "")
    link = db.first("subject_competencies", "competency_id",
                    eq={"subject_id": subject_id, "competency_id": cid})
    return link.get("competency_id", "")[:8]


def _fallback_ranking(subject_id: str, limit: int) -> list[dict]:
    """No requirements declared — order by raw verified-competency strength."""
    trainers, _ = db.select(
        "users",
        "id, name, role, designation, department, headline, avatar_url",
        eq={"role": "MASTER", "status": "ACTIVE"},
        order=("name", False), limit=500,
    )
    profs, _ = db.select(
        "trainer_competencies",
        "trainer_id, competency_id, proficiency, evidence, verified_by",
        limit=5000,
    )
    by_trainer: dict[str, list[dict]] = {}
    for p in profs:
        by_trainer.setdefault(p["trainer_id"], []).append(p)

    ranked = []
    for t in trainers:
        entries = by_trainer.get(t["id"], [])
        if not entries:
            continue
        avg = sum(float(e.get("proficiency") or 0) for e in entries) / len(entries)
        verified = sum(1 for e in entries if e.get("verified_by"))
        ranked.append({
            **t,
            "score": min(100.0, round(avg + min(verified * VERIFIED_BONUS, VERIFIED_CAP), 1)),
            "coverage": 0.0,
            "matched": len(entries),
            "required": 0,
            "verified": verified,
            "explanation": [
                f"No competency requirements published for this subject yet.",
                f"{len(entries)} competencies self-declared (avg {avg:.0f}%)",
            ],
        })
    ranked.sort(key=lambda r: (-r["score"], (r.get("name") or "").lower()))
    return ranked[:limit]


# ─── Routes ────────────────────────────────────────────────────────────────
@router.get("/trainers/{subject_id}")
def ranked_trainers(subject_id: str,
                    limit: int = Query(default=20, ge=1, le=100),
                    user=Depends(_auth)):
    """Ranked trainer matches for a subject (any authenticated user)."""
    return db.ok(rank_trainers(subject_id, limit))


@router.get("/mine")
def my_competencies(user=Depends(_auth)):
    """The caller's declared + verified competencies, with names."""
    rows, _ = db.select(
        "trainer_competencies",
        "trainer_id, competency_id, proficiency, evidence, verified_by, "
        "verified_at, updated_at, competencies(name, description)",
        eq={"trainer_id": user["uid"]},
    )
    flat = []
    for r in rows:
        emb = r.get("competencies") or {}
        if isinstance(emb, list):
            emb = emb[0] if emb else {}
        flat.append({
            "competency_id": r["competency_id"],
            "name": emb.get("name", ""),
            "description": emb.get("description", ""),
            "proficiency": r.get("proficiency", 0),
            "evidence": r.get("evidence", ""),
            "verified": bool(r.get("verified_by")),
            "verified_at": r.get("verified_at"),
        })
    flat.sort(key=lambda x: (-float(x["proficiency"]), x["name"].lower()))
    return db.ok(flat)


@router.get("/catalog")
def catalog(user=Depends(_auth)):
    """Every competency, grouped by the subjects that require it."""
    comps, _ = db.select("competencies", "*", order=("name", False), limit=500)
    links, _ = db.select("subject_competencies",
                         "subject_id, competency_id, required_weight", limit=1000)
    subjects, _ = db.select("subjects", "id, code, name", order=("name", False), limit=500)

    subj_by_id = {s["id"]: s for s in subjects}
    by_comp: dict[str, list] = {}
    for l in links:
        by_comp.setdefault(l["competency_id"], []).append(
            {"subject_id": l["subject_id"],
             "subject": subj_by_id.get(l["subject_id"], {}).get("name", ""),
             "weight": l.get("required_weight", 1)}
        )
    for c in comps:
        c["required_by"] = by_comp.get(c["id"], [])
    return db.ok(comps)


@router.put("/mine")
def upsert_self(payload: SelfAssessBulk, user=Depends(_auth)):
    """Trainer maintains their own competencies (proficiency + evidence)."""
    saved = []
    for item in payload.items[:100]:
        if not db.first("competencies", "id", eq={"id": item.competency_id}):
            continue
        try:
            db.upsert("trainer_competencies", {
                "trainer_id": user["uid"],
                "competency_id": item.competency_id,
                "proficiency": item.proficiency,
                "evidence": item.evidence.strip(),
            }, "trainer_id,competency_id")
            saved.append(item.competency_id)
        except db.Rejected:
            continue
    db.audit(user["uid"], "competency.self_update", "competency", "", {"n": len(saved)})
    return db.ok({"saved": saved, "count": len(saved)})


@router.delete("/mine/{competency_id}")
def remove_self(competency_id: str, user=Depends(_auth)):
    db.delete("trainer_competencies", trainer_id=user["uid"],
              competency_id=competency_id)
    return db.ok({"deleted": True})


@router.post("/verify")
def verify_competency(payload: VerifyIn, user=Depends(require_role(SUPREME))):
    """Supreme confirms a trainer's claimed competency (counts toward ranking)."""
    if not db.first("users", "id", eq={"id": payload.trainer_id}):
        raise db.NotFound("Trainer not found")
    if not db.first("competencies", "id", eq={"id": payload.competency_id}):
        raise db.NotFound("Competency not found")

    existing = db.first("trainer_competencies",
                        "trainer_id, competency_id, proficiency, evidence",
                        eq={"trainer_id": payload.trainer_id,
                            "competency_id": payload.competency_id})
    if not existing:
        raise db.NotFound(
            "Trainer has not declared this competency yet. Ask them to add it first."
        )

    if payload.verified:
        db.update("trainer_competencies",
                  {"verified_by": user["uid"], "verified_at": "now()"},
                  trainer_id=payload.trainer_id,
                  competency_id=payload.competency_id)
    else:
        db.update("trainer_competencies",
                  {"verified_by": None, "verified_at": None},
                  trainer_id=payload.trainer_id,
                  competency_id=payload.competency_id)

    db.audit(user["uid"], "competency.verify" if payload.verified
             else "competency.unverify", "competency", payload.competency_id,
             {"trainer": payload.trainer_id})
    return db.ok({"verified": payload.verified})


@router.get("/trainers/{trainer_id}/profile")
def trainer_competency_profile(trainer_id: str,
                               user=Depends(require_role(MASTER, SUPREME))):
    """Full competency breakdown for one trainer (for the review view)."""
    trainer = db.first("users",
                       "id, name, role, designation, department, headline",
                       eq={"id": trainer_id, "role": "MASTER"})
    if not trainer:
        raise db.NotFound("Trainer not found")
    rows, _ = db.select(
        "trainer_competencies",
        "competency_id, proficiency, evidence, verified_by, verified_at, "
        "competencies(name, description)",
        eq={"trainer_id": trainer_id},
    )
    flat = []
    for r in rows:
        emb = r.get("competencies") or {}
        if isinstance(emb, list):
            emb = emb[0] if emb else {}
        flat.append({
            "competency_id": r["competency_id"],
            "name": emb.get("name", ""),
            "description": emb.get("description", ""),
            "proficiency": r.get("proficiency", 0),
            "evidence": r.get("evidence", ""),
            "verified": bool(r.get("verified_by")),
            "verified_at": r.get("verified_at"),
        })
    flat.sort(key=lambda x: (-float(x["proficiency"]), x["name"].lower()))
    verified = sum(1 for f in flat if f["verified"])
    return db.ok({"trainer": trainer, "competencies": flat,
                  "verified_count": verified, "total": len(flat)})
