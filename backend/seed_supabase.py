import os

import dotenv

dotenv.load_dotenv()

from backend.database.seed import SEED_SCHOLARSHIPS


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "t", "yes", "y")


def load_local_colleges():
    try:
        from backend.database import local_db

        if not local_db.db_available():
            return None
    except Exception:
        return None

    rows = []
    limit = 1000
    offset = 0
    while True:
        batch, _ = local_db.query_colleges(limit=limit, offset=offset)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows or None


def map_college(c):
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "state": c.get("state"),
        "city": c.get("city"),
        "district": c.get("district"),
        "pin_code": c.get("pin_code"),
        "address": c.get("address"),
        "type": c.get("type"),
        "nirf_rank": _to_int(c.get("nirf_rank")),
        "nirf_year": _to_int(c.get("nirf_year")) or 2024,
        "avg_package": _to_float(c.get("avg_package")),
        "placement_pct": _to_int(c.get("placement_pct")),
        "rating": _to_float(c.get("rating")),
        "streams": c.get("streams") or [],
        "top_recruiters": c.get("top_recruiters") or [],
        "min_12th_marks": _to_int(c.get("min_12th_marks")),
        "website": c.get("website"),
        "affiliation": c.get("affiliation"),
        "founded": _to_int(c.get("founded")),
        "description": c.get("description"),
        "pros": c.get("pros") or [],
        "cons": c.get("cons") or [],
        "featured": _to_bool(c.get("featured")),
    }


def map_scholarship(s):
    return {
        "id": s.get("id"),
        "name": s.get("name"),
        "amount": s.get("amount"),
        "eligibility": s.get("eligibility"),
        "deadline": s.get("deadline"),
        "category": s.get("category"),
        "state": s.get("state"),
        "documents": s.get("documents") or [],
        "colleges": s.get("colleges") or [],
        "provider": s.get("provider"),
        "link": s.get("link"),
        "description": s.get("description"),
    }


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print(
            "[learnify] SUPABASE_URL / SUPABASE_SERVICE_KEY not set. Add them to .env first."
        )
        return

    from supabase import create_client

    sb = create_client(url, key)

    colleges = load_local_colleges()
    if colleges is None:
        from backend.database.seed import SEED_COLLEGES

        colleges = SEED_COLLEGES
        print("[learnify] Local DB not found; using SEED_COLLEGES fallback.")

    print(f"[learnify] Seeding {len(colleges)} colleges …")
    mapped = [map_college(c) for c in colleges]
    batch = 500
    for i in range(0, len(mapped), batch):
        sb.table("colleges").upsert(mapped[i : i + batch], on_conflict="id").execute()
        print(f"[learnify]   colleges {min(i + batch, len(mapped))}/{len(mapped)}")
    print(f"[learnify] Seeded colleges: {len(mapped)}")

    print(f"[learnify] Seeding {len(SEED_SCHOLARSHIPS)} scholarships …")
    scholarships = [map_scholarship(s) for s in SEED_SCHOLARSHIPS]
    sb.table("scholarships").upsert(scholarships, on_conflict="id").execute()
    print(f"[learnify] Seeded scholarships: {len(scholarships)}")
    print("[learnify] Done. Online database is now populated.")


if __name__ == "__main__":
    main()
