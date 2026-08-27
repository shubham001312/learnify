import json
import os
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
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _today():
    return time.strftime("%Y-%m-%d")


def google_scholarship_search(query, num=10):
    """Search live scholarship announcements via Google Programmable Search Engine.
    Returns (results, meta). Falls back to cache / empty when unconfigured or quota hit."""
    key = os.environ.get("GOOGLE_CSE_KEY")
    cx = os.environ.get("GOOGLE_CSE_CX")
    sites = os.environ.get(
        "GOOGLE_CSE_SITES",
        "scholarships.gov.in,buddy4study.com,national scholarship portal,education.gov.in",
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
        return [], {
            "source": "unconfigured",
            "note": "Set GOOGLE_CSE_KEY and GOOGLE_CSE_CX in .env to enable live search.",
        }

    if state["count"] >= DAILY_QUOTA:
        cached = state["cache"].get(cache_key, {}).get("items", [])
        return cached, {"source": "quota_exceeded", "remaining": 0}

    q = query
    if sites:
        q = (
            query
            + " "
            + " ".join("site:" + s.strip() for s in sites.split(",") if s.strip())
        )
    try:
        resp = requests.get(
            GOOGLE_ENDPOINT,
            params={"key": key, "cx": cx, "q": q, "num": min(num, 10)},
            timeout=15,
        )
        data = resp.json()
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
