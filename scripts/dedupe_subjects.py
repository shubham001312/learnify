"""Collapse duplicate subjects — same `name`, different rows.

`subjects.name` had no uniqueness, so every re-run of scripts/e2e_test.py
inserted another literal "Computer Networks".  This script repairs the live
data before the unique index is created:

    create unique index if not exists subjects_name_uk on subjects (lower(name));

PostgREST cannot execute DDL, so the index itself goes through the Management
API path used by Phase 1:

    python scripts/apply_lms_schema.py --only subjects_name_uk

Steps (all idempotent — a second run reports "nothing to do"):
  1. back up every affected table to backups/pre_subject_dedupe/<stamp>/
  2. group subjects by lower(trim(name)); groups of one are left alone
  3. keep the OLDEST row of each group (created_at, then id)
  4. retarget every subject_id / topic_id reference onto it
       - keyed tables lose the exact-duplicate child rows instead
         (their unique key could never accept the move)
       - topic merges also retarget the questions that point at the
         duplicate topic, so nothing is cascade-deleted by accident
  5. delete the losing subject rows

    python scripts/dedupe_subjects.py [--dry-run]
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402

from scripts.backup_live_db import dump_table  # noqa: E402 — same paging/backup shape

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
STAMP = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = ROOT / "backups" / "pre_subject_dedupe" / STAMP

# Every table with a `subject_id` column — discovered with a query against
# information_schema.columns and cross-checked against the FK constraints that
# reference `subjects`.
PLAIN_TABLES = [
    "assessments", "certificates", "courses", "library_items",
    "performance_reports", "questionnaires",
]
# subject_id + a unique key: repointing must not collide.
KEYED_TABLES: dict[str, tuple[tuple[str, ...], str | None]] = {
    # table: (extra key columns, id column or None for composite-key tables)
    "subject_topics": (("name",), "id"),
    "subject_competencies": (("competency_id",), None),
    "subject_benchmarks": (("topic_id",), "id"),
}
# Tables holding a plain `topic_id` FK to subject_topics (all NO ACTION — a
# topic that still has questions cannot be deleted until they are retargeted).
TOPIC_REF_TABLES = ["questionnaires", "questionnaire_questions",
                    "assessment_questions", "draft_questions"]
BACKUP_TABLES = ["subjects", *PLAIN_TABLES, *KEYED_TABLES,
                 "assessment_questions", "questionnaire_questions",
                 "draft_questions"]

FAILURES: list[str] = []


def client():
    if not URL or not SERVICE_KEY:
        sys.exit("FAIL: SUPABASE_URL / SUPABASE_SERVICE_KEY missing from .env")
    return create_client(URL, SERVICE_KEY)


def fetch(c, table: str, columns: str, in_=None, eq=None) -> list[dict]:
    try:
        q = c.table(table).select(columns)
        if in_:
            q = q.in_(in_[0], in_[1])
        if eq:
            for k, v in eq.items():
                q = q.eq(k, v)
        return q.execute().data or []
    except Exception as exc:  # noqa: BLE001
        msg = f"could not read {table}: {str(exc)[:200]}"
        FAILURES.append(msg)
        print(f"    ! {msg}")
        return []


def apply_row(c, table: str, action: str, ident: dict,
              payload: dict | None = None) -> bool:
    """Update/delete one row matched on `ident`. False + report on failure."""
    try:
        q = c.table(table).update(payload) if action == "update" \
            else c.table(table).delete()
        for k, v in ident.items():
            q = q.eq(k, v)
        q.execute()
        return True
    except Exception as exc:  # noqa: BLE001
        msg = f"could not {action} {table} ({', '.join(f'{k}={v}' for k, v in ident.items())}): {str(exc)[:200]}"
        FAILURES.append(msg)
        print(f"    ! {msg}")
        return False


def backup() -> None:
    """Snapshot the rows this script is about to touch (backups/ convention)."""
    (BACKUP_DIR / "tables").mkdir(parents=True, exist_ok=True)
    manifest = {"created_at": STAMP, "purpose": "pre_subject_dedupe", "tables": {}}
    for t in BACKUP_TABLES:
        try:
            res = dump_table(t)
        except Exception as exc:  # noqa: BLE001
            res = {"rows": [], "count": 0, "error": str(exc)}
        (BACKUP_DIR / "tables" / f"{t}.json").write_text(
            json.dumps(res.get("rows", []), indent=1, default=str),
            encoding="utf-8")
        manifest["tables"][t] = {"count": res.get("count", len(res.get("rows", []))),
                                 "error": res.get("error")}
        flag = "ERR" if res.get("error") else "ok "
        print(f"    [{flag}] {t}: {manifest['tables'][t]['count']} rows")
    (BACKUP_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  backup written to {BACKUP_DIR}")


# ─── one duplicate-name group ────────────────────────────────────────────────
class Stats:
    moved = dropped = deleted = 0


def merge_topics(c, keep_id: str, dup_ids: list[str], dry: bool,
                 st: Stats) -> None:
    """Plan what happens to every topic of a duplicate subject.

    A topic whose name already exists on the kept subject is MERGED: its
    questions, questionnaires and drafts are retargeted onto the kept subject's
    topic, then the duplicate topic row goes away.  Any other topic simply
    moves over with its subject_id.
    """
    keep_topics = {t.get("name"): t["id"] for t in
                   fetch(c, "subject_topics", "id, name", eq={"subject_id": keep_id})}
    dup_topics = fetch(c, "subject_topics", "id, name, subject_id",
                       in_=("subject_id", dup_ids))
    merge: dict[str, str] = {}          # duplicate topic id -> kept topic id
    move: list[str] = []                # duplicate topic ids that survive
    for t in dup_topics:
        target = keep_topics.get(t.get("name"))
        if target:
            merge[t["id"]] = target
        else:
            move.append(t["id"])
    print(f"    topics: {len(dup_topics)} on duplicates "
          f"({len(merge)} merge into an existing name, {len(move)} move over)")

    # 1. benchmarks carry (subject_id, topic_id) — retarget both at once so the
    #    unique key never sees a collision.
    keep_keys = {(r["subject_id"], r["topic_id"]) for r in
                 fetch(c, "subject_benchmarks", "subject_id, topic_id",
                       eq={"subject_id": keep_id})}
    benches = fetch(c, "subject_benchmarks", "id, subject_id, topic_id",
                    in_=("subject_id", dup_ids))
    if merge:
        extra = fetch(c, "subject_benchmarks", "id, subject_id, topic_id",
                      in_=("topic_id", list(merge)))
        seen = {b["id"] for b in benches}
        benches += [b for b in extra if b["id"] not in seen]
    for b in benches:
        new_subj = keep_id if b["subject_id"] in dup_ids else b["subject_id"]
        new_topic = merge.get(b["topic_id"], b["topic_id"])
        if (new_subj, new_topic) in keep_keys:
            if dry:
                print(f"    (dry run) would drop duplicate subject_benchmarks id={b['id']}")
                st.dropped += 1
            elif apply_row(c, "subject_benchmarks", "delete", {"id": b["id"]}):
                st.dropped += 1
                print(f"    - drop duplicate subject_benchmarks id={b['id']}")
        elif (new_subj, new_topic) != (b["subject_id"], b["topic_id"]):
            if dry:
                print(f"    (dry run) would retarget subject_benchmarks id={b['id']} "
                      f"subject_id={new_subj} topic_id={new_topic}")
                st.moved += 1
            elif apply_row(c, "subject_benchmarks", "update", {"id": b["id"]},
                           {"subject_id": new_subj, "topic_id": new_topic}):
                st.moved += 1
                keep_keys.add((new_subj, new_topic))
                print(f"    -> subject_benchmarks id={b['id']} "
                      f"subject_id={new_subj} topic_id={new_topic}")

    # 2. retarget the plain topic_id references of every merged topic, so the
    #    duplicate row is unreferenced before we delete it.
    for dup_topic, target in merge.items():
        for table in TOPIC_REF_TABLES:
            rows = fetch(c, table, "id", in_=("topic_id", [dup_topic]))
            for r in rows:
                if dry:
                    print(f"    (dry run) would retarget {table} id={r['id']} "
                          f"topic_id {dup_topic} -> {target}")
                    st.moved += 1
                elif apply_row(c, table, "update", {"id": r["id"]},
                               {"topic_id": target}):
                    st.moved += 1
                    print(f"    -> {table} id={r['id']} topic_id {dup_topic} -> {target}")

    # 3. delete merged duplicates, move the rest.
    for dup_topic in merge:
        if dry:
            print(f"    (dry run) would delete subject_topics {dup_topic}")
            st.deleted += 1
            continue
        if apply_row(c, "subject_topics", "delete", {"id": dup_topic}):
            st.dropped += 1
            print(f"    - delete merged subject_topics {dup_topic}")
    for tid in move:
        if dry:
            print(f"    (dry run) would move subject_topics {tid} -> {keep_id}")
            st.moved += 1
            continue
        if apply_row(c, "subject_topics", "update", {"id": tid},
                     {"subject_id": keep_id}):
            st.moved += 1
            print(f"    -> subject_topics {tid} subject_id -> {keep_id}")


def repoint_keyed(c, table: str, key_cols: tuple[str, ...], id_col: str | None,
                  dup_ids: list[str], keep_id: str, dry: bool, st: Stats) -> None:
    """Move child rows onto `keep_id`; drop the ones whose key already exists."""
    cols = ", ".join([x for x in (id_col, "subject_id", *key_cols) if x])
    rows = fetch(c, table, cols, in_=("subject_id", dup_ids))
    if not rows:
        return
    keep_keys = {tuple(r.get(k) for k in key_cols) for r in
                 fetch(c, table, cols, eq={"subject_id": keep_id})}

    def ident_of(r: dict) -> dict:
        return {id_col: r[id_col]} if id_col else {
            "subject_id": r["subject_id"], **{k: r.get(k) for k in key_cols}}

    for r in rows:
        key = tuple(r.get(k) for k in key_cols)
        ident = ident_of(r)
        label = ", ".join(f"{k}={r.get(k)}" for k in ident)
        if key in keep_keys:
            # Exact duplicate of a row the kept subject already has: the unique
            # key would reject the move and the content is identical anyway.
            if dry:
                print(f"    (dry run) would drop duplicate {table} ({label})")
                st.dropped += 1
            elif apply_row(c, table, "delete", ident):
                st.dropped += 1
                print(f"    - drop duplicate {table} ({label})")
        elif dry:
            print(f"    (dry run) would move {table} ({label}) -> {keep_id}")
            st.moved += 1
        elif apply_row(c, table, "update", ident, {"subject_id": keep_id}):
            st.moved += 1
            keep_keys.add(key)
            print(f"    -> {table} ({label}) subject_id -> {keep_id}")


def repoint_plain(c, table: str, dup_ids: list[str], keep_id: str,
                  dry: bool, st: Stats) -> None:
    for r in fetch(c, table, "id", in_=("subject_id", dup_ids)):
        if dry:
            print(f"    (dry run) would move {table} id={r['id']} -> {keep_id}")
            st.moved += 1
        elif apply_row(c, table, "update", {"id": r["id"]},
                       {"subject_id": keep_id}):
            st.moved += 1
            print(f"    -> {table} id={r['id']} subject_id -> {keep_id}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report the moves/deletes without writing")
    args = ap.parse_args()

    c = client()
    if args.dry_run:
        print("DRY RUN — no writes")
    else:
        print("Backing up affected tables")
        backup()

    subjects = fetch(c, "subjects", "id, code, name, created_at, is_active")
    groups: dict[str, list[dict]] = {}
    for s in subjects:
        groups.setdefault((s.get("name") or "").strip().lower(), []).append(s)

    dupes = {k: sorted(v, key=lambda r: (r.get("created_at") or "", r.get("id") or ""))
             for k, v in groups.items() if len(v) > 1}
    print(f"\nsubjects: {len(subjects)} rows, "
          f"{len(dupes)} name(s) appear more than once")
    if not dupes:
        print("Nothing to do — no duplicate subject names.")
        return 1 if FAILURES else 0

    st = Stats()
    for name, rows in sorted(dupes.items()):
        keep, lose = rows[0], rows[1:]
        lose_ids = [r["id"] for r in lose]
        print(f"\n[{name}] {len(rows)} rows -> keep {keep['id']} "
              f"(created {keep.get('created_at')}); drop {len(lose)}")
        print(f"  keep code={keep.get('code')}   "
              f"drop codes={', '.join(r.get('code') or '?' for r in lose)}")

        merge_topics(c, keep["id"], lose_ids, args.dry_run, st)

        print("  keyed child tables (collision-checked):")
        for table, (key_cols, id_col) in KEYED_TABLES.items():
            if table == "subject_topics":
                continue  # already handled by merge_topics()
            repoint_keyed(c, table, key_cols, id_col, lose_ids, keep["id"],
                          args.dry_run, st)

        print("  plain FK tables:")
        for table in PLAIN_TABLES:
            repoint_plain(c, table, lose_ids, keep["id"], args.dry_run, st)

        if args.dry_run:
            print(f"  (dry run) would delete subjects: {', '.join(lose_ids)}")
            st.deleted += len(lose_ids)
            continue
        if _delete_subjects(c, lose_ids):
            st.deleted += len(lose_ids)
            print(f"  deleted {len(lose_ids)} duplicate subject row(s)")
        else:
            print("  ! duplicate subject rows NOT deleted — see errors above")
            return 1

    after = len(fetch(c, "subjects", "id"))
    print(f"\n{'Would move' if args.dry_run else 'Moved'} {st.moved} reference "
          f"row(s), dropped {st.dropped} duplicate child row(s), "
          f"deleted {st.deleted} row(s) (merged topics + duplicate subjects)")
    print(f"subjects before={len(subjects)} after={after}")
    if FAILURES:
        print(f"\n{len(FAILURES)} operation(s) failed:")
        for f in FAILURES:
            print(f"  X {f}")
        return 1
    return 0


def _delete_subjects(c, ids: list[str]) -> bool:
    """Delete several subject rows in one statement; report any FK block."""
    try:
        c.table("subjects").delete().in_("id", ids).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        FAILURES.append(f"subject delete: {str(exc)[:300]}")
        print(f"    ! subject delete failed (a FK is still pointing): {str(exc)[:300]}")
        return False


if __name__ == "__main__":
    sys.exit(main())
