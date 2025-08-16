# db.py — robust SQLite helpers (cloud-safe)
# Drop-in file. Paste over your current db.py.

import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Iterable

# -------- DB location (works local & Streamlit Cloud) --------
if os.environ.get("HOME", "").endswith("appuser"):  # Cloud container user
    DB_PATH = Path("/tmp/crm.sqlite3")
else:
    DB_PATH = Path(__file__).parent / "crm.sqlite3"

# -------- Columns (agreed schema) --------
CONTACT_COLUMNS: List[str] = [
    "name", "phone", "email",
    "source", "interest",
    "lead_temperature",
    "communication_status",
    "registration_status",
    "tags", "assigned", "notes",
    "action_needed", "action_taken",
    "username", "password",
    "date", "country", "province", "city",
]

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# -------- Utilities --------
def _is_nan(x: Any) -> bool:
    try:
        return x != x  # NaN != NaN
    except Exception:
        return False

def _to_text(v: Any) -> str:
    """Normalize ANY value to a safe string for SQLite."""
    if v is None or _is_nan(v):
        return ""
    # flatten lists/tuples/sets from multiselects
    if isinstance(v, (list, tuple, set)):
        return ", ".join(_to_text(x) for x in v)
    # everything else
    return str(v)

def _clean_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {c: _to_text(row.get(c, "")) for c in CONTACT_COLUMNS}

# -------- Schema --------
def ensure_schema() -> None:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, phone TEXT, email TEXT,
            source TEXT, interest TEXT,
            lead_temperature TEXT,
            communication_status TEXT,
            registration_status TEXT,
            tags TEXT, assigned TEXT, notes TEXT,
            action_needed TEXT, action_taken TEXT,
            username TEXT, password TEXT,
            date TEXT, country TEXT, province TEXT, city TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        );
    """)
    cur.execute("PRAGMA table_info(contacts);")
    existing = {row["name"] for row in cur.fetchall()}
    for col in CONTACT_COLUMNS:
        if col not in existing:
            cur.execute(f"ALTER TABLE contacts ADD COLUMN {col} TEXT;")
    if "created_at" not in existing:
        cur.execute("ALTER TABLE contacts ADD COLUMN created_at TEXT;")
    if "updated_at" not in existing:
        cur.execute("ALTER TABLE contacts ADD COLUMN updated_at TEXT;")
    conn.commit()
    conn.close()

# Back-compat for older imports
def init_db() -> None:
    ensure_schema()

# -------- CRUD --------
def insert_contact(row: Dict[str, Any]) -> int:
    ensure_schema()
    payload = _clean_row(row)
    cols = ", ".join(CONTACT_COLUMNS)
    ph = ", ".join(["?"] * len(CONTACT_COLUMNS))
    vals = [payload[c] for c in CONTACT_COLUMNS]
    sql = f"INSERT INTO contacts ({cols}) VALUES ({ph})"
    conn = _conn()
    cur = conn.cursor()
    cur.execute(sql, vals)
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id

def insert_one_contact(row: Dict[str, Any]) -> int:  # alias
    return insert_contact(row)

def insert_contacts(rows: Iterable[Dict[str, Any]]) -> int:
    ensure_schema()
    rows = list(rows or [])
    if not rows:
        return 0
    data = [[_to_text(r.get(c, "")) for c in CONTACT_COLUMNS] for r in rows]
    cols = ", ".join(CONTACT_COLUMNS)
    ph = ", ".join(["?"] * len(CONTACT_COLUMNS))
    sql = f"INSERT INTO contacts ({cols}) VALUES ({ph})"
    conn = _conn()
    cur = conn.cursor()
    cur.executemany(sql, data)
    conn.commit()
    n = cur.rowcount if cur.rowcount is not None else len(rows)
    conn.close()
    return n

def update_contact(contact_id: int, updates: Dict[str, Any]) -> None:
    ensure_schema()
    safe = {k: _to_text(v) for k, v in (updates or {}).items() if k in CONTACT_COLUMNS}
    if not safe:
        return
    sets = ", ".join([f"{k}=?" for k in safe.keys()])
    vals = list(safe.values()) + [contact_id]
    conn = _conn()
    conn.execute(f"UPDATE contacts SET {sets}, updated_at=datetime('now') WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_contact(contact_id: int) -> None:
    ensure_schema()
    conn = _conn()
    conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    conn.commit()
    conn.close()

def delete_all_contacts() -> None:
    ensure_schema()
    conn = _conn()
    conn.execute("DELETE FROM contacts;")
    conn.commit()
    conn.close()

def fetch_contacts() -> List[Dict[str, Any]]:
    ensure_schema()
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM contacts ORDER BY id DESC;")
    out = [dict(r) for r in cur.fetchall()]
    conn.close()
    return out
