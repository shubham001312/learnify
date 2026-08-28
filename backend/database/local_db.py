import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "colleges.db")


def db_available() -> bool:
    return os.path.isfile(DB_PATH)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize(rows):
    out = []
    for r in rows:
        d = dict(r)
        d["streams"] = d["streams"].split(",") if d.get("streams") else []
        d["top_recruiters"] = (
            d["top_recruiters"].split(",") if d.get("top_recruiters") else []
        )
        d["pros"] = d["pros"].split(",") if d.get("pros") else []
        d["cons"] = d["cons"].split(",") if d.get("cons") else []
        out.append(d)
    return out


def query_colleges(
    type=None,
    state=None,
    q=None,
    stream=None,
    district=None,
    top=False,
    min_rank=None,
    min_package=None,
    sort="default",
    limit=60,
    offset=0,
):
    conn = _connect()
    cur = conn.cursor()
    wheres = []
    params = []
    if type:
        t = str(type).lower()
        if t in ("govt", "government"):
            wheres.append("type = 'govt'")
        elif t in ("private", "priv"):
            wheres.append("type = 'private'")
        elif t in ("deemed",):
            wheres.append("type = 'deemed'")
    if state:
        wheres.append("state = ?")
        params.append(state)
    if district:
        wheres.append("(district LIKE ? OR city LIKE ?)")
        params.append("%" + district + "%")
        params.append("%" + district + "%")
    if q:
        wheres.append("name LIKE ?")
        params.append("%" + q + "%")
    if stream:
        wheres.append("streams LIKE ?")
        params.append("%" + stream + "%")
    if min_rank is not None:
        wheres.append("nirf_rank IS NOT NULL AND nirf_rank <= ?")
        params.append(int(min_rank))
    if min_package is not None:
        wheres.append("avg_package IS NOT NULL AND avg_package >= ?")
        params.append(float(min_package))
    if top:
        wheres.append("nirf_rank IS NOT NULL AND nirf_rank > 0")

    where = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    s = (sort or "default").lower()
    if s == "nirf":
        order = "ORDER BY CASE WHEN nirf_rank IS NULL THEN 1 ELSE 0 END, nirf_rank ASC"
    elif s == "package":
        order = (
            "ORDER BY CASE WHEN avg_package IS NULL THEN 1 ELSE 0 END, avg_package DESC"
        )
    elif s == "name":
        order = "ORDER BY name ASC"
    elif top:
        order = "ORDER BY nirf_rank ASC"
    else:
        order = "ORDER BY featured DESC, name"

    cur.execute(
        f"SELECT * FROM colleges {where} {order} LIMIT ? OFFSET ?",
        params + [int(limit), int(offset)],
    )
    rows = _normalize(cur.fetchall())
    cur.execute(f"SELECT COUNT(*) FROM colleges {where}", params)
    total = cur.fetchone()[0]
    conn.close()
    return rows, total


def get_college(college_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM colleges WHERE id = ? LIMIT 1", (college_id,))
    row = cur.fetchone()
    conn.close()
    return _normalize([row])[0] if row else None


def list_states():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT state FROM colleges WHERE state IS NOT NULL ORDER BY state"
    )
    states = [r["state"] for r in cur.fetchall()]
    conn.close()
    return states


def list_cities(state=None):
    conn = _connect()
    cur = conn.cursor()
    if state:
        cur.execute(
            "SELECT DISTINCT city FROM colleges WHERE city IS NOT NULL AND state = ? ORDER BY city",
            (state,),
        )
    else:
        cur.execute(
            "SELECT DISTINCT city FROM colleges WHERE city IS NOT NULL ORDER BY city"
        )
    cities = [
        r["city"]
        for r in cur.fetchall()
        if r["city"] and len(r["city"]) >= 2 and not r["city"].isdigit()
    ]
    conn.close()
    return cities


def ensure_reviews_table():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS college_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            college_id INTEGER,
            author TEXT,
            rating REAL,
            text TEXT,
            pros TEXT,
            cons TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def get_reviews(college_id):
    ensure_reviews_table()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM college_reviews WHERE college_id = ? ORDER BY created_at DESC",
        (college_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_review(college_id, author, rating, text, pros, cons):
    ensure_reviews_table()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO college_reviews (college_id, author, rating, text, pros, cons)
           VALUES (?,?,?,?,?,?)""",
        (college_id, author, rating, text, pros, cons),
    )
    conn.commit()
    conn.close()


def ensure_scanned_table():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scanned_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            data_type TEXT DEFAULT 'note',
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            source TEXT DEFAULT '',
            meta TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scanned_user ON scanned_data(user_id)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_scanned_user_created "
        "ON scanned_data(user_id, created_at)"
    )
    conn.commit()
    conn.close()


def _row_to_dict(r):
    d = dict(r)
    try:
        d["meta"] = json.loads(d.get("meta") or "{}")
    except Exception:
        d["meta"] = {}
    return d


def add_scanned(record):
    ensure_scanned_table()
    conn = _connect()
    cur = conn.cursor()
    meta = record.get("meta") or {}
    meta_str = json.dumps(meta) if isinstance(meta, dict) else str(meta)
    cur.execute(
        """INSERT INTO scanned_data (user_id, data_type, title, content, source, meta)
           VALUES (?,?,?,?,?,?)""",
        (
            record.get("user_id"),
            record.get("data_type", "note"),
            record.get("title", ""),
            record.get("content", ""),
            record.get("source", ""),
            meta_str,
        ),
    )
    rid = cur.lastrowid
    conn.commit()
    cur.execute("SELECT * FROM scanned_data WHERE id = ?", (rid,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row) if row else record


def list_scanned(user_id, limit=100, offset=0):
    ensure_scanned_table()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM scanned_data WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, int(limit), int(offset)),
    )
    rows = [_row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_scanned(user_id, item_id):
    ensure_scanned_table()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM scanned_data WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    conn.commit()
    conn.close()
