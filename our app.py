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
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import streamlit.components.v1 as components

# 1. 앱 기본 설정
st.set_page_config(page_title="수기 커플 노트 v5.0", page_icon="❤️", layout="centered")

# --- 🌸 벚꽃 이펙트 (은은하게) ---
def show_cherry_blossoms():
    st.markdown("""
        <style>
        .blossom { color: rgba(255, 183, 197, 0.6); font-size: 1.2em; position: fixed; top: -10%; z-index: 9999; pointer-events: none;
                   animation-name: fall, shake; animation-duration: 10s, 3s; animation-iteration-count: infinite, infinite; }
        @keyframes fall { 0% { top: -10%; } 100% { top: 100%; } }
        @keyframes shake { 0%, 100% { transform: translateX(0) rotate(0deg); } 50% { transform: translateX(80px) rotate(180deg); } }
        .blossom:nth-of-type(1) { left: 10%; animation-delay: 0s; } .blossom:nth-of-type(2) { left: 20%; animation-delay: 2s; }
        .blossom:nth-of-type(3) { left: 30%; animation-delay: 4s; } .blossom:nth-of-type(4) { left: 40%; animation-delay: 1s; }
        .blossom:nth-of-type(5) { left: 50%; animation-delay: 5s; } .blossom:nth-of-type(6) { left: 60%; animation-delay: 3s; }
        .blossom:nth-of-type(7) { left: 70%; animation-delay: 7s; } .blossom:nth-of-type(8) { left: 80%; animation-delay: 2s; }
        .blossom:nth-of-type(9) { left: 90%; animation-delay: 4s; }
        </style>
        <div aria-hidden="true">
            <div class="blossom">🌸</div><div class="blossom">🌸</div><div class="blossom">🌸</div>
            <div class="blossom">🌸</div><div class="blossom">🌸</div><div class="blossom">🌸</div>
            <div class="blossom">🌸</div><div class="blossom">🌸</div><div class="blossom">🌸</div>
        </div>
    """, unsafe_allow_html=True)

show_cherry_blossoms()

# ==========================================
# 🍎 아이폰(iOS) 전용 홈 화면 아이콘 강제 주입
# ==========================================
components.html("""
    <script>
        const link = window.parent.document.createElement('link');
        link.rel = 'apple-touch-icon';
        link.href = 'https://cdn-icons-png.flaticon.com/512/833/833472.png'; 
        window.parent.document.head.appendChild(link);
    </script>
""", height=0, width=0)

# --- 🌐 한국 시간(KST) 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

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
    
    def safe_worksheet(name):
        try: return doc.worksheet(name)
        except: return None

    return {
        "main": safe_worksheet('시트1'), "memo": safe_worksheet('쪽지함'), "time": safe_worksheet('타임라인'),
        "date": safe_worksheet('데이트일정'), "wish": safe_worksheet('위시리스트'), "review": safe_worksheet('데이트후기'),
        "qna": safe_worksheet('문답데이터'), "capsule": safe_worksheet('타임캡슐데이터'),
        "tele": safe_worksheet('텔레파시'), "jukebox": safe_worksheet('주크박스')
    }

services = get_sheets()
if not services: st.error("🚨 구글 연동 실패! Secrets 설정을 확인해주세요.")

# --- 🚨 핵심 유틸리티: 유튜브 ID 추출기 ---
def extract_youtube_id(url):
    pattern = r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

if "DRIVE_FOLDER_ID" in st.secrets:
    DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
elif "google_auth" in st.secrets and "DRIVE_FOLDER_ID" in st.secrets["google_auth"]:
    DRIVE_FOLDER_ID = st.secrets["google_auth"]["DRIVE_FOLDER_ID"]
else:
    DRIVE_FOLDER_ID = ""

def get_drive_service():
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

# ==========================================
# ⚡️ 데이터 로드 및 아토믹 세이브
# ==========================================
def load_data():
    try:
        val = services["main"].acell('A1').value
        main_data = json.loads(val) if val else {}
    except: main_data = {}

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
        "jukebox_data": get_json_cell(services["jukebox"], [])
    }

def save_data_to_cell(sheet_key, data):
    if services and services.get(sheet_key):
        services[sheet_key].update_acell('A1', json.dumps(data))

def save_large_data(sheet_key, data_list):
    if services and services.get(sheet_key):
        json_str = json.dumps(data_list)
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cell_values = [[chunk] for chunk in chunks]
        services[sheet_key].batch_clear(['A2:A'])
        services[sheet_key].update(values=cell_values, range_name='A2', value_input_option='RAW')

def save_main_data():
    main_data = {
        "notice": st.session_state.notice,
        "promises": st.session_state.promises,
        "moods": st.session_state.moods,
        "mood_history": st.session_state.mood_history,
        "current_mood_date": st.session_state.current_mood_date,
        "menu_list": st.session_state.menu_list,
    }
    save_data_to_cell("main", main_data)

# ==========================================
# 📸 드라이브 연동 (v4.6 아키텍처)
# ==========================================
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

def delete_photo_from_drive(file_id):
    try:
        svc = get_drive_service() 
        svc.files().delete(fileId=file_id).execute()
        return True
    except: return False

@st.cache_data(show_spinner=False, ttl=3600)
def get_image_bytes(file_id):
    svc = get_drive_service()
    request = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    return fh.getvalue()

# ==========================================
# 🚨 로그인 시스템 (원클릭 접속)
# ==========================================
def validate_password():
    if st.session_state.pwd_input == "6146":
        st.session_state["password_correct"] = True
    else:
        st.error("비밀번호가 틀렸어! ❤️")

def check_login_and_user():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if "current_user" not in st.session_state: st.session_state["current_user"] = None

    if not st.session_state["password_correct"]:
        st.markdown("<h1 style='text-align: center; color: #FF85A2; margin-top: 50px;'>♥ 수기 커플 노트</h1>", unsafe_allow_html=True)
        st.text_input("우리만의 비밀번호", type="password", key="pwd_input", on_change=validate_password)
        return False
    
    if not st.session_state["current_user"]:
        st.markdown("<h2 style='text-align: center; color: #FF85A2; margin-top: 50px;'>누가 오셨나요? 👀</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>정확한 기록을 위해 본인을 선택해주세요!</p>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👦 수기남자친구"): st.session_state["current_user"] = "수기남자친구"; st.rerun()
        with col2:
            if st.button("👧 수기"): st.session_state["current_user"] = "수기"; st.rerun()
        return False
    return True

# --- 메인 실행 ---
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
        
        if st.session_state.current_mood_date != today_str:
            st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}
            st.session_state.current_mood_date = today_str
            save_main_data()

    # 📌 테마 설정
    current_hour = now_kst.hour
    is_night = current_hour >= 19 or current_hour <= 6
    if is_night:
        bg_color = "#1A1A2E"; card_bg = "#16213E"; text_color = "#E0E0E0"; input_bg = "#0F3460"; border_color = "#2E3B5E"
        accent_color = "#E94560" if user_name_only == "수기" else "#4B89FF"
    else:
        text_color = "#333333"; card_bg = "#ffffff"; input_bg = "#ffffff"; border_color = "#eeeeee"
        bg_color = "#FFF5F7" if user_name_only == "수기" else "#E3F2FD"
        accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"

    # ==========================================
    # 🌱 [v5.0] 다마고치 사랑의 나무 (사이드바)
    # ==========================================
    total_activity = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    if total_activity < 10: level, tree_icon = "씨앗", "🌱"
    elif total_activity < 30: level, tree_icon = "새싹", "🌿"
    elif total_activity < 70: level, tree_icon = "아기 나무", "🌳"
    else: level, tree_icon = "풍성한 나무", "🍎"

    with st.sidebar:
        st.markdown(f"""
            <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; border: 2px solid {accent_color}; text-align: center; margin-bottom: 15px;">
                <h1 style="margin:0;">{tree_icon}</h1>
                <h4 style="margin:5px 0;">우리의 사랑나무: {level}</h4>
                <p style="font-size: 0.8em; opacity: 0.8; margin:0;">활동 포인트: {total_activity} XP</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background-color: rgba(128,128,128,0.05); padding: 10px; border-radius: 10px; border-left: 5px solid {accent_color}; margin-bottom: 15px;">
                <h3 style='color:{accent_color}; margin:0;'>{user_icon} {user_name_only} 접속 중 👋</h3>
            </div>
            """, unsafe_allow_html=True)
            
        start_date = datetime.date(2026, 1, 1) 
        days_passed = (now_kst.date() - start_date).days
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
                st.session_state.toast_msg = "새로운 약속이 추가되었습니다! 🤝"
                st.rerun()
            
        st.divider()
        if st.button("로그아웃 🚪"): st.session_state.clear(); st.rerun()

    # --- CSS 주입 (span 제외 유지) ---
    st.markdown(f"""
        <div class="custom-bg-layer" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: {bg_color}; z-index: -99999; pointer-events: none;"></div>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, p, h1, h2, h3, h4, h5, h6, label, button, input, textarea, select, div[data-testid="stMetricValue"], .stMarkdown, .stText {{
            font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important;
        }}
        .stApp {{ background-color: transparent !important; background: transparent !important; }}
        input, textarea, select, div.stTextInput > div > div > input, div.stTextArea > div > div > textarea {{
            background-color: {input_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important;
        }}
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ 
            background-color: {card_bg} !important; opacity: 1 !important; border-right: 1px solid {border_color} !important;
        }}
        .card, [data-testid="stExpander"] {{ 
            background-color: {card_bg} !important; border-radius: 15px; padding: 15px; margin-bottom: 15px; border: 1px solid {border_color} !important; 
        }}
        .user-boy {{ border-left: 5px solid #4B89FF; text-align: left; background-color: rgba(75, 137, 255, 0.1) !important; }}
        .user-girl {{ border-right: 5px solid #FF85A2; text-align: right; background-color: rgba(255, 133, 162, 0.1) !important; }}
        .review-comment {{ background-color: rgba(128,128,128,0.1); padding: 8px 12px; border-radius: 8px; margin-top: 5px; font-size: 0.9em; }}
        .time-text {{ font-size: 0.8rem; color: gray !important; }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: {card_bg} !important; border: 1px solid {border_color} !important; color: {text_color} !important; }}
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
    # 9개 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "📸 추억 저장소", "⏳ 타임라인", "🎡 만능 룰렛", "📍 장소/기록", "🎁 타임캡슐", "🌸 텔레파시", "🎵 주크박스"])

    # 1. 데이트 (문답 ➔ 데이트일정 ➔ 기분)
    with tabs[0]:
        qna_list = [
            "1. 우리가 처음 만났던 날, 서로의 첫인상은 어땠어?", "2. 서로에게 가장 반했던 결정적인 순간은 언제야?",
            "3. 내가 가장 사랑스러워 보일 때는 언제야?", "4. 나의 잠버릇이나 술버릇 중 가장 귀여운 것은?",
            "5. 지금 당장 훌쩍 떠난다면 같이 가고 싶은 여행지는?", "6. 지금까지 우리의 가장 완벽했던 데이트는 언제였어?",
            "7. 우리의 첫 키스(뽀뽀) 때 어떤 기분이었어?", "8. 내가 해준 음식 중 최고의 메뉴는?",
            "9. 서로의 연락처 저장명과 그렇게 정한 이유는 뭐야?", "10. 화났을 때 내 기분을 100% 풀어주는 최고의 방법은?",
            "11. 나에게 들었던 가장 감동적인 말은 무엇이었어?", "12. 꼭 같이 배워보고 싶은 취미나 운동이 있다면?",
            "13. 나의 어떤 점을 가장 닮고 싶어?", "14. 지금까지 만나면서 나에게 가장 고마웠던 순간은?",
            "15. 싸웠을 때 우리의 암묵적인 룰을 하나 정한다면?", "16. 나를 생각하면 가장 먼저 떠오르는 노래는?",
            "17. 내가 가장 섹시해(멋있어/예뻐) 보일 때는 언제야?", "18. 서로에게 주고 싶은 가장 특별하고 의미 있는 선물은?",
            "19. 우리의 첫 데이트 때, 겉으론 안 그랬지만 속마음은 어땠어?", "20. 나를 동물로 표현한다면 어떤 동물이고 이유는 뭐야?",
            "21. 우리의 연애를 영화 장르로 따지면 어떤 장르일까?", "22. 하루 동안 서로 몸이 바뀐다면 가장 해보고 싶은 것은?",
            "23. 서로의 가족에게 해주고 싶은 작은 이벤트가 있다면?", "24. 폰에 있는 우리의 커플 사진 중 가장 좋아하는 사진은?",
            "25. 나를 만나고 나서 긍정적으로 변한 점이 있다면?", "26. 1년 뒤 오늘, 우리는 어떤 모습으로 무엇을 하고 있을까?",
            "27. 10년 뒤 우리는 서로에게 어떤 사람일까?", "28. 이번 주말, 나랑 하루 종일 방 안에서만 놀기 vs 하루 종일 밖에서 놀기",
            "29. 서로에게 절대 변치 말자고 엄지 걸고 약속하고 싶은 것 1가지는?", "30. 지금 당장 상대방을 꽉 안아주면서 해주고 싶은 말은?"
        ]
        q_idx = now_kst.toordinal() % 30
        today_question = qna_list[q_idx]
        q_key = f"qna_{q_idx}"

        if "qna_data" not in st.session_state: st.session_state.qna_data = {}
        if q_key not in st.session_state.qna_data: st.session_state.qna_data[q_key] = {"hodl": "", "sugi": ""}

        with st.expander(f"💌 오늘의 문답 (D-{30 - q_idx}일 남음)", expanded=True):
            st.subheader(today_question)
            ans_boy = st.session_state.qna_data[q_key].get("hodl", "")
            ans_girl = st.session_state.qna_data[q_key].get("sugi", "")
            both_answered = bool(ans_boy.strip() and ans_girl.strip())
            
            col1, col2 = st.columns(2)
            new_ans_boy = ans_boy; new_ans_girl = ans_girl
            
            with col1:
                st.markdown("👦 **수기남자친구님의 답변**")
                if user_name_only == "수기남자친구": new_ans_boy = st.text_area("내 답변 작성", value=ans_boy, height=100, label_visibility="collapsed")
                else:
                    if both_answered: st.info(ans_boy)
                    elif ans_boy.strip(): st.warning("🔒 수기남자친구님이 답변을 완료했어요! 수기님도 작성해야 볼 수 있어요.")
                    else: st.caption("아직 작성하지 않았어요 🤫")
                        
            with col2:
                st.markdown("👩 **수기님의 답변**")
                if user_name_only == "수기": new_ans_girl = st.text_area("내 답변 작성", value=ans_girl, height=100, label_visibility="collapsed")
                else:
                    if both_answered: st.info(ans_girl)
                    elif ans_girl.strip(): st.warning("🔒 수기님이 답변을 완료했어요! 수기남자친구님도 작성해야 볼 수 있어요.")
                    else: st.caption("아직 작성하지 않았어요 🤫")
                
            if st.button("내 답변 꾹 저장하기 💾"):
                st.session_state.qna_data[q_key]["hodl"] = new_ans_boy
                st.session_state.qna_data[q_key]["sugi"] = new_ans_girl
                save_data_to_cell("qna", st.session_state.qna_data)
                st.session_state.toast_msg = "소중한 답변이 영구 저장되었습니다! ✨"; st.rerun()

        st.divider()
        st.subheader("🗓️ 우리의 데이트 일정")
        with st.form("schedule_form", clear_on_submit=True):
            s_date = st.date_input("데이트 날짜")
            s_plan = st.text_input("무엇을 할까요?")
            if st.form_submit_button("일정 추가") and s_plan:
                st.session_state.date_schedules.append({"date": str(s_date), "plan": s_plan, "by": user_name_only})
                st.session_state.date_schedules.sort(key=lambda x: x['date'])
                save_large_data("date", st.session_state.date_schedules)
                st.session_state.toast_msg = "데이트 일정이 추가되었습니다! 🗓️"; st.rerun()
                
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 [{s['date']}] {s['plan']}"):
                edit_s = st.text_input("일정 수정", value=s['plan'], key=f"edit_s_{i}")
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("수정 완료", key=f"btn_s_edit_{i}"):
                    st.session_state.date_schedules[i]['plan'] = edit_s
                    save_large_data("date", st.session_state.date_schedules)
                    st.session_state.toast_msg = "일정이 수정되었습니다! ✨"; st.rerun()
                if col_s2.button("삭제하기 🗑️", key=f"btn_s_del_{i}"):
                    st.session_state.date_schedules.pop(i)
                    save_large_data("date", st.session_state.date_schedules)
                    st.session_state.toast_msg = "일정이 삭제되었습니다. 🗑️"; st.rerun()

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
            save_main_data()
            st.session_state.toast_msg = f"{user_name_only}님의 기분이 업데이트 되었습니다! 💖"; st.rerun()

        st.write(f"👦 수기남자친구: {st.session_state.moods.get('수기남자친구', '🙂')} ({mood_desc.get(st.session_state.moods.get('수기남자친구', '🙂'), '보통')})")
        st.write(f"👧 수기: {st.session_state.moods.get('수기', '🙂')} ({mood_desc.get(st.session_state.moods.get('수기', '🙂'), '보통')})")

    # 2. 쪽지함
    with tabs[1]:
        st.subheader("💌 오늘의 쪽지 (수정은 당일만!)")
        my_today_memo_idx = None
        for i, m in enumerate(st.session_state.memo_history):
            if m.get('date') == today_str and m.get('user') == user_name_only:
                my_today_memo_idx = i; break
        
        with st.container():
            if my_today_memo_idx is not None:
                st.info("오늘의 쪽지를 이미 작성했어요! ✍️")
                with st.form("edit_memo_form"):
                    edit_content = st.text_area("쪽지 내용", value=st.session_state.memo_history[my_today_memo_idx]['content'])
                    if st.form_submit_button("수정 완료"):
                        st.session_state.memo_history[my_today_memo_idx]['content'] = edit_content
                        st.session_state.memo_history[my_today_memo_idx]['edited'] = True
                        save_large_data("memo", st.session_state.memo_history)
                        st.session_state.toast_msg = "쪽지가 수정되었습니다! 💌"; st.rerun()
            else:
                with st.form("new_memo_form"):
                    content = st.text_area("오늘 하루, 하고 싶은 말은?")
                    if st.form_submit_button("남기기") and content:
                        st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content, "edited": False})
                        save_large_data("memo", st.session_state.memo_history)
                        st.session_state.toast_msg = "오늘의 쪽지를 남겼습니다! 💌"; st.rerun()

        st.divider()
        for m in st.session_state.memo_history:
            is_boy = "수기남자친구" in m.get('user', '')
            align_cls = "user-boy" if is_boy else "user-girl"
            st.markdown(f'<div class="card {align_cls}"><small><b>{m.get("user", "")}</b> | {m.get("date", "")}</small><p style="margin: 5px 0;">{m.get("content", "")}</p><span class="time-text">{m.get("time", "")}</span></div>', unsafe_allow_html=True)

    # 3. 추억 저장소
    with tabs[2]:
        st.subheader("📸 우리들의 추억 저장소")
        with st.expander("✨ 새로운 추억 보관하기", expanded=False):
            img_files = st.file_uploader("사진을 여러 장 선택해서 올릴 수 있어요!", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            col_e1, col_e2 = st.columns([0.4, 0.6])
            with col_e1: event_date_input = st.date_input("언제 있었던 일인가요? 🗓️", value=now_kst.date())
            with col_e2: event_name_input = st.text_input("어떤 추억인가요? ✏️", placeholder="예: 해운대 앞바다")
            
            if st.button("☁️ 2TB 드라이브에 안전하게 업로드"):
                if img_files:
                    with st.spinner("구글 드라이브 궁전으로 추억들을 전송하고 있습니다... ⏳"):
                        clean_event_name = event_name_input.strip().replace("_", " ").replace("/", " ")
                        if not clean_event_name: clean_event_name = "우리의 일상"
                        selected_date_str = str(event_date_input)
                        success_count = 0
                        for img_file in img_files:
                            ext = os.path.splitext(img_file.name)[1]
                            if not ext: ext = ".jpg"
                            filename = f"{selected_date_str}_{user_name_only}_{clean_event_name}_{random.randint(1000, 9999)}{ext}"
                            file_id = upload_photo_to_drive(img_file.getvalue(), filename, img_file.type)
                            if file_id: success_count += 1
                        if success_count > 0:
                            st.session_state.toast_msg = f"{success_count}장의 추억이 드라이브에 영구 저장되었습니다! 🚀"; st.rerun()
                else: st.warning("먼저 업로드할 사진을 선택해주세요!")
                
        st.divider()
        photos = load_photos_from_drive(limit=st.session_state.photo_limit)
        if not photos: st.caption("아직 보관된 추억이 없습니다. 첫 번째 추억을 올려보세요! 📸")
        else:
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

        st.divider()
        if len(photos) >= st.session_state.photo_limit:
            if st.button("⬇️ 과거 추억 더 불러오기 (20장)"):
                st.session_state.photo_limit += 20; st.rerun()

    # 4. 타임라인
    with tabs[3]:
        st.subheader("⏳ 타임라인")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event, "by": user_name_only})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_large_data("time", st.session_state.timeline)
                st.session_state.toast_msg = "타임라인이 기록되었습니다! ⏳"; st.rerun()
        for item in st.session_state.timeline:
            st.markdown(f'<div class="card"><b>{item.get("date", "")}</b> ({item.get("by", "")})<br>{item.get("event", "")}</div>', unsafe_allow_html=True)

    # 5. 만능 룰렛
    with tabs[4]:
        st.subheader("🎡 결정장애 해결! 만능 룰렛")
        st.markdown("#### 🎯 무엇이든 랜덤 뽑기!")
        custom_options = st.text_input("선택지 입력", placeholder="치킨, 피자, 족발")
        if st.button("결정의 룰렛 돌리기! 🎲"):
            opts = [o.strip() for o in custom_options.split(",") if o.strip()]
            if opts: st.success(f"🎉 당첨: **{random.choice(opts)}** ‼️"); st.balloons()
            else: st.warning("선택지를 제대로 입력해주세요!")
                
        st.divider()
        st.markdown("#### 😋 저장해둔 메뉴 리스트에서 뽑기")
        if st.button("메뉴 랜덤 뽑기! 🥩"):
            if st.session_state.menu_list: st.warning(f"오늘의 추천 메뉴는 바로: **{random.choice(st.session_state.menu_list)}** 😋")
            else: st.error("저장된 메뉴가 없습니다. 아래에서 추가해주세요!")
            
        with st.expander("🍽️ 우리만의 메뉴 리스트 관리"):
            with st.form("menu_form", clear_on_submit=True):
                new_menu = st.text_input("새로운 메뉴 추가")
                if st.form_submit_button("메뉴 추가") and new_menu:
                    st.session_state.menu_list.append(new_menu); save_main_data(); st.session_state.toast_msg = "추가되었습니다!"; st.rerun()
            for i, menu in enumerate(st.session_state.menu_list):
                col_m1, col_m2 = st.columns([0.7, 0.3])
                col_m1.write(f"- {menu}")
                if col_m2.button("삭제", key=f"btn_m_del_{i}"):
                    st.session_state.menu_list.pop(i); save_main_data(); st.rerun()

    # 6. 장소/기록 
    with tabs[5]:
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form", clear_on_submit=True):
            w_place = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가") and w_place:
                st.session_state.wishlist.append({"place": w_place, "visited": False, "by": user_name_only})
                save_large_data("wish", st.session_state.wishlist)
                st.session_state.toast_msg = "위시리스트에 장소가 추가되었습니다! 📍"; st.rerun()
                
        st.write("👇 **장소를 터치하여 방문 체크 및 관리하세요!**")
        for i, w in enumerate(st.session_state.wishlist):
            if isinstance(w, str):
                st.session_state.wishlist[i] = {"place": w, "visited": False, "by": "알수없음"}
                w = st.session_state.wishlist[i]
                
            is_visited = w.get('visited', False)
            icon = "✅" if is_visited else "📍"
            status_text = "(다녀옴!) " if is_visited else ""
            
            with st.expander(f"{icon} {status_text}{w.get('place', '')}"):
                new_visited = st.checkbox("다녀왔어요! 👣", value=is_visited, key=f"chk_w_{i}")
                if new_visited != is_visited:
                    st.session_state.wishlist[i]['visited'] = new_visited
                    save_large_data("wish", st.session_state.wishlist)
                    st.session_state.toast_msg = "방문 상태가 저장되었습니다! 👣"; st.rerun()
                
                if not new_visited:
                    edit_w = st.text_input("장소명 수정", value=w.get('place', ''), key=f"edit_w_{i}")
                    col_w1, col_w2 = st.columns(2)
                    if col_w1.button("수정 완료", key=f"btn_w_edit_{i}"):
                        st.session_state.wishlist[i]['place'] = edit_w
                        save_large_data("wish", st.session_state.wishlist)
                        st.session_state.toast_msg = "장소명이 수정되었습니다! ✨"; st.rerun()
                    if col_w2.button("삭제하기 🗑️", key=f"btn_w_del_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_large_data("wish", st.session_state.wishlist)
                        st.session_state.toast_msg = "장소가 목록에서 삭제되었습니다."; st.rerun()
                else:
                    if st.button("목록에서 완전히 삭제하기 🗑️", key=f"btn_w_del_v_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_large_data("wish", st.session_state.wishlist)
                        st.session_state.toast_msg = "장소가 완전히 삭제되었습니다."; st.rerun()
        
        st.divider()
        st.subheader("📝 데이트 후기 작성 및 소셜 갤러리")
        with st.form("r_form", clear_on_submit=True):
            r_date_input = st.date_input("방문 날짜 🗓️", value=now_kst.date())
            r_name = st.text_input("장소명 📍")
            r_link = st.text_input("장소 지도 링크 (URL - 선택사항) 🔗")
            r_cat = st.selectbox("종류 🏷️", ["음식점", "카페", "공원", "기타"])
            r_rating = st.selectbox("별점 ⭐", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
            r_comment = st.text_area("후기 내용 📝")
            if st.form_submit_button("후기 등록 완료!") and r_name:
                st.session_state.reviews.insert(0, {
                    "name": r_name, "link": r_link, "cat": r_cat, "rating": r_rating, 
                    "comment": r_comment, "photo_url": "", "date": str(r_date_input), "by": user_name_only,
                    "comments": [] 
                })
                save_large_data("review", st.session_state.reviews)
                st.session_state.toast_msg = "정성스러운 데이트 후기가 등록되었습니다! 📝"; st.rerun()
        
        st.divider()
        st.subheader("📚 우리의 데이트 기록장")
        for i, r in enumerate(st.session_state.reviews):
            if "comments" not in r: r["comments"] = []
            with st.container():
                link_html = f" | <a href='{r.get('link', '#')}' target='_blank'>🔗 지도에서 보기</a>" if r.get('link') else ""
                st.markdown(f"""
                    <div class="card" style="margin-bottom: 5px;">
                        <span style="background-color:rgba(128,128,128,0.2); padding:2px 5px; border-radius:5px; font-size:0.8rem; color:{text_color};">{r.get('cat', '')}</span>
                        <span style="font-size: 0.8rem; color: gray;"> {r.get('date', '')} by {r.get('by', '')}</span>
                        <br><b>{r.get('name', '')}</b> {r.get('rating', '')} {link_html}<br><br>
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
                                    c['text'] = edit_c_text; save_large_data("review", st.session_state.reviews)
                                    st.session_state.toast_msg = "내 댓글이 완벽하게 수정되었습니다! ✨"; st.rerun()
                                else: st.warning("빈칸으로 수정할 수 없어요!")
                            if col_c_del.button("댓글 삭제 🗑️", key=f"btn_c_del_{i}_{c_idx}"):
                                r["comments"].pop(c_idx); save_large_data("review", st.session_state.reviews)
                                st.session_state.toast_msg = "내 댓글이 삭제되었습니다. 🗑️"; st.rerun()
                
                col_c1, col_c2 = st.columns([0.8, 0.2])
                with col_c1: new_comment = st.text_input("댓글 달기", key=f"comment_input_{i}", label_visibility="collapsed", placeholder="나도 여기 좋았어! 😆")
                with col_c2:
                    if st.button("💬 달기", key=f"btn_comment_{i}") and new_comment:
                        r["comments"].append({"user": user_name_only, "text": new_comment, "time": current_time_str})
                        save_large_data("review", st.session_state.reviews)
                        st.session_state.toast_msg = "댓글이 등록되었습니다! 💬"; st.rerun()

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
                            save_large_data("review", st.session_state.reviews)
                            st.session_state.toast_msg = "후기 원본이 수정되었습니다! ✨"; st.rerun()
                        if col_e2.button("삭제하기 🗑️", key=f"btn_r_del_{i}"):
                            st.session_state.reviews.pop(i); save_large_data("review", st.session_state.reviews)
                            st.session_state.toast_msg = "후기가 목록에서 삭제되었습니다."; st.rerun()
                st.write("") 

    # 7. 타임캡슐
    with tabs[6]:
        st.subheader("🎁 미래로 보내는 편지")
        with st.form("capsule_form", clear_on_submit=True):
            c_title = st.text_input("타임캡슐 이름")
            c_date = st.date_input("열어볼 날짜", min_value=now_kst.date() + datetime.timedelta(days=1))
            c_content = st.text_area("미래의 우리에게 남길 편지")
            if st.form_submit_button("타임캡슐 묻기 ⛏️") and c_title and c_content:
                st.session_state.time_capsules.append({"title": c_title, "open_date": str(c_date), "content": c_content, "by": user_name_only, "created_date": today_str})
                st.session_state.time_capsules.sort(key=lambda x: x.get('open_date', ''))
                save_data_to_cell("capsule", st.session_state.time_capsules)
                st.session_state.toast_msg = f"{c_date}에 개봉될 타임캡슐을 묻었습니다! 🔒"; st.rerun()

        st.divider()
        for i, cap in enumerate(st.session_state.time_capsules):
            is_open = today_str >= cap.get('open_date', '')
            if is_open:
                with st.expander(f"🎉 [열림] {cap.get('title', '')} (개봉일: {cap.get('open_date', '')})"):
                    st.write(f"**📝 작성자:** {cap.get('by', '')}"); st.info(cap.get('content', ''))
                    if st.button("빈 캡슐 버리기 🗑️", key=f"del_cap_{i}"):
                        st.session_state.time_capsules.pop(i); save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()
            else:
                try: d_day = (datetime.datetime.strptime(cap.get('open_date', ''), "%Y-%m-%d").date() - now_kst.date()).days
                except: d_day = "?"
                with st.expander(f"🔒 [잠김] {cap.get('title', '')} (D-{d_day}일)"):
                    st.warning(f"이 캡슐은 **{cap.get('open_date', '')} 자정(KST)**에 열쇠가 풀립니다! 🗝️")
                    st.write(f"**📝 작성자:** {cap.get('by', '')}")

    # 8. 🌸 [v5.0.5] 텔레파시 (스니킹 알림 기능 추가)
    with tabs[7]:
        st.subheader("🌸 오늘의 텔레파시 밸런스 게임")
        questions = [["평생 여름", "평생 겨울"], ["카레맛 똥", "똥맛 카레"], ["찍먹", "부먹"], ["강아지", "고양이"]]
        tele_idx = now_kst.toordinal() % len(questions)
        q_pair = questions[tele_idx]
        
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        
        col1, col2 = st.columns(2)
        my_key = "hodl" if user_name_only == "수기남자친구" else "sugi"
        ans = st.session_state.tele_data[today_str].get(my_key)
        
        with col1: 
            if st.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
                st.session_state.tele_data[today_str][my_key] = q_pair[0]
                save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        with col2:
            if st.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
                st.session_state.tele_data[today_str][my_key] = q_pair[1]
                save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        
        st.divider()
        b_ans = st.session_state.tele_data[today_str].get("hodl")
        g_ans = st.session_state.tele_data[today_str].get("sugi")
        
        # 🚨 상대방의 선택 여부를 알려주는 세분화된 알림 로직
        if b_ans and g_ans:
            if b_ans == g_ans: 
                st.balloons()
                st.success(f"🎊 찌찌뽕! 두 분 다 **[{b_ans}]**를 선택하셨어요! 운명인가봐요 ❤️")
            else: 
                st.info(f"오호! 수기남자친구님은 **[{b_ans}]**, 수기님은 **[{g_ans}]**를 고르셨군요! (다름의 미학 😉)")
        else: 
            if b_ans: 
                st.warning("🔒 수기남자친구님은 선택을 완료했어요! 수기님의 선택을 기다리고 있어요 ⏳")
            elif g_ans: 
                st.warning("🔒 수기님은 선택을 완료했어요! 수기남자친구님의 선택을 기다리고 있어요 ⏳")
            else: 
                st.caption("아직 아무도 선택하지 않았어요! 먼저 텔레파시를 보내보세요 📡")

    # 9. 🎵 주크박스
    with tabs[8]:
        st.subheader("🎵 오늘의 커플 DJ")
        with st.form("dj_form", clear_on_submit=True):
            song_link = st.text_input("상대방에게 들려주고 싶은 노래 (유튜브 링크)")
            if st.form_submit_button("노래 신청하기 📻") and song_link:
                st.session_state.jukebox_data.insert(0, {"date": today_str, "user": user_name_only, "url": song_link})
                save_data_to_cell("jukebox", st.session_state.jukebox_data)
                st.session_state.toast_msg = "주크박스에 노래가 등록되었습니다! 🎧"; st.rerun()
        
        if st.session_state.jukebox_data:
            latest = st.session_state.jukebox_data[0]
            st.markdown(f"#### 🎧 {latest.get('user', '')}님이 신청한 BGM")
            vid_id = extract_youtube_id(latest.get('url', ''))
            if vid_id: st.video(f"https://www.youtube.com/watch?v={vid_id}")
            else: st.warning("유효한 유튜브 링크가 아니에요!")
