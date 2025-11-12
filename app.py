import streamlit as st
import sqlite3
import uuid
from datetime import datetime

# -------------------- 初始化数据库 --------------------
def init_db():
    conn = sqlite3.connect("customers.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT,
        contact TEXT,
        email TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS action_logs (
        id TEXT PRIMARY KEY,
        username TEXT,
        action TEXT,
        target_table TEXT,
        target_id TEXT,
        details TEXT,
        created_at TEXT
    )
    """)
    cur.execute("INSERT OR IGNORE INTO users VALUES (?,?,?)", ("admin", "123456", "admin"))
    conn.commit()
    conn.close()

init_db()

# -------------------- 通用函数 --------------------
def get_conn():
    return sqlite3.connect("customers.db")

def log_action(username, action, target_table, target_id, details):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO action_logs(id,username,action,target_table,target_id,details,created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (str(uuid.uuid4()), username, action, target_table, target_id, details, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# -------------------- 客户管理功能 --------------------
def get_customers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, contact, email, notes, created_at FROM customers ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

def add_customer(data):
    conn = get_conn()
    cur = conn.cursor()
    cid = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO customers(id,name,contact,email,notes,created_at)
        VALUES (?,?,?,?,?,?)
    """, (cid, data["name"], data["contact"], data["email"], data["notes"], datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "add_customer", "customers", cid, str(data))
    return cid

def update_customer(cid, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE customers SET name=?, contact=?, email=?, notes=? WHERE id=?
    """, (data["name"], data["contact"], data["email"], data["notes"], cid))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "update_customer", "customers", cid, str(data))

def delete_customer(cid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "delete_customer", "customers", cid, "{}")

# -------------------- 登录功能 --------------------
def login(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# -------------------- Streamlit 界面 --------------------
st.set_page_config(page_title="客户管理系统", layout="wide")

if "login" not in st.session_state:
    st.session_state["login"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

if not st.session_state["login"]:
    st.title("🔐 登录系统")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        role = login(username, password)
        if role:
            st.session_state["login"] = True
            st.session_state["username"] = username
            st.session_state["role"] = role
            st.success("登录成功！")
            st.rerun()
        else:
            st.error("用户名或密码错误")
    st.stop()

# -------------------- 登录后主界面 --------------------
st.sidebar.title(f"👋 欢迎 {st.session_state['username']}")
menu = st.sidebar.radio("选择功能", ["客户信息", "操作日志", "退出登录"])

if menu == "客户信息":
    st.header("📋 客户信息管理")

    with st.expander("➕ 添加客户", expanded=False):
        with st.form("add_form"):
            name = st.text_input("姓名")
            contact = st.text_input("联系电话")
            email = st.text_input("电子邮箱")
            notes = st.text_area("备注")
            submitted = st.form_submit_button("保存")
            if submitted:
                add_customer({
                    "name": name,
                    "contact": contact,
                    "email": email,
                    "notes": notes
                })
                st.success("✅ 客户已添加成功！")
                st.rerun()

    st.subheader("现有客户")
    customers = get_customers()
    if not customers:
        st.info("暂无客户信息")
    else:
        for cid, name, contact, email, notes, created_at in customers:
            with st.expander(f"👤 {name}"):
                st.write(f"📞 联系方式: {contact}")
                st.write(f"✉️ 邮箱: {email}")
                st.write(f"📝 备注: {notes}")
                st.write(f"🕓 创建时间: {created_at}")
                c1, c2 = st.columns(2)
                if c1.button("✏️ 编辑", key=f"edit_{cid}"):
                    new_name = st.text_input("新姓名", value=name, key=f"n_{cid}")
                    new_contact = st.text_input("新电话", value=contact, key=f"c_{cid}")
                    new_email = st.text_input("新邮箱", value=email, key=f"e_{cid}")
                    new_notes = st.text_area("新备注", value=notes, key=f"nt_{cid}")
                    if st.button("保存修改", key=f"save_{cid}"):
                        update_customer(cid, {
                            "name": new_name,
                            "contact": new_contact,
                            "email": new_email,
                            "notes": new_notes
                        })
                        st.success("已更新客户信息")
                        st.rerun()
                if c2.button("🗑 删除", key=f"del_{cid}"):
                    delete_customer(cid)
                    st.warning(f"客户 {name} 已被删除")
                    st.rerun()

elif menu == "操作日志":
    st.header("🧾 操作日志")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, action, target_table, target_id, created_at FROM action_logs ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    if rows:
        for u, a, t, i, c in rows:
            st.write(f"👤 {u} | 动作: {a} | 表: {t} | ID: {i} | 🕓 {c}")
    else:
        st.info("暂无日志记录")

elif menu == "退出登录":
    st.session_state["login"] = False
    st.session_state["username"] = ""
    st.success("已退出登录")
    st.rerun()
