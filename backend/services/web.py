"""Keyless live web lookup used as a Google-style knowledge card in search.

Uses Wikipedia's open public APIs (no API key required). Results are best-effort
and always wrapped so a failure never breaks the search response.
"""

import json
import urllib.parse
import urllib.request

_UA = "Learnify/1.0 (study companion; contact: admin@learnify.hosteler.shop)"
_TIMEOUT = 4


def _get_json(url: str):
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def web_lookup(q: str):
    """Return a knowledge-panel dict {title, extract, url} or None."""
    q = (q or "").strip()
    if len(q) < 3 or len(q) > 100:
        return None
    try:
        os_url = (
            "https://en.wikipedia.org/w/api.php?action=opensearch&limit=1&format=json&search="
            + urllib.parse.quote(q)
        )
        data = _get_json(os_url)
        titles = data[1] if len(data) > 1 else []
        urls = data[3] if len(data) > 3 else []
        if not titles:
            return None
        title = titles[0]
        url = (
            urls[0]
            if urls
            else "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title)
        )
        summary = _get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title)
        )
        extract = (summary.get("extract") or "").strip()
        if not extract:
            return None
        return {"title": title, "extract": extract[:420], "url": url}
    except Exception:
        return None
