# app.py (完整版)
import streamlit as st
import pandas as pd
import io
import uuid
import json
from datetime import datetime, timedelta
import altair as alt

from db_ops import (
    init_db, auth_user, add_user, list_users, update_user_password, delete_user,
    add_customer_record, list_customers_df, get_customer_by_id, update_customer, delete_customer,
    add_followup, list_followups, export_translations_as_dict, upsert_translation_row,
    recent_logs
)
import backup

# init DB
init_db()

# page config
st.set_page_config(page_title="氯雷他定用户统计 | AYaocustomers", layout="wide", page_icon="📊")

# load translations (primary from translations.json, DB fallback)
try:
    with open("translations.json", "r", encoding="utf-8") as f:
        UI_TX = json.load(f)
except:
    UI_TX = export_translations_as_dict()

LANG_CODES = {"中文":"zh","English":"en","Bahasa Indonesia":"id","ភាសាខ្មែរ":"km","Tiếng Việt":"vn"}

def t(key):
    lang = st.session_state.get("lang","中文")
    return UI_TX.get(LANG_CODES.get(lang, "zh"), UI_TX.get("zh",{})).get(key, key) if isinstance(UI_TX, dict) and len(UI_TX)>0 else key

# session defaults
if "logged" not in st.session_state:
    st.session_state["logged"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None
    st.session_state["lang"] = "中文"

# language selector persisted
lang_options = ["中文","English","Bahasa Indonesia","ភាសាខ្មែរ","Tiếng Việt"]
if "lang" not in st.session_state:
    st.session_state["lang"] = "中文"

# --- Login/Register view ---
if not st.session_state["logged"]:
    st.title(t("app_title") or "氯雷他定用户统计")
    st.info(t("login_prompt"))
    col1,col2 = st.columns(2)
    with col1:
        username = st.text_input(t("username"))
        password = st.text_input(t("password"), type="password")
        if st.button(t("login")):
            userinfo = auth_user(username, password)
            if userinfo:
                st.session_state["logged"] = True
                st.session_state["username"] = userinfo["username"]
                st.session_state["role"] = userinfo["role"]
                st.session_state["lang"] = userinfo.get("preferred_lang","中文")
                st.success(f"{t('welcome')}, {st.session_state['username']}")
                # try trigger backup on admin login if >24h
                if st.session_state["role"] == "admin":
                    ok, resp = backup.backup_db_to_github(st.secrets, actor=st.session_state["username"])
                    if ok:
                        st.info("自动备份已触发")
                    else:
                        st.info(f"备份未触发（{resp}）")
                st.rerun()
            else:
                st.error(t("login_prompt"))
    with col2:
        st.markdown("### " + t("admin_area"))
        st.write("- 首次使用默认管理员：`admin / admin123`")
        st.write("- 管理员登录后请创建用户并修改管理员密码")
    st.stop()

# --- Main app ---
username = st.session_state["username"]
role = st.session_state["role"]

# Sidebar
st.sidebar.title("📊 AYaocustomers")
st.sidebar.write(f"👤 {username} ({role})")
lang_choice = st.sidebar.selectbox("🌐 Language", options=lang_options, index=lang_options.index(st.session_state["lang"]))
if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice

if st.sidebar.button(t("logout")):
    st.session_state.clear()
    st.rerun()

# Admin tools in sidebar
if role == "admin":
    st.sidebar.markdown("#### " + t("admin_area"))
    if st.sidebar.button(t("backup_now")):
        ok, resp = backup.backup_db_to_github(st.secrets, actor=username)
        if ok:
            st.success("备份成功")
        else:
            st.error(f"备份失败：{resp}")

# Load customers (DataFrame)
df = list_customers_df()
# enforce permission: non-admin sees only their customers or where listed in assistant
if role != "admin":
    df = df[(df["main_person"]==username) | (df["assistant"].str.contains(username, na=False))]

# Top: filters and reports
st.title(t("app_title") or "氯雷他定用户统计")

c1,c2,c3,c4 = st.columns([2,1,1,1])
with c1:
    st.subheader(t("customers"))
with c2:
    period = st.selectbox(t("period"), ["全部","过去7天","过去30天","过去90天","自定义"])
with c3:
    owner_filter = st.selectbox(t("main_person"), ["全部"] + sorted(df["main_person"].dropna().unique().tolist()))
with c4:
    kw = st.text_input(t("keyword"))

# apply period filter
if period != "全部":
    if period == "过去7天":
        s = datetime.utcnow() - timedelta(days=7)
    elif period == "过去30天":
        s = datetime.utcnow() - timedelta(days=30)
    elif period == "过去90天":
        s = datetime.utcnow() - timedelta(days=90)
    else:
        s = None
else:
    s = None

df["created_at_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
if s is not None:
    df = df[df["created_at_dt"] >= s]

# keyword
if kw:
    df = df[df.apply(lambda r: kw.lower() in str(r.get("name","")).lower() or kw.lower() in str(r.get("country","")).lower(), axis=1)]

# owner filter
if owner_filter and owner_filter != "全部":
    df = df[df["main_person"]==owner_filter]

st.metric(t("client_count") if "client_count" in UI_TX.get("zh", {}) else "当前显示客户数", len(df))

# show table with key columns
display_cols = ["id","name","country","city","deal_amount","level","progress","main_person","assistant","created_at"]
if len(df)==0:
    st.info(t("no_data"))
else:
    st.dataframe(df[display_cols].sort_values("created_at", ascending=False), use_container_width=True)

# Select a customer to open details
sel = st.selectbox("🔎 " + t("details"), options=["(请选择)"] + [f"{r['name']} — {r['id']}" for _, r in df.iterrows()])
if sel and sel != "(请选择)":
    cid = sel.split(" — ")[-1]
    cust = get_customer_by_id(cid)
    if cust:
        st.header(f"{cust['name']}  — ID: {cust['id']}")
        left, right = st.columns([2,1])
        with left:
            st.subheader(t("details"))
            st.write(f"**{t('customer_name')}:** {cust.get('name')}")
            st.write(f"**{t('country')}:** {cust.get('country')} / {t('city')}: {cust.get('city')}")
            st.write(f"**{t('amount')}:** {cust.get('deal_amount')}  |  **{t('level')}:** {cust.get('level')}")
            st.write(f"**{t('status')}:** {cust.get('progress')}")
            st.write(f"**{t('main_person')}:** {cust.get('main_person')}  |  **{t('assistant')}:** {cust.get('assistant')}")
            st.markdown("**" + t("remark") + "**")
            st.write(cust.get("remark",""))
        with right:
            st.subheader("📄 操作")
            # Edit form
            with st.form("edit_cust"):
                new_progress = st.selectbox(t("status"), ["待联系","洽谈中","已成交","流失"], index=["待联系","洽谈中","已成交","流失"].index(cust.get("progress") or "待联系"))
                new_level = st.selectbox(t("level"), ["普通","重要","VIP"], index=["普通","重要","VIP"].index(cust.get("level") or "普通"))
                new_amount = st.number_input(t("amount"), value=float(cust.get("deal_amount") or 0.0))
                new_remark = st.text_area(t("remark"), value=cust.get("remark") or "")
                if st.form_submit_button(t("save")):
                    updates = {"progress": new_progress, "level": new_level, "deal_amount": new_amount, "remark": new_remark}
                    update_customer(cid, updates, actor=username)
                    st.success("保存成功")
                    st.rerun()
            # delete
            if role == "admin" or cust.get("main_person")==username:
                if st.button(t("delete")):
                    delete_customer(cid, actor=username)
                    st.warning("客户已删除")
                    st.rerun()

        # followups
        st.subheader(t("details") + " — 跟进记录")
        fups = list_followups(cid)
        if not fups.empty:
            st.table(fups[["created_at","author","note","next_action"]])
        else:
            st.info(t("no_data"))
        with st.form("add_fup"):
            note = st.text_area("跟进内容")
            next_act = st.text_input("下次动作")
            if st.form_submit_button(t("add_followup")):
                if note.strip():
                    add_followup(cid, username, note.strip(), next_act.strip())
                    st.success("跟进已添加")
                    st.rerun()

# Add new customer
st.markdown("---")
st.header(t("add_customer"))
with st.form("add_new"):
    name = st.text_input(t("customer_name"))
    whatsapp = st.text_input(t("whatsapp"))
    line = st.text_input(t("line"))
    telegram = st.text_input(t("telegram"))
    country = st.text_input(t("country"))
    city = st.text_input(t("city"))
    age = st.text_input(t("age"))
    job = st.text_input(t("job"))
    income = st.text_input(t("income"))
    relation = st.selectbox(t("relation"), ["单身","已婚","离异","丧偶"])
    deal_amount = st.number_input(t("amount"), min_value=0.0)
    level = st.selectbox(t("level"), ["普通","重要","VIP"])
    progress = st.selectbox(t("status"), ["待联系","洽谈中","已成交","流失"])
    main_person = st.selectbox(t("main_person"), options=["(未指定)"] + list_users()["username"].tolist())
    assistant = st.text_input(t("assistant"))
    remark = st.text_area(t("remark"))
    if st.form_submit_button(t("save")):
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
            "main_person": main_person if main_person!="(未指定)" else None,
            "assistant": assistant,
            "remark": remark
        }
        cid = add_customer_record(rec)
        st.success(f"客户已添加 (ID: {cid})")
        st.rerun()

# Export (admin full export; non-admin only their customers)
st.markdown("---")
if role == "admin":
    st.subheader("🔁 导出 & 管理")
    if st.button("导出全部客户 (Excel)"):
        df_all = list_customers_df()
        buf = io.BytesIO()
        df_all.to_excel(buf, index=False, engine="xlsxwriter")
        buf.seek(0)
        st.download_button("下载全部客户.xlsx", buf, file_name=f"all_customers_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")
    # user management
    st.subheader(t("admin_area"))
    users_df = list_users()
    st.dataframe(users_df)
    with st.form("add_user_form"):
        newu = st.text_input(t("new_username"))
        newp = st.text_input(t("new_password"), type="password")
        newr = st.selectbox(t("role"), ["user","admin"])
        if st.form_submit_button(t("add_user")):
            ok,msg = add_user(newu.strip(), newp.strip(), newr)
            if ok:
                st.success("用户已创建")
            else:
                st.error(msg)
    # reset/delete
    with st.form("reset_user"):
        sel = st.selectbox("选择用户", users_df["username"].tolist())
        newpw = st.text_input("新密码", type="password")
        if st.form_submit_button(t("reset_password")):
            update_user_password(sel, newpw)
            st.success("重置成功")
    with st.form("del_user"):
        sel2 = st.selectbox("选择删除用户", users_df["username"].tolist(), key="del")
        if st.form_submit_button("删除用户"):
            delete_user(sel2)
            st.success("用户已删除")

    # translation editing
    st.subheader("翻译编辑")
    try:
        with open("translations.json", "r", encoding="utf-8") as f:
            tx = json.load(f)
    except:
        tx = {}
    lang_edit = st.selectbox("选择语言编辑", list(tx.keys()))
    edited = {}
    for k,v in tx[lang_edit].items():
        newv = st.text_input(k, v, key=f"tx_{lang_edit}_{k}")
        edited[k] = newv
    if st.button(t("save_translations")):
        tx[lang_edit] = edited
        with open("translations.json", "w", encoding="utf-8") as f:
            json.dump(tx, f, ensure_ascii=False, indent=2)
        st.success("翻译已保存，请刷新页面")

else:
    # non-admin export own customers
    if st.button("导出我负责的客户 (Excel)"):
        me = username
        df_me = list_customers_df()
        df_me = df_me[(df_me["main_person"]==me) | (df_me["assistant"].str.contains(me, na=False))]
        buf = io.BytesIO()
        df_me.to_excel(buf, index=False, engine="xlsxwriter")
        buf.seek(0)
        st.download_button("下载我的客户.xlsx", buf, file_name=f"my_customers_{me}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")

# Owner reports / charts
st.markdown("---")
st.subheader(t("owner_report"))
selected_owner = st.selectbox("选择负责人", options=["(请选择)"] + sorted(list_customers_df()["main_person"].dropna().unique().tolist()))
if selected_owner and selected_owner!="(请选择)":
    df_owner = list_customers_df()
    df_owner = df_owner[df_owner["main_person"]==selected_owner]
    if not df_owner.empty:
        # level pie
        counts = df_owner["level"].value_counts().reset_index()
        counts.columns = ["level","count"]
        p = alt.Chart(counts).mark_arc().encode(theta="count:Q", color="level:N")
        st.altair_chart(p, use_container_width=True)
        # monthly trend
        df_owner["created_at_dt"] = pd.to_datetime(df_owner["created_at"], errors="coerce")
        monthly = df_owner.dropna(subset=["created_at_dt"]).groupby(df_owner["created_at_dt"].dt.to_period("M")).size().reset_index(name="新增")
        monthly["created_at_dt"] = monthly["created_at_dt"].astype(str)
        chart = alt.Chart(monthly).mark_line(point=True).encode(x="created_at_dt", y="新增")
        st.altair_chart(chart, use_container_width=True)
        total = len(df_owner)
        success = len(df_owner[df_owner["progress"]=="已成交"])
        st.write(f"成交成功率：{success}/{total} = {success/total*100:.1f}%")

# Logs visible to admin only
if role == "admin":
    st.markdown("---")
    st.subheader(t("logs"))
    logs_df = recent_logs(500)
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.info(t("no_data"))
