# app.py - AYaocustomers 完整版
import streamlit as st
import sqlite3
import pandas as pd
import uuid
import hashlib
import json
import io
from datetime import datetime, timedelta
import altair as alt

# 如果你实现了备份模块（backup.py），这里会被调用；否则注释掉相关调用
try:
    import backup
    HAS_BACKUP = True
except Exception:
    HAS_BACKUP = False

DB_FILE = "customers.db"
TRANS_FILE = "translations.json"

# ------------------ 辅助函数 ------------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def ensure_session_keys():
    if "lang" not in st.session_state:
        st.session_state["lang"] = "中文"
    if "logged" not in st.session_state:
        st.session_state["logged"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = None

# ------------------ 翻译加载 ------------------
def load_translations():
    try:
        with open(TRANS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # accept both keyed by short codes or Chinese key map; normalize to dict-of-dicts
            return data
    except Exception:
        # default minimal translations fallback
        return {
            "中文": {
                "app_title":"氯雷他定用户统计",
                "login":"登录",
                "username":"用户名",
                "password":"密码",
                "login_button":"登录",
                "logout_button":"退出登录",
                "customers":"客户管理",
                "add_customer":"新增客户",
                "export":"导出Excel",
                "details":"客户详情",
                "edit":"编辑",
                "delete":"删除",
                "save":"保存",
                "filter":"筛选",
                "language":"语言",
                "backup_now":"手动备份",
                "admin_area":"管理员设置",
                "no_data":"暂无数据"
            }
        }

TRANSLATIONS = load_translations()
LANG_OPTIONS = ["中文","English","Bahasa Indonesia","ភាសាខ្មែរ","Tiếng Việt"]

def t(key: str) -> str:
    # get translation for current session language, fallback to key
    lang = st.session_state.get("lang", "中文")
    mapping = TRANSLATIONS.get(lang) or TRANSLATIONS.get("中文") or {}
    return mapping.get(key, key)

# ------------------ 初始化数据库 ------------------
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
        preferred_lang TEXT DEFAULT '中文'
    )
    """)
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
    )
    """)
    # followups
    cur.execute("""
    CREATE TABLE IF NOT EXISTS followups (
        id TEXT PRIMARY KEY,
        customer_id TEXT,
        author TEXT,
        note TEXT,
        next_action TEXT,
        created_at TEXT
    )
    """)
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
    )
    """)
    # translations table optional (not required)
    conn.commit()
    # default admin user
    cur.execute("SELECT COUNT(1) as c FROM users")
    r = cur.fetchone()
    if r and r["c"] == 0:
        cur.execute("INSERT INTO users(username,password_hash,role,full_name,preferred_lang) VALUES (?,?,?,?,?)",
                    ("admin", hash_pw("admin123"), "admin", "管理员", "中文"))
        conn.commit()
    conn.close()

def log_action(username, action, target_table="", target_id="", details=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO action_logs(id,username,action,target_table,target_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), username, action, target_table, target_id, details, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# ------------------ 用户 / 客户 操作 ------------------
def auth_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username,role,preferred_lang FROM users WHERE username=? AND password_hash=?", (username, hash_pw(password)))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def add_user(username, password, role="user", full_name="", preferred_lang="中文"):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO users(username,password_hash,role,full_name,preferred_lang) VALUES (?,?,?,?,?)",
                    (username, hash_pw(password), role, full_name, preferred_lang))
        conn.commit()
        conn.close()
        log_action(st.session_state.get("username","system"), "add_user", "users", username, f"role={role}")
        return True, "OK"
    except Exception as e:
        return False, str(e)

def list_users_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT username,role,full_name,preferred_lang FROM users", conn)
    conn.close()
    return df

def reset_user_password(username, new_password):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_pw(new_password), username))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "reset_password", "users", username, "")

def delete_user(username):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "delete_user", "users", username, "")

# customer ops
def add_customer(rec: dict):
    cid = str(uuid.uuid4())
    rec_clean = {
        "id": cid,
        "name": rec.get("name"),
        "whatsapp": rec.get("whatsapp"),
        "line": rec.get("line"),
        "telegram": rec.get("telegram"),
        "country": rec.get("country"),
        "city": rec.get("city"),
        "age": int(rec.get("age")) if rec.get("age") else None,
        "job": rec.get("job"),
        "income": rec.get("income"),
        "relation": rec.get("relation"),
        "deal_amount": float(rec.get("deal_amount") or 0.0),
        "level": rec.get("level"),
        "progress": rec.get("progress"),
        "main_person": rec.get("main_person"),
        "assistant": rec.get("assistant"),
        "remark": rec.get("remark"),
        "created_at": datetime.utcnow().isoformat()
    }
    conn = get_conn()
    cur = conn.cursor()
    keys = ",".join(rec_clean.keys())
    qmarks = ",".join("?" for _ in rec_clean)
    cur.execute(f"INSERT INTO customers({keys}) VALUES ({qmarks})", tuple(rec_clean.values()))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "add_customer", "customers", cid, rec_clean)
    return cid

def list_customers_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()
    return df

def get_customer(cid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id=?", (cid,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def update_customer(cid, updates: dict):
    if not updates:
        return
    conn = get_conn()
    cur = conn.cursor()
    set_sql = ",".join([f"{k}=?" for k in updates.keys()])
    cur.execute(f"UPDATE customers SET {set_sql} WHERE id=?", tuple(list(updates.values()) + [cid]))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "update_customer", "customers", cid, str(updates))

def delete_customer(cid):
    conn = get_conn()
    conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("username","system"), "delete_customer", "customers", cid, "")

# followups
def add_followup(cid, author, note, next_act=""):
    fid = str(uuid.uuid4())
    conn = get_conn()
    conn.execute("INSERT INTO followups(id,customer_id,author,note,next_action,created_at) VALUES (?,?,?,?,?,?)",
                 (fid, cid, author, note, next_act, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    log_action(author, "add_followup", "followups", fid, f"customer_id={cid}")

def list_followups_df(cid):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM followups WHERE customer_id=? ORDER BY created_at DESC", conn, params=(cid,))
    conn.close()
    return df

def recent_actions(limit=500):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM action_logs ORDER BY created_at DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df

# ------------------ 初始化 ------------------
ensure_session_keys()
init_db()

# ------------------ 页面布局与逻辑 ------------------
st.set_page_config(page_title=t("app_title") if t("app_title") else "AYaocustomers", layout="wide")

# LOGIN VIEW
if not st.session_state["logged"]:
    st.title(t("login") if t("login") else "登录")
    st.info(t("login") if t("login") else "请登录")
    col1, col2 = st.columns([2,1])
    with col1:
        # language selector (persisted)
        if "lang" not in st.session_state:
            st.session_state["lang"] = "中文"
        lang_choice = st.selectbox(t("language") if t("language") else "语言", LANG_OPTIONS, index=LANG_OPTIONS.index(st.session_state["lang"]))
        st.session_state["lang"] = lang_choice

        username = st.text_input(t("username"))
        password = st.text_input(t("password"), type="password")
        if st.button(t("login_button") if t("login_button") else "登录"):
            user = auth_user(username, password)
            if user:
                st.session_state["logged"] = True
                st.session_state["username"] = user["username"]
                st.session_state["role"] = user["role"]
                st.session_state["lang"] = user.get("preferred_lang", st.session_state.get("lang","中文"))
                st.success(f"{t('welcome') if t('welcome') else '欢迎'}, {st.session_state['username']}")
                # admin auto backup trigger (best-effort)
                if HAS_BACKUP and st.session_state["role"] == "admin":
                    try:
                        ok, resp = backup.backup_db_to_github(st.secrets, actor=st.session_state["username"])
                        if ok:
                            st.info("自动备份触发成功（管理员登录）")
                        else:
                            st.info(f"自动备份未成功：{str(resp)[:200]}")
                    except Exception as e:
                        st.info(f"备份触发异常：{e}")
                st.rerun()
            else:
                st.error(t("login") if t("login") else "用户名或密码错误")
    with col2:
        st.markdown("### " + (t("admin_area") if t("admin_area") else "管理员设置"))
        st.write("- 默认管理员：admin / admin123")
        st.write("- 登录后请创建用户并修改密码")
    st.stop()

# MAIN APP
username = st.session_state["username"]
role = st.session_state["role"]
# topbar: language & logout
st.sidebar.title("📊 " + (t("app_title") if t("app_title") else "AYaocustomers"))
st.sidebar.write(f"👤 {username} ({role})")
if "lang" not in st.session_state:
    st.session_state["lang"] = "中文"
lang_choice = st.sidebar.selectbox(t("language") if t("language") else "Language", LANG_OPTIONS, index=LANG_OPTIONS.index(st.session_state["lang"]))
if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice
if st.sidebar.button(t("logout_button") if t("logout_button") else "退出登录"):
    st.session_state.clear()
    st.rerun()

# Admin quick actions
if role == "admin":
    if st.sidebar.button(t("backup_now") if t("backup_now") else "手动备份"):
        if HAS_BACKUP:
            ok, resp = backup.backup_db_to_github(st.secrets, actor=username)
            if ok:
                st.sidebar.success("备份成功")
            else:
                st.sidebar.error("备份失败：" + str(resp)[:200])
        else:
            st.sidebar.info("未检测到备份模块")

# Load customers table
df = list_customers_df()
# permission: non-admin only their customers
if role != "admin":
    df = df[(df["main_person"]==username) | (df["assistant"].str.contains(username, na=False))]

# Filters
st.title(t("app_title") if t("app_title") else "氯雷他定用户统计")
colf1, colf2, colf3 = st.columns([2,1,1])
with colf1:
    st.subheader(t("customers") if t("customers") else "客户管理")
with colf2:
    period = st.selectbox(t("filter") if t("filter") else "筛选", ["全部","最近7天","最近30天","最近90天"])
with colf3:
    owner_filter = st.selectbox(t("main_person") if "main_person" in (TRANSLATIONS.get(st.session_state["lang"]) or {}) else "主要负责人", ["全部"] + sorted(df["main_person"].dropna().unique().tolist()) if not df.empty else ["全部"])

# apply period
if period != "全部":
    days = 7 if period=="最近7天" else 30 if period=="最近30天" else 90
    cutoff = datetime.utcnow() - timedelta(days=days)
    df["created_at_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df[df["created_at_dt"] >= cutoff]

# apply owner filter
if owner_filter and owner_filter != "全部":
    df = df[df["main_person"]==owner_filter]

# keyword search
kw = st.text_input("关键字搜索 (姓名/国家/城市)")
if kw:
    df = df[df.apply(lambda r: kw.lower() in str(r.get("name","")).lower() or kw.lower() in str(r.get("country","")).lower(), axis=1)]

# show table
display_cols = ["id","name","country","city","deal_amount","level","progress","main_person","assistant","created_at"]
if df.empty:
    st.info(t("no_data") if t("no_data") else "暂无数据")
else:
    st.dataframe(df[display_cols].sort_values("created_at", ascending=False), use_container_width=True)

# select customer for details
sel_options = ["(请选择)"] + [f"{r['name']} — {r['id']}" for _, r in df.iterrows()]
sel = st.selectbox("🔎 " + (t("details") if t("details") else "客户详情"), sel_options)
if sel and sel != "(请选择)":
    cid = sel.split(" — ")[-1]
    cust = get_customer(cid)
    if cust:
        st.header(f"{cust['name']}  —  ID: {cust['id']}")
        left, right = st.columns([2,1])
        with left:
            st.subheader(t("details") if t("details") else "客户详情")
            st.write(f"**{t('customer_name') if 'customer_name' in (TRANSLATIONS.get(st.session_state['lang']) or {}) else '客户名称'}:** {cust.get('name')}")
            st.write(f"**Whatsapp / Line / Telegram:** {cust.get('whatsapp')} / {cust.get('line')} / {cust.get('telegram')}")
            st.write(f"**国家/城市:** {cust.get('country')} / {cust.get('city')}")
            st.write(f"**年龄 / 工作 / 收入:** {cust.get('age')} / {cust.get('job')} / {cust.get('income')}")
            st.write(f"**成交金额:** {cust.get('deal_amount')} | **等级:** {cust.get('level')} | **状态:** {cust.get('progress')}")
            st.write(f"**主要负责人:** {cust.get('main_person')} | **辅助:** {cust.get('assistant')}")
            st.markdown("**备注**")
            st.write(cust.get('remark') or "")
        with right:
            st.subheader("🔧 操作")
            with st.form("edit_form"):
                new_progress = st.selectbox("跟进状态", ["待联系","洽谈中","已成交","流失"], index=["待联系","洽谈中","已成交","流失"].index(cust.get("progress") or "待联系"))
                new_level = st.selectbox("客户等级", ["普通","重要","VIP"], index=["普通","重要","VIP"].index(cust.get("level") or "普通"))
                new_amount = st.number_input("成交金额", value=float(cust.get("deal_amount") or 0.0))
                new_remark = st.text_area("备注", value=cust.get("remark") or "")
                if st.form_submit_button(t("save") if t("save") else "保存"):
                    updates = {"progress": new_progress, "level": new_level, "deal_amount": new_amount, "remark": new_remark}
                    update_customer(cid, updates)
                    st.success("保存成功")
                    st.rerun()
            if role == "admin" or cust.get("main_person")==username:
                if st.button(t("delete") if t("delete") else "删除"):
                    delete_customer(cid)
                    st.warning("已删除客户")
                    st.rerun()
        # followups
        st.subheader("跟进记录")
        fups = list_followups_df(cid)
        if fups.empty:
            st.info(t("no_data") if t("no_data") else "暂无跟进")
        else:
            st.dataframe(fups[["created_at","author","note","next_action"]], use_container_width=True)
        with st.form("add_followup"):
            note = st.text_area("跟进内容")
            next_act = st.text_input("下次动作")
            if st.form_submit_button(t("add_followup") if t("add_followup") else "添加跟进"):
                if note.strip():
                    add_followup(cid, username, note.strip(), next_act.strip())
                    st.success("跟进已添加")
                    st.rerun()

# add new customer
st.markdown("---")
st.subheader(t("add_customer") if t("add_customer") else "新增客户")
with st.form("add_new_customer"):
    name = st.text_input("客户名称")
    whatsapp = st.text_input("Whatsapp")
    line = st.text_input("Line")
    telegram = st.text_input("Telegram")
    country = st.text_input("国家")
    city = st.text_input("城市")
    age = st.number_input("年龄", min_value=0, value=0)
    job = st.text_input("工作")
    income = st.text_input("薪资水平")
    relation = st.selectbox("感情状态", ["单身","已婚","离异","丧偶"])
    deal_amount = st.number_input("已成交金额", min_value=0.0)
    level = st.selectbox("客户等级", ["普通","重要","VIP"])
    progress = st.selectbox("跟进状态", ["待联系","洽谈中","已成交","流失"])
    main_person = st.selectbox("主要负责人", options=["(未指定)"] + list(list_users_df()["username"].tolist()))
    assistant = st.text_input("辅助人员（逗号分隔）")
    remark = st.text_area("备注")
    if st.form_submit_button(t("save") if t("save") else "保存"):
        rec = {
            "name": name,
            "whatsapp": whatsapp,
            "line": line,
            "telegram": telegram,
            "country": country,
            "city": city,
            "age": age,
            "job": job,
            "income": income,
            "relation": relation,
            "deal_amount": deal_amount,
            "level": level,
            "progress": progress,
            "main_person": None if main_person=="(未指定)" else main_person,
            "assistant": assistant,
            "remark": remark
        }
        cid_new = add_customer(rec)
        st.success(f"客户已添加 (ID: {cid_new})")
        st.rerun()

# Export
st.markdown("---")
st.subheader(t("export") if t("export") else "导出")
if role == "admin":
    if st.button("导出全部客户 (Excel)"):
        df_all = list_customers_df()
        buf = io.BytesIO()
        df_all.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button("下载全部客户.xlsx", buf, file_name=f"all_customers_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")
else:
    if st.button("导出我负责的客户 (Excel)"):
        me = username
        df_me = list_customers_df()
        df_me = df_me[(df_me["main_person"]==me) | (df_me["assistant"].str.contains(me, na=False))]
        buf = io.BytesIO()
        df_me.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button("下载我的客户.xlsx", buf, file_name=f"my_customers_{me}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")

# Owner reports
st.markdown("---")
st.subheader("📊 负责人报表")
owners = list_customers_df()["main_person"].dropna().unique().tolist()
sel_owner = st.selectbox("选择负责人", options=["(请选择)"] + owners)
if sel_owner and sel_owner != "(请选择)":
    df_owner = list_customers_df()
    df_owner = df_owner[df_owner["main_person"]==sel_owner]
    if not df_owner.empty:
        counts = df_owner["level"].value_counts().reset_index()
        counts.columns = ["level","count"]
        pie = alt.Chart(counts).mark_arc().encode(theta="count:Q", color="level:N")
        st.altair_chart(pie, use_container_width=True)
        df_owner["created_dt"] = pd.to_datetime(df_owner["created_at"], errors="coerce")
        monthly = df_owner.dropna(subset=["created_dt"]).groupby(df_owner["created_dt"].dt.to_period("M")).size().reset_index(name="count")
        if not monthly.empty:
            monthly["month"] = monthly["created_dt"].astype(str)
            line = alt.Chart(monthly).mark_line(point=True).encode(x="month:N", y="count:Q")
            st.altair_chart(line, use_container_width=True)
        total = len(df_owner)
        success = len(df_owner[df_owner["progress"]=="已成交"])
        if total>0:
            st.write(f"成交成功率：{success}/{total} = {success/total*100:.1f}%")
    else:
        st.info(t("no_data") if t("no_data") else "暂无数据")

# Admin tools: user mgmt, view logs, edit translations
if role == "admin":
    st.markdown("---")
    st.subheader(t("admin_area") if t("admin_area") else "管理员设置")
    # user management
    st.markdown("### 用户管理")
    users_df = list_users_df()
    st.dataframe(users_df)
    with st.form("add_user"):
        nu = st.text_input("用户名（新增）")
        npw = st.text_input("密码（新增）", type="password")
        nrole = st.selectbox("角色", ["user","admin"])
        if st.form_submit_button("新增用户"):
            ok,msg = add_user(nu.strip(), npw.strip(), nrole)
            if ok:
                st.success("用户创建成功")
            else:
                st.error(msg)
    with st.form("reset_pw"):
        sel = st.selectbox("选择用户（重置密码）", users_df["username"].tolist())
        newpw = st.text_input("新密码", type="password")
        if st.form_submit_button("重置密码"):
            reset_user_password(sel, newpw)
            st.success("密码已重置")
    with st.form("del_user"):
        sel2 = st.selectbox("选择删除用户", users_df["username"].tolist(), key="del1")
        if st.form_submit_button("删除用户"):
            delete_user(sel2)
            st.success("用户已删除")

    # edit translations (writes translations.json)
    st.markdown("### 翻译（在线编辑 translations.json）")
    try:
        with open(TRANS_FILE, "r", encoding="utf-8") as f:
            tx = json.load(f)
    except Exception:
        tx = TRANSLATIONS
    lang_edit = st.selectbox("选择语言编辑", list(tx.keys()))
    edited = {}
    for k,v in tx.get(lang_edit, {}).items():
        edited[k] = st.text_input(k, v, key=f"tx_{lang_edit}_{k}")
    if st.button("保存翻译"):
        tx[lang_edit] = edited
        with open(TRANS_FILE, "w", encoding="utf-8") as f:
            json.dump(tx, f, ensure_ascii=False, indent=2)
        st.success("翻译已保存")
        st.experimental_set_query_params()  # harmless noop to encourage state refresh

    # view logs
    st.markdown("### 操作日志")
    logs = recent_actions(500)
    if logs.empty:
        st.info("暂无日志")
    else:
        st.dataframe(logs, use_container_width=True)

# end
