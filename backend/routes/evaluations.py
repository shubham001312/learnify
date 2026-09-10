"""
Evaluation, completion, and credential verification.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from backend.middleware.rbac import (
    _extract_user,
    require_role,
    INDUSTRY,
    ACADEMICIAN,
    INSTITUTION_ADMIN,
)
from backend.database.client import db_available, get_client
from backend.services.cache import invalidate_pattern

router = APIRouter()


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


def _safe(client, table, columns="*", filters=None, order=None, limit=None):
    if not client:
        return []
    try:
        q = client.table(table).select(columns)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
        if order:
            q = q.order(order[0], desc=order[1] if len(order) > 1 else False)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    except Exception:
        return []


def _safe_insert(client, table, data):
    if not client:
        return None
    try:
        r = client.table(table).insert(data).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def _safe_update(client, table, data, filters):
    if not client:
        return False
    try:
        q = client.table(table).update(data)
        for col, op, val in filters:
            if op == "eq":
                q = q.eq(col, val)
        q.execute()
        return True
    except Exception:
        return False


def _compute_final_score(data):
    scores = [
        data.get("technical_skills", 0),
        data.get("problem_solving", 0),
        data.get("communication", 0),
        data.get("teamwork", 0),
        data.get("professionalism", 0),
        data.get("domain_knowledge", 0),
        data.get("initiative", 0),
        data.get("time_management", 0),
    ]
    return round(sum(scores) / max(len(scores), 1), 2)


# ─── Industry: Submit evaluation ─────────────────────────────
@router.post("/internships/{internship_id}/evaluate")
async def submit_evaluation(
    internship_id: str, data: dict, user=Depends(require_role(INDUSTRY))
):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    intern = _safe(
        client, "internships", "id, student_id", [("id", "eq", internship_id)], limit=1
    )
    if not intern:
        raise HTTPException(status_code=404, detail="Internship not found")

    final_score = _compute_final_score(data)

    result = _safe_insert(
        client,
        "evaluations",
        {
            "internship_id": internship_id,
            "student_id": intern[0]["student_id"],
            "evaluator_id": user["uid"],
            "technical_skills": data.get("technical_skills", 0),
            "problem_solving": data.get("problem_solving", 0),
            "communication": data.get("communication", 0),
            "teamwork": data.get("teamwork", 0),
            "professionalism": data.get("professionalism", 0),
            "domain_knowledge": data.get("domain_knowledge", 0),
            "initiative": data.get("initiative", 0),
            "time_management": data.get("time_management", 0),
            "overall_rating": data.get("overall_rating", final_score),
            "final_score": final_score,
            "strengths": data.get("strengths", ""),
            "areas_for_improvement": data.get("areas_for_improvement", ""),
            "recommendations": data.get("recommendations", ""),
            "would_recommend": data.get("would_recommend", True),
        },
    )

    if result:
        _safe_update(
            client,
            "internships",
            {"status": "COMPLETED", "completion_pct": 100},
            [("id", "eq", internship_id)],
        )
        invalidate_pattern(f"evaluations:{internship_id}")
        return {"status": "ok", "id": result["id"], "final_score": final_score}
    raise HTTPException(status_code=500, detail="Failed to submit evaluation")


# ─── Get evaluation for internship ───────────────────────────
@router.get("/internships/{internship_id}/evaluation")
async def get_evaluation(internship_id: str, user=Depends(_auth)):
    if not db_available():
        return None
    client = get_client()
    rows = _safe(
        client,
        "evaluations",
        "id, technical_skills, problem_solving, communication, teamwork, professionalism, domain_knowledge, initiative, time_management, overall_rating, final_score, strengths, areas_for_improvement, recommendations, would_recommend, created_at",
        [("internship_id", "eq", internship_id)],
        limit=1,
    )
    return rows[0] if rows else None


# ─── Student: My evaluations ─────────────────────────────────
@router.get("/evaluations/my")
async def my_evaluations(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    return _safe(
        client,
        "evaluations",
        "id, internship_id, final_score, overall_rating, strengths, areas_for_improvement, created_at",
        [("student_id", "eq", user["uid"])],
        order=("created_at", True),
    )


# ─── Request credential ──────────────────────────────────────
@router.post("/internships/{internship_id}/request-credential")
async def request_credential(internship_id: str, data: dict, user=Depends(_auth)):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()

    evals = _safe(
        client,
        "evaluations",
        "id, final_score",
        [("internship_id", "eq", internship_id)],
        limit=1,
    )
    if not evals:
        raise HTTPException(
            status_code=400, detail="Evaluation required before credential"
        )

    intern = _safe(
        client,
        "internships",
        "id, student_id, title, organization_id",
        [("id", "eq", internship_id)],
        limit=1,
    )
    if not intern:
        raise HTTPException(status_code=404, detail="Internship not found")

    result = _safe_insert(
        client,
        "credentials",
        {
            "internship_id": internship_id,
            "student_id": intern[0]["student_id"],
            "organization_id": intern[0].get("organization_id"),
            "credential_type": data.get("credential_type", "COMPLETION"),
            "title": data.get(
                "title", f"{intern[0].get('title', 'Internship')} Certificate"
            ),
            "final_score": evals[0].get("final_score", 0),
            "status": "PENDING",
        },
    )

    if result:
        return {"status": "ok", "id": result["id"]}
    raise HTTPException(status_code=500, detail="Failed to request credential")


# ─── Industry: Issue credential ──────────────────────────────
@router.post("/credentials/{credential_id}/issue")
async def issue_credential(credential_id: str, user=Depends(require_role(INDUSTRY))):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    _safe_update(
        client,
        "credentials",
        {"status": "ISSUED", "issued_at": "now()"},
        [("id", "eq", credential_id)],
    )
    return {"status": "ok"}


# ─── Verify credential ───────────────────────────────────────
@router.get("/credentials/{credential_id}/verify")
async def verify_credential(credential_id: str):
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
    client = get_client()
    rows = _safe(
        client,
        "credentials",
        "id, status, title, credential_type, final_score, issued_at, internship_id, student_id, organization_id",
        [("id", "eq", credential_id)],
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred = rows[0]
    return {
        "valid": cred.get("status") == "ISSUED",
        "credential_id": cred["id"],
        "title": cred.get("title"),
        "type": cred.get("credential_type"),
        "score": cred.get("final_score"),
        "issued_at": cred.get("issued_at"),
    }


# ─── Student: My credentials ─────────────────────────────────
@router.get("/credentials/my")
async def my_credentials(user=Depends(_auth)):
    if not db_available():
        return []
    client = get_client()
    rows = _safe(
        client,
        "credentials",
        "id, title, credential_type, final_score, status, issued_at, organization_id",
        [("student_id", "eq", user["uid"])],
        order=("issued_at", True),
    )
    org_ids = list(
        set(r.get("organization_id") for r in rows if r.get("organization_id"))
    )
    orgs = (
        _safe(client, "organizations", "id, name, logo_url", [("id", "in_", org_ids)])
        if org_ids
        else []
    )
    org_map = {o["id"]: o for o in orgs}
    for r in rows:
        o = org_map.get(r.get("organization_id"), {})
        r["organization_name"] = o.get("name", "")
        r["logo_url"] = o.get("logo_url")
    return rows
