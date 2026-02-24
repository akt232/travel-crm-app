import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import json
import os
import re

from openai import OpenAI
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from docx import Document


# =====================================================
# CONFIG
# =====================================================

CONFIG_FILE = "config.json"

DEFAULT_SHEET = ""
DEFAULT_TOUR_SHEET = ""
DEFAULT_GUIDE_SHEET = "https://docs.google.com/spreadsheets/d/1b7z00QcNuYjK54ikc2ctbxsF3Ok7snGKSx57LChIZpA/edit#gid=0"

LOGO_URL = "https://travel.com.vn/Content/images/logo.png"

st.set_page_config(
    page_title="Vietravel Sales Hub",
    page_icon="🌍",
    layout="wide"
)


# =====================================================
# LOAD CONFIG
# =====================================================

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    return {
    "sheet_url": DEFAULT_SHEET,
    "tour_sheet_url": DEFAULT_TOUR_SHEET,
    "guide_sheet_url": DEFAULT_GUIDE_SHEET
}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


config = load_config()


# =====================================================
# SESSION
# =====================================================

if "api_key" not in st.session_state:
    st.session_state.api_key = ""

if "sheet_url" not in st.session_state:
    st.session_state.sheet_url = config.get("sheet_url", "")

if "tour_sheet_url" not in st.session_state:
    st.session_state.tour_sheet_url = config.get("tour_sheet_url", "")

if "guide_sheet_url" not in st.session_state:
    st.session_state.guide_sheet_url = config.get("guide_sheet_url", DEFAULT_GUIDE_SHEET)

if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "customer_list" not in st.session_state:
    st.session_state.customer_list = [
        {"id": 1, "name": "Anh Hùng", "msg": "Anh muốn đi Nhật tháng 3 ngân sách 40000000", "time": "10:30"},
        {"id": 2, "name": "Chị Lan", "msg": "Tour Thái Lan bao nhiêu tiền em?", "time": "09:15"},
        {"id": 3, "name": "Khách Web", "msg": "Tư vấn giúp tour Đà Nẵng", "time": "08:00"},
    ]


# =====================================================
# CSS
# =====================================================

st.markdown("""
<style>
.stApp {background:#0f172a;color:#e2e8f0;}
.stButton>button {background:#1d4ed8;color:white;border-radius:6px;border:none;height:40px;}
.chat-box {background:#020617;border:1px solid #1e293b;border-radius:10px;height:60vh;display:flex;flex-direction:column;}
.chat-area {flex-grow:1;overflow-y:auto;padding:15px;}
.msg {background:#334155;padding:10px;border-radius:8px;margin-bottom:10px;}
</style>
""", unsafe_allow_html=True)


# =====================================================
# CHATGPT FUNCTION
# =====================================================

def ask_chatgpt(prompt):

    if not st.session_state.api_key:
        return "Chưa nhập OpenAI API Key"

    try:
        client = OpenAI(api_key=st.session_state.api_key)

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia du lịch."},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return str(e)


# =====================================================
# GOOGLE SHEET
# =====================================================

def connect_sheet(url):

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = st.secrets["gcp_service_account"]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        scope
    )

    client = gspread.authorize(creds)

    sheet = client.open_by_url(url).sheet1

    return sheet


def load_sheet():
    try:
        sheet = connect_sheet(st.session_state.sheet_url)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()


def load_tour_sheet():
    try:
        sheet = connect_sheet(st.session_state.tour_sheet_url)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()


def load_guide_sheet():
    try:
        sheet = connect_sheet(st.session_state.guide_sheet_url)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()


def save_to_sheet(row):
    try:
        sheet = connect_sheet(st.session_state.sheet_url)
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(e)
        return False


def delete_row(row_number):
    try:
        sheet = connect_sheet(st.session_state.sheet_url)
        sheet.delete_rows(row_number)
        return True
    except:
        return False


# =====================================================
# TOUR SUGGEST
# =====================================================

STOP_WORDS = [
    "tư", "vấn", "giúp", "tour", "muốn", "đi", "em", "anh",
    "chị", "bao", "nhiêu", "tiền", "tháng", "ngân", "sách"
]


def clean_words(text):
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def suggest_tour(message):

    df = load_tour_sheet()

    if df.empty:
        return pd.DataFrame()

    keywords = clean_words(message)

    results = []

    for _, row in df.iterrows():

        text = " ".join([str(row).lower()])

        score = 0

        for kw in keywords:
            if kw in text:
                score += 1

        if score > 0:
            r = row.copy()
            r["Score"] = score
            results.append(r)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    return result_df.sort_values("Score", ascending=False).drop(columns=["Score"])


# =====================================================
# DASHBOARD
# =====================================================

def render_dashboard():

    st.title("📊 Dashboard")

    df = load_sheet()

    if df.empty:
        st.warning("Chưa có dữ liệu")
        return

    # ===== CLEAN DATA =====
    if "Giá" in df.columns:
        df["Giá"] = (
            df["Giá"]
            .astype(str)
            .str.replace(",", "")
            .str.replace("đ", "")
        )
        df["Giá"] = pd.to_numeric(df["Giá"], errors="coerce").fillna(0)

    if "Ngày" in df.columns:
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")

    today = datetime.now().date()
    today_df = df[df["Ngày"].dt.date == today]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Khách hôm nay", len(today_df))
    col2.metric("Doanh thu hôm nay", f"{today_df['Giá'].sum():,.0f} đ")
    col3.metric("Tổng khách", len(df))
    col4.metric("Tổng doanh thu", f"{df['Giá'].sum():,.0f} đ")

    st.divider()

    # ===== DOANH THU THEO TOUR =====
    if "Tour" in df.columns:

        route_df = df.groupby("Tour").agg({
            "Tên": "count",
            "Giá": "sum"
        }).reset_index()

        fig1 = px.bar(
            route_df,
            x="Tour",
            y="Giá",
            color="Tour",
            title="Doanh thu theo Tour"
        )

        st.plotly_chart(fig1, use_container_width=True)

    # ===== DOANH THU THEO NGÀY =====
    daily = df.groupby("Ngày")["Giá"].sum().reset_index()

    fig2 = px.line(
        daily,
        x="Ngày",
        y="Giá",
        markers=True,
        title="Doanh thu theo ngày"
    )

    st.plotly_chart(fig2, use_container_width=True)

# =====================================================
# SALES CENTER
# =====================================================

def render_sales_center():

    col_left, col_mid, col_right = st.columns([1, 2, 1])

    with col_left:

        st.subheader("Khách hàng")

        for cust in st.session_state.customer_list:
            if st.button(f"{cust['name']} - {cust['time']}", key=cust["id"]):
                st.session_state.selected_customer = cust

    with col_mid:

        cust = st.session_state.selected_customer

        if cust:

            st.subheader(f"Chat với {cust['name']}")

            st.markdown(f"""
            <div class="chat-box">
                <div class="chat-area">
                    <div class="msg">{cust["msg"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.subheader("🎯 Tour phù hợp")

            suggest_df = suggest_tour(cust["msg"])

            if suggest_df.empty:
                st.info("Không tìm thấy tour")
            else:
                st.dataframe(suggest_df)

            st.subheader("🤖 AI gợi ý trả lời")

            if st.button("Gợi ý trả lời khách"):
                prompt = f"Khách nói: {cust['msg']}. Hãy trả lời tư vấn tour chuyên nghiệp."
                reply = ask_chatgpt(prompt)
                st.success(reply)

            status = st.selectbox(
                "Trạng thái",
                ["Đang theo dõi", "Đã chốt đơn", "Không chốt"]
            )

            if status == "Đã chốt đơn":

                with st.form("deal"):

                    name = st.text_input("Tên", cust["name"])
                    tour = st.text_input("Tour")
                    price = st.text_input("Giá")
                    note = st.text_area("Note")
                    sale = st.text_input("Sale")

                    channel = st.selectbox(
                        "Kênh",
                        ["Online", "Facebook", "Zalo", "Chi nhánh"]
                    )

                    ok = st.form_submit_button("Xác nhận")

                    if ok:

                        saved = save_to_sheet([
                            datetime.now().strftime("%Y-%m-%d"),
                            name,
                            tour,
                            price,
                            note,
                            channel,
                            sale
                        ])

                        if saved:
                            st.success("✅ Đã lưu Google Sheet")

    with col_right:

        st.subheader("AI Hỏi Tour")

        user_q = st.text_input("Hỏi AI")

        if st.button("Gửi"):

            res = ask_chatgpt(user_q)

            st.session_state.chat_history.append(("Bạn", user_q))
            st.session_state.chat_history.append(("AI", res))

        for role, msg in st.session_state.chat_history:
            st.write(f"**{role}:** {msg}")


# =====================================================
# CUSTOMERS & ORDERS
# =====================================================

def render_customer_orders():

    st.title("Customers & Orders")

    st.subheader("Danh sách khách")
    st.dataframe(pd.DataFrame(st.session_state.customer_list))

    st.divider()

    df = load_sheet()

    st.subheader("Đơn đã chốt")

    if df.empty:
        st.info("Chưa có dữ liệu")
        return

    for idx, row in df.iterrows():

        col1, col2, col3, col4, col5, col6 = st.columns([2,2,2,2,2,1])

        with col1:
            st.write(row.get('Ngày',''))

        with col2:
            st.write(row.get('Tên',''))

        with col3:
            st.write(row.get('Tour',''))

        with col4:
            st.write(row.get('Giá',''))

        with col5:
            st.write(row.get('Kênh',''))

        with col6:

            if st.button("❌", key=f"del_{idx}"):

                ok = delete_row(idx + 2)

                if ok:
                    st.success("Đã xóa")
                    st.rerun()


# =====================================================
# GUIDE CENTER
# =====================================================

# =====================================================
# GUIDE CENTER
# =====================================================

def render_guide_center():

    st.title("📘 Cẩm nang")

    df = load_guide_sheet()

    if df.empty:
        st.warning("Không có dữ liệu")
        return

    # ===== XÁC ĐỊNH CỘT MỤC =====
    possible_cols = ["Mục", "Category", "Danh mục", "Loai"]

    category_col = None

    for col in possible_cols:
        if col in df.columns:
            category_col = col
            break

    # Nếu không có cột mục thì hiển thị thẳng
    if not category_col:
        st.dataframe(df, use_container_width=True)
        return

    # ===== DANH SÁCH MỤC =====
    categories = df[category_col].dropna().unique()

    selected_cat = st.selectbox(
        "Chọn mục",
        categories
    )

    cat_df = df[df[category_col] == selected_cat]

    st.dataframe(cat_df, use_container_width=True)

    st.divider()

    # ===== AI HỎI THEO MỤC =====
    st.subheader("🤖 Hỏi AI theo mục này")

    user_q = st.text_input("Nhập câu hỏi")

    if st.button("Hỏi"):

        knowledge = cat_df.to_string()

        prompt = f"""
Dữ liệu cẩm nang:
{knowledge}

Câu hỏi:
{user_q}

Trả lời chính xác theo dữ liệu.
"""

        res = ask_chatgpt(prompt)

        st.success(res)
# =====================================================
# VISA AI
# =====================================================

def read_docx(file_path):
    try:
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except:
        return ""


visa_rule_1 = read_docx("THÔNG BÁO NHẬN QT NN.docx")
visa_rule_2 = read_docx("CÁC LƯU Ý VISA NHẬP CẢNH VIỆT NAM CHO NGƯỜI NƯỚC NGOÀI.docx")

visa_knowledge = visa_rule_1 + "\n" + visa_rule_2


def visa_tab():

    st.title("🛂 Visa Information")

    nationality = st.text_input("Quốc tịch")
    destination = st.text_input("Điểm đến")

    if st.button("Kiểm tra Visa"):

        prompt = f"""
Dữ liệu:
{visa_knowledge}

Khách quốc tịch {nationality} đi {destination}.

Tư vấn visa chi tiết.
"""

        result = ask_chatgpt(prompt)
        st.write(result)


# =====================================================
# SETTINGS
# =====================================================

def render_settings():

    st.title("Settings")

    key = st.text_input("OpenAI API Key", value=st.session_state.api_key)

    if st.button("Save API"):
        st.session_state.api_key = key
        st.success("Saved")

    st.divider()

    sheet_link = st.text_input(
        "Link Sheet Orders",
        value=st.session_state.sheet_url
    )

    tour_link = st.text_input(
        "Link Sheet Tour",
        value=st.session_state.tour_sheet_url
    )

    guide_link = st.text_input(
        "Link Sheet Guide",
        value=st.session_state.guide_sheet_url
    )

    if st.button("Lưu cấu hình"):

        st.session_state.sheet_url = sheet_link
        st.session_state.tour_sheet_url = tour_link
        st.session_state.guide_sheet_url = guide_link

        save_config({
            "sheet_url": sheet_link,
            "tour_sheet_url": tour_link,
            "guide_sheet_url": guide_link
        })

        st.success("Đã lưu vĩnh viễn")

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.image(LOGO_URL, width=150)

menu = st.sidebar.radio(
    "MENU",
    ["Dashboard", "Sales Center", "Customers & Orders", "Guide Center", "Visa Info", "Settings"]
)


# =====================================================
# ROUTER
# =====================================================

if menu == "Dashboard":
    render_dashboard()

elif menu == "Sales Center":
    render_sales_center()

elif menu == "Customers & Orders":
    render_customer_orders()

elif menu == "Guide Center":
    render_guide_center()

elif menu == "Visa Info":
    visa_tab()

elif menu == "Settings":
    render_settings()



