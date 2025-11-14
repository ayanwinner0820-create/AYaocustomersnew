# app.py — AYaocustomers 完整版（含：登录/多语言/用户管理/客户CRUD/跟进/报表/导出/日志）
import streamlit as st
import sqlite3
import uuid
import json
from datetime import datetime, timedelta, date
import pandas as pd
import altair as alt
from io import BytesIO

# try import backup module (optional). If exists, functions in backup.py can be called.
try:
    import backup
    HAS_BACKUP = True
except Exception:
    HAS_BACKUP = False

# ------------------ CONFIG ------------------
DB_FILE = "customers.db"
PAGE_TITLE = "氯雷他定用户统计"
PAGE_ICON = "📊"
THEME_COLOR = "#C62828"  # 喜庆红

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# small css for theme
st.markdown(f"""
<style>
[data-testid="stHeader"]{{display:none}}
section.main .block-container{{padding-top:1rem}}
.stButton>button{{background-color:{THEME_COLOR} !important; border:none}}
</style>
""", unsafe_allow_html=True)

# ------------------ TRANSLATIONS (in-memory) ------------------
TRANSLATIONS = {
    "中文": {
        "app_title": "氯雷他定用户统计",
        "login_prompt": "请输入用户名与密码登录。",
        "username": "用户名",
        "password": "密码",
        "login": "登录",
        "logout": "退出登录",
        "customers": "客户管理",
        "add_customer": "新增客户",
        "edit_customer": "编辑客户",
        "delete_customer": "删除客户",
        "customer_detail": "客户详情",
        "export": "导出Excel",
        "filter": "筛选",
        "period": "时间筛选",
        "keyword": "关键字搜索",
        "owner_report": "负责人报表",
        "logs": "操作日志（管理员可见）",
        "admin_area": "管理员设置",
        "add_user": "新增用户",
        "reset_password": "重置密码",
        "save": "保存",
        "confirm": "确认",
        "no_data": "暂无数据",
    },
    "English": {
        "app_title": "Loratadine Customer Dashboard",
        "login_prompt": "Please log in with your username and password.",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "logout": "Logout",
        "customers": "Customer Management",
        "add_customer": "Add Customer",
        "edit_customer": "Edit Customer",
        "delete_customer": "Delete Customer",
        "customer_detail": "Customer Detail",
        "export": "Export Excel",
        "filter": "Filter",
        "period": "Period",
        "keyword": "Keyword",
        "owner_report": "Owner Reports",
        "logs": "Action Logs (admin)",
        "admin_area": "Admin Settings",
        "add_user": "Add User",
        "reset_password": "Reset Password",
        "save": "Save",
        "confirm": "Confirm",
        "no_data": "No data",
    },
    "Bahasa Indonesia": {
        "app_title": "Dashboard Pelanggan Loratadine",
        "login_prompt": "Silakan masuk dengan nama pengguna dan kata sandi.",
        "username": "Nama pengguna",
        "password": "Kata sandi",
        "login": "Masuk",
        "logout": "Keluar",
        "customers": "Manajemen Pelanggan",
        "add_customer": "Tambah Pelanggan",
        "edit_customer": "Ubah Pelanggan",
        "delete_customer": "Hapus Pelanggan",
        "customer_detail": "Detail Pelanggan",
        "export": "Ekspor Excel",
        "filter": "Saring",
        "period": "Periode",
        "keyword": "Kata kunci",
        "owner_report": "Laporan Penanggung Jawab",
        "logs": "Log Operasi (admin)",
        "admin_area": "Pengaturan Admin",
        "add_user": "Tambah Pengguna",
        "reset_password": "Reset Kata Sandi",
        "save": "Simpan",
        "confirm": "Konfirmasi",
        "no_data": "Belum ada data",
    },
    "ភាសាខ្មែរ": {
        "app_title": "ផ្ទាំងអតិថិជន Loratadine",
        "login_prompt": "សូមចូលដោយឈ្មោះអ្នកប្រើ និងពាក្យសម្ងាត់។",
        "username": "ឈ្មោះអ្នកប្រើ",
        "password": "ពាក្យសម្ងាត់",
        "login": "ចូល",
        "logout": "ចាកចេញ",
        "customers": "ការគ្រប់គ្រងអតិថិជន",
        "add_customer": "បន្ថែមអតិថិជន",
        "edit_customer": "កែប្រែអតិថិជន",
        "delete_customer": "លុបអតិថិជន",
        "customer_detail": "ព័ត៌មានលម្អិត",
        "export": "នាំចេញ Excel",
        "filter": "ចម្រាញ់",
        "period": "រយៈពេល",
        "keyword": "ពាក្យគន្លឹះ",
        "owner_report": "របាយការណ៍",
        "logs": "កំណត់ហេតុប្រតិបត្តិការ (admin)",
        "admin_area": "ការកំណត់អនុគណ៍",
        "add_user": "បន្ថែមអ្នកប្រើ",
        "reset_password": "កំណត់ពាក្យសម្ងាត់ឡើងវិញ",
        "save": "រក្សាទុក",
        "confirm": "បញ្ជាក់",
        "no_data": "មិនមានទិន្នន័យ"
    },
    "Tiếng Việt": {
        "app_title": "Bảng khách hàng Loratadine",
        "login_prompt": "Vui lòng đăng nhập bằng tên người dùng và mật khẩu.",
        "username": "Tên người dùng",
        "password": "Mật khẩu",
        "login": "Đăng nhập",
        "logout": "Đăng xuất",
        "customers": "Quản lý khách hàng",
        "add_customer": "Thêm khách hàng",
        "edit_customer": "Sửa khách hàng",
        "delete_customer": "Xóa khách hàng",
        "customer_detail": "Chi tiết khách hàng",
        "export": "Xuất Excel",
        "filter": "Lọc",
        "period": "Khoảng thời gian",
        "keyword": "Từ khóa",
        "owner_report": "Báo cáo người phụ trách",
        "logs": "Nhật ký thao tác (admin)",
        "admin_area": "Cài đặt quản trị",
        "add_user": "Thêm người dùng",
        "reset_password": "Đặt lại mật khẩu",
        "save": "Lưu",
        "confirm": "Xác nhận",
        "no_data": "Không có dữ liệu"
    }
}

LANG_OPTIONS = list(TRANSLATIONS.keys())

def tr(key):
    lang = st.session_state.get("lang", "中文")
    return TRANSLATIONS.get(lang, TRANSLATIONS["中文"]).get(key, key)

# ------------------ DB helpers ------------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        language TEXT DEFAULT '中文'
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
        marital_status TEXT,
        deal_amount REAL,
        level TEXT,
        progress TEXT,
        main_owner TEXT,
        assistant TEXT,
        notes TEXT,
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
    # default admin
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users(username,password,role,language) VALUES(?,?,?,?)", ("admin","admin123","admin","中文"))
    conn.commit()
    conn.close()

def now_iso():
    return datetime.utcnow().isoformat()

def log_action(username, action, target_table="", target_id="", details=""):
    # ensure details is JSON/string
    if isinstance(details, (dict, list)):
        try:
            details = json.dumps(details, ensure_ascii=False)
        except Exception:
            details = str(details)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO action_logs(id,username,action,target_table,target_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), username, action, target_table, target_id, details, now_iso()))
    conn.commit()
    conn.close()

# ------------------ Session defaults ------------------
if "lang" not in st.session_state:
    st.session_state["lang"] = "中文"
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None

# initialize db
init_db()

# ------------------ Auth ------------------
def authenticate(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username,role,language FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# ------------------ User management ------------------
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
    log_action(st.session_state.get("user","system"), "add_user", "users", username, {"role": role})

def reset_user_password(username, new_password):
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("user","system"), "reset_password", "users", username, "")

def delete_user(username):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("user","system"), "delete_user", "users", username, "")

# ------------------ Customer ops ------------------
def insert_customer(rec: dict):
    conn = get_conn()
    cur = conn.cursor()
    cid = str(uuid.uuid4())
    now = now_iso()
    cur.execute("""
    INSERT INTO customers(id,name,whatsapp,line,telegram,country,city,age,job,income,marital_status,deal_amount,level,progress,main_owner,assistant,notes,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        cid,
        rec.get("name"),
        rec.get("whatsapp"),
        rec.get("line"),
        rec.get("telegram"),
        rec.get("country"),
        rec.get("city"),
        rec.get("age"),
        rec.get("job"),
        rec.get("income"),
        rec.get("marital_status"),
        rec.get("deal_amount"),
        rec.get("level"),
        rec.get("progress"),
        rec.get("main_owner"),
        rec.get("assistant"),
        rec.get("notes"),
        now
    ))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("user","system"), "add_customer", "customers", cid, rec)
    return cid

def update_customer(cid: str, updates: dict):
    conn = get_conn()
    cur = conn.cursor()
    keys = ",".join([f"{k}=?" for k in updates.keys()])
    params = list(updates.values()) + [cid]
    cur.execute(f"UPDATE customers SET {keys} WHERE id=?", params)
    conn.commit()
    conn.close()
    log_action(st.session_state.get("user","system"), "update_customer", "customers", cid, updates)

def delete_customer(cid: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM customers WHERE id=?", (cid,))
    row = cur.fetchone()
    name = row["name"] if row else ""
    cur.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    log_action(st.session_state.get("user","system"), "delete_customer", "customers", cid, {"name": name})

def get_customer(cid: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id=?", (cid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def list_customers_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM customers ORDER BY created_at DESC", conn)
    conn.close()
    return df

def list_followups(cid: str):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM followups WHERE customer_id=? ORDER BY created_at DESC", conn, params=(cid,))
    conn.close()
    return df

def add_followup(cid: str, author: str, note: str, next_action: str=""):
    conn = get_conn()
    cur = conn.cursor()
    fid = str(uuid.uuid4())
    cur.execute("INSERT INTO followups(id,customer_id,author,note,next_action,created_at) VALUES(?,?,?,?,?,?)",
                (fid, cid, author, note, next_action, now_iso()))
    conn.commit()
    conn.close()
    log_action(author, "add_followup", "followups", fid, {"customer_id": cid, "note": note})

# ------------------ Utility ------------------
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="customers")
    return output.getvalue()

def apply_filters(df: pd.DataFrame, period: str, kw: str, owner: str, start_date=None, end_date=None):
    if df is None or df.empty:
        return df
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
        res = res[res.apply(lambda r: key in str(r.get("name","")).lower() or key in str(r.get("country","")).lower() or key in str(r.get("city","")).lower() or key in str(r.get("whatsapp","")).lower(), axis=1)]
    return res

def list_owners():
    df = list_customers_df()
    if df.empty:
        return []
    return sorted(df["main_owner"].dropna().unique().tolist())

# ------------------ Views ------------------
def login_view():
    st.title(tr("app_title"))
    st.write(tr("login_prompt"))
    col1, col2 = st.columns([2,1])
    with col1:
        username = st.text_input(tr("username"))
        password = st.text_input(tr("password"), type="password")
        if st.button(tr("login")):
            info = authenticate(username.strip(), password.strip())
            if info:
                st.session_state["user"] = info["username"]
                st.session_state["role"] = info["role"]
                st.session_state["lang"] = info.get("language") or st.session_state.get("lang","中文")
                st.success(f"欢迎 {st.session_state['user']}")
                # optionally trigger backup on admin login (best-effort)
                if HAS_BACKUP and st.session_state["role"] == "admin":
                    try:
                        ok, resp = backup.backup_db_to_github(st.secrets, actor=st.session_state["user"])
                        if ok:
                            st.info("管理员登录：自动备份已触发")
                        else:
                            st.info("自动备份未成功：" + str(resp)[:200])
                    except Exception:
                        pass
                st.experimental_rerun()
            else:
                st.error(tr("login") + " error")
    with col2:
        st.info("默认管理员：admin / admin123（首次登录请修改）")
    st.stop()

def sidebar():
    st.sidebar.title("📊 " + tr("app_title"))
    st.sidebar.write(f"👤 {st.session_state.get('user')} ({st.session_state.get('role')})")
    # language select persisted
    lang_choice = st.sidebar.selectbox("🌐 Language", LANG_OPTIONS, index=LANG_OPTIONS.index(st.session_state.get("lang","中文")))
    if lang_choice != st.session_state.get("lang"):
        st.session_state["lang"] = lang_choice
        # save preference if user exists
        if st.session_state.get("user"):
            conn = get_conn()
            conn.execute("UPDATE users SET language=? WHERE username=?", (lang_choice, st.session_state["user"]))
            conn.commit()
            conn.close()
    if st.sidebar.button(tr("logout")):
        # clear session
        st.session_state["user"] = None
        st.session_state["role"] = None
        st.experimental_rerun()

def page_customers():
    st.header(tr("customers"))

    # filters
    c1, c2, c3, c4 = st.columns([2,1,1,2])
    with c1:
        period = st.selectbox(tr("period"), ["全部","最近7天","最近30天","最近90天","自定义"])
    with c2:
        owner_list = ["全部"] + list_owners()
        owner = st.selectbox("负责人", owner_list, index=0)
    with c3:
        kw = st.text_input(tr("keyword"))
    with c4:
        if st.button(tr("export")):
            df_all = list_customers_df()
            if st.session_state.get("role") != "admin":
                df_all = df_all[(df_all["main_owner"]==st.session_state["user"]) | (df_all["assistant"].str.contains(st.session_state["user"], na=False))]
            df_export = apply_filters(df_all, period, kw, owner)
            content = df_to_excel_bytes(df_export)
            st.download_button("下载 Excel", data=content, file_name=f"customers_{datetime.utcnow().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    start_date = None
    end_date = None
    if period == "自定义":
        start_date = st.date_input("开始")
        end_date = st.date_input("结束")

    df = list_customers_df()
    # permission
    if st.session_state.get("role") != "admin":
        df = df[(df["main_owner"]==st.session_state["user"]) | (df["assistant"].str.contains(st.session_state["user"], na=False))]

    df_display = apply_filters(df, period, kw, owner, start_date, end_date)
    if df_display.empty:
        st.info(tr("no_data"))
    else:
        cols = ["id","name","whatsapp","line","telegram","country","city","age","job","income","marital_status","deal_amount","level","progress","main_owner","assistant","created_at"]
        st.dataframe(df_display[cols].sort_values("created_at", ascending=False), use_container_width=True)

    # select by id to show detail/edit
    sel = st.text_input("输入客户 ID 查看详情（或从表格复制粘贴）")
    if sel:
        cust = get_customer(sel.strip())
        if cust:
            show_customer_detail(cust)
        else:
            st.warning("未找到客户ID")

    # quick add
    st.markdown("---")
    st.subheader(tr("add_customer"))
    with st.form("add_customer"):
        name = st.text_input("客户名称")
        whatsapp = st.text_input("Whatsapp")
        line = st.text_input("Line")
        telegram = st.text_input("Telegram")
        country = st.text_input("国家")
        city = st.text_input("所在城市")
        age = st.number_input("年龄", min_value=0, max_value=120, value=0)
        job = st.text_input("工作")
        income = st.text_input("薪资水平")
        marital_status = st.selectbox("感情状态", ["单身","已婚","离异","丧偶"])
        deal_amount = st.number_input("已成交金额", min_value=0.0, value=0.0)
        level = st.selectbox("客户等级", ["普通","重要","VIP"])
        progress = st.selectbox("跟进状态", ["待联系","洽谈中","已成交","流失"])
        main_owner = st.selectbox("主要负责人", ["(未指定)"] + list_users_df()["username"].tolist())
        assistant = st.text_input("辅助人员（逗号分隔）")
        notes = st.text_area("备注")
        submitted = st.form_submit_button(tr("save"))
        if submitted:
            data = {
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
                "main_owner": None if main_owner == "(未指定)" else main_owner,
                "assistant": assistant.strip(),
                "notes": notes.strip()
            }
            if not data["name"]:
                st.warning("请填写客户名称")
            else:
                try:
                    cid = insert_customer(data)
                    st.success(f"客户已添加 (ID: {cid})")
                    st.experimental_rerun()
                except Exception as e:
                    st.error("保存失败：" + str(e))

def show_customer_detail(cust: dict):
    st.markdown("---")
    st.subheader(tr("customer_detail"))
    st.write(f"**ID:** {cust.get('id')}")
    left, right = st.columns([2,1])
    with left:
        st.write(f"**客户名称:** {cust.get('name')}")
        st.write(f"**WhatsApp / Line / Telegram:** {cust.get('whatsapp')} / {cust.get('line')} / {cust.get('telegram')}")
        st.write(f"**国家 / 城市:** {cust.get('country')} / {cust.get('city')}")
        st.write(f"**年龄 / 工作 / 薪资:** {cust.get('age')} / {cust.get('job')} / {cust.get('income')}")
        st.write(f"**感情状态:** {cust.get('marital_status')}")
    with right:
        st.write(f"**已成交金额:** {cust.get('deal_amount')}")
        st.write(f"**客户等级:** {cust.get('level')}")
        st.write(f"**跟进状态:** {cust.get('progress')}")
        st.write(f"**主要负责人:** {cust.get('main_owner')}")
        st.write(f"**辅助人员:** {cust.get('assistant')}")
        st.write(f"**创建时间:** {cust.get('created_at')}")
    st.markdown("**备注**")
    st.write(cust.get("notes") or "")

    # show followups
    st.subheader("跟进记录")
    fups = list_followups(cust.get("id"))
    if fups.empty:
        st.info(tr("no_data"))
    else:
        st.table(fups[["created_at","author","note","next_action"]])

    # edit form
    st.subheader(tr("edit_customer"))
    with st.form(f"edit_{cust.get('id')}"):
        new_name = st.text_input("客户名称", value=cust.get("name") or "")
        new_whatsapp = st.text_input("Whatsapp", value=cust.get("whatsapp") or "")
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
        new_main = st.selectbox("主要负责人", ["(未指定)"] + list_users_df()["username"].tolist(), index=0 if not cust.get("main_owner") else (["(未指定)"] + list_users_df()["username"].tolist()).index(cust.get("main_owner")))
        new_assist = st.text_input("辅助人员", value=cust.get("assistant") or "")
        new_notes = st.text_area("备注", value=cust.get("notes") or "")
        if st.form_submit_button(tr("save")):
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
                "main_owner": None if new_main == "(未指定)" else new_main,
                "assistant": new_assist.strip(),
                "notes": new_notes.strip()
            }
            try:
                update_customer(cust.get("id"), updates)
                st.success("已保存修改")
                st.experimental_rerun()
            except Exception as e:
                st.error("保存失败：" + str(e))

    # add followup
    with st.form(f"fup_{cust.get('id')}"):
        note = st.text_area("跟进内容")
        next_act = st.text_input("下次动作")
        if st.form_submit_button("添加跟进"):
            if note.strip():
                add_followup(cust.get("id"), st.session_state.get("user","unknown"), note.strip(), next_act.strip())
                st.success("跟进已添加")
                st.experimental_rerun()

    # delete (two-step confirm)
    if st.session_state.get("role") == "admin" or st.session_state.get("user") == cust.get("main_owner"):
        st.markdown("### 删除客户")
        confirm = st.checkbox(f"确认删除客户 {cust.get('name')} ?", key=f"confirm_del_{cust.get('id')}")
        if confirm:
            if st.button("最终确认删除"):
                delete_customer(cust.get("id"))
                st.success("客户已删除")
                st.experimental_rerun()

def page_reports():
    st.header(tr("owner_report"))
    owners = ["(全部)"] + list_owners()
    sel_owner = st.selectbox("选择负责人", owners, index=0)
    period = st.selectbox("时间段", ["全部","最近7天","最近30天","最近90天"])
    df = list_customers_df()
    if st.session_state.get("role") != "admin":
        df = df[(df["main_owner"]==st.session_state.get("user")) | (df["assistant"].str.contains(st.session_state.get("user"), na=False))]
    df = apply_filters(df, period, "", sel_owner if sel_owner != "(全部)" else "全部")
    if df.empty:
        st.info(tr("no_data"))
        return
    # level pie
    level_counts = df["level"].value_counts().reset_index()
    level_counts.columns = ["level","count"]
    pie = alt.Chart(level_counts).mark_arc().encode(theta="count:Q", color="level:N", tooltip=["level","count"])
    st.altair_chart(pie, use_container_width=True)
    # deal trend by month
    df["dt"] = pd.to_datetime(df["created_at"]).dt.to_period("M").astype(str)
    trend = df.groupby("dt").agg(total_deal=("deal_amount","sum"), cnt=("id","count")).reset_index()
    if not trend.empty:
        line = alt.Chart(trend).mark_line(point=True).encode(x="dt:N", y="total_deal:Q")
        st.altair_chart(line, use_container_width=True)
    total = len(df)
    success = len(df[df["progress"]=="已成交"])
    if total>0:
        st.write(f"成交成功率：{success}/{total} = {success/total*100:.1f}%")

def page_admin():
    st.header(tr("admin_area"))
    st.subheader("用户管理")
    users = list_users_df()
    st.dataframe(users)
    with st.form("add_user"):
        nu = st.text_input("新用户名")
        npw = st.text_input("新密码", type="password")
        nrole = st.selectbox("角色", ["user","admin"])
        nlang = st.selectbox("语言偏好", LANG_OPTIONS, index=LANG_OPTIONS.index("中文"))
        if st.form_submit_button(tr("add_user")):
            if not nu or not npw:
                st.warning("用户名/密码不能为空")
            else:
                add_user(nu.strip(), npw.strip(), nrole, nlang)
                st.success("用户已创建")
                st.experimental_rerun()
    st.subheader(tr("reset_password"))
    sel = st.selectbox("选择用户", users["username"].tolist())
    newpw = st.text_input("新密码", type="password")
    if st.button("重置密码"):
        if not newpw:
            st.warning("请输入新密码")
        else:
            reset_user_password(sel, newpw)
            st.success("密码已重置")
    st.subheader("删除用户")
    delsel = st.selectbox("选择要删除的用户", users["username"].tolist(), key="del_user")
    if st.button("删除"):
        if delsel == "admin":
            st.warning("不能删除默认管理员")
        else:
            delete_user(delsel)
            st.success("用户已删除")
            st.experimental_rerun()
    st.markdown("---")
    st.subheader(tr("logs"))
    conn = get_conn()
    logs_df = pd.read_sql_query("SELECT * FROM action_logs ORDER BY created_at DESC LIMIT 500", conn)
    conn.close()
    if logs_df.empty:
        st.info(tr("no_data"))
    else:
        st.dataframe(logs_df, use_container_width=True)

# ------------------ Router ------------------
def main_app():
    sidebar()
    # menu: include admin only panel
    menu_items = ["客户管理", "负责人报表"]
    if st.session_state.get("role") == "admin":
        menu_items.append("管理员设置")
    menu = st.sidebar.radio("导航", menu_items)
    if menu == "客户管理":
        page_customers()
    elif menu == "负责人报表":
        page_reports()
    elif menu == "管理员设置":
        page_admin()
    else:
        page_customers()

# ------------------ run ------------------
if not st.session_state.get("user"):
    login_view()
else:
    main_app()
