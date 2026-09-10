"""
Skill-based matching engine for opportunities.

Uses Supabase client (same pattern as existing routes).
"""

from backend.database.client import db_available, get_client
from backend.services.cache import get as cache_get, set as cache_set

SIMILAR_SKILLS = {
    "python": ["python3", "fastapi", "django", "flask"],
    "javascript": ["react", "node", "typescript", "html", "css"],
    "react": ["nextjs", "javascript", "typescript", "redux"],
    "node": ["express", "javascript", "typescript"],
    "sql": ["postgresql", "mysql", "database"],
    "docker": ["kubernetes", "devops", "ci_cd"],
    "java": ["spring", "android", "kotlin"],
    "machine_learning": ["deep_learning", "tensorflow", "pytorch", "data_science"],
    "aws": ["cloud_computing", "gcp", "azure"],
    "flutter": ["dart", "mobile_development"],
    "typescript": ["javascript", "react", "node"],
    "postgresql": ["sql", "database", "backend"],
    "spring": ["java", "backend"],
    "nextjs": ["react", "javascript", "typescript"],
    "html": ["css", "javascript"],
    "css": ["html", "javascript"],
}


def _safe_select(client, table, columns="*", filters=None, limit=None):
    if not client:
        return []
    try:
        q = client.table(table).select(columns)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "like":
                    q = q.like(col, val)
                elif op == "gte":
                    q = q.gte(col, val)
                elif op == "lte":
                    q = q.lte(col, val)
                elif op == "in_":
                    q = q.in_(col, val)
        if limit:
            q = q.limit(limit)
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def _skill_overlap(user_skills, required_skills):
    user_set = {s.lower().strip() for s in user_skills}
    req_set = {s.lower().strip() for s in required_skills}
    matched = set()
    for u in user_set:
        for r in req_set:
            if u == r:
                matched.add(r)
            elif r in SIMILAR_SKILLS.get(u, []):
                matched.add(r)
            elif u in SIMILAR_SKILLS.get(r, []):
                matched.add(r)
    return matched, len(matched) / max(len(req_set), 1)


def match_student_opportunity(user_id, opportunity_id):
    cached = cache_get(f"learnify:match:{user_id}:{opportunity_id}")
    if cached:
        return cached

    if not db_available():
        return {
            "user_id": user_id,
            "opportunity_id": opportunity_id,
            "total_score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
            "reasons": [],
        }

    client = get_client()

    user_skill_rows = _safe_select(
        client,
        "user_skills",
        "skill_id",
        [("user_id", "eq", user_id), ("is_active", "eq", True)],
    )
    user_skill_ids = [r["skill_id"] for r in user_skill_rows]
    user_skill_names = []
    if user_skill_ids:
        names = _safe_select(client, "skills", "name", [("id", "in_", user_skill_ids)])
        user_skill_names = [n["name"] for n in names]

    opp_skill_rows = _safe_select(
        client,
        "opportunity_skills",
        "skill_id",
        [("opportunity_id", "eq", opportunity_id)],
    )
    opp_skill_ids = [r["skill_id"] for r in opp_skill_rows]
    opp_skill_names = []
    if opp_skill_ids:
        names = _safe_select(client, "skills", "name", [("id", "in_", opp_skill_ids)])
        opp_skill_names = [n["name"] for n in names]

    matched, skill_score = _skill_overlap(user_skill_names, opp_skill_names)

    opportunity = _safe_select(
        client,
        "opportunities",
        "min_gpa, location, remote_allowed, required_level",
        [("id", "eq", opportunity_id)],
        limit=1,
    )

    eligibility_score = 1.0
    if opportunity and opportunity[0].get("min_gpa"):
        gpa_row = _safe_select(
            client, "students", "gpa", [("user_id", "eq", user_id)], limit=1
        )
        if gpa_row:
            eligibility_score = (
                1.0
                if (gpa_row[0].get("gpa") or 0) >= opportunity[0]["min_gpa"]
                else 0.0
            )

    missing = set(n.lower() for n in opp_skill_names) - matched

    reasons = []
    if matched:
        reasons.append(f"Matched skills: {', '.join(matched)}")
    if missing:
        reasons.append(f"Missing skills: {', '.join(missing)}")

    total_score = skill_score * 0.7 + eligibility_score * 0.3

    result = {
        "user_id": user_id,
        "opportunity_id": opportunity_id,
        "total_score": round(total_score, 2),
        "skill_score": round(skill_score, 2),
        "eligibility_score": eligibility_score,
        "matched_skills": list(matched),
        "missing_skills": list(missing),
        "reasons": reasons,
    }

    cache_set(f"learnify:match:{user_id}:{opportunity_id}", result, 1800)
    return result


def rank_opportunities(user_id, limit=10):
    cached = cache_get(f"learnify:rank_opps:{user_id}")
    if cached:
        return cached

    if not db_available():
        return []

    client = get_client()

    opps = _safe_select(
        client,
        "opportunities",
        "id, title, type, location, remote_allowed",
        [("status", "eq", "OPEN")],
        limit=50,
    )

    results = []
    for opp in opps:
        match = match_student_opportunity(user_id, opp["id"])
        results.append(
            {
                "opportunity_id": opp["id"],
                "title": opp.get("title", ""),
                "type": opp.get("type", ""),
                "location": opp.get("location", ""),
                "remote_allowed": opp.get("remote_allowed", False),
                "match_score": match["total_score"],
                "matched_skills": match["matched_skills"],
                "missing_skills": match["missing_skills"],
            }
        )

    results.sort(key=lambda x: x["match_score"], reverse=True)
    results = results[:limit]
    cache_set(f"learnify:rank_opps:{user_id}", results, 1800)
    return results
