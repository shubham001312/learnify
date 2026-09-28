"""Seed the curated subject catalogue — 24 distinct subjects, one pass.

Idempotent: a subject is skipped when a row with the same lower(name) already
exists (enforced by the live unique index `subjects_name_uk` as well), and a
code clash is reported instead of crashing, so re-running is always safe.

Codes follow the convention in backend/routes/subjects.py:
    code = payload.code.strip().upper()   (2-24 chars, `code text not null unique`)

The `course-covers` storage bucket is NOT created here — it is declared in
backend/database/schema.sql and applied with the rest of the DDL through
scripts/apply_lms_schema.py (--only storage\\.buckets).

    python scripts/seed_subjects.py [--dry-run]
"""
import argparse
import os
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""

ENG = "Engineering & Technology"
SCI = "Science"
COM = "Commerce & Management"
HUM = "Humanities & Skills"

# (code, name, category, description)
SUBJECTS: list[tuple[str, str, str, str]] = [
    # ── Engineering & Technology ────────────────────────────────────────────
    ("CN", "Computer Networks", ENG,
     "OSI/TCP-IP models, routing, switching and the protocols that move data."),
    ("DSA", "Data Structures & Algorithms", ENG,
     "Arrays, trees, graphs, hashing and the complexity of solving problems efficiently."),
    ("DBMS", "Database Systems", ENG,
     "Relational modelling, SQL, normalisation, indexing and transaction safety."),
    ("OS", "Operating Systems", ENG,
     "Processes, threads, memory management, file systems and scheduling."),
    ("WEBDEV", "Web Development", ENG,
     "HTML, CSS, JavaScript and the request/response life of a modern web app."),
    ("ML", "Machine Learning", ENG,
     "Supervised and unsupervised models, evaluation, and shipping models to production."),
    ("CYBER", "Cybersecurity", ENG,
     "Threats, cryptography, network defence and secure-by-design engineering."),
    ("EMBED", "Embedded Systems", ENG,
     "Microcontrollers, real-time constraints, sensors and hardware/software co-design."),
    ("CLOUD", "Cloud Computing", ENG,
     "Virtualisation, containers, orchestration and scalable infrastructure on demand."),
    ("SWE", "Software Engineering", ENG,
     "Requirements, design, testing, version control and collaborative delivery."),
    # ── Science ─────────────────────────────────────────────────────────────
    ("MATH", "Mathematics", SCI,
     "Algebra, calculus, discrete structures and the notation used across engineering."),
    ("PHYS", "Physics", SCI,
     "Mechanics, electromagnetism, waves and the principles behind real devices."),
    ("CHEM", "Chemistry", SCI,
     "Atomic structure, bonding, reactions and the laboratory methods that verify them."),
    ("BIO", "Biology", SCI,
     "Cells, genetics, physiology and the living systems that biotechnology builds on."),
    ("STAT", "Statistics", SCI,
     "Distributions, inference, regression and reading data without fooling yourself."),
    # ── Commerce & Management ───────────────────────────────────────────────
    ("FINACC", "Financial Accounting", COM,
     "Journal entries, ledgers, final accounts and the meaning behind the numbers."),
    ("BUSMGT", "Business Management", COM,
     "Planning, organising, leading and controlling an organisation day to day."),
    ("MKTG", "Marketing", COM,
     "Segmentation, positioning, the marketing mix and measuring campaign results."),
    ("ECON", "Economics", COM,
     "Supply, demand, market structures and the policy trade-offs behind growth."),
    ("PROJMGT", "Project Management", COM,
     "Scope, schedule, cost and risk — from kickoff to a delivered, accepted result."),
    # ── Humanities & Skills ─────────────────────────────────────────────────
    ("ENGCOM", "English Communication", HUM,
     "Clear speaking and writing for interviews, meetings and everyday professional life."),
    ("DIGLIT", "Digital Literacy", HUM,
     "Confident, safe use of the web, cloud tools and everyday productivity software."),
    ("APTRES", "Aptitude & Reasoning", HUM,
     "Quantitative, logical and verbal reasoning patterns used in placement tests."),
    ("TECHWRI", "Technical Writing", HUM,
     "Documenting systems: structure, precision and readers who were not in the room."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be inserted, write nothing")
    args = ap.parse_args()

    if not URL or not SERVICE_KEY:
        print("FAIL: SUPABASE_URL / SUPABASE_SERVICE_KEY missing from .env")
        return 1
    if len({s[1].strip().lower() for s in SUBJECTS}) != len(SUBJECTS) \
            or len({s[0] for s in SUBJECTS}) != len(SUBJECTS):
        print("FAIL: the curated list itself contains a duplicate name or code")
        return 1

    c = create_client(URL, SERVICE_KEY)

    existing = c.table("subjects").select("id, code, name").execute().data or []
    by_name = {(r.get("name") or "").strip().lower(): r for r in existing}
    by_code = {(r.get("code") or "").strip().upper(): r for r in existing}

    inserted, skipped, conflicts = [], [], []
    for code, name, category, description in SUBJECTS:
        key = name.strip().lower()
        if key in by_name:
            skipped.append(f"{name} (as {by_name[key]['code']})")
            continue
        if code in by_code:
            conflicts.append(f"{name} -> code {code} already used by "
                             f"'{by_code[code]['name']}'")
            continue
        if args.dry_run:
            inserted.append(name)
            print(f"  [dry ] {code:7} {name} — {category}")
            continue
        try:
            row = c.table("subjects").insert({
                "code": code, "name": name.strip(), "category": category,
                "description": description, "is_active": True,
            }).execute().data[0]
        except Exception as exc:  # noqa: BLE001 — e.g. the unique index fired
            conflicts.append(f"{name}: {str(exc)[:160]}")
            continue
        by_name[key] = row
        by_code[code] = row
        inserted.append(name)
        print(f"  [ok  ] {code:7} {name} — {category}")

    print(f"\ninserted {len(inserted)}, already present {len(skipped)}, "
          f"skipped on conflict {len(conflicts)}")
    for s in skipped:
        print(f"  = kept existing {s}")
    for s in conflicts:
        print(f"  ! {s}")

    rows = c.table("subjects").select("id, code, name, category") \
        .order("name").limit(500).execute().data or []
    names = [r["name"] for r in rows]
    print(f"\nfinal subject count: {len(names)}")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {r['code']:<8} {r['name']}  [{r.get('category', '')}]")
    unique = {n.strip().lower() for n in names}
    print(f"distinct names (case-insensitive): {len(unique)}")
    return 0 if len(unique) == len(names) else 1


if __name__ == "__main__":
    sys.exit(main())
