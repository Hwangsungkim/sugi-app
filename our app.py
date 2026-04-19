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
st.set_page_config(page_title="수기 커플 노트 v5.9", page_icon="❤️", layout="centered")

# --- 🌐 한국 시간(KST) 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

# ==========================================
# 🌤️ 실시간 날씨 API 연동 (최상단 고정 이모티콘)
# ==========================================
@st.cache_data(ttl=3600)
def get_busan_weather():
    try:
        res = requests.get("https://api.open-meteo.com/v1/forecast?latitude=35.1796&longitude=129.0756&current_weather=true", timeout=1.5)
        if res.status_code == 200:
            cw = res.json().get("current_weather", {})
            code = cw.get("weathercode", 0)
            wind = cw.get("windspeed", 0)
            if wind > 15.0: return "💨"
            if code in [51, 53, 55, 61, 63, 65, 67, 80, 81, 82]: return "🌧️"
            elif code in [71, 73, 75, 77, 85, 86]: return "❄️"
            elif code in [1, 2, 3, 45, 48]: return "☁️"
            else: return "☀️"
        return "☀️"
    except: return "☀️"

weather_emoji = get_busan_weather()

# --- 🍎 아이폰 전용 홈 화면 아이콘 ---
components.html("""<script>const link = window.parent.document.createElement('link'); link.rel = 'apple-touch-icon'; link.href = 'https://cdn-icons-png.flaticon.com/512/833/833472.png'; window.parent.document.head.appendChild(link);</script>""", height=0, width=0)

# --- 🚀 구글 인증 및 서비스 설정 ---
@st.cache_resource
def get_credentials():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "google_auth" in st.secrets:
        return Credentials.from_authorized_user_info(json.loads(st.secrets["google_auth"]["token"]), scopes)
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

def extract_youtube_id(url):
    if not url or not isinstance(url, str): return None
    match = re.search(r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else None

DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID") or st.secrets.get("google_auth", {}).get("DRIVE_FOLDER_ID") or ""

def get_drive_service():
    return build('drive', 'v3', credentials=get_credentials(), cache_discovery=False)

def upload_photo_to_drive(file_bytes, filename, mime_type):
    if not DRIVE_FOLDER_ID: return None
    try:
        svc = get_drive_service()
        file = svc.files().create(body={'name': filename, 'parents': [DRIVE_FOLDER_ID]}, media_body=MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True), fields='id').execute()
        return file.get('id')
    except: return None

def load_photos_from_drive(limit=20):
    if not DRIVE_FOLDER_ID: return []
    try: return get_drive_service().files().list(q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false", pageSize=limit, fields="files(id, name)", orderBy="createdTime desc").execute().get('files', [])
    except: return []

@st.cache_data(show_spinner=False, ttl=3600)
def get_image_bytes(file_id):
    svc = get_drive_service(); request = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    return fh.getvalue()

def delete_photo_from_drive(file_id):
    try: svc = get_drive_service(); svc.files().delete(fileId=file_id).execute(); return True
    except: return False

# ==========================================
# ⚡️ 데이터 엔진
# ==========================================
def load_data():
    try: val = services["main"].acell('A1').value
    except: val = None
    main_data = json.loads(val) if val else {}
    def get_large_data(sheet_obj):
        if not sheet_obj: return []
        try: vals = sheet_obj.col_values(1)[1:]; return json.loads("".join(vals)) if vals else []
        except: return []
    def get_json_cell(sheet_obj, default_val):
        if not sheet_obj: return default_val
        try: val = sheet_obj.acell('A1').value; return json.loads(val) if val else default_val
        except: return default_val
    return {
        "notice": main_data.get("notice", "오늘 하루도 화이팅! ✨"),
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
        json_str = json.dumps(data_list); chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cell_values = [[chunk] for chunk in chunks]; services[sheet_key].batch_clear(['A2:A'])
        services[sheet_key].update(values=cell_values, range_name='A2', value_input_option='RAW')

def save_main_data():
    save_data_to_cell("main", {"notice": st.session_state.notice, "promises": st.session_state.promises, "moods": st.session_state.moods, "mood_history": st.session_state.mood_history, "current_mood_date": st.session_state.current_mood_date, "menu_list": st.session_state.menu_list})

# ==========================================
# 🔐 자동 로그인
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
        st.text_input("우리만의 비밀번호", type="password", key="pwd_input", on_change=validate_password); return False
    if not st.session_state["current_user"]:
        st.markdown("<h2 style='text-align: center; color: #FF85A2; margin-top: 50px;'>누가 오셨나요? 👀</h2>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👦 수기남자친구", use_container_width=True): st.session_state["current_user"] = "수기남자친구"; st.query_params["auth"] = "hodl"; st.rerun()
        with c2:
            if st.button("👧 수기", use_container_width=True): st.session_state["current_user"] = "수기"; st.query_params["auth"] = "sugi"; st.rerun()
        return False
    return True

if check_login_and_user():
    user_name_only = st.session_state["current_user"]
    if 'data_loaded' not in st.session_state:
        saved = load_data()
        for k, v in saved.items(): st.session_state[k] = v
        st.session_state['data_loaded'] = True; st.session_state.photo_limit = 20; st.session_state.memo_limit = 10; st.session_state.review_limit = 10; st.session_state.photo_cart = []
        if st.session_state.current_mood_date != today_str: st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}; st.session_state.current_mood_date = today_str; save_main_data()

    # 🎨 [디자인 고정] 24시간 파스텔 테마 및 명도 가독성 확보
    bg_color = "#FFF5F7" if user_name_only == "수기" else "#E3F2FD"
    accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"
    text_color = "#333333"

    st.markdown(f"""
        <div class="custom-bg-layer" style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:{bg_color}; z-index:-99999; pointer-events:none;"></div>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, p, h1, h2, h3, h4, h5, h6, label, button, input, textarea, select, div[data-testid="stMetricValue"], .stMarkdown, .stText {{ font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important; }}
        .stApp {{ background: transparent !important; }}
        input, textarea, select {{ background-color: rgba(255,255,255,0.9) !important; color: #000000 !important; border: 1px solid rgba(0,0,0,0.1) !important; }}
        div[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ background-color: rgba(255,255,255,0.6) !important; border-right: 1px solid rgba(0,0,0,0.05) !important; }}
        .card, [data-testid="stExpander"] {{ background: rgba(255,255,255,0.5) !important; backdrop-filter: blur(10px); border-radius: 15px; padding: 15px; margin-bottom: 15px; border-left: 5px solid {accent_color} !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .user-boy {{ border-left:5px solid #4B89FF !important; background:rgba(75,137,255,0.15) !important; text-align: left; }}
        .user-girl {{ border-right:5px solid #FF85A2 !important; background:rgba(255,133,162,0.15) !important; text-align: right; border-left: none !important; }}
        .review-badge {{ background-color: rgba(128,128,128,0.2); padding: 3px 8px; border-radius: 5px; font-size: 0.8rem; margin-right: 5px; color: {text_color}; }}
        .review-comment {{ background-color: rgba(255,255,255,0.8); padding: 8px 12px; border-radius: 8px; margin-top: 5px; border: 1px solid rgba(0,0,0,0.05); }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: rgba(255,255,255,0.9) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important; }}
        </style>
    """, unsafe_allow_html=True)

    # 🚨 [날씨 이모티콘 최적화] 고정 레이어 및 시인성 극대화
    st.markdown(f"<div style='position: fixed; top: 15px; right: 25px; font-size: 2.8rem; z-index: 999999; text-shadow: 2px 2px 4px rgba(0,0,0,0.1);'>{weather_emoji}</div>", unsafe_allow_html=True)

    # ==========================================
    # 🌱 사이드바 완벽 복구
    # ==========================================
    total_act = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    level, tree_icon = ("풍성한 나무", "🍎") if total_act >= 70 else (("아기 나무", "🌳") if total_act >= 30 else (("새싹", "🌿") if total_act >= 10 else ("씨앗", "🌱")))
    
    badges = []
    if len(st.session_state.memo_history) >= 10: badges.append("📝 편지왕")
    if len(st.session_state.reviews) >= 5: badges.append("🍽️ 미슐랭")
    if len(st.session_state.date_schedules) >= 5: badges.append("🗓️ 파워J")
    badge_html = "".join([f"<span style='background:rgba(255,255,255,0.4); padding:4px 8px; border-radius:10px; font-size:0.8em; margin:2px; display:inline-block;'>{b}</span>" for b in badges])

    with st.sidebar:
        st.markdown(f"""<div style="background:rgba(255,255,255,0.4); padding:15px; border-radius:15px; border:2px solid {accent_color}; text-align:center;">
                <h1 style="margin:0;">{tree_icon}</h1><h4 style="margin:5px 0;">사랑나무: {level}</h4>
                <p style="font-size:0.8em; color:gray; margin:0;">포인트: {total_act} XP</p>
                <div style="margin-top:10px;">{badge_html}</div></div>""", unsafe_allow_html=True)
        start_date = datetime.date(2026, 1, 1); days_passed = (now_kst.date() - start_date).days + 1
        st.metric(label="🌸 우리의 D-Day", value=f"D + {days_passed}일")
        st.divider()

        st.markdown("### 📊 월간 수기 백서")
        this_month = now_kst.strftime("%Y-%m")
        m_rev = [r for r in st.session_state.reviews if str(r.get('date','')).startswith(this_month)]
        m_memo = [m for m in st.session_state.memo_history if str(m.get('date','')).startswith(this_month)]
        st.write(f"📅 **{now_kst.month}월 결산**")
        c_s1, c_s2 = st.columns(2)
        c_s1.metric("데이트", f"{len(m_rev)}회"); c_s2.metric("쪽지", f"{len(m_memo)}개")
        
        all_text = " ".join([m.get('content', '') for m in m_memo] + [r.get('comment', '') for r in m_rev])
        words = [w for w in re.findall(r'[가-힣]{2,}', all_text) if len(w) > 1]
        counts = {}
        for w in words: counts[w] = counts.get(w, 0) + 1
        top_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_words:
            st.markdown("**🏷️ 이번 달 많이 쓴 단어**")
            st.caption(" ".join([f"#{w[0]}" for w in top_words]))
        st.divider()

        st.markdown("### 📜 우리의 약속")
        for i, p in enumerate(st.session_state.promises):
            col_p1, col_p2 = st.columns([0.8, 0.2])
            col_p1.write(f"{i+1}. {p['text'] if isinstance(p, dict) else p}")
            if col_p2.button("X", key=f"del_p_{i}"): st.session_state.promises.pop(i); save_main_data(); st.rerun()
        with st.expander("약속 추가하기 ✍️"):
            new_p = st.text_input("새로운 다짐", key="side_p_in")
            if st.button("저장", key="side_p_btn") and new_p: st.session_state.promises.append({"text": new_p, "by": user_name_only}); save_main_data(); st.rerun()
        st.divider()
        if st.button("로그아웃 🚪", use_container_width=True): st.query_params.clear(); st.session_state.clear(); st.rerun()

    # --- 메인 헤더 ---
    col_h1, col_h2 = st.columns([0.85, 0.15])
    col_h1.markdown(f"<h2 style='color: #FF85A2; margin:0;'>♥ 수기 커플 노트</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄 리셋"): st.session_state.clear(); st.rerun()

    st.success(f"📢 {st.session_state.notice}")

    # ==========================================
    # 🚨 9개 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # 1. 💕 데이트
    with tabs[0]:
        qna_list = [
            "1. 우리가 처음 만났던 날, 서로의 첫인상은 어땠어?", "2. 서로에게 가장 반했던 결정적인 순간은 언제야?", "3. 내가 가장 사랑스러워 보일 때는 언제야?", "10. 화났을 때 내 기분을 100% 풀어주는 최고의 방법은?",
            "11. 나에게 들었던 가장 감동적인 말은 무엇이었어?", "15. 싸웠을 때 우리의 암묵적인 룰을 하나 정한다면?", "20. 나를 동물로 표현한다면 어떤 동물이고 이유는 뭐야?", "26. 1년 뒤 오늘, 우리는 어떤 모습으로 무엇을 하고 있을까?"
        ] # (실제 80개 데이터 생략 - 코드 무결성을 위해 구조 유지)
        q_idx = now_kst.toordinal() % len(qna_list); q_key = f"qna_{q_idx}"
        st.session_state.qna_data.setdefault(q_key, {"hodl": "", "sugi": ""})
        
        with st.expander(f"💌 오늘의 문답 (No.{q_idx + 1})", expanded=True):
            st.subheader(qna_list[q_idx])
            ans_b = st.session_state.qna_data[q_key]["hodl"]; ans_g = st.session_state.qna_data[q_key]["sugi"]
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("<div class='user-boy' style='padding:8px; border-radius:8px; margin-bottom:5px;'>👦 <b>수기남자친구</b></div>", unsafe_allow_html=True)
                if user_name_only == "수기남자친구":
                    n_ans_b = st.text_area("작성", value=ans_b, key="q_b", label_visibility="collapsed")
                else:
                    if ans_b and ans_g: st.info(ans_b)
                    elif ans_b and not ans_g: st.success("🔒 상대가 답을 작성했습니다!")
                    else: st.warning("⏳ 아직 작성하지 않았습니다.")
            
            with c2:
                st.markdown("<div class='user-girl' style='padding:8px; border-radius:8px; margin-bottom:5px;'>👩 <b>수기</b></div>", unsafe_allow_html=True)
                if user_name_only == "수기":
                    n_ans_g = st.text_area("작성", value=ans_g, key="q_g", label_visibility="collapsed")
                else:
                    if ans_b and ans_g: st.info(ans_g)
                    elif ans_g and not ans_b: st.success("🔒 상대가 답을 작성했습니다!")
                    else: st.warning("⏳ 아직 작성하지 않았습니다.")

            if st.button("답변 저장 💾"):
                if user_name_only == "수기남자친구": st.session_state.qna_data[q_key]["hodl"] = n_ans_b
                else: st.session_state.qna_data[q_key]["sugi"] = n_ans_g
                save_data_to_cell("qna", st.session_state.qna_data); st.rerun()

        st.divider()
        st.subheader("🎭 오늘 우리의 기분 점수")
        mood_opts = ["😢", "☁️", "🙂", "🥰", "🔥"]
        mood_desc = {"😢": "피곤함/우울", "☁️": "그저그럼", "🙂": "보통/평온", "🥰": "기분좋음", "🔥": "최고/열정!"}
        
        my_mood = st.select_slider(f"{user_name_only}의 기분 선택", options=mood_opts, value=st.session_state.moods.get(user_name_only, "🙂"))
        if st.button("기분 업데이트 ✨"):
            st.session_state.moods[user_name_only] = my_mood
            m_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
            today_rec = next((item for item in st.session_state.mood_history if item["date"] == today_str), None)
            if today_rec: today_rec[f"{user_name_only}_score"] = m_score[my_mood]
            else:
                new_rec = {"date": today_str, "수기남자친구_score": m_score[st.session_state.moods.get("수기남자친구", "🙂")], "수기_score": m_score[st.session_state.moods.get("수기", "🙂")]}
                new_rec[f"{user_name_only}_score"] = m_score[my_mood]
                st.session_state.mood_history.append(new_rec)
            save_main_data(); st.rerun()

        st.markdown(f"👦 **수기남자친구:** {st.session_state.moods.get('수기남자친구','🙂')} ({mood_desc[st.session_state.moods.get('수기남자친구','🙂')]})")
        st.markdown(f"👩 **수기:** {st.session_state.moods.get('수기','🙂')} ({mood_desc[st.session_state.moods.get('수기','🙂')]})")

        if len(st.session_state.mood_history) >= 2:
            df = pd.DataFrame(st.session_state.mood_history).set_index('date')
            if '수기남자친구_score' in df.columns and '수기_score' in df.columns:
                df = df[['수기남자친구_score', '수기_score']]
                df.columns = ['👦 수기남자친구 점수', '👧 수기 점수']
                st.line_chart(df, color=["#4B89FF", "#FF85A2"])

    # 2. 💌 쪽지함 (🚨 1일 1회 업데이트 및 개별 삭제 기능 탑재)
    with tabs[1]:
        st.subheader("💌 오늘의 한마디")
        content = st.text_area("마음 전하기", key="memo_in")
        if st.button("보내기 ✈️") and content:
            existing_idx = -1
            for idx, m in enumerate(st.session_state.memo_history):
                if m.get('date') == today_str and m.get('user') == user_name_only:
                    existing_idx = idx
                    break
            if existing_idx != -1: st.session_state.memo_history[existing_idx]['content'] = content
            else: st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
            save_large_data("memo", st.session_state.memo_history); st.rerun()
            
        for idx, m in enumerate(st.session_state.memo_history[:st.session_state.memo_limit]):
            cls = "user-boy" if "수기남자친구" in m.get('user','') else "user-girl"
            col_m1, col_m2 = st.columns([0.88, 0.12])
            with col_m1:
                st.markdown(f"<div class='card {cls}'><b>{m.get('user','')}</b> | {m.get('date','')}<br>{m.get('content','')}</div>", unsafe_allow_html=True)
            with col_m2:
                if m.get('user') == user_name_only:
                    if st.button("🗑️", key=f"del_memo_{idx}"):
                        st.session_state.memo_history.pop(idx)
                        save_large_data("memo", st.session_state.memo_history); st.rerun()

    # 3. 🌸 텔레파시
    with tabs[2]:
        tele_qs = [["평생 여름", "평생 겨울"], ["찍먹", "부먹"], ["강아지", "고양이"], ["연락 5시간", "여사친과 술"]]
        t_idx = now_kst.toordinal() % len(tele_qs); q_pair = tele_qs[t_idx]
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        ans = st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"]
        c1, c2 = st.columns(2)
        if c1.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[0]; save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        if c2.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
            st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[1]; save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        b_ans = st.session_state.tele_data[today_str].get("hodl"); g_ans = st.session_state.tele_data[today_str].get("sugi")
        if b_ans and g_ans:
            if st.button("🎁 결과 확인!"):
                if b_ans == g_ans: st.balloons(); st.success(f"찌찌뽕! **[{b_ans}]** ❤️")
                else: st.info(f"👦 수기남자친구: {b_ans} / 👧 수기: {g_ans}")

    # 4. 🎵 주크박스
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        if isinstance(st.session_state.jukebox_data, list): st.session_state.jukebox_data = {"hodl": None, "sugi": None}
        yt_safe = "https://www.youtube.com/watch?v="
        with st.form("dj_dual"):
            link = st.text_input("유튜브 링크")
            if st.form_submit_button("신청"):
                st.session_state.jukebox_data["hodl" if user_name_only == "수기남자친구" else "sugi"] = link; save_data_to_cell("jukebox", st.session_state.jukebox_data); st.rerun()
        cb, cg = st.columns(2)
        with cb:
            b_id = extract_youtube_id(st.session_state.jukebox_data.get("hodl", ""))
            if b_id: st.markdown("<div class='user-boy' style='padding:5px; border-radius:5px;'>👦 <b>수기남자친구 Pick</b></div>", unsafe_allow_html=True); st.video(yt_safe + b_id)
        with cg:
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.markdown("<div class='user-girl' style='padding:5px; border-radius:5px;'>👧 <b>수기 Pick</b></div>", unsafe_allow_html=True); st.video(yt_safe + g_id)

    # 5. 📸 추억저장소
    with tabs[4]:
        st.subheader("📸 추억 보관함")
        with st.expander("✨ 새로운 추억 보관하기"):
            mode = st.radio("업로드 방식", ["🍎 아이폰 (여러 장)", "🤖 안드로이드 (장바구니)"], horizontal=True)
            col1, col2 = st.columns([0.4, 0.6])
            ev_d = col1.date_input("날짜", key="ph_d"); ev_n = col2.text_input("제목", key="ph_n")
            if "아이폰" in mode:
                img_fs = st.file_uploader("사진 선택", type=['jpg','png','jpeg'], accept_multiple_files=True)
                if st.button("☁️ 업로드"):
                    if img_fs:
                        for f in img_fs:
                            img = Image.open(f); img = ImageOps.exif_transpose(img)
                            img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                            upload_photo_to_drive(out.getvalue(), f"{ev_d}_{user_name_only}_{ev_n}_{random.randint(1000,9999)}.jpg", "image/jpeg")
                        st.success("완료!"); st.rerun()
            else:
                new_f = st.file_uploader("1장씩 선택", type=['jpg','png','jpeg'], accept_multiple_files=False)
                if st.button("🛒 담기") and new_f: st.session_state.photo_cart.append(new_f.getvalue()); st.rerun()
                if st.session_state.photo_cart:
                    if st.button("☁️ 전송"):
                        for fb in st.session_state.photo_cart:
                            img = Image.open(io.BytesIO(fb)); img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                            upload_photo_to_drive(out.getvalue(), f"{ev_d}_{user_name_only}_{ev_n}_{random.randint(1000,9999)}.jpg", "image/jpeg")
                        st.session_state.photo_cart = []; st.rerun()

        st.divider()
        photos = load_photos_from_drive(st.session_state.photo_limit); grouped_photos = {}
        for p in photos:
            parts = p['name'].split('_')
            key = f"🗓️ {parts[0]} | 📂 {parts[2]}" if len(parts)>=4 else "기타"
            grouped_photos.setdefault(key, []).append(p)
        for k, pl in grouped_photos.items():
            with st.expander(f"{k} ({len(pl)}장)"):
                cols = st.columns(2)
                for idx, p in enumerate(pl):
                    try: img_b = get_image_bytes(p['id']); cols[idx%2].image(img_b, use_container_width=True)
                    except: pass

    # 6. ⏳ 타임라인
    with tabs[5]:
        st.subheader("⏳ 타임라인")
        with st.form("t_form", clear_on_submit=True):
            td = st.date_input("날짜"); te = st.text_input("사건")
            if st.form_submit_button("기록"):
                st.session_state.timeline.insert(0, {"date": str(td), "event": te, "by": user_name_only}); save_large_data("time", st.session_state.timeline); st.rerun()
        for t in st.session_state.timeline: st.markdown(f"<div class='card'><b>{t.get('date','')}</b>: {t.get('event','')}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록
    with tabs[6]:
        st.subheader("📍 위시리스트")
        for i, w in enumerate(st.session_state.wishlist):
            v = w.get('visited', False)
            with st.expander(f"{'✅' if v else '📍'} {w.get('place','')}"):
                if st.checkbox("다녀왔어요!", value=v, key=f"chk_{i}") != v: st.session_state.wishlist[i]['visited'] = not v; save_large_data("wish", st.session_state.wishlist); st.rerun()
        st.divider(); st.subheader("📝 데이트 후기")
        with st.form("r_form"):
            rn = st.text_input("장소명"); rc = st.text_area("내용")
            if st.form_submit_button("등록"):
                st.session_state.reviews.insert(0, {"name": rn, "comment": rc, "date": today_str, "by": user_name_only, "comments": []}); save_large_data("review", st.session_state.reviews); st.rerun()
        for i, r in enumerate(st.session_state.reviews):
            st.markdown(f"<div class='card'><small>{r.get('date','')}</small><br><b>{r.get('name','')}</b><p>{r.get('comment','')}</p></div>", unsafe_allow_html=True)

    # 8. 🎁 타임캡슐
    with tabs[7]:
        st.subheader("🎁 미래의 우리에게")
        with st.form("cap_form"):
            ct = st.text_input("제목"); cd = st.date_input("열어볼 날짜"); cc = st.text_area("내용")
            if st.form_submit_button("묻기"):
                st.session_state.time_capsules.append({"title": ct, "open_date": str(cd), "content": cc, "by": user_name_only}); save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()
        for i, cap in enumerate(st.session_state.time_capsules):
            icon = "🎉" if today_str >= cap.get('open_date','') else "🔒"
            st.warning(f"{icon} {cap.get('title')} ({cap.get('open_date')} 개봉 예정)")

    # 9. 🎡 만능 룰렛
    with tabs[8]:
        st.subheader("🎡 결정장애 해결사")
        with st.form("roulette_form", clear_on_submit=True):
            nm = st.text_input("메뉴 추가"); add = st.form_submit_button("추가")
            if add and nm: st.session_state.menu_list.append(nm); save_main_data(); st.rerun()
        for i, m in enumerate(st.session_state.menu_list):
            c1, c2 = st.columns([0.8, 0.2]); c1.write(f"- {m}")
            if c2.button("❌", key=f"dm_{i}"): st.session_state.menu_list.pop(i); save_main_data(); st.rerun()
        if st.session_state.menu_list and st.button("🎲 룰렛 돌리기!"):
            res = random.choice(st.session_state.menu_list); st.success(f"🎉 오늘의 선택: **{res}** ‼️"); st.balloons()
