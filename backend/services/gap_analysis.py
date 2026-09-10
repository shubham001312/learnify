"""
Skill gap analysis and career readiness scoring.

Uses Supabase client (same pattern as existing routes).
"""

from backend.database.client import db_available, get_client
from backend.services.cache import (
    get as cache_get,
    set as cache_set,
    invalidate_pattern,
)

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
    "postgis": ["spatial_data", "geographic_information_systems"],
    "arcgis": ["gis", "spatial_analysis"],
    "machinelearning": ["deep_learning", "ai", "data_science"],
    "postgresql": ["sql", "database", "backend"],
    "spring": ["java", "backend"],
    "nextjs": ["react", "javascript", "typescript"],
    "flutter": ["dart", "mobile_development"],
    "postman": ["api", "rest_api"],
    "figma": ["ui_design", "ux_design"],
    "video_editing": ["creative", "media"],
}


def _expand_skills(skills):
    expanded = set()
    for skill in skills:
        expanded.add(skill.lower().strip())
        for alias in SIMILAR_SKILLS.get(skill.lower().strip(), []):
            expanded.add(alias)
    return expanded


def _safe_select(client, table, columns="*", filters=None, limit=None):
    """Safe Supabase select that returns [] on error."""
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


def get_gaps(user_id):
    cached = cache_get(f"learnify:gap_analysis:{user_id}")
    if cached:
        return cached

    if not db_available():
        return {"user_id": user_id, "skills": [], "gaps": [], "career": None}

    client = get_client()

    skill_rows = _safe_select(
        client,
        "user_skills",
        "skill_id, level, confidence",
        [("user_id", "eq", user_id), ("is_active", "eq", True)],
    )

    user_skills = []
    if skill_rows:
        skill_ids = [r["skill_id"] for r in skill_rows]
        skill_names = _safe_select(
            client, "skills", "id, name, category_id", [("id", "in_", skill_ids)]
        )
        name_map = {s["id"]: s for s in skill_names}
        for r in skill_rows:
            s = name_map.get(r["skill_id"], {})
            user_skills.append(
                {
                    "name": s.get("name", ""),
                    "level": r.get("level", "BEGINNER"),
                    "confidence": r.get("confidence", 0.0),
                }
            )

    user_level = "INTERMEDIATE"
    roles = _safe_select(client, "user_roles", "role", [("user_id", "eq", user_id)])
    for role_row in roles:
        role_name = role_row.get("role", "")
        if role_name in ("INDUSTRY", "ACADEMICIAN", "INSTITUTION_ADMIN"):
            user_level = "ADVANCED"
            break
        elif role_name == "STUDENT":
            progress = _safe_select(
                client, "learning_progress", "progress", [("user_id", "eq", user_id)]
            )
            completed = [
                p["progress"]
                for p in progress
                if p.get("progress") and float(p["progress"]) >= 0.8
            ]
            if len(completed) >= 5:
                user_level = "ADVANCED"
            elif len(completed) >= 2:
                user_level = "INTERMEDIATE"
            else:
                user_level = "BEGINNER"

    career_id = None
    for role_row in roles:
        if role_row.get("role") == "STUDENT":
            interest = _safe_select(
                client,
                "student_interests",
                "career_role_id",
                [("user_id", "eq", user_id)],
                limit=1,
            )
            if interest:
                career_id = interest[0].get("career_role_id")
            break

    if not career_id:
        careers = _safe_select(
            client,
            "career_roles",
            "id",
            [("is_active", "eq", True)],
            limit=1,
        )
        if careers:
            career_id = careers[0].get("id")

    if not career_id:
        return {"user_id": user_id, "skills": user_skills, "gaps": [], "career": None}

    career_info = _safe_select(
        client,
        "career_roles",
        "id, title, description, required_level",
        [("id", "eq", career_id)],
        limit=1,
    )

    required_skills = _safe_select(
        client,
        "role_skills",
        "skill_id, importance_weight",
        [("career_role_id", "eq", career_id), ("is_active", "eq", True)],
    )

    if not required_skills:
        return {
            "user_id": user_id,
            "skills": user_skills,
            "gaps": [],
            "career": career_info[0] if career_info else None,
        }

    req_skill_ids = [r["skill_id"] for r in required_skills]
    req_skill_names = _safe_select(
        client, "skills", "id, name, category_id", [("id", "in_", req_skill_ids)]
    )
    req_name_map = {s["id"]: s for s in req_skill_names}

    user_skill_map = {s["name"].lower().strip(): s for s in user_skills}

    gaps = []
    level_order = {"BEGINNER": 0, "INTERMEDIATE": 1, "ADVANCED": 2}

    for rs in required_skills:
        skill_info = req_name_map.get(rs["skill_id"], {})
        skill_name = skill_info.get("name", "")
        category_id = skill_info.get("category_id")
        importance = rs.get("importance_weight", 1.0) or 1.0

        user_level_val = "none"
        if skill_name.lower().strip() in user_skill_map:
            user_level_val = user_skill_map[skill_name.lower().strip()]["level"]

        required_level = "INTERMEDIATE" if importance >= 1.5 else "BEGINNER"
        current_level_num = level_order.get(user_level_val, -1)
        required_level_num = level_order.get(required_level, 1)

        if current_level_num < required_level_num:
            gaps.append(
                {
                    "skill": skill_name,
                    "category_id": category_id,
                    "importance": importance,
                    "current_level": user_level_val,
                    "required_level": required_level,
                    "gap_severity": (
                        "critical"
                        if importance >= 1.5 and current_level_num == -1
                        else "moderate"
                        if current_level_num == -1
                        else "minor"
                    ),
                    "learning_resources": [],
                }
            )

    gaps.sort(
        key=lambda x: {"critical": 0, "moderate": 1, "minor": 2}[x["gap_severity"]]
    )

    result = {
        "user_id": user_id,
        "skills": user_skills,
        "gaps": gaps,
        "career": {
            "id": career_info[0]["id"],
            "title": career_info[0]["title"],
            "description": career_info[0]["description"],
            "required_level": career_info[0]["required_level"],
        }
        if career_info
        else None,
    }

    cache_set(f"learnify:gap_analysis:{user_id}", result, 1800)
    return result


def clear_gaps_cache(user_id):
    invalidate_pattern(f"learnify:gap_analysis:{user_id}")


def get_readiness_score(user_id):
    cached = cache_get(f"learnify:career_readiness:{user_id}")
    if cached:
        return cached

    gaps_data = get_gaps(user_id)
    gaps = gaps_data.get("gaps", [])
    skills = gaps_data.get("skills", [])
    critical = len([g for g in gaps if g["gap_severity"] == "critical"])
    moderate = len([g for g in gaps if g["gap_severity"] == "moderate"])
    minor = len([g for g in gaps if g["gap_severity"] == "minor"])

    readiness = len(skills) * 10 - critical * 15 - moderate * 8 - minor * 3
    readiness = max(0.0, min(100.0, float(readiness)))

    if readiness >= 80:
        level = "advanced"
    elif readiness >= 50:
        level = "intermediate"
    elif readiness >= 20:
        level = "beginner"
    else:
        level = "none"

    result = {
        "readiness": round(readiness, 1),
        "level": level,
        "gaps_count": len(gaps),
        "total_skills": len(skills),
    }
    cache_set(f"learnify:career_readiness:{user_id}", result, 1800)
    return result
