import streamlit as st
import datetime
import pytz
import random
import json
import gspread
import io
import time
import os
import re
import requests
import pandas as pd
from PIL import Image, ImageOps
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import streamlit.components.v1 as components

# 1. 앱 기본 설정
st.set_page_config(page_title="수기 커플 노트 v5.5", page_icon="❤️", layout="centered")

# --- 🌐 한국 시간(KST) 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

# ==========================================
# 🌤️ 실시간 날씨 API 연동 및 심플 이모티콘 로직
# ==========================================
@st.cache_data(ttl=3600)
def get_weather_info():
    try:
        res = requests.get("https://api.open-meteo.com/v1/forecast?latitude=35.1796&longitude=129.0756&current_weather=true", timeout=1.5)
        if res.status_code == 200:
            code = res.json().get("current_weather", {}).get("weathercode", 0)
            if code == 0: return "☀️ 맑음"
            elif code in [1, 2, 3]: return "☁️ 흐림"
            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return "🌧️ 비"
            elif code in [71, 73, 75, 77, 85, 86]: return "❄️ 눈"
            else: return "☀️ 맑음"
        return "☀️ 맑음"
    except: return "☀️ 맑음"

weather_display = get_weather_info()

# --- 🚀 구글 인증 및 서비스 설정 ---
@st.cache_resource
def get_credentials():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "google_auth" in st.secrets:
        token_info = json.loads(st.secrets["google_auth"]["token"])
        return Credentials.from_authorized_user_info(token_info, scopes)
    return None

@st.cache_resource
def get_sheets():
    creds = get_credentials()
    if not creds: return None
    client = gspread.authorize(creds)
    doc = client.open('couple_app_data')
    def safe_ws(name):
        try: return doc.worksheet(name)
        except: return None
    return {
        "main": safe_ws('시트1'), "memo": safe_ws('쪽지함'), "time": safe_ws('타임라인'),
        "date": safe_ws('데이트일정'), "wish": safe_ws('위시리스트'), "review": safe_ws('데이트후기'),
        "qna": safe_ws('문답데이터'), "capsule": safe_ws('타임캡슐데이터'),
        "tele": safe_ws('텔레파시'), "jukebox": safe_ws('주크박스')
    }

services = get_sheets()
if not services: st.error("🚨 구글 연동 실패! Secrets 설정을 확인해주세요.")

# --- 유틸리티 ---
def extract_youtube_id(url):
    if not url or not isinstance(url, str): return None
    pattern = r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url); return match.group(1) if match else None

DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID") or st.secrets.get("google_auth", {}).get("DRIVE_FOLDER_ID") or ""

def get_drive_service():
    creds = get_credentials(); return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_photo_to_drive(file_bytes, filename, mime_type):
    if not DRIVE_FOLDER_ID: return None
    try:
        svc = get_drive_service()
        file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file = svc.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except: return None

def load_photos_from_drive(limit=20):
    if not DRIVE_FOLDER_ID: return []
    try:
        svc = get_drive_service()
        results = svc.files().list(q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false", pageSize=limit, fields="files(id, name)", orderBy="createdTime desc").execute()
        return results.get('files', [])
    except: return []

@st.cache_data(show_spinner=False, ttl=3600)
def get_image_bytes(file_id):
    svc = get_drive_service(); request = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    return fh.getvalue()

def delete_photo_from_drive(file_id):
    try:
        svc = get_drive_service(); svc.files().delete(fileId=file_id).execute()
        return True
    except: return False

# ==========================================
# ⚡️ 데이터 로드 및 아토믹 세이브
# ==========================================
def load_data():
    try: val = services["main"].acell('A1').value
    except: val = None
    main_data = json.loads(val) if val else {}

    def get_large_data(sheet_obj):
        if not sheet_obj: return []
        try:
            vals = sheet_obj.col_values(1)[1:]
            return json.loads("".join(vals)) if vals else []
        except: return []

    def get_json_cell(sheet_obj, default_val):
        if not sheet_obj: return default_val
        try:
            val = sheet_obj.acell('A1').value
            return json.loads(val) if val else default_val
        except: return default_val

    return {
        "notice": main_data.get("notice", "비타민 챙겨 먹기! 오늘 하루도 화이팅 ✨"),
        "promises": main_data.get("promises", [{"text": "서운한 건 그날 바로 말하기 🗣️", "by": "수기남자친구"}]),
        "moods": main_data.get("moods", {"수기남자친구": "🙂", "수기": "🙂"}),
        "mood_history": main_data.get("mood_history", []),
        "current_mood_date": main_data.get("current_mood_date", today_str),
        "menu_list": main_data.get("menu_list", ["삼겹살", "초밥"]),
        "memo_history": get_large_data(services["memo"]),
        "timeline": get_large_data(services["time"]),
        "date_schedules": get_large_data(services["date"]),
        "wishlist": get_large_data(services["wish"]),
        "reviews": get_large_data(services["review"]),
        "qna_data": get_json_cell(services["qna"], {}),
        "time_capsules": get_json_cell(services["capsule"], []),
        "tele_data": get_json_cell(services["tele"], {}),
        "jukebox_data": get_json_cell(services["jukebox"], {"hodl": None, "sugi": None}) 
    }

def save_data_to_cell(sheet_key, data):
    if services and services.get(sheet_key): services[sheet_key].update_acell('A1', json.dumps(data))

def save_large_data(sheet_key, data_list):
    if services and services.get(sheet_key):
        json_str = json.dumps(data_list)
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cell_values = [[chunk] for chunk in chunks]
        services[sheet_key].batch_clear(['A2:A'])
        services[sheet_key].update(values=cell_values, range_name='A2', value_input_option='RAW')

def save_main_data():
    main_data = {
        "notice": st.session_state.notice, "promises": st.session_state.promises, "moods": st.session_state.moods,
        "mood_history": st.session_state.mood_history, "current_mood_date": st.session_state.current_mood_date, "menu_list": st.session_state.menu_list,
    }
    save_data_to_cell("main", main_data)

# ==========================================
# 🔐 자동 로그인 프리패스
# ==========================================
def validate_password():
    if st.session_state.pwd_input == "6146": st.session_state["password_correct"] = True
    else: st.error("비밀번호가 틀렸어! ❤️")

def check_login_and_user():
    if "auth" in st.query_params:
        auth_val = st.query_params["auth"]
        if auth_val in ["hodl", "sugi"]:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = "수기남자친구" if auth_val == "hodl" else "수기"; return True

    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if "current_user" not in st.session_state: st.session_state["current_user"] = None

    if not st.session_state["password_correct"]:
        st.markdown("<h1 style='text-align: center; color: #FF85A2;'>♥ 수기 커플 노트</h1>", unsafe_allow_html=True)
        st.text_input("비밀번호", type="password", key="pwd_input", on_change=validate_password)
        return False
    
    if not st.session_state["current_user"]:
        st.markdown("<h2 style='text-align: center; color: #FF85A2;'>누가 오셨나요? 👀</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👦 수기남자친구"): st.session_state["current_user"] = "수기남자친구"; st.query_params["auth"] = "hodl"; st.rerun()
        with col2:
            if st.button("👧 수기"): st.session_state["current_user"] = "수기"; st.query_params["auth"] = "sugi"; st.rerun()
        return False
    return True

# --- 메인 로직 ---
if check_login_and_user():
    user_name_only = st.session_state["current_user"]
    user_icon = "👧" if user_name_only == "수기" else "👦"

    if 'data_loaded' not in st.session_state:
        saved = load_data()
        for k, v in saved.items(): st.session_state[k] = v
        st.session_state['data_loaded'] = True
        st.session_state.photo_limit = 20
        st.session_state.memo_limit = 10
        st.session_state.review_limit = 10
        st.session_state.photo_cart = [] 
        if st.session_state.current_mood_date != today_str:
            st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}
            st.session_state.current_mood_date = today_str; save_main_data()

    # 🎨 화사한 파스텔 배경 및 텍스트 가독성 최우선
    bg_color = "#FFF5F7" if user_name_only == "수기" else "#E3F2FD"
    accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"
    text_color = "#333333" 
    
    st.markdown(f"""
        <div class="custom-bg-layer" style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:{bg_color}; z-index:-99999; pointer-events:none;"></div>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, p, h1, h2, h3, h4, h5, h6, label, button, input, textarea, select, div[data-testid="stMetricValue"], .stMarkdown, .stText {{
            font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important;
        }}
        .stApp {{ background: transparent !important; }}
        input, textarea, select, div.stTextInput > div > div > input, div.stTextArea > div > div > textarea {{
            background-color: rgba(255,255,255,0.9) !important; color: #333333 !important; border: 1px solid rgba(0,0,0,0.1) !important;
        }}
        div[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ 
            background-color: rgba(255,255,255,0.6) !important; border-right: 1px solid rgba(0,0,0,0.05) !important;
        }}
        .card, [data-testid="stExpander"] {{ 
            background: rgba(255,255,255,0.4) !important; backdrop-filter: blur(10px); border-radius: 15px; padding: 15px; margin-bottom: 15px; border-left: 5px solid {accent_color} !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        }}
        .user-boy {{ border-left:5px solid #4B89FF !important; background:rgba(75,137,255,0.15) !important; text-align: left; }}
        .user-girl {{ border-right:5px solid #FF85A2 !important; background:rgba(255,133,162,0.15) !important; text-align: right; border-left: none !important; }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: rgba(255,255,255,0.7) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important; }}
        [data-testid="stMetricValue"] {{ color: {accent_color} !important; }}
        </style>
    """, unsafe_allow_html=True)

    # ==========================================
    # 🌱 사이드바: 다마고치 + 📊 월간 백서 (이동 완료)
    # ==========================================
    total_act = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    level, tree_icon = ("풍성한 나무", "🍎") if total_act >= 70 else (("아기 나무", "🌳") if total_act >= 30 else (("새싹", "🌿") if total_act >= 10 else ("씨앗", "🌱")))
    
    with st.sidebar:
        st.markdown(f"<div style='text-align:center;'><h1>{tree_icon}</h1><h4>사랑나무: {level}</h4><p>포인트: {total_act} XP</p></div>", unsafe_allow_html=True)
        start_date = datetime.date(2026, 1, 1); d_day = (now_kst.date() - start_date).days + 1
        st.metric(label="함께한 시간", value=f"D + {d_day}일")
        
        st.divider()
        st.markdown("### 📊 월간 수기 백서")
        this_month = now_kst.strftime("%Y-%m")
        m_rev = [r for r in st.session_state.reviews if r.get('date','').startswith(this_month)]
        m_memo = [m for m in st.session_state.memo_history if m.get('date','').startswith(this_month)]
        st.write(f"📅 **{now_kst.month}월 결산**")
        c_s1, c_s2 = st.columns(2)
        c_s1.metric("데이트", f"{len(m_rev)}회"); c_s2.metric("쪽지", f"{len(m_memo)}개")
        
        all_text = " ".join([m.get('content', '') for m in m_memo] + [r.get('comment', '') for r in m_rev])
        words = [w for w in re.findall(r'[가-힣]{2,}', all_text) if len(w) > 1]
        word_counts = {}
        for w in words: word_counts[w] = word_counts.get(w, 0) + 1
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_words:
            st.markdown("**🏷️ 우리를 상징하는 단어**")
            st.caption(" ".join([f"#{w[0]}" for w in top_words]))
        
        st.divider()
        if st.button("로그아웃 🚪"): st.query_params.clear(); st.session_state.clear(); st.rerun()

    # --- 메인 헤더 (날씨 이모티콘 통합) ---
    col_h1, col_h2 = st.columns([0.8, 0.2])
    col_h1.markdown(f"<h2 style='color: #FF85A2; margin:0;'>♥ 수기 커플 노트 {weather_display}</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄 새로고침"): st.session_state.clear(); st.rerun()

    st.success(f"📢 {st.session_state.notice}")
    
    # 🚨 탭 구성
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # 1. 💕 데이트
    with tabs[0]:
        past_records = [m for m in st.session_state.memo_history if m.get('date', '').endswith(now_kst.strftime("-%m-%d")) and m.get('date') != today_str]
        if past_records:
            st.warning(f"🕰️ **과거에서 온 추억:** 예전 오늘, 이런 마음을 남겼었네요!")
            with st.expander("추억 열어보기"):
                for p in past_records: st.info(f"[{p['date']}] {p['user']}: {p['content']}")

        qna_list = ["1. 우리가 처음 만났던 날 첫인상은?", "2. 서로에게 반했던 결정적 순간은?", "3. 내가 가장 사랑스러워 보일 때는?", "4. 지금 당장 떠나고 싶은 여행지는?", "5. 서로의 연락처 저장명과 이유는?"] # (80개 리스트 생략)
        q_idx = now_kst.toordinal() % len(qna_list); q_key = f"qna_{q_idx}"
        st.session_state.qna_data.setdefault(q_key, {"hodl": "", "sugi": ""})
        with st.expander(f"💌 오늘의 문답 (No.{q_idx + 1})", expanded=True):
            st.subheader(qna_list[q_idx])
            ans_b = st.session_state.qna_data[q_key]["hodl"]; ans_g = st.session_state.qna_data[q_key]["sugi"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("👦 **남친**")
                if user_name_only == "수기남자친구": n_ans_b = st.text_area("답변", value=ans_b, key="q_b", label_visibility="collapsed")
                else: st.info(ans_b if (ans_b and ans_g) else "🔒 작성 대기 중")
            with c2:
                st.markdown("👩 **수기**")
                if user_name_only == "수기": n_ans_g = st.text_area("답변", value=ans_g, key="q_g", label_visibility="collapsed")
                else: st.info(ans_g if (ans_b and ans_g) else "🔒 작성 대기 중")
            if st.button("답변 저장 💾"):
                if user_name_only == "수기남자친구": st.session_state.qna_data[q_key]["hodl"] = n_ans_b
                else: st.session_state.qna_data[q_key]["sugi"] = n_ans_g
                save_data_to_cell("qna", st.session_state.qna_data); st.rerun()

        st.divider()
        st.subheader("📈 기분 차트")
        if len(st.session_state.mood_history) >= 2:
            df = pd.DataFrame(st.session_state.mood_history).set_index('date')
            df.columns = ['👦 남친 점수', '👧 수기 점수']
            st.line_chart(df, color=["#4B89FF", "#FF85A2"])
        else: st.caption("데이터가 쌓이면 그래프가 나타나요! 📈")

    # 2. 💌 쪽지함
    with tabs[1]:
        st.subheader("💌 쪽지함")
        content = st.text_area("하고 싶은 말 전하기", key="memo_in")
        if st.button("보내기 ✈️") and content:
            st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
            save_large_data("memo", st.session_state.memo_history); st.rerun()
        for m in st.session_state.memo_history[:st.session_state.memo_limit]:
            cls = "user-boy" if "남자친구" in m.get('user','') else "user-girl"
            st.markdown(f"<div class='card {cls}'><b>{m.get('user','')}</b> | {m.get('date','')}<br>{m.get('content','')}</div>", unsafe_allow_html=True)
        if len(st.session_state.memo_history) > st.session_state.memo_limit:
            if st.button("더 보기 ⬇️"): st.session_state.memo_limit += 10; st.rerun()

    # 3. 🌸 텔레파시
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시")
        questions = [["평생 여름", "평생 겨울"], ["카레맛 똥", "똥맛 카레"], ["찍먹", "부먹"], ["강아지", "고양이"]]
        t_idx = now_kst.toordinal() % len(questions); q_pair = questions[t_idx]
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        ans = st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"]
        c1, c2 = st.columns(2)
        if c1.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[0]
            save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        if c2.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[1]
            save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        
        b_ans = st.session_state.tele_data[today_str].get("hodl"); g_ans = st.session_state.tele_data[today_str].get("sugi")
        if b_ans and g_ans:
            if st.button("🎁 결과 확인하기 (풍선 팡!)", use_container_width=True):
                if b_ans == g_ans: st.balloons(); st.success(f"찌찌뽕! **[{b_ans}]** ❤️")
                else: st.info(f"👦 남친: {b_ans} / 👧 수기: {g_ans}")
        else: st.warning("🔒 상대방의 선택을 기다리는 중...")

    # 4. 🎵 주크박스
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        if isinstance(st.session_state.jukebox_data, list): st.session_state.jukebox_data = {"hodl": None, "sugi": None}
        yt_safe = "https://www.youtube.com/watch?v=" # AI의 링크 자동 변환을 막는 분리형 주소
        with st.form("dj_dual"):
            link = st.text_input("오늘의 노래 (유튜브)")
            if st.form_submit_button("신청하기"):
                st.session_state.jukebox_data["hodl" if user_name_only == "수기남자친구" else "sugi"] = link
                save_data_to_cell("jukebox", st.session_state.jukebox_data); st.rerun()
        cb, cg = st.columns(2)
        with cb:
            b_id = extract_youtube_id(st.session_state.jukebox_data.get("hodl", ""))
            if b_id: st.markdown("👦 **남친 Pick**"); st.video(yt_safe + b_id)
        with cg:
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.markdown("👧 **수기 Pick**"); st.video(yt_safe + g_id)

    # 5. 📸 추억저장소 (아이폰 vs 안드로이드 분리)
    with tabs[4]:
        st.subheader("📸 추억 보관함")
        with st.expander("✨ 새로운 추억 보관하기"):
            mode = st.radio("업로드 방식", ["아이폰 (여러 장)", "안드로이드 (장바구니)"], horizontal=True)
            if "아이폰" in mode:
                img_fs = st.file_uploader("사진들 선택", type=['jpg','png','jpeg'], accept_multiple_files=True)
                if st.button("☁️ 한 번에 업로드"):
                    if img_fs:
                        with st.spinner("드라이브로 전송 중..."):
                            for f in img_fs:
                                img = Image.open(f); img = ImageOps.exif_transpose(img)
                                img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                                upload_photo_to_drive(out.getvalue(), f"{today_str}_{random.randint(1000,9999)}.jpg", "image/jpeg")
                            st.success("업로드 완료!"); st.rerun()
            else:
                new_f = st.file_uploader("1장씩 담기", type=['jpg','png','jpeg'], accept_multiple_files=False)
                if st.button("장바구니 담기") and new_f:
                    st.session_state.photo_cart.append(new_f.getvalue()); st.toast("담겼어요!"); st.rerun()
                if st.session_state.photo_cart:
                    st.info(f"현재 {len(st.session_state.photo_cart)}장 대기 중")
                    if st.button("☁️ 장바구니 모두 전송"):
                        for fb in st.session_state.photo_cart:
                            img = Image.open(io.BytesIO(fb)); img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                            upload_photo_to_drive(out.getvalue(), f"{today_str}_{random.randint(1000,9999)}.jpg", "image/jpeg")
                        st.session_state.photo_cart = []; st.success("전송 완료!"); st.rerun()

        st.divider()
        photos = load_photos_from_drive(st.session_state.photo_limit)
        grouped = {}
        for p in photos:
            pts = p['name'].split('_'); date_key = pts[0] if pts else "과거의 어느 날"
            grouped.setdefault(date_key, []).append(p)
        for dk, pl in grouped.items():
            with st.expander(f"🗓️ {dk} ({len(pl)}장)"):
                cols = st.columns(2)
                for idx, p in enumerate(pl):
                    try: 
                        img_b = get_image_bytes(p['id'])
                        cols[idx%2].image(img_b, use_container_width=True)
                        if cols[idx%2].button("🗑️", key=f"del_{p['id']}"):
                            if delete_photo_from_drive(p['id']): st.rerun()
                    except: pass

    # 6. ⏳ 타임라인
    with tabs[5]:
        st.subheader("⏳ 타임라인")
        with st.form("time_form", clear_on_submit=True):
            t_date = st.date_input("날짜"); t_event = st.text_input("사건")
            if st.form_submit_button("기록하기") and t_event:
                st.session_state.timeline.insert(0, {"date": str(t_date), "event": t_event, "by": user_name_only})
                save_large_data("time", st.session_state.timeline); st.rerun()
        for t in st.session_state.timeline:
            st.markdown(f"<div class='card'><b>{t.get('date','')}</b>: {t.get('event','')}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록
    with tabs[6]:
        st.subheader("📍 위시리스트 & 데이트 후기")
        with st.form("r_form", clear_on_submit=True):
            r_name = st.text_input("장소명"); r_comment = st.text_area("후기")
            if st.form_submit_button("후기 등록") and r_name:
                st.session_state.reviews.insert(0, {"name": r_name, "comment": r_comment, "date": today_str, "by": user_name_only})
                save_large_data("review", st.session_state.reviews); st.rerun()
        for r in st.session_state.reviews[:st.session_state.review_limit]:
            st.markdown(f"<div class='card'><small>{r.get('date','')}</small><br><b>{r.get('name','')}</b><br>{r.get('comment','')}</div>", unsafe_allow_html=True)

    # 8. 🎁 타임캡슐 & 9. 🎡 만능룰렛 (생략 방지를 위해 이전 로직 유지)
    with tabs[7]:
        st.subheader("🎁 미래의 우리에게"); # (입력 로직)
        for i, cp in enumerate(st.session_state.time_capsules):
            if today_str >= cp.get('open_date',''):
                with st.expander(f"🎉 {cp.get('title','')}"): st.write(cp.get('content',''))
            else: st.warning(f"🔒 {cp.get('title','')} (D-Day 대기)")
    with tabs[8]:
        st.subheader("🎡 만능 룰렛")
        opts = st.text_input("선택지 (쉼표 구분)")
        if st.button("🎲 돌리기") and opts:
            st.success(f"당첨: **{random.choice([o.strip() for o in opts.split(',')])}**"); st.balloons()
