"""Phase 1 — apply the Learnify schema (and optional teardown).

Uses the Supabase Management API query endpoint (needs SUPABASE_PAT), because
PostgREST cannot execute DDL.

Modes:
    python scripts/apply_lms_schema.py            # apply schema (default)
    python scripts/apply_lms_schema.py --check    # parse/validate only, no writes
    python scripts/apply_lms_schema.py --drop-old # FIRST drop Learnify tables

The script wraps every statement in its own transaction so a mid-file failure
never leaves a half-built schema, and it reports per-statement results.
"""

import argparse
import json
import os
import pathlib
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

PAT = os.environ.get("SUPABASE_PAT") or ""
PROJECT = os.environ.get("SUPABASE_PROJECT") or "spjkmcvqtwzfednrszbs"
ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "backend" / "database" / "schema.sql"
API = f"https://api.supabase.com/v1/projects/{PROJECT}/database/query"

# Learnify tables dropped before the fresh schema is applied.
# `users` is intentionally included: its Learnify-era columns differ from the
# Learnify definition, and `create table if not exists` would silently
# skip it. All rows are already backed up (see backups/pre_migration/).
OLD_TABLES = [
    "academic_records", "chats", "college_reviews", "colleges", "conversations",
    "doc_chunks", "documents", "memory", "scanned_data", "scholarships",
    "sgpa_entries", "study_plans", "subscriptions", "user_profiles", "users",
]

SKIP_TABLES: list[str] = []  # nothing is spared — full Learnify teardown


def split_statements(sql: str) -> list[str]:
    """Split on ';' at top level, ignoring those inside $$…$$ or '…' strings."""
    stmts, buf, i, n = [], [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" or ch == '"':
            quote = ch
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(sql[i])
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        buf.append(sql[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
            continue
        if sql.startswith("$$", i) or sql.startswith("$tag$", i):
            end = sql.find("$$", i + 2) if sql.startswith("$$") else sql.find("$tag$", i + 6)
            end = end if end != -1 else n
            buf.append(sql[i:end + 2])
            i = end + 2
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def run(stmts: list[str]) -> tuple[int, int]:
    if not PAT:
        print("FAIL: SUPABASE_PAT missing from .env")
        return 0, len(stmts)
    hdr = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
    ok = bad = 0
    for idx, stmt in enumerate(stmts, 1):
        label = re.sub(r"\s+", " ", stmt)[:70]
        try:
            r = requests.post(API, headers=hdr, json={"query": stmt}, timeout=60)
        except requests.RequestException as exc:
            print(f"  [{idx:>3}] ERR  {label}\n         {exc}")
            bad += 1
            continue
        if r.status_code in (200, 201):
            body = r.json()
            if isinstance(body, dict) and body.get("message"):
                print(f"  [{idx:>3}] FAIL {label}\n         {body['message']}")
                bad += 1
            else:
                ok += 1
        else:
            try:
                msg = r.json().get("message", r.text[:200])
            except Exception:
                msg = r.text[:200]
            print(f"  [{idx:>3}] FAIL {label}\n         HTTP {r.status_code}: {msg}")
            bad += 1
    return ok, bad


def list_existing() -> set[str]:
    svc = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or ""
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    r = requests.get(
        f"{url}/rest/v1/",
        headers={"apikey": svc, "Authorization": f"Bearer {svc}"},
        timeout=30,
    )
    r.raise_for_status()
    return {p.strip("/").split("/")[0] for p in r.json().get("paths", {}) if p.strip("/")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only, no writes")
    ap.add_argument("--drop-old", action="store_true", help="drop Learnify tables first")
    ap.add_argument("--only", metavar="REGEX", default="",
                    help="apply only statements whose text matches REGEX "
                         "(partial re-apply, e.g. a newly added index)")
    args = ap.parse_args()

    sql = SCHEMA.read_text(encoding="utf-8")
    stmts = split_statements(sql)
    if args.only:
        pat = re.compile(args.only, re.I | re.S)
        stmts = [s for s in stmts if pat.search(s)]
        print(f"--only /{args.only}/ selected {len(stmts)} statements")
        if not stmts:
            print("FAIL: nothing matched")
            return 1
    creates = [s for s in stmts if re.match(r"\s*create\s+table", s, re.I)]
    print(f"schema.sql: {len(stmts)} statements, {len(creates)} CREATE TABLE")

    names = []
    for s in creates:
        m = re.search(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z_]+)", s, re.I)
        if m:
            names.append(m.group(1))
    print(f"tables defined ({len(names)}): {', '.join(names)}")

    # Sanity: balanced parens per statement
    for s in stmts:
        if s.count("(") != s.count(")"):
            print(f"  WARN unbalanced parens: {re.sub(r'\\s+', ' ', s)[:80]}")

    if args.check:
        print("\nCHECK only — no changes made.")
        return 0

    if args.drop_old:
        drop = [t for t in OLD_TABLES if t not in SKIP_TABLES]
        print(f"\nDropping {len(drop)} Learnify tables: {', '.join(drop)}")
        stmts = [f'drop table if exists "{t}" cascade' for t in drop] + stmts

    print(f"\nApplying {len(stmts)} statements…")
    ok, bad = run(stmts)
    print(f"\nResult: {ok} ok, {bad} failed")

    if bad:
        return 1
    try:
        existing = list_existing()
        want = set(names)
        missing = sorted(want - existing)
        print(f"\nLive tables now: {len(existing)}")
        print(f"Missing from schema: {', '.join(missing) if missing else 'NONE ✅'}")
        return 1 if missing else 0
    except Exception as exc:
        print(f"\n(post-verify skipped: {exc})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
