# db_ops.py
import sqlite3
import pathlib
import uuid
import hashlib
import pandas as pd
from datetime import datetime

DB_FILE = pathlib.Path("crm_data.sqlite")

def get_conn():
    DB_FILE.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        preferred_lang TEXT DEFAULT 'zh'
    )""")

    # customers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT,
        whatsapp TEXT,
        line TEXT,
        telegram TEXT,
        country TEXT,
        city TEXT,
        age INTEGER,
        job TEXT,
        income TEXT,
        relation TEXT,
        deal_amount REAL,
        level TEXT,
        progress TEXT,
        main_person TEXT,
        assistant TEXT,
        remark TEXT,
        created_at TEXT
    )""")

    # followups
    cur.execute("""
    CREATE TABLE IF NOT EXISTS followups (
        id TEXT PRIMARY KEY,
        customer_id TEXT,
        author TEXT,
        note TEXT,
        next_action TEXT,
        created_at TEXT
    )""")

    # translations
    cur.execute("""
    CREATE TABLE IF NOT EXISTS translations (
        key TEXT PRIMARY KEY,
        zh TEXT,
        en TEXT,
        idn TEXT,
        km TEXT,
        vn TEXT
    )""")

    # action logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS action_logs (
        id TEXT PRIMARY KEY,
        username TEXT,
        action TEXT,
        target_table TEXT,
        target_id TEXT,
        details TEXT,
        created_at TEXT
    )""")

    # default admin user
    cur.execute("SELECT COUNT(1) as c FROM users")
    cnt = cur.fetchone()["c"]
    if cnt == 0:
        cur.execute("INSERT INTO users(username,password_hash,role,full_name,preferred_lang) VALUES (?,?,?,?,?)",
                    ("admin", hash_pw("admin123"), "admin", "管理员", "zh"))

    conn.commit()
    conn.close()

# User ops
def auth_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username,role,preferred_lang FROM users WHERE username=? AND password_hash=?", (username, hash_pw(password)))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def add_user(username, password, role="user", full_name="", preferred_lang="zh"):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users(username,password_hash,role,full_name,preferred_lang) VALUES (?,?,?,?,?)",
                    (username, hash_pw(password), role, full_name, preferred_lang))
        conn.commit()
        log_action(username, "add_user", "users", username, f"role={role}, full_name={full_name}")
        return True, "OK"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def list_users():
    conn = get_conn()
    df = pd.read_sql_query("SELECT username,role,full_name,preferred_lang FROM users", conn)
    conn.close()
    return df

def update_user_password(username, new_password):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_pw(new_password), username))
    conn.commit()
    log_action(username, "reset_password", "users", username, "")
    conn.close()

def delete_user(username):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    log_action(username, "delete_user", "users", username, "")
    conn.close()

# Customer ops
def add_customer_record(rec: dict):
    conn = get_conn()
    cur = conn.cursor()
    cid = str(uuid.uuid4())
    rec_db = {
        "id": cid,
        "name": rec.get("name"),
        "whatsapp": rec.get("whatsapp"),
        "line": rec.get("line"),
        "telegram": rec.get("telegram"),
        "country": rec.get("country"),
        "city": rec.get("city"),
        "age": rec.get("age"),
        "job": rec.get("job"),
        "income": rec.get("income"),
        "relation": rec.get("relation"),
        "deal_amount": rec.get("deal_amount") or 0.0,
        "level": rec.get("level"),
        "progress": rec.get("progress"),
        "main_person": rec.get("main_person"),
        "assistant": rec.get("assistant"),
        "remark": rec.get("remark"),
        "created_at": datetime.utcnow().isoformat()
    }
    keys = ",".join(rec_db.keys())
    vals = ",".join("?" for _ in rec_db)
    cur.execute(f"INSERT INTO customers({keys}) VALUES ({vals})", tuple(rec_db.values()))
    conn.commit()
    conn.close()
    log_action(rec_db["main_person"] or "system", "add_customer", "customers", cid, str(rec_db))
    return cid

def list_customers_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()
    return df

def get_customer_by_id(cid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id=?", (cid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_customer(cid, updates: dict, actor="system"):
    conn = get_conn()
    cur = conn.cursor()
    set_sql = ",".join([f"{k}=?" for k in updates.keys()])
    cur.execute(f"UPDATE customers SET {set_sql} WHERE id=?", tuple(list(updates.values()) + [cid]))
    conn.commit()
    conn.close()
    log_action(actor, "update_customer", "customers", cid, str(updates))

def delete_customer(cid, actor="system"):
    conn = get_conn()
    conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    log_action(actor, "delete_customer", "customers", cid, "")

# Followups
def add_followup(cid, author, note, next_action=""):
    conn = get_conn()
    cur = conn.cursor()
    fid = str(uuid.uuid4())
    cur.execute("INSERT INTO followups(id,customer_id,author,note,next_action,created_at) VALUES (?,?,?,?,?,?)",
                (fid, cid, author, note, next_action, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    log_action(author, "add_followup", "followups", fid, f"customer_id={cid}")

def list_followups(cid):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM followups WHERE customer_id=? ORDER BY created_at DESC", conn, params=(cid,))
    conn.close()
    return df

# Translations storage (optional)
def upsert_translation_row(key, zh, en, idn, km, vn):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO translations(key,zh,en,idn,km,vn) VALUES (?,?,?,?,?,?)",
                 (key, zh, en, idn, km, vn))
    conn.commit()
    conn.close()

def export_translations_as_dict():
    # fallback: read translations.json if DB empty
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM translations", conn)
    conn.close()
    if df.empty:
        import json, pathlib
        p = pathlib.Path("translations.json")
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}
    res = {}
    for _, r in df.iterrows():
        res[r["key"]] = {"zh": r["zh"], "en": r["en"], "id": r["idn"], "km": r["km"], "vn": r["vn"]}
    return res

# Logs
def log_action(username, action, target_table="", target_id="", details=""):
    conn = get_conn()
    conn.execute("INSERT INTO action_logs(id,username,action,target_table,target_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                 (str(uuid.uuid4()), username, action, target_table, target_id, details, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def recent_logs(limit=200):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM action_logs ORDER BY created_at DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df
