"""Shared database helpers for Learnify routes.

Keeps PostgREST access uniform: consistent column selection, scoped filters,
and predictable error handling (never leak SQL/Postgres errors to clients).
"""

import logging
import time
from typing import Any, Iterable, Optional

from backend.database.client import db_available, get_client


class NotFound(Exception):
    """404 — resource missing, or not visible to this caller."""


class Denied(Exception):
    """403 — authenticated but not permitted."""


class Rejected(Exception):
    """400 — request violates a business rule."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class Unavailable(Exception):
    """503 — the database did not answer; the caller may safely retry."""


def client_or_none():
    if not db_available():
        return None
    return get_client()


def require_client():
    from fastapi import HTTPException

    c = client_or_none()
    if c is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return c


# ── Transient upstream failures ────────────────────────────────────────────
# Supabase PostgREST drops requests intermittently on this network — typically
# `[WinError 10035] The read operation timed out`. That is an infrastructure
# hiccup, not a bad request, so it must never reach the client as a 400.

_TRANSIENT_MARKERS = (
    "winerror 10035", "winerror 10054", "winerror 10060", "winerror 10061",
    "the read operation timed out", "read timed out", "connect timeout",
    "timed out", "timeout", "connection reset", "connection aborted",
    "connection refused", "max retries exceeded",
    "failed to establish a new connection", "temporarily unavailable",
    "broken pipe", "bad gateway", "service unavailable", "gateway timeout",
    "unexpectedly closed", "getaddrinfo failed", "name or service not known",
    "network is unreachable",
)
_READ_ATTEMPTS = 3
_READ_BACKOFF = (0.2, 0.6)


def _is_transient(e: Exception) -> bool:
    """True when the failure is the link, not the query."""
    code = getattr(getattr(e, "response", None), "status_code", None)
    if code in (429, 502, 503, 504):
        return True
    raw = str(e).lower()
    return any(m in raw for m in _TRANSIENT_MARKERS)


def _run(fn, table: str, verb: str, *, retry: bool = False):
    """Execute `fn()`, retrying only where replaying it is safe.

    Reads are idempotent, so a transient drop is retried with a short backoff.
    Writes are never retried: if the response was lost *after* the server
    committed, replaying it would duplicate the row. They are classified
    straight away, which surfaces as a 503 the caller may retry itself.
    """
    attempts = _READ_ATTEMPTS if retry else 1
    for n in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if retry and n + 1 < attempts and _is_transient(e):
                logging.getLogger("learnify.db").warning(
                    "%s %s transient failure (attempt %d/%d) [%s]: %s",
                    verb, table, n + 1, attempts, type(e).__name__, str(e)[:200],
                )
                time.sleep(_READ_BACKOFF[min(n, len(_READ_BACKOFF) - 1)])
                continue
            raise _classify(e, table, verb) from None


def select(
    table: str,
    columns: str = "*",
    *,
    eq: Optional[dict] = None,
    in_: Optional[dict] = None,
    is_not_null: Iterable[str] = (),
    order: Optional[tuple] = None,
    limit: Optional[int] = None,
    from_: int = 0,
    count: bool = False,
) -> tuple[list, int]:
    """Run a SELECT; returns (rows, total_count).

    `eq`   → column: value equality filters
    `in_`  → column: [values] membership filters
    `order`→ (column, desc?)

    Failures are classified rather than blanket-swallowed: a malformed id can
    never match a row, so it is a 404 (not a 500), and anything else that still
    leaks is reported without exposing SQL to the client.
    """
    c = require_client()
    try:
        q = c.table(table).select(columns, count="exact" if count else None)
        for k, v in (eq or {}).items():
            q = q.eq(k, v)
        for k, v in (in_ or {}).items():
            q = q.in_(k, v)
        for col in is_not_null:
            q = q.not_.is_(col, "null")
        if order:
            q = q.order(order[0], desc=bool(order[1]) if len(order) > 1 else False)
        if from_:
            q = q.range(from_, from_ + (limit or 100) - 1)
        elif limit:
            q = q.limit(limit)
        res = _run(q.execute, table, "read", retry=True)
        rows = res.data or []
        total = res.count if (count and res.count is not None) else len(rows)
        return rows, total
    except Exception as e:  # noqa: BLE001
        raise _classify(e, table, "read")


def _classify(e: Exception, table: str, verb: str) -> Exception:
    """Map a Postgres/PostgREST failure onto a domain error.

    Deliberately never embeds `str(e)` in the returned message: Postgres
    errors carry column names, constraint names and query fragments, and the
    message is returned verbatim to the client. The detail is logged instead.
    """
    import logging

    if isinstance(e, (NotFound, Denied, Rejected, Unavailable)):
        # Already resolved by `_run`; re-classifying would turn a precise
        # 404/503 back into a generic 400.
        return e

    raw = str(e)
    log = logging.getLogger("learnify.db")

    if "22P02" in raw or "invalid input syntax for type" in raw:
        # Malformed id (e.g. eq={'id': 'None'} against a uuid column).
        # Nothing can match it, so the resource is simply absent.
        noun = table[:-1] if table.endswith("s") else table
        return NotFound(f"No such {noun}")
    if "23505" in raw or "duplicate key" in raw:
        return Rejected("That record already exists")
    if "23503" in raw or "violates foreign key" in raw:
        return Rejected("That reference does not exist")
    if "42501" in raw or "permission denied" in raw or "row-level security" in raw:
        return Denied("You do not have access to this resource")

    log.warning("%s %s failed for table %s [%s]: %s",
                verb, table, table, type(e).__name__, raw[:400])
    if _is_transient(e):
        # Still failing after the read retries above: this is ours, not the
        # caller's. 503 tells clients and monitors to back off and retry
        # rather than treating an outage as a malformed request.
        return Unavailable(
            f"The service is temporarily unavailable while trying to "
            f"{verb} {table}. Please try again."
        )
    return Rejected(f"Could not {verb} {table}")


def first(table: str, columns: str = "*", **kw) -> Optional[dict]:
    rows, _ = select(table, columns, limit=1, **kw)
    return rows[0] if rows else None


def insert(table: str, row: dict) -> dict:
    c = require_client()
    try:
        res = _run(lambda: c.table(table).insert(row).execute(), table, "create")
        return (res.data or [{}])[0]
    except Exception as e:  # noqa: BLE001
        raise _classify(e, table, "create")


def upsert(table: str, row: dict, on_conflict: str) -> dict:
    c = require_client()
    try:
        res = _run(lambda: c.table(table).upsert(row, on_conflict=on_conflict).execute(),
                   table, "save")
        return (res.data or [{}])[0]
    except Exception as e:  # noqa: BLE001
        raise _classify(e, table, "save")


def update(table: str, row: dict, **filters) -> list:
    c = require_client()
    try:
        q = c.table(table).update(row)
        for k, v in filters.items():
            q = q.eq(k, v)
        res = _run(q.execute, table, "update")
        return res.data or []
    except Exception as e:  # noqa: BLE001
        raise _classify(e, table, "update")


def delete(table: str, **filters) -> list:
    c = require_client()
    try:
        q = c.table(table).delete()
        for k, v in filters.items():
            q = q.eq(k, v)
        res = _run(q.execute, table, "delete")
        return res.data or []
    except Exception as e:  # noqa: BLE001
        raise _classify(e, table, "delete")


def count(table: str, **filters) -> int:
    c = require_client()
    try:
        q = c.table(table).select("id", count="exact")
        for k, v in filters.items():
            q = q.eq(k, v)
        res = _run(q.execute, table, "read", retry=True)
        return res.count or 0
    except Exception:
        # Counters are advisory (pagination, badges): a read that still fails
        # after retries degrades to 0 rather than failing the whole request.
        return 0


def audit(actor_id: str, action: str, resource_type: str = "",
          resource_id: str = "", metadata: Optional[dict] = None,
          ip_address: str = "") -> None:
    """Best-effort audit trail — never blocks the action it records."""
    c = client_or_none()
    if c is None:
        return
    try:
        c.table("audit_logs").insert({
            "actor_id": actor_id, "action": action,
            "resource_type": resource_type, "resource_id": str(resource_id or ""),
            "metadata": metadata or {}, "ip_address": ip_address,
        }).execute()
    except Exception:
        pass


def ok(data: Any = None, **extra) -> dict:
    """Uniform response envelope."""
    body = {"success": True, "data": data, "error": None}
    body.update(extra)
    return body
