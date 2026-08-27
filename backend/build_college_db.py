import csv
import os
import sqlite3

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "colleges.db")

SOURCES = [
    "https://raw.githubusercontent.com/PriyanKishoreMS/colleges-api/master/data/colleges.csv",
    "https://raw.githubusercontent.com/arpitagarwala/indian-institutions-data/main/data/colleges.csv",
]


def download_csv(url):
    print(f"[build] downloading {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.text.splitlines()


# Only HIGH-CONFIDENCE tokens are used. Anything ambiguous is left unlabeled
# (type = None) instead of being guessed wrongly.
GOVT_HINTS = (
    "indian institute of technology",
    "national institute of technology",
    "indian institute of information technology",
    "indian institute of science",
    "indian institute of management",
    "all india institute of medical",
    "indian statistical",
    "national law university",
    "sardar vallabhbhai",
    "government",
    "govt",
    "central university",
    "state university",
    "national institute of",
    "indian institute of",
    "rajiv gandhi university",
    "dr. babasaheb ambedkar",
    "indira gandhi national",
    "maulana azad",
    "aligarh muslim university",
    "banaras hindu university",
    "visva-bharati",
    "english and foreign languages university",
    "university of delhi",
    "university of calcutta",
    "university of madras",
    "university of mumbai",
    "university of hyderabad",
    "jamia millia islamia",
    "jawaharlal nehru university",
)
PRIV_HINTS = (
    "private",
    "deemed",
    "self finance",
    "self-finance",
    "self financed",
    "self-financed",
    "(deemed",
    "(private",
    "private university",
    "private college",
    "group of institutions",
)


def classify_type(name: str):
    n = (name or "").lower()
    if any(h in n for h in GOVT_HINTS):
        return "govt"
    if any(h in n for h in PRIV_HINTS):
        return "private"
    return None


def build():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS colleges")
    cur.execute(
        """
        CREATE TABLE colleges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            state TEXT,
            city TEXT,
            district TEXT,
            pin_code TEXT,
            address TEXT,
            type TEXT,
            nirf_rank INTEGER,
            avg_package REAL,
            placement_pct INTEGER,
            rating REAL,
            streams TEXT,
            top_recruiters TEXT,
            min_12th_marks INTEGER,
            website TEXT,
            affiliation TEXT,
            founded TEXT,
            description TEXT,
            pros TEXT,
            cons TEXT,
            featured INTEGER DEFAULT 0
        )
        """
    )

    total = 0
    for url in SOURCES:
        try:
            lines = download_csv(url)
        except Exception as e:
            print(f"[build] source failed: {e}")
            continue
        reader = csv.DictReader(lines)
        rows = []
        for row in reader:
            name = (row.get("Name") or row.get("name") or "").strip()
            if not name:
                continue
            state = (
                row.get("State") or row.get("stateName") or row.get("state") or ""
            ).strip()
            city = (
                row.get("City") or row.get("districtName") or row.get("city") or ""
            ).strip()
            addr = " ".join(
                [row.get("Address_line1", ""), row.get("Address_line2", "")]
            ).strip()
            t = classify_type(name)
            rows.append(
                (name, state or None, city or None, None, None, addr or None, t)
            )
        cur.executemany(
            "INSERT INTO colleges (name, state, city, district, pin_code, address, type, featured) VALUES (?,?,?,?,?,?,?,0)",
            rows,
        )
        total += len(rows)
        print(f"[build] inserted {len(rows)} from {url}")
        break  # first successful source is enough

    # Featured, enriched colleges from our curated seed
    try:
        from backend.database.seed import SEED_COLLEGES

        feat = []
        for c in SEED_COLLEGES:
            feat.append(
                (
                    c["name"],
                    c.get("state"),
                    c.get("location"),
                    c.get("district"),
                    c.get("pin_code"),
                    c.get("address")
                    or " ".join(
                        [
                            (c.get("address_line1") or ""),
                            (c.get("address_line2") or ""),
                        ]
                    ).strip()
                    or None,
                    c.get("type"),
                    1,
                    c.get("nirf_rank"),
                    float(c["avg_package"]) if c.get("avg_package") else None,
                    c.get("placement_pct"),
                    c.get("rating"),
                    ",".join(c.get("streams", [])) or None,
                    ",".join(c.get("top_recruiters", [])) or None,
                    c.get("min_12th_marks"),
                    c.get("website"),
                    c.get("affiliation"),
                    c.get("founded"),
                    c.get("description"),
                    ",".join(c.get("pros", [])) or None,
                    ",".join(c.get("cons", [])) or None,
                )
            )
        cur.executemany(
            """INSERT INTO colleges
               (name, state, city, district, pin_code, address, type, featured, nirf_rank, avg_package,
                placement_pct, rating, streams, top_recruiters, min_12th_marks, website, affiliation,
                founded, description, pros, cons)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            feat,
        )
        print(f"[build] inserted {len(feat)} featured colleges")
    except Exception as e:
        print(f"[build] featured insert skipped: {e}")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM colleges")
    print("[build] total colleges in DB:", cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    build()
