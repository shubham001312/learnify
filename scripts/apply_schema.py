import os
import sys
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY in .env")
    sys.exit(1)

# Use supabase client without extra options to avoid type issues
from supabase import create_client

client = create_client(url, key)

# Read schema.sql and extract CREATE TABLE IF NOT EXISTS statements
schema_path = os.path.join(
    os.path.dirname(__file__), "backend", "database", "schema.sql"
)
with open(schema_path, "r", encoding="utf-8") as f:
    schema_sql = f.read()

# The schema.sql has many CREATE TABLE IF NOT EXISTS statements.
# The supabase Python client doesn't support raw DDL execution.
# Instead, let's check which tables exist and which are missing,
# then provide the migration path.

# List of all table names from schema.sql
all_table_names = [
    "users",
    "colleges",
    "scholarships",
    "college_reviews",
    "scanned_data",
    "documents",
    "doc_chunks",
    "conversations",
    "memory",
    "subscriptions",
    "sgpa_entries",
    "user_profiles",
    "study_plans",
    "organizations",
    "user_roles",
    "skill_categories",
    "skills",
    "skill_aliases",
    "user_skills",
    "assessments",
    "assessment_questions",
    "assessment_options",
    "question_skills",
    "assessment_attempts",
    "assessment_responses",
    "career_roles",
    "role_skills",
    "opportunities",
    "opportunity_skills",
    "applications",
    "application_events",
    "learning_resources",
    "resource_skills",
    "learning_progress",
    "portfolio_items",
    "verification_records",
    "notifications",
    "audit_logs",
    "internships",
    "milestones",
    "internship_tasks",
    "deliverables",
    "mentor_assignments",
    "mentor_feedback",
    "evaluations",
    "credentials",
    "institution_sync_jobs",
    "collaboration_projects",
]

print("=== TABLE INVENTORY ===")
existing_tables = []
missing_tables = []

for t in all_table_names:
    try:
        r = client.table(t).select("*").limit(1).execute()
        existing_tables.append(t)
        print(f"  ✓ {t}")
    except Exception as e:
        missing_tables.append(t)
        err_msg = str(e)
        if "Could not find the table" in err_msg:
            print(f"  ✗ {t} — MISSING (table not in schema cache)")
        else:
            print(f"  ? {t} — ERROR: {err_msg[:80]}")

print(f"\nExisting: {len(existing_tables)}/{len(all_table_names)}")
print(f"Missing:  {len(missing_tables)}/{len(all_table_names)}")

if missing_tables:
    print(f"\n{len(missing_tables)} tables are missing from Supabase.")
    print("To apply the schema, open Supabase Dashboard → SQL Editor")
    print("and run the contents of: backend/database/schema.sql")
    print("Then re-run this script to verify.")

print("\n=== NEXT STEPS ===")
print("1. Apply schema.sql to Supabase SQL Editor")
print("2. Re-run: python apply_schema.py")
print("3. Run: python backend/database/seed.py  (to populate demo data)")
print("4. Test E2E: uvicorn backend.main:app --reload & open http://127.0.0.1:8000")
