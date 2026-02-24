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
DEFAULT_GUIDE_SHEET = ""

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
        "guide_sheet_url": DEFAULT_GUIDE_SHEET,
        "api_key": ""
    }


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


config = load_config()


# =====================================================
# SESSION
# =====================================================

if "api_key" not in st.session_state:
    st.session_state.api_key = config.get("api_key", "")

if "sheet_url" not in st.session_state:
    st.session_state.sheet_url = config.get("sheet_url", "")

if "tour_sheet_url" not in st.session_state:
    st.session_state.tour_sheet_url = config.get("tour_sheet_url", "")

if "guide_sheet_url" not in st.session_state:
    st.session_state.guide_sheet_url = config.get("guide_sheet_url", "")

if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# =====================================================
# CSS
# =====================================================

st.markdown("""
<style>
.stApp {background:#0f172a;color:#e2e8f0;}
.stButton>button {background:#1d4ed8;color:white;border-radius:6px;border:none;height:40px;}
.chat-box {background:#020617;border:1px solid #1e293b;border-radius:10px;height:60vh;}
.msg {background:#334155;padding:10px;border-radius:8px;margin:10px;}
</style>
""", unsafe_allow_html=True)


# =====================================================
# CHATGPT
# =====================================================

def ask_chatgpt(prompt):

    if not st.session_state.api_key:
        return "Chưa nhập API Key"

    client = OpenAI(api_key=st.session_state.api_key)

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia du lịch Vietravel."},
            {"role": "user", "content": prompt}
        ]
    )

    return res.choices[0].message.content


# =====================================================
# GOOGLE SHEET
# =====================================================

def connect_sheet(url):

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )

    client = gspread.authorize(creds)

    return client.open_by_url(url).sheet1


def load_sheet(url):

    try:
        sheet = connect_sheet(url)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()


# =====================================================
# READ DOCX
# =====================================================

def read_docx(file):

    try:
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except:
        return ""


# =====================================================
# AI KNOWLEDGE BASE (QUAN TRỌNG)
# =====================================================

def load_company_knowledge():

    text = ""

    # docx nội bộ
    files = [
        "THÔNG BÁO NHẬN QT NN.docx",
        "CÁC LƯU Ý VISA NHẬP CẢNH VIỆT NAM CHO NGƯỜI NƯỚC NGOÀI.docx"
    ]

    for f in files:
        if os.path.exists(f):
            text += read_docx(f) + "\n"

    # sheet tour
    df = load_sheet(st.session_state.tour_sheet_url)

    if not df.empty:
        text += df.to_string()

    return text


def ask_company_ai(question):

    knowledge = load_company_knowledge()

    prompt = f"""
Dữ liệu nội bộ công ty:

{knowledge}

Câu hỏi:
{question}

Trả lời chính xác theo dữ liệu công ty.
"""

    return ask_chatgpt(prompt)


# =====================================================
# TOUR SUGGEST (KHÔNG AI)
# =====================================================

STOP_WORDS = ["tư", "vấn", "giúp", "tour", "muốn", "đi"]

def suggest_tour(message):

    df = load_sheet(st.session_state.tour_sheet_url)

    if df.empty:
        return pd.DataFrame()

    keywords = re.findall(r'\w+', message.lower())

    results = []

    for _, row in df.iterrows():

        text = str(row).lower()

        score = sum(1 for k in keywords if k in text)

        if score > 0:
            r = row.copy()
            r["Score"] = score
            results.append(r)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("Score", ascending=False)


# =====================================================
# DASHBOARD
# =====================================================

def dashboard():

    st.title("📊 Dashboard")

    df = load_sheet(st.session_state.sheet_url)

    if df.empty:
        st.warning("Chưa có dữ liệu")
        return

    st.dataframe(df)


# =====================================================
# SALES CENTER
# =====================================================

def sales_center():

    st.title("💬 Sales AI Center")

    msg = st.text_area("Tin nhắn khách")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🎯 Gợi ý tour"):

            df = suggest_tour(msg)

            if df.empty:
                st.info("Không tìm thấy")
            else:
                st.dataframe(df)

    with col2:
        if st.button("🤖 AI trả lời"):

            res = ask_company_ai(msg)

            st.success(res)

    with col3:
        if st.button("🧠 Xử lý từ chối"):

            prompt = f"Khách nói: {msg}. Đưa 3 cách xử lý chuyên nghiệp."
            res = ask_chatgpt(prompt)

            st.success(res)

    st.divider()

    # AI TRA CỨU NỘI BỘ

    st.subheader("⚡ AI Tra cứu nội bộ")

    q = st.text_input("Hỏi dữ liệu công ty")

    if st.button("Tra cứu nhanh"):
        res = ask_company_ai(q)
        st.success(res)

    st.divider()

    # SO SÁNH TOUR

    st.subheader("📊 So sánh tour")

    t1 = st.text_input("Tour 1")
    t2 = st.text_input("Tour 2")

    if st.button("So sánh"):
        prompt = f"So sánh 2 tour {t1} và {t2} của công ty."
        res = ask_company_ai(prompt)
        st.write(res)


# =====================================================
# VISA
# =====================================================

def visa_tab():

    st.title("🛂 Visa AI")

    nat = st.text_input("Quốc tịch")
    des = st.text_input("Điểm đến")

    if st.button("Kiểm tra"):

        q = f"Khách quốc tịch {nat} đi {des} cần visa gì?"
        res = ask_company_ai(q)

        st.success(res)


# =====================================================
# GUIDE CENTER
# =====================================================

def guide_center():

    st.title("📘 Cẩm nang")

    st.link_button("Mở cẩm nang công ty", st.session_state.guide_sheet_url)


# =====================================================
# SETTINGS
# =====================================================

def settings():

    st.title("⚙️ Settings")

    key = st.text_input("API Key", value=st.session_state.api_key)

    if st.button("Save"):

        st.session_state.api_key = key

        save_config({
            "sheet_url": st.session_state.sheet_url,
            "tour_sheet_url": st.session_state.tour_sheet_url,
            "guide_sheet_url": st.session_state.guide_sheet_url,
            "api_key": key
        })

        st.success("Saved")


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.image(LOGO_URL, width=150)

menu = st.sidebar.radio(
    "Menu",
    ["Dashboard", "Sales Center", "Visa AI", "Guide Center", "Settings"]
)

if menu == "Dashboard":
    dashboard()

elif menu == "Sales Center":
    sales_center()

elif menu == "Visa AI":
    visa_tab()

elif menu == "Guide Center":
    guide_center()

elif menu == "Settings":
    settings()
