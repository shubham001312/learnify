"""Rate limiting for the three endpoints that invite abuse.

Only credential endpoints are metered: a portal with open registration and
no limit anywhere is a signup farm and a password-spraying target, while
metering ordinary API traffic would punish legitimate list/pagination calls
for sharing an office NAT.

Design notes
    * Fixed windows keyed on ``(path, client ip)`` — per-account limits do
      not belong here, because an attacker controls the account they are
      spraying at.
    * Trust ``X-Forwarded-For`` **only** when the TCP peer is loopback. A
      remote client can write any value it likes into that header, so
      trusting it unconditionally would let one host rotate through the
      limit. A loopback peer means the request arrived from our own reverse
      proxy, which appends the real client address last.
    * Reads and writes are in-process; this app runs as a single uvicorn
      worker. Running several workers would make each worker's window
      independent — move to a shared store before scaling out.
    * Every limit is env-overridable and ``0`` disables that endpoint's
      metering entirely; ``RATE_LIMIT_DISABLED=true`` turns the lot off.
"""

import hashlib
import os
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

# path -> (env override, default limit, window seconds, bucket)
#
# Credential endpoints have no bearer token yet, so they fall back to the
# client address. The two Groq-spending endpoints do carry one, which keys
# them per account instead of per address — otherwise every user behind a
# shared office NAT would draw from the same budget.
#
# `bucket` is what the budget is actually named by. Both AI endpoints share
# one ("ai") so an account's total Groq spend is capped, rather than getting
# a fresh allowance on each route it can reach.
RULES = {
    "/api/auth/login": ("RATE_LIMIT_LOGIN", 15, 60, "login"),
    "/api/auth/register": ("RATE_LIMIT_REGISTER", 10, 60, "register"),
    "/api/auth/change-password": ("RATE_LIMIT_CHANGE_PASSWORD", 5, 60, "change-password"),
    "/api/v1/ai/generate-questions": ("RATE_LIMIT_AI", 10, 60, "ai"),
    "/api/v1/ai/personalise-report": ("RATE_LIMIT_AI", 10, 60, "ai"),
    # Admin only, but one press writes a row per recipient: a stuck button or
    # a runaway loop would still put thousands of rows in front of everybody.
    "/api/v1/admin/notifications": ("RATE_LIMIT_NOTIFY", 20, 60, "notify"),
}

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
_MAX_KEYS = 50_000

_TRUTHY = ("1", "true", "yes", "on")


def _off() -> bool:
    return os.environ.get("RATE_LIMIT_DISABLED", "").strip().lower() in _TRUTHY


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in _LOOPBACK:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            # Last entry is the one our proxy appended.
            return xff.split(",")[-1].strip() or peer
    return peer


def _key(request: Request, bucket: str) -> str:
    """Bucket identity: the caller's token if there is one, else its address.

    The token is only hashed to keep it out of the limiter's keys — it is
    never validated here, auth still happens in the route.
    """
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer " and len(auth) > 7:
        digest = hashlib.sha256(auth[7:].encode("utf-8")).hexdigest()[:16]
        return f"{bucket}|u:{digest}"
    return f"{bucket}|ip:{_client_ip(request)}"


class _Limiter:
    """Sliding-window hit counter. Thread-safe; bounded memory."""

    def __init__(self) -> None:
        self._hits: dict = {}
        self._lock = threading.Lock()

    def _sweep(self, now: float, window: float) -> None:
        # Called only once over the key cap, so it may cost a full pass.
        stale = window * 2
        for key in [k for k, q in self._hits.items()
                    if not q or q[-1] <= now - stale]:
            del self._hits[key]

    def allow(self, key: str, limit: int, window: float) -> int:
        """Return 0 when allowed, else seconds the caller should wait."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._sweep(now, window)
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            cutoff = now - window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) < limit:
                hits.append(now)
                return 0
            # Oldest hit still inside the window decides when a slot frees.
            return max(1, int(window - (now - hits[0])) + 1)


_LIMIT = _Limiter()


def gate(request: Request) -> Optional[JSONResponse]:
    """Return a 429 body when this request has used its whole budget.

    Returns ``None`` for everything else, which is the overwhelmingly common
    case — one dict lookup on a path that is almost never in RULES.
    """
    if _off():
        return None
    rule = RULES.get(request.url.path)
    if rule is None:
        return None

    env_name, default_limit, window, bucket = rule
    raw = os.environ.get(env_name, "").strip()
    try:
        limit = int(raw) if raw else default_limit
    except ValueError:
        limit = default_limit
    if limit <= 0:
        return None

    key = _key(request, bucket)
    wait = _LIMIT.allow(key, limit, float(window))
    if not wait:
        return None

    msg = f"Too many attempts. Please try again in {wait} seconds."
    return JSONResponse(
        {"success": False, "data": None, "error": msg, "detail": msg},
        status_code=429,
        headers={"Retry-After": str(wait)},
    )
