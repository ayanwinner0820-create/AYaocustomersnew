import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

from config import PAGE_TITLE, PAGE_ICON, THEME_COLOR, LANG_OPTIONS
from db import init_db
import auth
import customers
import logs
import translate
import backup


# ---------------------------------------------------------
# 初始化
# ---------------------------------------------------------
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 数据库初始化（如果不存在则创建）
init_db()

# 加载翻译
translations = translate.load_translations()


# ---------------------------------------------------------
# 工具函数：多语言文字
# ---------------------------------------------------------
def T(key: str) -> str:
    lang = st.session_state.get("lang", "中文")
    if lang in translations and key in translations[lang]:
        return translations[lang][key]
    # fallback
    return translations["中文"].get(key, key)


# ---------------------------------------------------------
# 登录界面
# ---------------------------------------------------------
def login_view():
    st.title("🔐 登录 Login")

    # 避免刷新循环
    if "login_block" not in st.session_state:
        st.session_state["login_block"] = False

    username = st.text_input("用户名 / Username")
    password = st.text_input("密码 / Password", type="password")

    if st.button("登录 / Login"):
        user = auth.authenticate(username, password)
        if user:
            st.session_state["username"] = user["username"]
            st.session_state["role"] = user["role"]
            st.session_state["lang"] = user.get("language", "中文")
            st.experimental_rerun()
        else:
            st.error("账号或密码错误 / Incorrect username or password")


# ---------------------------------------------------------
# 顶部导航
# ---------------------------------------------------------
def top_nav():
    st.sidebar.title("导航 Navigation")

    pages = {
        "客户列表": "customers",
        "图表报表": "charts",
        "跟进记录": "followups",
        "操作日志": "logs",
        "用户管理（管理员）": "users",
        "翻译管理（管理员）": "translate",
        "GitHub 备份（管理员）": "backup",
    }

    if st.session_state.get("role") != "admin":
        del pages["用户管理（管理员）"]
        del pages["翻译管理（管理员）"]
        del pages["GitHub 备份（管理员）"]

    choice = st.sidebar.radio("选择页面", list(pages.keys()))
    return pages[choice]


# ---------------------------------------------------------
# 页面：客户管理
# ---------------------------------------------------------
def page_customers():
    st.title("📋 客户管理")

    df = customers.list_customers_df()

    with st.expander("➕ 添加客户"):
        rec = {}
        rec["name"] = st.text_input("客户名称")
        rec["whatsapp"] = st.text_input("Whatsapp")
        rec["line"] = st.text_input("Line")
        rec["telegram"] = st.text_input("Telegram")
        rec["country"] = st.text_input("国家")
        rec["city"] = st.text_input("城市")
        rec["age"] = st.number_input("年龄", 0, 120)
        rec["job"] = st.text_input("工作")
        rec["income"] = st.text_input("薪资水平")
        rec["marital_status"] = st.selectbox("感情状态", ["单身", "已婚", "离异", "丧偶"])
        rec["deal_amount"] = st.number_input("成交金额", 0.0)
        rec["level"] = st.selectbox("客户等级", ["普通", "重要", "VIP"])
        rec["progress"] = st.selectbox("跟进状态", ["待联系", "洽谈中", "已成交", "流失"])
        rec["main_owner"] = st.text_input("主要负责人")
        rec["assistant"] = st.text_input("辅助人员")
        rec["notes"] = st.text_area("备注")
        rec["operator"] = st.session_state.get("username")

        if st.button("提交保存"):
            cid = customers.insert_customer(rec)
            st.success(f"客户已添加：{cid}")
            st.experimental_rerun()

    # --------------------
    # 显示客户表格
    # --------------------
    st.subheader("所有客户")

    if df.empty:
        st.info("暂无客户信息")
        return

    st.dataframe(df)

    # 搜索 / 筛选
    st.subheader("筛选")
    owner = st.text_input("按主要负责人搜索")
    if owner:
        df = df[df["main_owner"] == owner]

    # 编辑 / 删除
    st.subheader("编辑 / 删除客户")
    cid = st.text_input("输入客户 ID")
    if cid:
        cust = customers.get_customer(cid)
        if not cust:
            st.error("未找到客户")
        else:
            st.write("当前数据：", cust)

            with st.form(f"edit_{cid}"):
                updates = {}
                for field in ["name", "whatsapp", "line", "telegram", "country", "city",
                              "age", "job", "income", "marital_status", "deal_amount",
                              "level", "progress", "main_owner", "assistant", "notes"]:
                    updates[field] = st.text_input(field, value=str(cust.get(field)))

                if st.form_submit_button("提交更新"):
                    customers.update_customer(cid, updates, operator=st.session_state["username"])
                    st.success("已更新")
                    st.experimental_rerun()

            if st.checkbox("确认删除该客户"):
                if st.button("删除客户"):
                    customers.delete_customer(cid, operator=st.session_state["username"])
                    st.success("客户已删除")
                    st.experimental_rerun()


# ---------------------------------------------------------
# 页面：跟进记录
# ---------------------------------------------------------
def page_followups():
    st.title("📝 客户跟进记录")

    cid = st.text_input("客户 ID")
    if not cid:
        return

    cust = customers.get_customer(cid)
    if not cust:
        st.error("此客户不存在")
        return

    st.write("客户：", cust["name"])

    # 添加记录
    with st.form("add_followup"):
        note = st.text_area("跟进内容")
        next_action = st.text_input("下一步动作")
        if st.form_submit_button("提交"):
            customers.add_followup(cid, st.session_state["username"], note, next_action)
            st.success("跟进记录已创建")
            st.experimental_rerun()

    # 显示记录
    df = customers.list_followups_df(cid)
    st.dataframe(df)


# ---------------------------------------------------------
# 页面：图表报表
# ---------------------------------------------------------
def page_charts():
    st.title("📊 负责人数据报表")

    df = customers.list_customers_df()
    if df.empty:
        st.info("暂无客户数据")
        return

    # 负责人筛选
    owner = st.selectbox("选择负责人", ["全部"] + sorted(df["main_owner"].unique().tolist()))
    if owner != "全部":
        df = df[df["main_owner"] == owner]

    # 时间筛选
    t = st.selectbox("时间区间", ["全部", "最近 7 天", "最近 30 天", "最近 90 天"])
    if t != "全部":
        days = {"最近 7 天": 7, "最近 30 天": 30, "最近 90 天": 90}[t]
        df = df[df["created_at"] >= (datetime.utcnow() - timedelta(days=days)).isoformat()]

    st.write("当前数据量：", len(df))

    # 来源占比
    st.subheader("客户等级占比")
    chart = alt.Chart(df).mark_arc().encode(
        theta="count()",
        color="level"
    )
    st.altair_chart(chart, use_container_width=True)

    # 成交趋势
    st.subheader("成交趋势")
    df2 = df[df["progress"] == "已成交"]
    if df2.empty:
        st.info("暂无成交数据")
    else:
        df2["date"] = df2["created_at"].str[:10]
        line = alt.Chart(df2).mark_line().encode(
            x="date:T",
            y="count()"
        )
        st.altair_chart(line, use_container_width=True)


# ---------------------------------------------------------
# 页面：操作日志
# ---------------------------------------------------------
def page_logs():
    st.title("📜 操作日志")
    df = logs.recent_actions(500)
    st.dataframe(df)


# ---------------------------------------------------------
# 页面：用户管理（管理员）
# ---------------------------------------------------------
def page_users():
    st.title("👤 用户管理（管理员）")

    df = auth.list_users()
    st.dataframe(df)

    st.subheader("添加用户")
    with st.form("add_user"):
        u = st.text_input("用户名")
        p = st.text_input("密码")
        r = st.selectbox("角色", ["user", "admin"])
        lang = st.selectbox("默认语言", LANG_OPTIONS)
        if st.form_submit_button("提交"):
            auth.add_user(u, p, r, lang)
            st.success("用户已创建")
            st.experimental_rerun()

    st.subheader("重置密码")
    with st.form("reset_pass"):
        u = st.text_input("用户名（重置）")
        p = st.text_input("新密码")
        if st.form_submit_button("重置"):
            auth.reset_password(u, p)
            st.success("密码已重置")

    st.subheader("删除用户")
    d = st.text_input("要删除的用户名")
    if st.button("删除用户"):
        auth.delete_user(d)
        st.success("用户已删除")
        st.experimental_rerun()


# ---------------------------------------------------------
# 页面：翻译管理（管理员）
# ---------------------------------------------------------
def page_translate():
    st.title("🌐 多语言翻译管理")
    data = translate.load_translations()

    st.write("当前翻译 JSON：")
    st.json(data, expanded=False)

    new = st.text_area("编辑翻译 JSON（格式必须正确）", value=str(data))

    if st.button("保存"):
        try:
            obj = eval(new)
            translate.save_translations(obj)
            st.success("翻译已保存")
            st.experimental_rerun()
        except Exception as e:
            st.error(str(e))


# ---------------------------------------------------------
# 页面：GitHub 自动备份（管理员）
# ---------------------------------------------------------
def page_backup():
    st.title("💾 GitHub 自动备份")

    st.info("自动备份使用 Streamlit Secrets 中的： GITHUB_TOKEN / GITHUB_REPO / GITHUB_USERNAME")

    if st.button("立即备份数据库"):
        ok, msg = backup.backup_db_to_github(st.secrets, actor=st.session_state["username"])
        if ok:
            st.success("备份成功")
        else:
            st.error(f"备份失败：{msg}")


# ---------------------------------------------------------
# 主程序入口
# ---------------------------------------------------------
def main():
    # 未登录 → 显示登录界面
    if "username" not in st.session_state:
        login_view()
        return

    # 已登录 → 显示导航与页面
    page = top_nav()

    if page == "customers":
        page_customers()
    elif page == "followups":
        page_followups()
    elif page == "charts":
        page_charts()
    elif page == "logs":
        page_logs()
    elif page == "users":
        page_users()
    elif page == "translate":
        page_translate()
    elif page == "backup":
        page_backup()


if __name__ == "__main__":
    main()
