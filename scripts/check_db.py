import os
import sys
from dotenv import load_dotenv

load_dotenv()

os.chdir(r"A:\Learnify")
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_ANON_KEY"]
client = create_client(url, key)

# Check what tables and columns actually exist
tables_to_check = ["users", "colleges", "scholarships"]

for t in tables_to_check:
    try:
        r = client.table(t).select("*").limit(1).execute()
        if r.data:
            print(f"\n=== {t} ===")
            print(f"  Columns: {list(r.data[0].keys())}")
            print(f"  Sample row: {r.data[0]}")
        else:
            print(f"\n=== {t} ===")
            print(f"  No data rows")
    except Exception as e:
        print(f"\n=== {t} ===")
        print(f"  ERROR: {str(e)[:100]}")

# Also check a few more
for t in ["college_reviews", "scanned_data", "documents"]:
    try:
        r = client.table(t).select("*").limit(1).execute()
        if r.data:
            print(f"\n=== {t} ===")
            print(f"  Columns: {list(r.data[0].keys())}")
        else:
            print(f"\n=== {t} ===")
            print(f"  No data rows")
    except Exception as e:
        print(f"\n=== {t} ===")
        print(f"  MISSING or ERROR: {str(e)[:60]}")
