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
# 🌤️ 실시간 날씨 API 연동 및 고급 CSS 감성 이펙트 (이모티콘 삭제)
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
        # 빗줄기 CSS
        effect_css = """
        .drop { position: fixed; background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(150, 200, 255, 0.5)); 
                width: 2px; height: 10vh; top: -10vh; z-index: 9999; pointer-events: none; animation: fall 0.7s linear infinite; }
        @keyframes fall { to { transform: translateY(110vh); } }
        """
        divs = "".join([f"<div class='drop' style='left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,1):.2f}s;'></div>" for _ in range(30)])
        st.markdown(f"<style>{effect_css}</style><div aria-hidden='true'>{divs}</div>", unsafe_allow_html=True)
    
    elif w_type == "snow":
        # 눈송이 CSS
        effect_css = """
        .flake { position: fixed; background: rgba(255, 255, 255, 0.8); border-radius: 50%; box-shadow: 0 0 5px rgba(255,255,255,0.5);
                 top: -10vh; z-index: 9999; pointer-events: none; animation: snow_fall 4s linear infinite, snow_shake 3s ease-in-out infinite alternate; }
        @keyframes snow_fall { to { transform: translateY(110vh); } }
        @keyframes snow_shake { from { transform: translateX(-15px); } to { transform: translateX(15px); } }
        """
        divs = "".join([f"<div class='flake' style='left:{random.randint(0,100)}%; animation-delay:{random.uniform(0,4):.2f}s; width:{random.randint(4,8)}px; height:{random.randint(4,8)}px;'></div>" for _ in range(30)])
        st.markdown(f"<style>{effect_css}</style><div aria-hidden='true'>{divs}</div>", unsafe_allow_html=True)
    
    elif w_type == "cloud":
        # 흐린 날 은은한 오버레이
        st.markdown("""<style>.cloud-layer { position: fixed; top:0; left:0; width:100vw; height:100vh; background: rgba(200, 210, 220, 0.15); z-index:-99998; pointer-events:none; }</style><div class="cloud-layer"></div>""", unsafe_allow_html=True)
    
    else:
        # 맑은 날 햇빛 그라데이션
        st.markdown("""<style>.sun-layer { position: fixed; top:0; left:0; width:100vw; height:100vh; background: radial-gradient(circle at top right, rgba(255, 220, 100, 0.12), transparent 60%); z-index:-99998; pointer-events:none; }</style><div class="sun-layer"></div>""", unsafe_allow_html=True)

show_weather_effect(weather_type)

# --- 🍎 아이폰(iOS) 전용 홈 화면 아이콘 강제 주입 ---
components.html("""
    <script>
        const link = window.parent.document.createElement('link');
        link.rel = 'apple-touch-icon';
        link.href = 'https://cdn-icons-png.flaticon.com/512/833/833472.png'; 
        window.parent.document.head.appendChild(link);
    </script>
""", height=0, width=0)

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

# --- 🚨 [버그 픽스] 유튜브 URL 추출기 방어막 (None 에러 차단) ---
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
        svc = get_drive_service() 
        svc.files().delete(fileId=file_id).execute()
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

    if "toast_msg" not in st.session_state: st.session_state.toast_msg = ""
    if st.session_state.toast_msg:
        st.toast(st.session_state.toast_msg)
        st.session_state.toast_msg = ""

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
            st.session_state.current_mood_date = today_str
            save_main_data()

    # 🎨 [디자인 완벽 롤백] 야간 모드 영구 삭제. 화사한 파스텔 배경 고정
    bg_color = "#FFF5F7" if user_name_only == "수기" else "#E3F2FD"
    accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"
    text_color = "#333333" 
    
    # ==========================================
    # 🌱 다마고치 사랑나무 & 배지 (사이드바)
    # ==========================================
    total_act = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    level, tree_icon = ("풍성한 나무", "🍎") if total_act >= 70 else (("아기 나무", "🌳") if total_act >= 30 else (("새싹", "🌿") if total_act >= 10 else ("씨앗", "🌱")))
    
    badges = []
    if len(st.session_state.memo_history) >= 10: badges.append("📝 편지왕")
    if len(st.session_state.reviews) >= 5: badges.append("🍽️ 미슐랭")
    if len(st.session_state.date_schedules) >= 5: badges.append("🗓️ 파워J")
    badge_html = "".join([f"<span style='background:rgba(255,255,255,0.4); padding:4px 8px; border-radius:10px; font-size:0.8em; margin:2px; display:inline-block;'>{b}</span>" for b in badges])

    with st.sidebar:
        st.markdown(f"""<div style="background:rgba(255,255,255,0.4); padding:15px; border-radius:15px; border:2px solid {accent_color}; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                <h1 style="margin:0;">{tree_icon}</h1><h4 style="color:{text_color}; margin:5px 0;">사랑나무: {level}</h4>
                <p style="font-size:0.8em; color:gray; margin:0;">포인트: {total_act} XP</p><div style="margin-top:10px;">{badge_html}</div></div>""", unsafe_allow_html=True)
        
        start_date = datetime.date(2026, 1, 1) 
        days_passed = (now_kst.date() - start_date).days + 1 
        st.markdown(f"### 🌸 우리의 D-Day")
        st.metric(label=f"연애 시작일: {start_date}", value=f"D + {days_passed}일")
        
        st.divider()
        st.markdown("### 🗓️ 오늘 데이트 일정")
        today_plans = [p for p in st.session_state.date_schedules if p['date'] == today_str]
        if today_plans:
            for p in today_plans: st.write(f"✨ {p['plan']}")
        else: st.caption("오늘 등록된 일정이 없어요!")
            
        st.divider()
        st.markdown("### 📜 우리의 약속")
        for i, p in enumerate(st.session_state.promises):
            p_text = p['text'] if isinstance(p, dict) else p
            st.write(f"{i+1}. {p_text}")
            
        with st.expander("약속 추가하기 ✍️"):
            new_promise = st.text_input("새로운 약속", key="new_promise_input")
            if st.button("추가") and new_promise:
                st.session_state.promises.append({"text": new_promise, "by": user_name_only})
                save_main_data()
                st.session_state.toast_msg = "새로운 약속이 추가되었습니다! 🤝"; st.rerun()
            
        st.divider()
        if st.button("로그아웃 🚪"): st.query_params.clear(); st.session_state.clear(); st.rerun()

    # --- CSS 주입 (가독성 및 감성 테마 100% 복원) ---
    st.markdown(f"""
        <div class="custom-bg-layer" style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:{bg_color}; z-index:-99999; pointer-events:none;"></div>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, p, h1, h2, h3, h4, h5, h6, label, button, input, textarea, select, div[data-testid="stMetricValue"], .stMarkdown, .stText {{
            font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important;
        }}
        .stApp {{ background: transparent !important; }}
        input, textarea, select, div.stTextInput > div > div > input, div.stTextArea > div > div > textarea {{
            background-color: rgba(255,255,255,0.9) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important;
        }}
        div[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ 
            background-color: rgba(255,255,255,0.6) !important; border-right: 1px solid rgba(0,0,0,0.05) !important;
        }}
        .card, [data-testid="stExpander"] {{ 
            background: rgba(255,255,255,0.4) !important; backdrop-filter: blur(10px); border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.5) !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
        }}
        .user-boy {{ border-left:5px solid #4B89FF !important; background:rgba(75,137,255,0.15) !important; text-align: left; }}
        .user-girl {{ border-right:5px solid #FF85A2 !important; background:rgba(255,133,162,0.15) !important; text-align: right; border-left: none !important; }}
        .review-comment {{ background-color: rgba(255,255,255,0.5); padding: 8px 12px; border-radius: 8px; margin-top: 5px; font-size: 0.9em; }}
        .time-text {{ font-size: 0.8rem; color: #666666 !important; }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: rgba(255,255,255,0.7) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        [data-testid="stMetricValue"] {{ color: {accent_color} !important; }}
        </style>
    """, unsafe_allow_html=True)

    col_h1, col_h2 = st.columns([0.85, 0.15])
    col_h1.markdown(f"<h2 style='color: #FF85A2; margin:0;'>♥ 수기 커플 노트</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄 새로고침"): st.session_state.clear(); st.rerun()

    st.success(f"📢 {st.session_state.notice}")
    with st.expander("✏️ 공지사항 수정"):
        new_notice = st.text_input("새로운 공지 내용을 적어주세요.", value=st.session_state.notice)
        if st.button("공지 변경 확정 💾"):
            st.session_state.notice = new_notice; save_main_data()
            st.session_state.toast_msg = "공지사항이 성공적으로 변경되었습니다! 📢"; st.rerun()

    # ==========================================
    # 🚨 탭 순서 동선 최적화
    # 0:데이트 ➔ 1:쪽지함 ➔ 2:텔레파시 ➔ 3:주크박스 ➔ 4:추억저장소 ➔ 5:타임라인 ➔ 6:장소/기록 ➔ 7:타임캡슐 ➔ 8:만능룰렛
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # ------------------
    # 1. 💕 데이트
    # ------------------
    with tabs[0]:
        past_records = [m for m in st.session_state.memo_history if m.get('date', '').endswith(now_kst.strftime("-%m-%d")) and m.get('date') != today_str]
        if past_records:
            st.warning(f"🕰️ **과거에서 온 추억:** 예전 오늘, 이런 마음을 남겼었네요!")
            with st.expander("추억 열어보기"):
                for p in past_records: st.info(f"[{p['date']}] {p['user']}: {p['content']}")

        qna_list = [
            "1. 우리가 처음 만났던 날, 서로의 첫인상은 어땠어?", "2. 서로에게 가장 반했던 결정적인 순간은 언제야?", "3. 내가 가장 사랑스러워 보일 때는 언제야?", "4. 나의 잠버릇이나 술버릇 중 가장 귀여운 것은?", "5. 지금 당장 훌쩍 떠난다면 같이 가고 싶은 여행지는?",
            "6. 지금까지 우리의 가장 완벽했던 데이트는 언제였어?", "7. 우리의 첫 키스(뽀뽀) 때 어떤 기분이었어?", "8. 내가 해준 음식 중 최고의 메뉴는?", "9. 서로의 연락처 저장명과 그렇게 정한 이유는 뭐야?", "10. 화났을 때 내 기분을 100% 풀어주는 최고의 방법은?",
            "11. 나에게 들었던 가장 감동적인 말은 무엇이었어?", "12. 꼭 같이 배워보고 싶은 취미나 운동이 있다면?", "13. 나의 어떤 점을 가장 닮고 싶어?", "14. 지금까지 만나면서 나에게 가장 고마웠던 순간은?", "15. 싸웠을 때 우리의 암묵적인 룰을 하나 정한다면?",
            "16. 나를 생각하면 가장 먼저 떠오르는 노래는?", "17. 내가 가장 섹시해(멋있어/예뻐) 보일 때는 언제야?", "18. 서로에게 주고 싶은 가장 특별하고 의미 있는 선물은?", "19. 우리의 첫 데이트 때, 겉으론 안 그랬지만 속마음은 어땠어?", "20. 나를 동물로 표현한다면 어떤 동물이고 이유는 뭐야?",
            "21. 우리의 연애를 영화 장르로 따지면 어떤 장르일까?", "22. 하루 동안 서로 몸이 바뀐다면 가장 해보고 싶은 것은?", "23. 서로의 가족에게 해주고 싶은 작은 이벤트가 있다면?", "24. 폰에 있는 우리의 커플 사진 중 가장 좋아하는 사진은?", "25. 나를 만나고 나서 긍정적으로 변한 점이 있다면?",
            "26. 1년 뒤 오늘, 우리는 어떤 모습으로 무엇을 하고 있을까?", "27. 10년 뒤 우리는 서로에게 어떤 사람일까?", "28. 이번 주말, 나랑 하루 종일 방 안에서만 놀기 vs 하루 종일 밖에서 놀기", "29. 서로에게 절대 변치 말자고 엄지 걸고 약속하고 싶은 것 1가지는?", "30. 지금 당장 상대방을 꽉 안아주면서 해주고 싶은 말은?",
            "31. 상대방의 외모 중 가장 좋아하는 부분은?", "32. 내가 가장 좋아하는 상대방의 향기나 냄새는?", "33. 로또 1등에 당첨된다면 나한테 뭐해줄 거야?", "34. 내가 해준 스킨십 중 가장 설레는 스킨십은?", "35. 상대방의 핸드폰에 내 지문을 등록해 놓을 수 있다 vs 없다",
            "36. 나중에 결혼을 한다면 결혼식은 어떻게 하고 싶어?", "37. 만약 무인도에 간다면 나 말고 꼭 챙겨갈 3가지는?", "38. 우리의 연애 스토리를 책으로 쓴다면 첫 문장은?", "39. 밤새 통화했던 날 중 가장 기억에 남는 대화는?", "40. 나로 인해 새롭게 알게 된 취향이나 습관이 있다면?",
            "41. 내가 가장 멋있어 보이는 나의 일하는(공부하는) 모습은?", "42. 상대방의 단점 중 '이것만큼은 내가 평생 안아줄게' 하는 것은?", "43. 우리 둘 사이에서 가장 잘 맞는 음식 코드는?", "44. 가장 기억에 남는 깜짝 이벤트나 서프라이즈는?", "45. '이 사람은 진짜 나를 사랑하는구나'라고 느꼈던 순간은?",
            "46. 우리가 나중에 늙어서 할머니, 할아버지가 되면 어떤 모습일까?", "47. 나랑 같이 밤새도록 보고 싶은 영화나 드라마 시리즈는?", "48. 길을 걷다 우연히 마주친다면 어떤 표정을 지을까?", "49. 내 목소리를 들으면 가장 먼저 드는 감정이나 기분은?", "50. 만약 내가 10살 어려진다면 나한테 해주고 싶은 말은?",
            "51. 서로의 매력을 한 단어로 표현한다면?", "52. 가장 좋아하는 스킨십 타이밍은 언제야?", "53. 만약 내가 강아지/고양이로 변한다면 어떻게 키워줄 거야?", "54. 나랑 같이 꼭 가보고 싶은 유명한 맛집이 있다면?", "55. 상대방의 옷 스타일 중 가장 마음에 드는 코디는?",
            "56. 우리가 처음 손잡았던 순간의 기억은?", "57. 나에게 어울리는 색깔은 무슨 색이라고 생각해?", "58. 내가 화났을 때 나를 웃게 만드는 필살기가 있다면?", "59. 같이 살아본다면 가장 기대되는 일상 모습은?", "60. 나를 떠올리면 생각나는 계절은 언제야?",
            "61. 지금까지 내가 해준 칭찬 중 가장 기분 좋았던 것은?", "62. 나랑 꼭 같이 해보고 싶은 액티비티나 익스트림 스포츠는?", "63. 만약 하루 투명인간이 된다면 나한테 어떤 장난을 칠 거야?", "64. 나의 연락을 기다리며 가장 설렜던 때는 언제야?", "65. 나랑 같이 듣고 싶은 비 오는 날의 노래는?",
            "66. 상대방의 잠자는 모습을 처음 봤을 때 어떤 생각이 들었어?", "67. 나의 콤플렉스 중 네가 가장 사랑해 줄 수 있는 것은?", "68. 나랑 같이 장을 본다면 카트에 가장 먼저 담을 물건은?", "69. 우리가 만약 같은 직장에서 일한다면 어떤 모습일까?", "70. 상대방의 삐진 모습을 가장 빨리 풀어줄 수 있는 음식은?",
            "71. 나랑 같이 해보고 싶은 커플 챌린지가 있다면?", "72. 내 핸드폰 배경화면으로 해놓고 싶은 내 사진은?", "73. 만약 내가 기억 상실증에 걸린다면 나한테 어떻게 다가올 거야?", "74. 나랑 같이 만들어보고 싶은 커플 아이템(반지, 향수 등)은?", "75. 상대방의 요리 실력을 10점 만점으로 평가한다면?",
            "76. 나랑 같이 꼭 타보고 싶은 놀이기구는?", "77. 나의 어떤 점이 가장 든든하고 의지가 돼?", "78. 나랑 같이 꼭 해보고 싶은 봉사활동이나 의미 있는 일은?", "79. 만약 내가 연예인이 된다면 어떤 반응을 보일 거야?", "80. 지금 이 순간, 나한테 가장 해주고 싶은 짧은 한마디는?"
        ]
        q_idx = now_kst.toordinal() % 80
        q_key = f"qna_{q_idx}"
        st.session_state.qna_data.setdefault(q_key, {"hodl": "", "sugi": ""})
        
        with st.expander(f"💌 오늘의 문답 (No.{q_idx + 1})", expanded=True):
            st.subheader(qna_list[q_idx])
            ans_b = st.session_state.qna_data[q_key]["hodl"]; ans_g = st.session_state.qna_data[q_key]["sugi"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("👦 **남친**")
                if user_name_only == "수기남자친구": n_ans_b = st.text_area("작성", value=ans_b, key="q_b", label_visibility="collapsed")
                else: st.info(ans_b if (ans_b and ans_g) else "🔒 작성 대기 중")
            with c2:
                st.markdown("👩 **수기**")
                if user_name_only == "수기": n_ans_g = st.text_area("작성", value=ans_g, key="q_g", label_visibility="collapsed")
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
        else: st.caption("기분 데이터가 2일 이상 쌓이면 예쁜 그래프가 나타나요! 📈")

        st.divider()
        st.subheader("🗓️ 우리의 데이트 일정")
        with st.form("schedule_form", clear_on_submit=True):
            s_date = st.date_input("데이트 날짜")
            s_plan = st.text_input("무엇을 할까요?")
            if st.form_submit_button("일정 추가") and s_plan:
                st.session_state.date_schedules.append({"date": str(s_date), "plan": s_plan, "by": user_name_only})
                st.session_state.date_schedules.sort(key=lambda x: x['date'])
                save_large_data("date", st.session_state.date_schedules); st.rerun()
                
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 [{s['date']}] {s['plan']}"):
                edit_s = st.text_input("일정 수정", value=s['plan'], key=f"edit_s_{i}")
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("수정 완료", key=f"btn_s_edit_{i}"):
                    st.session_state.date_schedules[i]['plan'] = edit_s; save_large_data("date", st.session_state.date_schedules); st.rerun()
                if col_s2.button("삭제하기 🗑️", key=f"btn_s_del_{i}"):
                    st.session_state.date_schedules.pop(i); save_large_data("date", st.session_state.date_schedules); st.rerun()

        st.divider()
        st.subheader("🎭 오늘 우리의 기분")
        mood_options = ["😢", "☁️", "🙂", "🥰", "🔥"]
        mood_desc = {"😢": "피곤함/우울", "☁️": "그저그럼", "🙂": "보통/평온", "🥰": "기분좋음", "🔥": "최고/열정!"}
        
        my_mood = st.select_slider(f"{user_name_only}의 기분 선택", options=mood_options, value=st.session_state.moods.get(user_name_only, "🙂"))
        st.write(f"👉 선택한 기분: **{mood_desc.get(my_mood, '보통/평온')}**")
        
        if st.button("기분 업데이트"):
            st.session_state.moods[user_name_only] = my_mood
            today_record = next((item for item in st.session_state.mood_history if item["date"] == today_str), None)
            mood_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
            if today_record: today_record[f"{user_name_only}_score"] = mood_score[my_mood]
            else:
                new_record = {"date": today_str, "수기남자친구_score": mood_score[st.session_state.moods.get("수기남자친구", "🙂")], "수기_score": mood_score[st.session_state.moods.get("수기", "🙂")]}
                new_record[f"{user_name_only}_score"] = mood_score[my_mood]
                st.session_state.mood_history.append(new_record)
            save_main_data(); st.rerun()

        st.write(f"👦 수기남자친구: {st.session_state.moods.get('수기남자친구', '🙂')} ({mood_desc.get(st.session_state.moods.get('수기남자친구', '🙂'), '보통')})")
        st.write(f"👧 수기: {st.session_state.moods.get('수기', '🙂')} ({mood_desc.get(st.session_state.moods.get('수기', '🙂'), '보통')})")

    # 2. 💌 쪽지함
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

    # 3. 🌸 텔레파시 (수동 격발)
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시")
        questions = [
            ["평생 여름", "평생 겨울"], ["카레맛 똥", "똥맛 카레"], ["찍먹", "부먹"], ["강아지", "고양이"],
            ["연락 5시간 안됨", "친구(이성)랑 단둘이 밥"], ["월 200 백수", "월 1000 주100시간 근무"], ["평생 씻기 안함", "평생 이빨 안닦기"], ["초능력: 투명인간", "초능력: 하늘날기"],
            ["내가 좋아하는 사람", "나를 좋아하는 사람"], ["데이트: 방구석 넷플릭스", "데이트: 하루종일 아웃도어"], ["평생 고기 안먹기", "평생 밀가루 안먹기"], ["과거로 돌아가기", "미래로 가기"],
            ["평생 샤워 물 온도 고정: 찬물", "뜨거운 물"], ["다시 태어나면: 엄청난 미남/미녀", "엄청난 천재"], ["결혼식: 하와이 스몰웨딩", "초호화 호텔 예식"], ["평생 한 음식만 먹어야 한다면: 라면", "치킨"],
            ["귀신이 나오는 흉가에서 1박", "무인도에서 1박"], ["연인의 흑역사 사진 보기", "내 흑역사 사진 보여주기"], ["환승이별 당하기", "잠수이별 당하기"], ["내 과거를 볼 수 있는 연인", "내 미래를 볼 수 있는 연인"],
            ["평생 에어컨 없이 살기", "평생 보일러 없이 살기"], ["바퀴벌레 먹고 10억 받기", "안 먹고 안 받기"], ["모든 기억을 잃은 연인", "나에 대한 기억만 잃은 연인"], ["로또 1등 당첨금 100% 내가 갖기", "연인과 50% 나누기"],
            ["평생 스마트폰 없이 살기", "평생 컴퓨터 없이 살기"], ["연인에게 내 폰 1주일 맡기기", "연인 폰 1주일 내가 보기"], ["애인과 싸웠을 때: 당장 풀기", "생각할 시간 갖기"], ["애인의 이성 친구: 단둘이 커피", "단둘이 술"],
            ["10년 전으로 돌아가기", "10년 후로 가기"], ["평생 낮만 있는 세상", "평생 밤만 있는 세상"], ["애인이 빚 10억", "내가 빚 10억"], ["평생 매운 것만 먹기", "평생 단 것만 먹기"],
            ["돈은 많지만 바쁜 애인", "돈은 없지만 항상 같이 있는 애인"], ["평생 씻지 않는 애인", "평생 양치 안 하는 애인"], ["내가 더 사랑하는 연애", "내가 더 사랑받는 연애"], ["모든 사람이 내 생각 읽기", "내가 모든 사람 생각 읽기"],
            ["애인 폰에 내 지문 등록: 필수", "선택"], ["기념일에: 비싼 선물", "감동적인 편지와 정성"], ["평생 한 가지 음료만: 콜라", "커피"], ["애인과 영혼이 바뀐다면: 하루 종일 집", "하루 종일 밖"],
            ["평생 한 장르만 본다면: 로맨스", "액션/스릴러"], ["애인이랑 꼭 가고 싶은 곳: 유럽", "휴양지(발리)"], ["애인이 화났을 때: 애교로 풀기", "논리적으로 대화하기"], ["애인의 치명적인 단점: 방귀 냄새 최악", "코골이 최악"],
            ["평생 한 운동만 한다면: 수영", "헬스"], ["애인과 꼭 해보고 싶은 동거: 찬성", "반대"], ["결혼 후 통장 관리: 각자 알아서", "한 사람이 전담"], ["자녀 계획: 딩크족", "최소 2명 이상"],
            ["평생 한 가지 취미만: 게임", "독서"], ["애인과 싸웠을 때: 져주는 편", "이겨야 하는 편"], ["애인에게 듣고 싶은 말: '사랑해'", "'고마워'"], ["애인의 과거: 다 알고 싶다", "전혀 알고 싶지 않다"],
            ["평생 한 가지 계절만: 봄", "가을"], ["애인과 꼭 해보고 싶은 데이트: 놀이공원 교복 데이트", "호캉스"], ["애인의 스킨십: 공공장소 가능", "절대 불가"], ["애인의 주사: 잠자기", "울기/진상"],
            ["평생 한 가지 색깔 옷만: 검정", "하양"], ["애인과 꼭 해보고 싶은 커플템: 반지", "커플티"], ["애인의 연락: 10분에 한 번", "하루에 한 번"], ["애인의 거짓말: 선의의 거짓말은 용서", "절대 용서 불가"],
            ["평생 한 가지 음식만: 떡볶이", "초밥"], ["애인과 꼭 해보고 싶은 여행: 배낭여행", "호캉스"], ["애인의 남사친/여사친: 1명도 용납 불가", "선만 지키면 가능"], ["애인의 덕질: 아이돌 덕질", "애니메이션 덕질"],
            ["평생 한 가지 주류만: 소주", "맥주"], ["애인과 꼭 해보고 싶은 취미: 등산", "베이킹"], ["애인의 식성: 극단적인 편식", "뭐든 잘 먹음"], ["애인의 소비 습관: 짠돌이/짠순이", "욜로(YOLO)"],
            ["평생 한 가지 매체만: 유튜브", "넷플릭스"], ["애인과 꼭 해보고 싶은 게임: 협동 게임", "경쟁 게임"], ["애인의 헤어스타일: 장발", "단발"], ["애인의 체형: 마른 체형", "근육질 체형"],
            ["평생 한 가지 야식만: 치킨", "족발"], ["애인과 꼭 해보고 싶은 알바: 카페 알바", "단기 알바"], ["애인의 잠버릇: 이갈기", "잠꼬대"], ["애인의 운전 스타일: 난폭 운전", "초보 운전"],
            ["평생 한 가지 향수만: 비누향", "머스크향"], ["애인과 꼭 해보고 싶은 스포츠: 테니스", "볼링"], ["애인의 패션: 스트릿 패션", "수트/오피스룩"], ["애인의 타투: 손목에 작은 타투", "등에 큰 타투"],
            ["평생 한 가지 간식만: 아이스크림", "과자"], ["애인과 꼭 해보고 싶은 챌린지: 댄스 챌린지", "먹방 챌린지"], ["애인의 SNS: 비공개 계정", "인플루언서"], ["애인의 MBTI: 극 E", "극 I"],
            ["평생 한 가지 과일만: 수박", "딸기"], ["애인과 꼭 해보고 싶은 팝업스토어: 캐릭터 팝업", "패션 팝업"], ["애인의 요리 실력: 셰프급", "라면도 못 끓임"], ["애인의 정리 정돈: 결벽증", "돼지우리"],
            ["평생 한 가지 빵만: 크루아상", "소금빵"], ["애인과 꼭 해보고 싶은 클래스: 원데이 클래스", "장기 클래스"], ["애인의 정치 성향: 나와 완전 반대", "정치에 관심 없음"], ["애인의 종교: 나와 완전 반대", "무교"],
            ["평생 한 가지 면요리만: 짜장면", "파스타"], ["애인과 꼭 해보고 싶은 전시회: 미술 전시회", "미디어 아트 전시회"], ["애인의 언어 습관: 욕설", "줄임말"], ["애인의 연락처: 내 이름 저장 안 함", "내 이름 이상하게 저장함"],
            ["평생 한 가지 고기만: 돼지고기", "소고기"], ["애인과 꼭 해보고 싶은 축제: 뮤직 페스티벌", "맥주 축제"], ["애인의 애완동물: 뱀/도마뱀", "거미"], ["애인의 특기: 노래", "춤"]
        ]
        t_idx = now_kst.toordinal() % len(questions)
        q_pair = questions[t_idx]
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
        else: 
            if b_ans: st.warning("🔒 남친님은 선택 완료! 수기님 대기 중 ⏳")
            elif g_ans: st.warning("🔒 수기님은 선택 완료! 남친님 대기 중 ⏳")
            else: st.caption("먼저 텔레파시를 보내보세요 📡")

    # 4. 🎵 주크박스
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        if isinstance(st.session_state.jukebox_data, list): st.session_state.jukebox_data = {"hodl": None, "sugi": None}
        
        # 🚨 URL 링크 깨짐을 막는 완벽한 포매팅 분리 로직
        yt_base_url = "https://" + "www.youtube.com/watch?v="
        
        with st.form("dj_dual"):
            link = st.text_input("오늘의 추천곡 (유튜브)")
            if st.form_submit_button("신청") and link:
                st.session_state.jukebox_data["hodl" if user_name_only == "수기남자친구" else "sugi"] = link
                save_data_to_cell("jukebox", st.session_state.jukebox_data); st.rerun()
        
        col_b, col_g = st.columns(2)
        with col_b:
            st.info("👦 남친의 Pick")
            b_id = extract_youtube_id(st.session_state.jukebox_data.get("hodl", ""))
            if b_id: st.video(yt_base_url + b_id)
        with col_g:
            st.success("👧 수기의 Pick")
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.video(yt_base_url + g_id)

    # 5. 📸 추억저장소 (🚨 아이폰 다중 업로드 완벽 분리 복구 & 갤러리 장바구니 적용)
    with tabs[4]:
        st.subheader("📸 추억 보관함")
        with st.expander("✨ 새로운 추억 보관하기", expanded=False):
            upload_mode = st.radio("업로드 방식을 선택해주세요!", ["🍎 아이폰 전용 (여러 장 쾌적하게 올리기)", "🤖 안드로이드 전용 (1장씩 장바구니에 담기)"], horizontal=False)
            
            if "아이폰" in upload_mode:
                img_files = st.file_uploader("사진을 여러 장 쭈욱 선택해주세요!", type=['jpg','png','jpeg'], accept_multiple_files=True)
                col_e1, col_e2 = st.columns([0.4, 0.6])
                with col_e1: event_date_input = st.date_input("언제 있었던 일인가요? 🗓️", value=now_kst.date(), key="iphone_date")
                with col_e2: event_name_input = st.text_input("어떤 추억인가요? ✏️", placeholder="예: 해운대 앞바다", key="iphone_name")
                
                if st.button("☁️ 여러 장 한 번에 전송 (아이폰 전용)", use_container_width=True):
                    if img_files:
                        with st.spinner("구글 드라이브 궁전으로 추억들을 전송하고 있습니다... ⏳"):
                            clean_event_name = event_name_input.strip().replace("_", " ").replace("/", " ")
                            if not clean_event_name: clean_event_name = "우리의 일상"
                            selected_date_str = str(event_date_input)
                            success_count = 0
                            for img_f in img_files:
                                try:
                                    img = Image.open(img_f)
                                    img = ImageOps.exif_transpose(img)
                                    img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                                    out = io.BytesIO()
                                    img.save(out, format="JPEG", quality=85)
                                    
                                    # f-string URL 파괴를 막기 위한 안전 문자열 생성
                                    safe_filename = f"{selected_date_str}_{user_name_only}_{clean_event_name}_{random.randint(1000, 9999)}.jpg"
                                    if upload_photo_to_drive(out.getvalue(), safe_filename, "image/jpeg"): success_count += 1
                                except: pass
                            if success_count > 0:
                                st.session_state.toast_msg = f"{success_count}장의 추억이 드라이브에 저장되었습니다! 🚀"; st.rerun()
                    else: st.warning("먼저 업로드할 사진을 선택해주세요!")
            
            else:
                st.info("💡 갤럭시는 튕김을 막기 위해 '사진 1장 담기'로 여러 번 모은 후 전송하세요!")
                new_f = st.file_uploader("사진 고르기 (1장씩 담기)", type=['jpg','png','jpeg'], accept_multiple_files=False)
                if st.button("장바구니에 담기 ➕") and new_f:
                    st.session_state.photo_cart.append(new_f.getvalue())
                    st.toast("장바구니에 쏙! 🛒"); st.rerun()
                
                if st.session_state.photo_cart:
                    st.success(f"🛒 현재 장바구니에 {len(st.session_state.photo_cart)}장의 사진이 대기 중입니다.")
                    col_e1, col_e2 = st.columns([0.4, 0.6])
                    with col_e1: event_date_input = st.date_input("언제 있었던 일인가요? 🗓️", value=now_kst.date(), key="and_date")
                    with col_e2: event_name_input = st.text_input("어떤 추억인가요? ✏️", placeholder="예: 해운대 앞바다", key="and_name")

                    if st.button("☁️ 장바구니 모두 전송! ({})".format(len(st.session_state.photo_cart)), use_container_width=True):
                        with st.spinner("압축 및 전송 중..."):
                            clean_event_name = event_name_input.strip().replace("_", " ").replace("/", " ")
                            if not clean_event_name: clean_event_name = "우리의 일상"
                            selected_date_str = str(event_date_input)
                            for f_bytes in st.session_state.photo_cart:
                                try:
                                    img = Image.open(io.BytesIO(f_bytes))
                                    img = ImageOps.exif_transpose(img)
                                    img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                                    out = io.BytesIO()
                                    img.save(out, format="JPEG", quality=85)
                                    
                                    safe_filename = f"{selected_date_str}_{user_name_only}_{clean_event_name}_{random.randint(1000, 9999)}.jpg"
                                    upload_photo_to_drive(out.getvalue(), safe_filename, "image/jpeg")
                                except: pass
                            st.session_state.photo_cart = []; st.success("전송 완료! 🚀"); st.rerun()
                    if st.button("장바구니 비우기 🗑️"): st.session_state.photo_cart = []; st.rerun()

        st.divider()
        photos = load_photos_from_drive(st.session_state.photo_limit)
        
        grouped_photos = {}
        for p in photos:
            parts = p['name'].split('_')
            if len(parts) >= 4: date_str = parts[0]; event_str = parts[2]
            elif len(parts) == 3: date_str = parts[0]; event_str = "기록 없는 추억"
            else: date_str = "과거의 어느 날"; event_str = "기록 없는 추억"
            group_key = f"🗓️ {date_str} | 📂 {event_str}"
            if group_key not in grouped_photos: grouped_photos[group_key] = []
            grouped_photos[group_key].append(p)

        for group_key, photo_list in grouped_photos.items():
            with st.expander(f"{group_key} (총 {len(photo_list)}장)"):
                cols = st.columns(2)
                for idx, p in enumerate(photo_list):
                    col = cols[idx % 2]
                    try:
                        img_bytes = get_image_bytes(p['id'])
                        parts = p['name'].split('_')
                        writer = parts[1] if len(parts) >= 2 else "알수없음"
                        col.image(img_bytes, caption=f"by {writer}", use_container_width=True)
                        if col.button("🗑️ 지우기", key=f"del_img_{p['id']}"):
                            if delete_photo_from_drive(p['id']):
                                st.session_state.toast_msg = "선택한 추억이 삭제되었습니다. 🗑️"; st.rerun()
                    except: col.error("사진을 불러오지 못했습니다.")

        if len(photos) >= st.session_state.photo_limit:
            if st.button("⬇️ 과거 추억 더 불러오기 (20장)"):
                st.session_state.photo_limit += 20; st.rerun()

    # 6. ⏳ 타임라인
    with tabs[5]:
        st.subheader("⏳ 타임라인")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event, "by": user_name_only})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_large_data("time", st.session_state.timeline); st.rerun()
        for t in st.session_state.timeline: st.markdown(f"<div class='card'><b>{t['date']}</b>: {t['event']}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록 (🚨 딕셔너리로 단어 추출 안전 픽스 완벽 반영)
    with tabs[6]:
        st.subheader("📊 월간 수기 백서")
        this_month = now_kst.strftime("%Y-%m")
        m_rev = [r for r in st.session_state.reviews if r.get('date','').startswith(this_month)]
        m_memo = [m for m in st.session_state.memo_history if m.get('date','').startswith(this_month)]
        
        st.write(f"📅 **{now_kst.month}월 결산 리포트**")
        c1, c2 = st.columns(2)
        c1.metric("데이트", f"{len(m_rev)}회")
        c2.metric("주고받은 쪽지", f"{len(m_memo)}개")
        
        all_text = " ".join([m.get('content', '') for m in m_memo] + [r.get('comment', '') for r in m_rev])
        words = [w for w in re.findall(r'[가-힣]{2,}', all_text) if len(w) > 1]
        
        word_counts = {}
        for w in words: word_counts[w] = word_counts.get(w, 0) + 1
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if top_words:
            st.write("🏷️ **우리가 이번 달 많이 쓴 단어:**")
            st.write(", ".join([f"#{w[0]}" for w in top_words]))

        st.divider()
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form", clear_on_submit=True):
            w_place = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가") and w_place:
                st.session_state.wishlist.append({"place": w_place, "visited": False, "by": user_name_only})
                save_large_data("wish", st.session_state.wishlist); st.rerun()
                
        for i, w in enumerate(st.session_state.wishlist):
            if isinstance(w, str): st.session_state.wishlist[i] = {"place": w, "visited": False, "by": "알수없음"}; w = st.session_state.wishlist[i]
            is_visited = w.get('visited', False)
            icon = "✅" if is_visited else "📍"
            with st.expander(f"{icon} {w.get('place', '')}"):
                if st.checkbox("다녀왔어요! 👣", value=is_visited, key=f"chk_w_{i}") != is_visited:
                    st.session_state.wishlist[i]['visited'] = not is_visited
                    save_large_data("wish", st.session_state.wishlist); st.rerun()
                if st.button("삭제하기 🗑️", key=f"btn_w_del_{i}"):
                    st.session_state.wishlist.pop(i); save_large_data("wish", st.session_state.wishlist); st.rerun()

        st.divider()
        st.subheader("📝 데이트 후기")
        with st.form("r_form", clear_on_submit=True):
            r_date_input = st.date_input("방문 날짜 🗓️", value=now_kst.date())
            r_name = st.text_input("장소명 📍")
            r_cat = st.selectbox("종류 🏷️", ["음식점", "카페", "공원", "기타"])
            r_rating = st.selectbox("별점 ⭐", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
            r_comment = st.text_area("후기 내용 📝")
            if st.form_submit_button("후기 등록!") and r_name:
                st.session_state.reviews.insert(0, {"name": r_name, "link": "", "cat": r_cat, "rating": r_rating, "comment": r_comment, "date": str(r_date_input), "by": user_name_only, "comments": []})
                save_large_data("review", st.session_state.reviews); st.rerun()
        
        for i, r in enumerate(st.session_state.reviews[:st.session_state.review_limit]):
            if "comments" not in r: r["comments"] = []
            with st.container():
                st.markdown(f"""
                    <div class="card" style="margin-bottom: 5px;">
                        <span style="background-color:rgba(128,128,128,0.2); padding:2px 5px; border-radius:5px; font-size:0.8rem; color:{text_color};">{r.get('cat', '')}</span>
                        <span style="font-size: 0.8rem; color: gray;"> {r.get('date', '')} by {r.get('by', '')}</span>
                        <br><b>{r.get('name', '')}</b> {r.get('rating', '')}<br><br>
                        <p style="margin: 0; color:{text_color};">{r.get('comment', '')}</p>
                    </div>
                """, unsafe_allow_html=True)

                for c_idx, c in enumerate(r["comments"]):
                    st.markdown(f"<div class='review-comment'><b>{c.get('user', '')}</b>: {c.get('text', '')} <span class='time-text'>({c.get('time', '')})</span></div>", unsafe_allow_html=True)
                    if c.get('user') == user_name_only:
                        with st.expander(f"💬 내 댓글 수정 / 삭제", expanded=False):
                            edit_c_text = st.text_input("댓글 내용 수정", value=c.get('text', ''), key=f"edit_c_txt_{i}_{c_idx}")
                            col_c_edit, col_c_del = st.columns(2)
                            if col_c_edit.button("수정 완료 💾", key=f"btn_c_edit_{i}_{c_idx}"):
                                if edit_c_text.strip():
                                    c['text'] = edit_c_text; save_large_data("review", st.session_state.reviews); st.rerun()
                            if col_c_del.button("댓글 삭제 🗑️", key=f"btn_c_del_{i}_{c_idx}"):
                                r["comments"].pop(c_idx); save_large_data("review", st.session_state.reviews); st.rerun()
                
                col_c1, col_c2 = st.columns([0.8, 0.2])
                with col_c1: new_comment = st.text_input("댓글 달기", key=f"comment_input_{i}", label_visibility="collapsed", placeholder="나도 여기 좋았어! 😆")
                with col_c2:
                    if st.button("💬 달기", key=f"btn_comment_{i}") and new_comment:
                        r["comments"].append({"user": user_name_only, "text": new_comment, "time": current_time_str})
                        save_large_data("review", st.session_state.reviews); st.rerun()

                if r.get('by') == user_name_only:
                    with st.expander("⚙️ 내 후기 원본 수정 / 삭제하기"):
                        try: parsed_date = datetime.datetime.strptime(r.get('date', today_str), "%Y-%m-%d").date()
                        except: parsed_date = now_kst.date()
                        edit_r_date = st.date_input("방문 날짜 수정", value=parsed_date, key=f"edit_r_date_{i}")
                        edit_r_name = st.text_input("장소명 수정", value=r.get('name', ''), key=f"edit_r_name_{i}")
                        edit_r_comment = st.text_area("후기 내용 수정", value=r.get('comment', ''), key=f"edit_r_comment_{i}")
                        col_e1, col_e2 = st.columns(2)
                        if col_e1.button("수정 완료 💾", key=f"btn_r_edit_{i}"):
                            r['date'] = str(edit_r_date); r['name'] = edit_r_name; r['comment'] = edit_r_comment
                            save_large_data("review", st.session_state.reviews); st.rerun()
                        if col_e2.button("삭제하기 🗑️", key=f"btn_r_del_{i}"):
                            st.session_state.reviews.pop(i); save_large_data("review", st.session_state.reviews); st.rerun()
                st.write("") 

        if len(st.session_state.reviews) >= st.session_state.review_limit:
            if st.button("⬇️ 과거 데이트 후기 더 보기 (10개)"):
                st.session_state.review_limit += 10; st.rerun()

    # 8. 🎁 타임캡슐
    with tabs[7]:
        st.subheader("🎁 미래로 보내는 편지")
        with st.form("capsule_form", clear_on_submit=True):
            c_title = st.text_input("타임캡슐 이름")
            c_date = st.date_input("열어볼 날짜", min_value=now_kst.date() + datetime.timedelta(days=1))
            c_content = st.text_area("편지 내용")
            if st.form_submit_button("묻기 ⛏️") and c_title and c_content:
                st.session_state.time_capsules.append({"title": c_title, "open_date": str(c_date), "content": c_content, "by": user_name_only})
                save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()

        for i, cap in enumerate(st.session_state.time_capsules):
            if today_str >= cap.get('open_date', ''):
                with st.expander(f"🎉 [열림] {cap.get('title', '')}"):
                    st.info(cap.get('content', ''))
                    if st.button("버리기", key=f"del_cap_{i}"): st.session_state.time_capsules.pop(i); save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()
            else: st.warning(f"🔒 [잠김] {cap.get('title', '')} ({cap.get('open_date', '')} 개봉)")

    # 9. 🎡 만능 룰렛
    with tabs[8]:
        st.subheader("🎡 결정장애 룰렛")
        custom_opts = st.text_input("선택지 입력 (쉼표 구분)")
        if st.button("돌리기! 🎲") and custom_opts: st.success(f"🎉 당첨: **{random.choice([o.strip() for o in custom_opts.split(',') if o.strip()])}** ‼️"); st.balloons()
