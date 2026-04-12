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
from collections import Counter
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
# 🌤️ 실시간 날씨 API 연동 및 감성 이펙트
# ==========================================
@st.cache_data(ttl=3600)
def get_busan_weather_effect():
    try:
        res = requests.get("https://api.open-meteo.com/v1/forecast?latitude=35.1796&longitude=129.0756&current_weather=true", timeout=1.5)
        if res.status_code == 200:
            code = res.json().get("current_weather", {}).get("weathercode", 0)
            if code in [51, 53, 55, 61, 63, 65, 67, 80, 81, 82]: return "rain"
            elif code in [71, 73, 75, 77, 85, 86]: return "snow"
            elif code in [1, 2, 3]: return "cloud"
            else: return "sun"
        return "sun"
    except: return "sun"

weather_type = get_busan_weather_effect()

def show_weather_effect(w_type):
    if w_type == "rain":
        effect_css = """.effect { color: rgba(173, 216, 230, 0.7); font-size: 1.5em; position: fixed; top: -10%; z-index: 9999; pointer-events: none; animation: fall 1.5s linear infinite; } @keyframes fall { 0% { top: -10%; } 100% { top: 100%; } }"""
        symbol = "💧"
    elif w_type == "snow":
        effect_css = """.effect { color: rgba(255, 255, 255, 0.8); font-size: 1.2em; position: fixed; top: -10%; z-index: 9999; pointer-events: none; animation: fall 5s linear infinite, shake 3s ease-in-out infinite; } @keyframes fall { 0% { top: -10%; } 100% { top: 100%; } } @keyframes shake { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(50px); } }"""
        symbol = "❄️"
    elif w_type == "cloud":
        effect_css = """.effect { color: rgba(200, 200, 200, 0.5); font-size: 3em; position: fixed; top: 10%; z-index: -1; pointer-events: none; animation: drift 30s linear infinite; } @keyframes drift { 0% { left: -20%; } 100% { left: 120%; } }"""
        symbol = "☁️"
    else:
        effect_css = """.effect { color: rgba(255, 223, 0, 0.3); font-size: 4em; position: fixed; top: 5%; left: 80%; z-index: -1; pointer-events: none; animation: pulse 4s ease-in-out infinite; } @keyframes pulse { 0%, 100% { transform: scale(1); opacity: 0.3; } 50% { transform: scale(1.1); opacity: 0.6; } }"""
        symbol = "✨"
    divs = "".join([f'<div class="effect" style="left:{random.randint(5,95)}%; animation-delay:{random.uniform(0, 5):.1f}s;">{symbol}</div>' for _ in range(10 if w_type in ["rain", "snow"] else (3 if w_type == "cloud" else 1))])
    st.markdown(f"<style>{effect_css}</style><div aria-hidden='true'>{divs}</div>", unsafe_allow_html=True)

show_weather_effect(weather_type)

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

# --- 유틸리티 및 드라이브 ---
def extract_youtube_id(url):
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
# 🔐 URL 기반 자동 로그인 프리패스
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
        st.markdown("<h1 style='text-align: center; color: #FF85A2; margin-top: 50px;'>♥ 수기 커플 노트</h1>", unsafe_allow_html=True)
        st.text_input("우리만의 비밀번호", type="password", key="pwd_input", on_change=validate_password)
        return False
    
    if not st.session_state["current_user"]:
        st.markdown("<h2 style='text-align: center; color: #FF85A2; margin-top: 50px;'>누가 오셨나요? 👀</h2>", unsafe_allow_html=True)
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
        st.session_state.photo_cart = [] # 🛒 갤럭사용 장바구니 초기화
        
    # 테마 설정
    current_hour = now_kst.hour
    is_night = current_hour >= 19 or current_hour <= 6
    bg_color = "#1A1A2E" if is_night else ("#FFF5F7" if user_name_only == "수기" else "#E3F2FD")
    accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"
    text_color = "#E0E0E0" if is_night else "#333333"

    # ==========================================
    # 🌱 다마고치 사랑나무 & 배지 (사이드바)
    # ==========================================
    total_act = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    level, tree_icon = ("풍성한 나무", "🍎") if total_act >= 70 else (("아기 나무", "🌳") if total_act >= 30 else (("새싹", "🌿") if total_act >= 10 else ("씨앗", "🌱")))
    
    badges = []
    if len(st.session_state.memo_history) >= 10: badges.append("📝 편지왕")
    if len(st.session_state.reviews) >= 5: badges.append("🍽️ 미슐랭")
    badge_html = "".join([f"<span style='background:rgba(255,255,255,0.2); padding:2px 8px; border-radius:10px; font-size:0.8em; margin:2px;'>{b}</span>" for b in badges])

    with st.sidebar:
        st.markdown(f"""<div style="background:rgba(255,255,255,0.1); padding:15px; border-radius:15px; border:2px solid {accent_color}; text-align:center;">
                <h1 style="margin:0;">{tree_icon}</h1><h4>사랑나무: {level}</h4>
                <p style="font-size:0.8em; opacity:0.8;">포인트: {total_act} XP</p><div>{badge_html}</div></div>""", unsafe_allow_html=True)
        
        start_date = datetime.date(2026, 1, 1) 
        st.metric(label="우리의 D-Day (한국식 교정)", value=f"D + {(now_kst.date() - start_date).days + 1}일")
        if st.button("로그아웃 🚪"): st.query_params.clear(); st.session_state.clear(); st.rerun()

    # --- CSS 주입 ---
    st.markdown(f"""
        <div class="custom-bg-layer" style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:{bg_color}; z-index:-99999; pointer-events:none;"></div>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, [data-testid="stMetricValue"], .stMarkdown, .stText {{ font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important; }}
        .stApp {{ background: transparent !important; }}
        .card {{ background: rgba(255,255,255,0.1); padding:15px; border-radius:15px; margin-bottom:10px; border-left:5px solid {accent_color}; }}
        .user-boy {{ border-left:5px solid #4B89FF; background:rgba(75,137,255,0.1) !important; }}
        .user-girl {{ border-right:5px solid #FF85A2; text-align:right; background:rgba(255,133,162,0.1) !important; }}
        </style>
    """, unsafe_allow_html=True)

    # ==========================================
    # 🚨 동선 최적화 9개 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # 1. 💕 데이트 (QnA 80제 + 기분 차트 + 타임머신)
    with tabs[0]:
        # 🕰️ [v5.5 신규] 감성 타임머신
        past_records = [m for m in st.session_state.memo_history if m['date'].endswith(now_kst.strftime("-%m-%d")) and m['date'] != today_str]
        if past_records:
            st.warning(f"🕰️ **과거에서 온 추억:** {len(past_records)}년 전 오늘, 이런 마음을 남겼었네요!")
            with st.expander("추억 열어보기"):
                for p in past_records: st.info(f"[{p['date']}] {p['user']}: {p['content']}")

        # QnA 80제
        qna_list = ["첫인상은?", "반했던 순간?", "가고 싶은 곳?", "가장 설레는 스킨십?"] # (80개 리스트 생략/이전 리스트 동일 적용)
        q_idx = now_kst.toordinal() % 80
        q_key = f"qna_{q_idx}"
        st.session_state.qna_data.setdefault(q_key, {"hodl": "", "sugi": ""})
        with st.expander(f"💌 오늘의 문답 (No.{q_idx + 1})", expanded=True):
            st.subheader(f"Q: {qna_list[q_idx % len(qna_list)]}")
            ans_b = st.session_state.qna_data[q_key]["hodl"]; ans_g = st.session_state.qna_data[q_key]["sugi"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("👦 **남친**")
                if user_name_only == "수기남자친구": n_ans_b = st.text_area("작성", value=ans_b, key="q_b")
                else: st.info(ans_b if (ans_b and ans_g) else "🔒 작성 대기 중")
            with c2:
                st.markdown("👩 **수기**")
                if user_name_only == "수기": n_ans_g = st.text_area("작성", value=ans_g, key="q_g")
                else: st.info(ans_g if (ans_b and ans_g) else "🔒 작성 대기 중")
            if st.button("답변 저장 💾"):
                if user_name_only == "수기남자친구": st.session_state.qna_data[q_key]["hodl"] = n_ans_b
                else: st.session_state.qna_data[q_key]["sugi"] = n_ans_g
                save_data_to_cell("qna", st.session_state.qna_data); st.rerun()

        st.divider()
        st.subheader("📈 기분 차트")
        if len(st.session_state.mood_history) >= 2:
            df = pd.DataFrame(st.session_state.mood_history).set_index('date')
            st.line_chart(df, color=["#4B89FF", "#FF85A2"])

    # 2. 💌 쪽지함 (더 보기 추가)
    with tabs[1]:
        st.subheader("💌 오늘의 한마디")
        content = st.text_area("마음 전하기", key="memo_in")
        if st.button("보내기 ✈️") and content:
            st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
            save_large_data("memo", st.session_state.memo_history); st.rerun()
        for m in st.session_state.memo_history[:st.session_state.memo_limit]:
            cls = "user-boy" if "남자친구" in m['user'] else "user-girl"
            st.markdown(f"<div class='card {cls}'><b>{m['user']}</b><br>{m['content']}<br><small>{m['date']}</small></div>", unsafe_allow_html=True)
        if len(st.session_state.memo_history) > st.session_state.memo_limit:
            if st.button("더 보기 ⬇️"): st.session_state.memo_limit += 10; st.rerun()

    # 3. 🌸 텔레파시 (수동 격발 장치)
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시")
        questions = [["평생 여름", "평생 겨울"], ["찍먹", "부먹"], ["강아지", "고양이"]] # (100개 동일)
        t_idx = now_kst.toordinal() % 100
        q_pair = questions[t_idx % len(questions)]
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        ans = st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"]
        c1, c2 = st.columns(2)
        if c1.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[0]
            save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        if c2.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[1]
            save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        
        b_ans = st.session_state.tele_data[today_str]["hodl"]; g_ans = st.session_state.tele_data[today_str]["sugi"]
        if b_ans and g_ans:
            if st.button("🎁 결과 확인하기 (풍선 팡!)", use_container_width=True):
                if b_ans == g_ans: st.balloons(); st.success(f"찌찌뽕! **[{b_ans}]** ❤️")
                else: st.info(f"남친: {b_ans} / 수기: {g_ans}")
        else: st.warning("🔒 상대방의 선택을 기다리고 있어요!")

    # 4. 🎵 주크박스 (듀얼 채널)
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        with st.form("dj_dual"):
            link = st.text_input("오늘의 추천곡 (유튜브)")
            if st.form_submit_button("신청") and link:
                st.session_state.jukebox_data["hodl" if user_name_only == "수기남자친구" else "sugi"] = link
                save_data_to_cell("jukebox", st.session_state.jukebox_data); st.rerun()
        
        col_b, col_g = st.columns(2)
        with col_b:
            st.info("👦 남친의 Pick")
            b_id = extract_youtube_id(st.session_state.jukebox_data.get("hodl", ""))
            if b_id: st.video(f"https://www.youtube.com/watch?v={b_id}")
        with col_g:
            st.success("👧 수기의 Pick")
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.video(f"https://www.youtube.com/watch?v={g_id}")

    # 5. 📸 추억저장소 (🛒 갤럭시 장바구니 시스템)
    with tabs[4]:
        st.subheader("📸 추억 보관함 (장바구니 모드)")
        st.info("💡 갤럭시는 '사진 담기'로 여러 장을 모은 후 한 번에 전송하세요!")
        
        with st.expander("🛒 내 장바구니 (현재 {}장)".format(len(st.session_state.photo_cart))):
            new_f = st.file_uploader("사진 고르기", type=['jpg','png','jpeg'], accept_multiple_files=False)
            if st.button("장바구니에 담기 ➕") and new_f:
                st.session_state.photo_cart.append(new_f.getvalue())
                st.toast("장바구니에 쏙! 🛒"); st.rerun()
            
            if st.session_state.photo_cart:
                if st.button("☁️ 드라이브로 최종 전송! ({})".format(len(st.session_state.photo_cart))):
                    with st.spinner("압축 및 전송 중..."):
                        for f_bytes in st.session_state.photo_cart:
                            img = Image.open(io.BytesIO(f_bytes))
                            img = ImageOps.exif_transpose(img)
                            img.thumbnail((1920, 1920)); out = io.BytesIO()
                            img.save(out, format="JPEG", quality=80)
                            upload_photo_to_drive(out.getvalue(), f"{today_str}_{random.randint(1000,9999)}.jpg", "image/jpeg")
                        st.session_state.photo_cart = []; st.success("전송 완료! 🚀"); st.rerun()
                if st.button("장바구니 비우기 🗑️"): st.session_state.photo_cart = []; st.rerun()

        # 갤러리 렌더링 (이전과 동일)
        st.divider()
        photos = load_photos_from_drive(st.session_state.photo_limit)
        for p in photos:
            try: st.image(get_image_bytes(p['id']), caption=p['name'], use_container_width=True)
            except: pass

    # 6. ⏳ 타임라인 (더 보기)
    with tabs[5]:
        st.subheader("⏳ 타임라인")
        # (입력 로직 동일)
        for t in st.session_state.timeline: st.markdown(f"<div class='card'><b>{t['date']}</b>: {t['event']}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록 (월간 백서 & 단어 구름)
    with tabs[6]:
        st.subheader("📊 월간 수기 백서")
        this_month = now_kst.strftime("%Y-%m")
        m_rev = [r for r in st.session_state.reviews if r['date'].startswith(this_month)]
        m_memo = [m for m in st.session_state.memo_history if m['date'].startswith(this_month)]
        
        st.write(f"📅 **{now_kst.month}월 결산 리포트**")
        c1, c2, c3 = st.columns(3)
        c1.metric("데이트", f"{len(m_rev)}회")
        c2.metric("주고받은 쪽지", f"{len(m_memo)}개")
        
        # 기억의 파편 (주요 단어)
        all_text = " ".join([m['content'] for m in m_memo] + [r['comment'] for r in m_rev])
        words = [w for w in re.findall(r'[가-힣]{2,}', all_text) if len(w) > 1]
        top_words = Counter(words).most_common(5)
        if top_words:
            st.write("🏷️ **우리가 이번 달 많이 쓴 단어:**")
            st.write(", ".join([f"#{w[0]}" for w in top_words]))

    # 8. 🎁 타임캡슐 & 9. 🎡 만능룰렛 (이전 로직 유지)
    with tabs[7]: st.subheader("🎁 타임캡슐"); # (로직 생략)
    with tabs[8]: st.subheader("🎡 만능 룰렛"); # (로직 생략)
