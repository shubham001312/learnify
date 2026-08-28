import json
import os
import re
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "data", "search_cache.json")
GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
DAILY_QUOTA = 100
TTL = 60 * 60 * 24  # 24h cache


def _load():
    if os.path.isfile(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"day": "", "count": 0, "cache": {}}


def _save(state):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _today():
    return time.strftime("%Y-%m-%d")


def internal_scholarship_match(query, num=10):
    """Free, key-less matching against our own scholarship database."""
    try:
        from backend.database.supabase_db import list_scholarships
        rows = list_scholarships() or []
    except Exception:
        rows = []
    if not rows:
        try:
            from backend.database.seed import SEED_SCHOLARSHIPS
            rows = SEED_SCHOLARSHIPS
        except Exception:
            rows = []
    ql = (query or "").lower()
    qwords = {w for w in re.findall(r"[a-z0-9]+", ql) if len(w) > 2}
    scored = []
    for s in rows:
        text = " ".join(str(s.get(k, "")) for k in
                       ("name", "eligibility", "description", "category", "state", "provider", "amount")).lower()
        score = sum(1 for w in qwords if w in text)
        if s.get("state") and s.get("state").lower() in ql:
            score += 3
        if s.get("category") and s.get("category").lower() in ql:
            score += 2
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for score, s in scored if score > 0][:num]
    if not top:
        top = [s for _, s in scored][:num]
    items = []
    for s in top:
        items.append({
            "title": s.get("name"),
            "link": s.get("link") or "#",
            "snippet": ((s.get("amount") or "") + " · " + (s.get("eligibility") or s.get("description") or ""))[:240],
            "source": s.get("provider") or "Learnify DB",
        })
    return items, {"source": "database", "note": "Matched from our scholarship database."}


def google_scholarship_search(query, num=10):
    """Search live scholarship announcements via Google Programmable Search Engine.
    Returns (results, meta). Falls back to cache / empty when unconfigured or quota hit."""
    key = os.environ.get("GOOGLE_CSE_KEY") or os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CSE_CX") or os.environ.get("GOOGLE_CSE_ID")
    sites = os.environ.get(
        "GOOGLE_CSE_SITES",
        "scholarships.gov.in,buddy4study.com,nsp.gov.in",
    )
    state = _load()
    today = _today()
    if state.get("day") != today:
        state["day"] = today
        state["count"] = 0
    cache_key = query.strip().lower()

    if cache_key in state["cache"]:
        entry = state["cache"][cache_key]
        if time.time() - entry.get("ts", 0) < TTL:
            return entry["items"], {
                "source": "cache",
                "remaining": max(0, DAILY_QUOTA - state["count"]),
            }

    if not key or not cx:
        return internal_scholarship_match(query, num)

    if state["count"] >= DAILY_QUOTA:
        cached = state["cache"].get(cache_key, {}).get("items", [])
        return cached, {"source": "quota_exceeded", "remaining": 0}

    q = query
    if sites:
        site_clauses = ["site:" + s.strip() for s in sites.split(",") if s.strip()]
        if site_clauses:
            q = query + " (" + " OR ".join(site_clauses) + ")"
    try:
        resp = requests.get(
            GOOGLE_ENDPOINT,
            params={"key": key, "cx": cx, "q": q, "num": min(num, 10)},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("error"):
            gerr = data.get("error", {})
            return [], {
                "source": "error",
                "note": "Google CSE: " + str(gerr.get("message", resp.text)[:200]),
            }
        items = [
            {
                "title": i.get("title"),
                "link": i.get("link"),
                "snippet": i.get("snippet"),
                "source": i.get("displayLink"),
            }
            for i in data.get("items", [])
        ]
        state["count"] += 1
        state["cache"][cache_key] = {"ts": time.time(), "items": items}
        _save(state)
        return items, {
            "source": "live",
            "remaining": max(0, DAILY_QUOTA - state["count"]),
        }
    except Exception as e:
        return [], {"source": "error", "note": str(e)}
