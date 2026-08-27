from backend.database.local_db import _connect

cur = _connect().cursor()
print("FEATURED:")
cur.execute(
    "SELECT name, avg_package, placement_pct, rating, nirf_rank FROM colleges WHERE featured=1 LIMIT 3"
)
for r in cur.fetchall():
    print(
        "  ",
        r["name"],
        "| pkg",
        r["avg_package"],
        "| place",
        r["placement_pct"],
        "| rating",
        r["rating"],
    )
print("BULK govt:")
cur.execute(
    "SELECT name, avg_package, placement_pct, rating, nirf_rank FROM colleges WHERE featured=0 AND type='govt' LIMIT 3"
)
for r in cur.fetchall():
    print(
        "  ",
        r["name"],
        "| pkg",
        r["avg_package"],
        "| place",
        r["placement_pct"],
        "| rating",
        r["rating"],
    )
cur.execute("SELECT COUNT(*) FROM colleges WHERE avg_package IS NOT NULL")
print("WITH avg_package:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM colleges WHERE placement_pct IS NOT NULL")
print("WITH placement_pct:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM colleges WHERE rating IS NOT NULL")
print("WITH rating:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM colleges WHERE type IS NOT NULL")
print("WITH type:", cur.fetchone()[0])
