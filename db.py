
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import pandas as pd

# SQLite DB next to this file
DB_PATH = Path(__file__).with_name("crm.sqlite3")

# ---------------- Schema ----------------
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level INTEGER CHECK(level BETWEEN 1 AND 13),
    leg TEXT,
    associate_id TEXT,
    name TEXT NOT NULL,
    member_status TEXT CHECK(member_status IN ('Active','Expired')) DEFAULT 'Active',
    distributor_status TEXT CHECK(distributor_status IN ('Distributor','Inactive')) DEFAULT 'Distributor',
    location TEXT,
    phone TEXT UNIQUE,
    email TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    order_date TEXT,
    product TEXT,
    qty INTEGER DEFAULT 1,
    amount REAL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    channel TEXT,
    message TEXT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS contacts_updated_at
AFTER UPDATE ON contacts
FOR EACH ROW
BEGIN
    UPDATE contacts SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""

# ---------------- Connection helpers ----------------
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(TRIGGERS_SQL)

def row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}

# ---------------- Contacts ----------------
def fetch_contacts(filters: dict=None) -> list:
    filters = filters or {}
    sql = "SELECT * FROM contacts WHERE 1=1"
    params = []
    q = filters.get("q")
    if q:
        sql += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ? OR associate_id LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like, like]
    ms = filters.get("member_status")
    if ms:
        sql += " AND member_status IN (" + ",".join(["?"]*len(ms)) + ")"
        params += list(ms)
    ds = filters.get("distributor_status")
    if ds:
        sql += " AND distributor_status IN (" + ",".join(["?"]*len(ds)) + ")"
        params += list(ds)
    lv = filters.get("levels")
    if lv:
        sql += " AND level IN (" + ",".join(["?"]*len(lv)) + ")"
        params += list(lv)
    legs = filters.get("legs")
    if legs:
        sql += " AND leg IN (" + ",".join(["?"]*len(legs)) + ")"
        params += list(legs)
    sql += " ORDER BY level ASC, name ASC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_dict(r) for r in rows]

def insert_contact(data: dict) -> int:
    keys = ["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"]
    vals = [data.get(k) for k in keys]
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO contacts ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})",
            vals
        )
        return cur.lastrowid

def update_contact(contact_id: int, data: dict):
    allowed = ["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"]
    sets, vals = [], []
    for k,v in data.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    vals.append(contact_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id=?", vals)

def delete_contact(contact_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))

def bulk_upsert_from_dataframe(df):
    """Accepts a DataFrame with sample headers and upserts into contacts table."""
    df2 = df.copy()
    df2.columns = [str(c).strip() for c in df2.columns]
    rename = {
        "Level": "level",
        "Leg": "leg",
        "Associate's ID": "associate_id",
        "Name and surname": "name",
        "GO status": "member_status",
        "Location": "location",
        "Phone": "phone",
        "E-mail": "email",
        "Tags (comma-separated)": "tags",
    }
    for src, dst in rename.items():
        if src in df2.columns:
            df2.rename(columns={src: dst}, inplace=True)
    df2["distributor_status"] = "Distributor"
    if "member_status" in df2.columns:
        df2["member_status"] = (
            df2["member_status"].astype(str).str.strip().str.capitalize()
            .replace({"Expired": "Expired", "Active": "Active"})
        )
    else:
        df2["member_status"] = "Active"
    if "level" in df2.columns:
        df2["level"] = pd.to_numeric(df2["level"], errors="coerce").fillna(1).astype(int).clip(1,13)

    with get_conn() as conn:
        for _, r in df2.iterrows():
            rec = {k: (None if pd.isna(r.get(k)) else r.get(k)) for k in
                   ["level","leg","associate_id","name","member_status","distributor_status","location","phone","email","tags"]}
            if rec.get("phone"):
                exist = conn.execute("SELECT id FROM contacts WHERE phone=?", (rec["phone"],)).fetchone()
            else:
                exist = conn.execute("SELECT id FROM contacts WHERE associate_id=? AND name=?",
                                     (rec.get("associate_id"), rec.get("name"))).fetchone()
            if exist:
                conn.execute(
                    "UPDATE contacts SET level=?, leg=?, associate_id=?, name=?, member_status=?, distributor_status=?, location=?, phone=?, email=?, tags=? WHERE id=?",
                    (rec["level"], rec["leg"], rec["associate_id"], rec["name"], rec["member_status"],
                     rec["distributor_status"], rec["location"], rec["phone"], rec["email"], rec["tags"], exist["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO contacts(level,leg,associate_id,name,member_status,distributor_status,location,phone,email,tags) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (rec["level"], rec["leg"], rec["associate_id"], rec["name"], rec["member_status"],
                     rec["distributor_status"], rec["location"], rec["phone"], rec["email"], rec["tags"])
                )

# ---------------- Orders ----------------
def insert_order(data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders(contact_id,order_date,product,qty,amount,notes) VALUES(?,?,?,?,?,?)",
            (data.get("contact_id"), data.get("order_date"), data.get("product"),
             data.get("qty", 1), data.get("amount", 0.0), data.get("notes"))
        )
        return cur.lastrowid

def fetch_orders() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY order_date DESC, id DESC").fetchall()
        return [row_to_dict(r) for r in rows]

# ---------------- Activities & Campaigns ----------------
def insert_activity(contact_id: int, channel: str, message: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO activities(contact_id, channel, message) VALUES(?,?,?)",
                     (contact_id, channel, message))

def fetch_activities(contact_id: int=None) -> list:
    with get_conn() as conn:
        if contact_id:
            rows = conn.execute("SELECT * FROM activities WHERE contact_id=? ORDER BY ts DESC", (contact_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM activities ORDER BY ts DESC").fetchall()
        return [row_to_dict(r) for r in rows]

def insert_campaign(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO campaigns(name) VALUES(?)", (name,))
        return cur.lastrowid

def fetch_campaigns() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
        return [row_to_dict(r) for r in rows]

# ---------------- Dashboard KPIs ----------------
def kpis() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM contacts").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) c FROM contacts WHERE member_status='Active'").fetchone()["c"]
        expired = conn.execute("SELECT COUNT(*) c FROM contacts WHERE member_status='Expired'").fetchone()["c"]
        distributors = conn.execute("SELECT COUNT(*) c FROM contacts WHERE distributor_status='Distributor'").fetchone()["c"]
        inactive = conn.execute("SELECT COUNT(*) c FROM contacts WHERE distributor_status='Inactive'").fetchone()["c"]
        orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        return {
            "total_contacts": total,
            "active": active,
            "expired": expired,
            "distributors": distributors,
            "inactive": inactive,
            "orders": orders
        }

# Initialize DB if run directly
if __name__ == "__main__":
    init_db()
