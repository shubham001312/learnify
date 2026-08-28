import os

from backend.database.client import db_available, get_client


def _to_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x not in (None, "")]
    if isinstance(v, str):
        return [s for s in v.split(",") if s.strip()]
    return [str(v)]


def _normalize(rows):
    for r in rows:
        r["streams"] = _to_list(r.get("streams"))
        r["top_recruiters"] = _to_list(r.get("top_recruiters"))
        r["pros"] = _to_list(r.get("pros"))
        r["cons"] = _to_list(r.get("cons"))
    return rows


def query_colleges(
    type=None,
    state=None,
    q=None,
    stream=None,
    district=None,
    top=False,
    min_rank=None,
    min_package=None,
    sort="default",
    limit=60,
    offset=0,
):
    client = get_client()
    qb = client.table("colleges").select("*", count="exact")

    if type:
        t = str(type).lower()
        if t in ("govt", "government"):
            qb = qb.eq("type", "govt")
        elif t in ("private", "priv"):
            qb = qb.eq("type", "private")
        elif t == "deemed":
            qb = qb.eq("type", "deemed")

    if state:
        qb = qb.eq("state", state)

    if district:
        qb = qb.or_(f"district.ilike.%{district}%,city.ilike.%{district}%")

    if q:
        qb = qb.or_(f"name.ilike.*{q}*,city.ilike.*{q}*,state.ilike.*{q}*")

    if stream:
        qb = qb.contains("streams", [stream])

    if top:
        qb = qb.not_.is_("nirf_rank", "null").gt("nirf_rank", 0)
    if min_rank is not None:
        qb = qb.not_.is_("nirf_rank", "null").lte("nirf_rank", int(min_rank))
    if min_package is not None:
        qb = qb.not_.is_("avg_package", "null").gte("avg_package", float(min_package))

    s = (sort or "default").lower()
    if s == "nirf":
        qb = qb.order("nirf_rank", desc=False).order("name")
    elif s == "package":
        qb = qb.order("avg_package", desc=True).order("name")
    elif s == "name":
        qb = qb.order("name")
    elif top:
        qb = qb.order("nirf_rank")
    else:
        qb = qb.order("featured", desc=True).order("name")

    qb = qb.range(offset, offset + limit - 1)
    res = qb.execute()
    rows = _normalize(res.data or [])
    total = res.count if res.count is not None else len(rows)
    return rows, total


def get_college(college_id):
    client = get_client()
    res = client.table("colleges").select("*").eq("id", college_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    return _normalize(rows)[0]


def list_states():
    client = get_client()
    res = client.table("colleges").select("state").execute()
    return sorted({r["state"] for r in (res.data or []) if r.get("state")})


def list_cities(state=None):
    client = get_client()
    qb = client.table("colleges").select("city")
    if state:
        qb = qb.eq("state", state)
    res = qb.execute()
    return sorted({r["city"] for r in (res.data or []) if r.get("city")})


def get_reviews(college_id):
    client = get_client()
    res = (
        client.table("college_reviews")
        .select("*")
        .eq("college_id", college_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def add_review(college_id, author, rating, text, pros, cons):
    client = get_client()
    client.table("college_reviews").insert(
        {
            "college_id": college_id,
            "author": author,
            "rating": rating,
            "text": text,
            "pros": pros,
            "cons": cons,
        }
    ).execute()


def list_scholarships(category=None, state=None, q=None):
    client = get_client()
    qb = client.table("scholarships").select("*")
    if category:
        qb = qb.eq("category", category)
    if state:
        qb = qb.eq("state", state)
    if q:
        qb = qb.or_(f"name.ilike.*{q}*,eligibility.ilike.*{q}*,state.ilike.*{q}*")
    res = qb.execute()
    data = res.data or []
    for s in data:
        s["documents"] = _to_list(s.get("documents"))
        s["colleges"] = _to_list(s.get("colleges"))
    return data
