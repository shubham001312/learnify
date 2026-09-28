"""Phase 0 — full logical backup of the live Supabase project BEFORE the
Learnify schema replacement.

Dumps every table exposed by PostgREST (row data as JSON) plus the Supabase
Auth users list into:
    backups/pre_migration/<timestamp>/
        tables/<table>.json
        auth_users.json
        manifest.json

Usage:
    python scripts/backup_live_db.py
"""

import datetime as dt
import json
import os
import pathlib
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or ""
PAT = os.environ.get("SUPABASE_PAT") or ""
PROJECT = os.environ.get("SUPABASE_PROJECT") or "spjkmcvqtwzfednrszbs"

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAMP = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = ROOT / "backups" / "pre_migration" / STAMP

HEADERS = {"apikey": SERVICE_KEY or ANON_KEY, "Authorization": f"Bearer {SERVICE_KEY or ANON_KEY}"}


def list_tables() -> list[str]:
    """Discover tables from the PostgREST OpenAPI doc (service key sees all)."""
    r = requests.get(f"{URL}/rest/v1/", headers=HEADERS, timeout=30)
    r.raise_for_status()
    paths = r.json().get("paths", {})
    tables = set()
    for p in paths:
        seg = p.strip("/").split("/")[0]
        if seg:
            tables.add(seg)
    return sorted(tables)


def dump_table(table: str) -> dict:
    """Page through a whole table so nothing is truncated.

    PostgREST enforces max-rows=1000 per response regardless of the Range
    header, so we request 1000-row windows and only stop on an empty page.
    """
    rows, start, page = [], 0, 1000
    while True:
        headers = dict(HEADERS)
        headers["Range"] = f"{start}-{start + page - 1}"
        headers["Prefer"] = "count=exact"
        r = requests.get(f"{URL}/rest/v1/{table}?select=*", headers=headers, timeout=120)
        # 200 = full body, 206 = Partial Content (correct for a Range request)
        if r.status_code not in (200, 206):
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}", "rows": rows}
        chunk = r.json()
        if not isinstance(chunk, list):
            return {"error": f"unexpected payload: {str(chunk)[:200]}", "rows": rows}
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < page:
            break
        start += page
        if start > 500_000:  # safety valve
            break
    return {"rows": rows, "count": len(rows)}


def dump_auth_users() -> dict:
    """Auth users via the GoTrue admin API (service key).

    Uses /auth/v1/admin/users — the Management-API route
    /v1/projects/{ref}/auth/users does not exist (404).
    """
    if not SERVICE_KEY:
        return {"error": "SUPABASE_SERVICE_KEY not set — auth users not exported"}
    users, page = [], 1
    while True:
        r = requests.get(
            f"{URL}/auth/v1/admin/users?page={page}&per_page=200",
            headers=HEADERS,
            timeout=60,
        )
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}", "users": users}
        batch = r.json().get("users", [])
        users.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        if page > 50:
            break
    scrubbed = [
        {
            "id": u.get("id"),
            "email": u.get("email"),
            "created_at": u.get("created_at"),
            "email_confirmed_at": u.get("email_confirmed_at"),
            "user_metadata": u.get("user_metadata"),
            "app_metadata": u.get("app_metadata"),
        }
        for u in users
    ]
    return {"count": len(scrubbed), "users": scrubbed}


def main() -> int:
    if not URL or not (SERVICE_KEY or ANON_KEY):
        print("FAIL: SUPABASE_URL / keys missing from .env")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tables").mkdir(exist_ok=True)

    print(f"Backup target: {OUT}")
    tables = list_tables()
    print(f"Discovered {len(tables)} tables: {', '.join(tables)}")

    manifest = {"created_at": STAMP, "project": PROJECT, "tables": {}}
    failed = 0
    for t in tables:
        try:
            res = dump_table(t)
        except Exception as exc:  # noqa: BLE001 — record and continue
            res = {"error": str(exc), "rows": []}
        (OUT / "tables" / f"{t}.json").write_text(
            json.dumps(res["rows"], indent=1, default=str), encoding="utf-8"
        )
        manifest["tables"][t] = {
            "count": res.get("count", len(res["rows"])),
            "error": res.get("error"),
        }
        flag = "ERR" if res.get("error") else "ok "
        print(f"  [{flag}] {t}: {manifest['tables'][t]['count']} rows")
        if res.get("error"):
            failed += 1

    auth = dump_auth_users()
    (OUT / "auth_users.json").write_text(json.dumps(auth, indent=1, default=str), encoding="utf-8")
    manifest["auth_users"] = auth.get("count", 0)
    print(f"  [ok ] auth.users: {manifest['auth_users']} users")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(v["count"] for v in manifest["tables"].values())
    print(f"\nDone. {len(tables)} tables / {total} rows backed up. Failures: {failed}")
    print(f"Manifest: {OUT / 'manifest.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
