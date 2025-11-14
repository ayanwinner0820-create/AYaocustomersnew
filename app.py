# app.py — AYaocustomers 完整版（单文件部署）
import streamlit as st
import sqlite3
import uuid
import json
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
from io import BytesIO

# ---------- 配置 ----------
DB_FILE = "customers.db"
PAGE_TITLE = "氯雷他定用户统计"
PAGE_ICON = "📊"

# set page
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# 小段 CSS 设置主色为“喜庆红”
st.markdown(
    """
<style>
/* page accent */
[data-testid="stHeader"] {display:none}
.section-title { color: #b71c1c; font-weight:700; }
.stButton>button { background-color: #c62828 !important; border:none; }
[data-testid="stSidebar"] .css-1d391kg { background: linear-gradient(180deg,#fff5f5,#ffeaea); }
</style>
""",
    unsafe_allow_html=True,
)

# ---------- DB helpers ----------
def get_conn():
    # isolated connection; check_same_thread False for streamlit concurrency
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        language TEXT DEFAULT '中文'
    )""")
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
        marital_status TEXT,
        deal_amount REAL,
        level TEXT,
        progress TEXT,
        main_owner TEXT,
        assistant TEXT,
        notes TEXT,
        created_at TEXT
    )""")
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
    # default admin (if not exists)
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", ("admin", "admin123", "admin"))
    conn.commit()
    conn.close()

def pretty_now():
    return datetime.utcnow().isoformat()

def log_action(username, action, target_table="", target_id="", details=""):
    # details -> json string
    if isinstance(details, (dict, list)):
        try:
            details = json.dumps(details, ensure_ascii=False)
        except Exception:
            details = str(details)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO action_logs(id,username,action,target_table,target_id,details,created_at)
        VALUES(?,?,?,?,?,?,?)
    """, (str(uuid.uuid4()), username, action, target_table, target_id, details, pretty_now()))
    conn.commit()
    conn.close()

# ---------- Session defaults ----------
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
if "lang" not in st.session_state:
    st.session_state["lang"] = "中文"

# ---------- Initialization ----------
init_db()

# ---------- Auth ----------
def authenticate(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username,role,language FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def require_login():
    if not st.session_state["user"]:
        st.session_state["next_page"] = st.experimental_get_query_params().get("page", ["main"])[0] if st.experimental_get_query_params() else "main"
        login_view()
        st.stop()

# ---------- UI: Login View ----------
def login_view():
    st.title(PAGE_TITLE)
    st.markdown("### 请先登录（管理员拥有新增/删除用户权限）")
    col1, col2 = st.columns([2,1])
    with col1:
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        if st.button("登录"):
            info = authenticate(username.strip(), password.strip())
            if info:
                st.session_state["user"] = info["username"]
                st.session_state["role"] = info["role"]
                st.session_state["lang"] = info.get("language") or st.session_state["lang"]
                st.success(f"欢迎 {st.session_state['user']}！")
                st.experimental_rerun()
            else:
                st.error("用户名或密码错误")
    with col2:
        st.info("默认管理员：用户名 `admin` / 密码 `admin123`（首次登录请修改）")

# ---------- Data access ----------
def customers_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM customers ORDER BY created_at DESC", conn)
    conn.close()
    return df

def customers_df_for_user(user, role):
    df = customers_df()
    if role != "admin":
        # show rows where main_owner==user or assistant contains user
        df = df[(df["main_owner"] == user) | (df["assistant"].fillna("").str.contains(user))]
    return df

def get_customer_by_id(cid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id=?", (cid,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def insert_customer(record):
    conn = get_conn()
    cur = conn.cursor()
    cid = str(uuid.uuid4())
    now = pretty_now()
    cur.execute("""
        INSERT INTO customers(id,name,whatsapp,line,telegram,country,city,age,job,income,marital_status,deal_amount,level,progress,main_owner,assistant,notes,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        cid,
        record.get("name"),
        record.get("whatsapp"),
        record.get("line"),
        record.get("telegram"),
        record.get("country"),
        record.get("city"),
        record.get("age"),
        record.get("job"),
        record.get("income"),
        record.get("marital_status"),
        record.get("deal_amount"),
        record.get("level"),
        record.get("progress"),
        record.get("main_owner"),
        record.get("assistant"),
        record.get("notes"),
        now
    ))
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "add_customer", "customers", cid, record)
    return cid

def update_customer(cid, updates):
    # updates is dict of column->value
    conn = get_conn()
    cur = conn.cursor()
    set_sql = ", ".join([f"{k}=?" for k in updates.keys()])
    params = list(updates.values()) + [cid]
    cur.execute(f"UPDATE customers SET {set_sql} WHERE id=?", params)
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "update_customer", "customers", cid, updates)

def delete_customer(cid):
    conn = get_conn()
    cur = conn.cursor()
    cust = get_customer_by_id(cid)
    cur.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "delete_customer", "customers", cid, {"name": cust.get("name") if cust else ""})

# ---------- Admin user ops ----------
def list_users_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT username, role, language FROM users", conn)
    conn.close()
    return df

def add_user(username, password, role="user", language="中文"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users(username,password,role,language) VALUES(?,?,?,?)", (username, password, role, language))
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "add_user", "users", username, {"role": role})

def reset_password(username, newpw):
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE username=?", (newpw, username))
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "reset_password", "users", username, "")

def remove_user(username):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    log_action(st.session_state["user"] or "system", "delete_user", "users", username, "")

# ---------- Exports ----------
def df_to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="customers")
    return output.getvalue()

# ---------- Views ----------

def sidebar_common():
    st.sidebar.title("📊 " + PAGE_TITLE)
    st.sidebar.write(f"👤 {st.session_state['user']} ({st.session_state['role']})")
    # language (simple two options for now; can be expanded)
    lang = st.sidebar.selectbox("🌐 语言 / Language", ["中文", "English"], index=0 if st.session_state.get("lang","中文")=="中文" else 1)
    st.session_state["lang"] = lang
    if st.sidebar.button("退出登录 / Logout"):
        st.session_state["user"] = None
        st.session_state["role"] = None
        st.experimental_rerun()

def page_customers():
    st.markdown(f"## <span class='section-title'>客户管理</span>", unsafe_allow_html=True)

    # Filters: date presets and custom
    col1, col2, col3, col4 = st.columns([2,1,1,2])
    with col1:
        period = st.selectbox("时间范围", ["全部", "最近7天", "最近30天", "最近90天", "自定义"])
    with col2:
        owner_list = ["全部"] + sorted(list_users_df()["username"].tolist())
        owner = st.selectbox("主要负责人", owner_list, index=0)
    with col3:
        kw = st.text_input("搜索关键字（名称/国家/城市/WhatsApp）")
    with col4:
        if st.button("导出当前列表 (Excel)"):
            df_cur = customers_df_for_user(st.session_state["user"], st.session_state["role"])
            # apply same filters as below to df_cur
            df_export = apply_filters_to_df(df_cur, period, kw, owner)
            content = df_to_excel_bytes(df_export)
            st.download_button("下载 Excel", data=content, file_name=f"customers_{datetime.utcnow().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # custom date range
    start_date = None
    end_date = None
    if period == "自定义":
        start_date = st.date_input("开始日期")
        end_date = st.date_input("结束日期")

    # show data
    df = customers_df_for_user(st.session_state["user"], st.session_state["role"])
    df_display = apply_filters_to_df(df, period, kw, owner, start_date, end_date)
    if df_display.empty:
        st.info("暂无客户数据")
    else:
        # provide a selectable table: display key columns
        cols = ["id","name","whatsapp","line","telegram","country","city","age","job","income","marital_status","deal_amount","level","progress","main_owner","assistant","created_at"]
        st.dataframe(df_display[cols].sort_values("created_at", ascending=False), use_container_width=True)

    # select a customer to open detail/edit
    sel = st.selectbox("在下方选择或输入客户 ID 来查看/编辑（可复制ID）", [""] + df_display["id"].tolist() if not df_display.empty else [""])
    if sel:
        cust = get_customer_by_id(sel)
        if cust:
            show_customer_detail_and_edit(cust)

    # quick add form
    st.markdown("---")
    st.subheader("➕ 手动添加客户")
    with st.form("add_customer_form"):
        name = st.text_input("客户名称", "")
        whatsapp = st.text_input("WhatsApp", "")
        line = st.text_input("Line", "")
        telegram = st.text_input("Telegram", "")
        country = st.text_input("国家", "")
        city = st.text_input("所在城市", "")
        age = st.number_input("年龄", min_value=0, max_value=120, value=0)
        job = st.text_input("工作", "")
        income = st.text_input("薪资水平", "")
        marital_status = st.selectbox("感情状态", ["单身","已婚","离异","丧偶"])
        deal_amount = st.number_input("已成交金额", min_value=0.0, value=0.0)
        level = st.selectbox("客户等级", ["普通","重要","VIP"])
        progress = st.selectbox("跟进状态", ["待联系","洽谈中","已成交","流失"])
        main_owner = st.selectbox("主要负责人", ["(未指定)"] + list_users_df()["username"].tolist())
        assistant = st.text_input("辅助人员（多个用逗号分隔）", "")
        notes = st.text_area("备注", "")
        submitted = st.form_submit_button("保存")
        if submitted:
            rec = {
                "name": name.strip(),
                "whatsapp": whatsapp.strip(),
                "line": line.strip(),
                "telegram": telegram.strip(),
                "country": country.strip(),
                "city": city.strip(),
                "age": int(age) if age else None,
                "job": job.strip(),
                "income": income.strip(),
                "marital_status": marital_status,
                "deal_amount": float(deal_amount),
                "level": level,
                "progress": progress,
                "main_owner": None if main_owner=="(未指定)" else main_owner,
                "assistant": assistant.strip(),
                "notes": notes.strip()
            }
            # basic validation
            if not rec["name"]:
                st.warning("请填写客户名称")
            else:
                try:
                    cid = insert_customer(rec)
                    st.success(f"客户已保存 (ID: {cid})")
                    # refresh display immediately
                    st.experimental_rerun()
                except Exception as e:
                    st.error("保存失败：" + str(e))

def apply_filters_to_df(df, period, kw, owner, start_date=None, end_date=None):
    if df is None or df.empty:
        return pd.DataFrame()
    res = df.copy()
    # date filter
    if period != "全部":
        if period == "最近7天":
            cutoff = datetime.utcnow() - timedelta(days=7)
            res = res[pd.to_datetime(res["created_at"]) >= cutoff]
        elif period == "最近30天":
            cutoff = datetime.utcnow() - timedelta(days=30)
            res = res[pd.to_datetime(res["created_at"]) >= cutoff]
        elif period == "最近90天":
            cutoff = datetime.utcnow() - timedelta(days=90)
            res = res[pd.to_datetime(res["created_at"]) >= cutoff]
        elif period == "自定义" and start_date and end_date:
            s = pd.to_datetime(start_date)
            e = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            res = res[(pd.to_datetime(res["created_at"]) >= s) & (pd.to_datetime(res["created_at"]) < e)]
    # owner filter
    if owner and owner != "全部":
        res = res[res["main_owner"] == owner]
    # keyword
    if kw and kw.strip():
        key = kw.strip().lower()
        res = res[res.apply(lambda r: key in str(r.get("name","")).lower()
                                   or key in str(r.get("country","")).lower()
                                   or key in str(r.get("city","")).lower()
                                   or key in str(r.get("whatsapp","")).lower(), axis=1)]
    return res

def show_customer_detail_and_edit(cust):
    st.markdown("---")
    st.subheader("🔎 客户详情（可编辑）")
    st.write(f"**ID:** {cust['id']}")
    left, right = st.columns(2)
    with left:
        st.write(f"**客户名称:** {cust.get('name')}")
        st.write(f"**WhatsApp:** {cust.get('whatsapp')}")
        st.write(f"**Line:** {cust.get('line')}")
        st.write(f"**Telegram:** {cust.get('telegram')}")
        st.write(f"**国家 / 城市:** {cust.get('country')} / {cust.get('city')}")
        st.write(f"**年龄 / 工作 / 薪资:** {cust.get('age')} / {cust.get('job')} / {cust.get('income')}")
        st.write(f"**感情状态:** {cust.get('marital_status')}")
    with right:
        st.write(f"**成交金额:** {cust.get('deal_amount')}")
        st.write(f"**客户等级:** {cust.get('level')}")
        st.write(f"**跟进状态:** {cust.get('progress')}")
        st.write(f"**主要负责人:** {cust.get('main_owner')}")
        st.write(f"**辅助人员:** {cust.get('assistant')}")
        st.write(f"**创建时间:** {cust.get('created_at')}")
    st.markdown("**备注**")
    st.write(cust.get('notes') or "")

    # Edit form
    with st.form(f"edit_{cust['id']}"):
        new_name = st.text_input("客户名称", value=cust.get("name") or "")
        new_whatsapp = st.text_input("WhatsApp", value=cust.get("whatsapp") or "")
        new_line = st.text_input("Line", value=cust.get("line") or "")
        new_telegram = st.text_input("Telegram", value=cust.get("telegram") or "")
        new_country = st.text_input("国家", value=cust.get("country") or "")
        new_city = st.text_input("城市", value=cust.get("city") or "")
        new_age = st.number_input("年龄", min_value=0, max_value=120, value=int(cust.get("age") or 0))
        new_job = st.text_input("工作", value=cust.get("job") or "")
        new_income = st.text_input("薪资水平", value=cust.get("income") or "")
        new_relation = st.selectbox("感情状态", ["单身","已婚","离异","丧偶"], index=["单身","已婚","离异","丧偶"].index(cust.get("marital_status") or "单身"))
        new_amount = st.number_input("已成交金额", value=float(cust.get("deal_amount") or 0.0))
        new_level = st.selectbox("客户等级", ["普通","重要","VIP"], index=["普通","重要","VIP"].index(cust.get("level") or "普通"))
        new_progress = st.selectbox("跟进状态", ["待联系","洽谈中","已成交","流失"], index=["待联系","洽谈中","已成交","流失"].index(cust.get("progress") or "待联系"))
        new_main = st.selectbox("主要负责人", ["(未指定)"] + list_users_df()["username"].tolist(), index=0 if not cust.get("main_owner") else ( ["(未指定)"] + list_users_df()["username"].tolist() ).index(cust.get("main_owner")))
        new_assist = st.text_input("辅助人员", value=cust.get("assistant") or "")
        new_notes = st.text_area("备注", value=cust.get("notes") or "")
        if st.form_submit_button("保存修改"):
            updates = {
                "name": new_name.strip(),
                "whatsapp": new_whatsapp.strip(),
                "line": new_line.strip(),
                "telegram": new_telegram.strip(),
                "country": new_country.strip(),
                "city": new_city.strip(),
                "age": int(new_age) if new_age is not None else None,
                "job": new_job.strip(),
                "income": new_income.strip(),
                "marital_status": new_relation,
                "deal_amount": float(new_amount),
                "level": new_level,
                "progress": new_progress,
                "main_owner": None if new_main=="(未指定)" else new_main,
                "assistant": new_assist.strip(),
                "notes": new_notes.strip()
            }
            try:
                update_customer(cust['id'], updates)
                st.success("已保存修改")
                st.experimental_rerun()
            except Exception as e:
                st.error("保存失败：" + str(e))

    # delete button (admin or owner)
    if st.session_state["role"] == "admin" or st.session_state["user"] == cust.get("main_owner"):
        if st.button("删除客户", key=f"del_{cust['id']}"):
            if st.confirm := st.checkbox(f"确认要删除客户 {cust.get('name')}？（勾选确认）", key=f"confirm_{cust['id']}"):
                delete_customer(cust['id'])
                st.success("客户已删除")
                st.experimental_rerun()

def page_reports():
    st.markdown(f"## <span class='section-title'>负责人报表</span>", unsafe_allow_html=True)
    owners = ["(全部)"] + sorted(list_customers_owners())
    sel_owner = st.selectbox("选择负责人", owners, index=0)
    period = st.selectbox("时间段", ["全部","最近7天","最近30天","最近90天"])
    df = customers_df_for_user(st.session_state["user"], st.session_state["role"])
    df = apply_filters_to_df(df, period, "", sel_owner if sel_owner!=="(全部)" else "全部")
    if df.empty:
        st.info("暂无数据")
        return
    # level share
    level_count = df["level"].value_counts().reset_index()
    level_count.columns = ["level","count"]
    chart1 = alt.Chart(level_count).mark_arc().encode(theta="count:Q", color="level:N", tooltip=["level","count"])
    st.altair_chart(chart1, use_container_width=True)
    # deal trend by date
    df["dt"] = pd.to_datetime(df["created_at"]).dt.date
    trend = df.groupby("dt").agg(total_deal=("deal_amount","sum"), cnt=("id","count")).reset_index()
    if not trend.empty:
        line = alt.Chart(trend).mark_line(point=True).encode(x="dt:T", y="total_deal:Q")
        st.altair_chart(line, use_container_width=True)
    # success rate
    total = len(df)
    success = len(df[df["progress"]=="已成交"])
    st.write(f"成交成功率：{success}/{total} = {success/total*100:.1f}%")

# helper for owners list
def list_customers_owners():
    df = customers_df()
    if df.empty:
        return []
    return sorted(df["main_owner"].dropna().unique().tolist())

# ---------- Admin page ----------
def page_admin():
    st.markdown(f"## <span class='section-title'>管理员面板</span>", unsafe_allow_html=True)
    st.subheader("用户管理")
    users = list_users_df()
    st.dataframe(users)
    with st.form("add_user_form"):
        newu = st.text_input("用户名")
        newp = st.text_input("密码", type="password")
        newr = st.selectbox("角色", ["user","admin"])
        if st.form_submit_button("新增用户"):
            if not newu.strip() or not newp:
                st.warning("用户名/密码不能为空")
            else:
                add_user(newu.strip(), newp.strip(), newr)
                st.success("用户已创建")
                st.experimental_rerun()
    st.subheader("重置/删除用户")
    sel = st.selectbox("选择用户", users["username"].tolist())
    col1, col2 = st.columns(2)
    with col1:
        newpw = st.text_input("新密码", type="password")
        if st.button("重置密码"):
            if newpw:
                reset_password(sel, newpw)
                st.success("密码已重置")
            else:
                st.warning("请输入新密码")
    with col2:
        if st.button("删除用户"):
            if sel == "admin":
                st.warning("不能删除默认管理员")
            else:
                remove_user(sel)
                st.success("用户已删除")
                st.experimental_rerun()

    st.markdown("---")
    st.subheader("操作日志（仅管理员可见）")
    conn = get_conn()
    logs = pd.read_sql_query("SELECT * FROM action_logs ORDER BY created_at DESC LIMIT 500", conn)
    conn.close()
    st.dataframe(logs)

# ---------- Main router ----------
def main():
    sidebar_common()
    menu = st.sidebar.radio("功能导航", ["客户管理","负责人报表","管理员面板" if st.session_state["role"]=="admin" else None])
    # flatten menu
    menu = [m for m in menu if m][0] if isinstance(menu, list) else menu
    if menu == "客户管理":
        page_customers()
    elif menu == "负责人报表":
        page_reports()
    elif menu == "管理员面板":
        page_admin()
    else:
        page_customers()

# ---------- Run ----------
require_login = (st.session_state["user"] is None)
if require_login:
    login_view()
else:
    main()
