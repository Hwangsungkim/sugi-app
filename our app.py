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
# 🌤️ 실시간 날씨 (단 1개의 이모티콘만 깔끔하게 흘러가는 로직)
# ==========================================
@st.cache_data(ttl=3600)
def get_busan_weather():
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

weather_type = get_busan_weather()

def show_weather_effect(w_type):
    # 🚨 단 1개의 구름/햇살만 화면을 가로지르도록 최적화
    if w_type == "cloud":
        effect_css = ".weather-icon { position: fixed; top: 15vh; left: -20vw; font-size: 6em; opacity: 0.6; z-index: -99998; pointer-events: none; animation: cloud_drift 30s linear infinite; } @keyframes cloud_drift { to { transform: translateX(120vw); } }"
        divs = "<div class='weather-icon'>☁️</div>"
    elif w_type == "sun":
        effect_css = ".weather-icon { position: fixed; top: 10vh; left: -20vw; font-size: 6em; opacity: 0.5; z-index: -99998; pointer-events: none; animation: sun_drift 40s linear infinite; } @keyframes sun_drift { to { transform: translateX(120vw) rotate(180deg); } }"
        divs = "<div class='weather-icon'>☀️</div>"
    elif w_type == "rain":
        effect_css = ".weather-icon { position: fixed; top: -10vh; left: 50vw; font-size: 5em; opacity: 0.5; z-index: -99998; pointer-events: none; animation: rain_fall 2s linear infinite; } @keyframes rain_fall { to { transform: translateY(110vh); } }"
        divs = "<div class='weather-icon'>🌧️</div>"
    else:
        effect_css = ".weather-icon { position: fixed; top: -10vh; left: 50vw; font-size: 4em; opacity: 0.6; z-index: -99998; pointer-events: none; animation: snow_fall 5s linear infinite; } @keyframes snow_fall { to { transform: translateY(110vh) translateX(30px); } }"
        divs = "<div class='weather-icon'>❄️</div>"
    st.markdown(f"<style>{effect_css}</style><div aria-hidden='true'>{divs}</div>", unsafe_allow_html=True)

# --- 🍎 아이폰 홈 화면 아이콘 ---
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
    return { "main": safe_ws('시트1'), "memo": safe_ws('쪽지함'), "time": safe_ws('타임라인'), "date": safe_ws('데이트일정'), "wish": safe_ws('위시리스트'), "review": safe_ws('데이트후기'), "qna": safe_ws('문답데이터'), "capsule": safe_ws('타임캡슐데이터'), "tele": safe_ws('텔레파시'), "jukebox": safe_ws('주크박스') }

services = get_sheets()

def extract_youtube_id(url):
    if not url or not isinstance(url, str): return None
    match = re.search(r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else None

DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "")

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
    try: get_drive_service().files().delete(fileId=file_id).execute(); return True
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

    # 🎨 [디자인 고정] 24시간 파스텔 테마
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
        .review-badge {{ background-color: #eee; padding: 3px 8px; border-radius: 5px; font-size: 0.8rem; margin-right: 5px; color: #333; }}
        .review-comment {{ background-color: rgba(255,255,255,0.8); padding: 8px 12px; border-radius: 8px; margin-top: 5px; border: 1px solid rgba(0,0,0,0.05); }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: rgba(255,255,255,0.9) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important; }}
        </style>
    """, unsafe_allow_html=True)

    # 🔥 날씨 이펙트 호출
    show_weather_effect(weather_type)

    # ==========================================
    # 🌱 사이드바 완벽 복구
    # ==========================================
    total_act = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    level, tree_icon = ("풍성한 나무", "🍎") if total_act >= 70 else (("아기 나무", "🌳") if total_act >= 30 else (("새싹", "🌿") if total_act >= 10 else ("씨앗", "🌱")))
    
    with st.sidebar:
        st.markdown(f"""<div style="background:rgba(255,255,255,0.4); padding:15px; border-radius:15px; border:2px solid {accent_color}; text-align:center;">
                <h1 style="margin:0;">{tree_icon}</h1><h4 style="margin:5px 0;">사랑나무: {level}</h4>
                <p style="font-size:0.8em; color:gray; margin:0;">포인트: {total_act} XP</p></div>""", unsafe_allow_html=True)
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
    with st.expander("✏️ 공지 수정"):
        new_notice = st.text_input("공지 내용", value=st.session_state.notice)
        if st.button("공지 확정"): st.session_state.notice = new_notice; save_main_data(); st.rerun()

    # ==========================================
    # 🚨 9개 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # 1. 💕 데이트
    with tabs[0]:
        past_records = [m for m in st.session_state.memo_history if m.get('date', '').endswith(now_kst.strftime("-%m-%d")) and m.get('date') != today_str]
        if past_records:
            st.warning(f"🕰️ **과거에서 온 추억:** 예전 오늘, 이런 마음을 남겼었네요!")
            with st.expander("열어보기"):
                for p in past_records: st.info(f"[{p['date']}] {p['user']}: {p['content']}")

        # 🚨 80개 문답 및 남/여 전용 색상 UI 복구
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
        q_idx = now_kst.toordinal() % 80; q_key = f"qna_{q_idx}"
        st.session_state.qna_data.setdefault(q_key, {"hodl": "", "sugi": ""})
        
        with st.expander(f"💌 오늘의 문답 (No.{q_idx + 1})", expanded=True):
            st.subheader(qna_list[q_idx])
            ans_b = st.session_state.qna_data[q_key]["hodl"]; ans_g = st.session_state.qna_data[q_key]["sugi"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("<div style='background-color:rgba(75,137,255,0.15); padding:10px; border-radius:10px; border-left:5px solid #4B89FF; margin-bottom:10px;'>👦 <b>남친</b></div>", unsafe_allow_html=True)
                if user_name_only == "수기남자친구": n_ans_b = st.text_area("작성", value=ans_b, key="q_b", label_visibility="collapsed")
                else: st.info(ans_b if (ans_b and ans_g) else "🔒 작성 대기 중")
            with c2:
                st.markdown("<div style='background-color:rgba(255,133,162,0.15); padding:10px; border-radius:10px; border-right:5px solid #FF85A2; text-align:right; margin-bottom:10px;'>👩 <b>수기</b></div>", unsafe_allow_html=True)
                if user_name_only == "수기": n_ans_g = st.text_area("작성", value=ans_g, key="q_g", label_visibility="collapsed")
                else: st.info(ans_g if (ans_b and ans_g) else "🔒 작성 대기 중")
            if st.button("답변 저장 💾"):
                if user_name_only == "수기남자친구": st.session_state.qna_data[q_key]["hodl"] = n_ans_b
                else: st.session_state.qna_data[q_key]["sugi"] = n_ans_g
                save_data_to_cell("qna", st.session_state.qna_data); st.rerun()

        st.divider()
        # 🚨 기분 요약 텍스트 및 차트 색상 반전 에러 완벽 해결
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

        b_md = st.session_state.moods.get('수기남자친구', '🙂')
        g_md = st.session_state.moods.get('수기', '🙂')
        st.markdown(f"<div class='card user-boy'>👦 <b>수기남자친구:</b> {b_md} ({mood_desc[b_md]})</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card user-girl'>👩 <b>수기:</b> {g_md} ({mood_desc[g_md]})</div>", unsafe_allow_html=True)

        if len(st.session_state.mood_history) >= 2:
            df = pd.DataFrame(st.session_state.mood_history).set_index('date')
            if '수기남자친구_score' in df.columns and '수기_score' in df.columns:
                df = df[['수기남자친구_score', '수기_score']] # 🚨 순서 강제 고정으로 색상 꼬임 방지
                df.columns = ['👦 남친 점수', '👧 수기 점수']
                st.line_chart(df, color=["#4B89FF", "#FF85A2"]) # 파랑, 분홍 정확히 매핑
        
        st.divider()
        st.subheader("🗓️ 데이트 일정")
        with st.form("sch_form", clear_on_submit=True):
            sd = st.date_input("날짜"); sp = st.text_input("어디서 무얼 할까요?")
            if st.form_submit_button("일정 추가") and sp:
                st.session_state.date_schedules.append({"date": str(sd), "plan": sp, "by": user_name_only}); save_large_data("date", st.session_state.date_schedules); st.rerun()
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 {s['date']} {s['plan']}"):
                if st.button("삭제", key=f"ds_{i}"): st.session_state.date_schedules.pop(i); save_large_data("date", st.session_state.date_schedules); st.rerun()

    # 2. 💌 쪽지함
    with tabs[1]:
        st.subheader("💌 오늘의 한마디")
        content = st.text_area("마음 전하기", key="memo_in")
        if st.button("보내기 ✈️") and content:
            st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
            save_large_data("memo", st.session_state.memo_history); st.rerun()
        for m in st.session_state.memo_history[:st.session_state.memo_limit]:
            cls = "user-boy" if "남자친구" in m.get('user','') else "user-girl"
            st.markdown(f"<div class='card {cls}'><b>{m.get('user','')}</b> | {m.get('date','')}<br>{m.get('content','')}</div>", unsafe_allow_html=True)
        if len(st.session_state.memo_history) > st.session_state.memo_limit:
            if st.button("더 보기 ⬇️"): st.session_state.memo_limit += 10; st.rerun()

    # 3. 🌸 텔레파시 100제
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시")
        tele_qs = [
            ["평생 여름", "평생 겨울"], ["카레맛 똥", "똥맛 카레"], ["찍먹", "부먹"], ["강아지", "고양이"], ["연락 5시간 안됨", "여사친과 단둘이 밥"], ["월 200 백수", "월 1000 주100시간"], ["평생 안씻기", "평생 양치안하기"], ["투명인간", "하늘날기"], ["좋아하는 사람", "나를 좋아하는 사람"], ["넷플릭스", "아웃도어"],
            ["고기 안먹기", "밀가루 안먹기"], ["찬물 샤워", "뜨거운 물"], ["미남미녀", "천재"], ["스몰웨딩", "호텔예식"], ["무인도 1박", "흉가 1박"], ["라면만 먹기", "치킨만 먹기"], ["내 흑역사 보여주기", "애인 흑역사 보기"], ["환승이별", "잠수이별"], ["과거보는 연인", "미래보는 연인"], ["에어컨 없이", "보일러 없이"],
            ["바퀴벌레 먹고 10억", "안먹고 안받기"], ["기억 모두 잃은 애인", "나만 잃은 애인"], ["당첨금 혼자", "반반 나누기"], ["스마트폰 없이", "컴퓨터 없이"], ["폰 맡기기", "폰 보기"], ["싸우면 당장풀기", "시간갖기"], ["이성친구랑 커피", "이성친구랑 술"], ["낮만 있기", "밤만 있기"], ["애인 빚 10억", "내 빚 10억"], ["매운것만", "단것만"],
            ["돈많고 바쁜 애인", "돈없고 항상같이"], ["내가 더 사랑", "더 사랑받는"], ["내생각 읽히기", "내가 생각읽기"], ["지문등록 필수", "선택"], ["비싼선물", "정성편지"], ["콜라", "커피"], ["하루종일 집", "하루종일 밖"], ["로맨스", "액션"], ["유럽여행", "휴양지"], ["애교로 풀기", "논리적 대화"],
            ["방귀냄새 최악", "코골이 최악"], ["수영", "헬스"], ["동거 찬성", "반대"], ["통장 각자", "전담"], ["딩크", "자녀2명"], ["게임", "독서"], ["져주는편", "이기는편"], ["사랑해", "고마워"], ["과거 다알기", "전혀 모르기"], ["봄", "가을"],
            ["놀이공원 교복", "호캉스"], ["공공장소 스킨십", "절대불가"], ["주사 잠자기", "울기"], ["검정옷", "하양옷"], ["커플반지", "커플티"], ["10분연락", "하루한번"], ["선의거짓말 용서", "절대불가"], ["떡볶이", "초밥"], ["배낭여행", "호캉스"], ["남사친여사친 불가", "선지키면가능"],
            ["아이돌덕질", "애니덕질"], ["소주", "맥주"], ["등산", "베이킹"], ["극단적편식", "뭐든잘먹음"], ["짠돌이", "욜로"], ["유튜브", "넷플릭스"], ["협동게임", "경쟁게임"], ["장발", "단발"], ["마른체형", "근육질체형"], ["치킨", "족발"],
            ["카페알바", "단기알바"], ["이갈기", "잠꼬대"], ["난폭운전", "초보운전"], ["비누향", "머스크향"], ["테니스", "볼링"], ["스트릿패션", "수트오피스룩"], ["손목작은타투", "등에큰타투"], ["아이스크림", "과자"], ["댄스챌린지", "먹방챌린지"], ["비공개계정", "인플루언서"],
            ["극E", "극I"], ["수박", "딸기"], ["캐릭터팝업", "패션팝업"], ["요리 셰프급", "라면도못끓임"], ["결벽증", "돼지우리"], ["크루아상", "소금빵"], ["원데이클래스", "장기클래스"], ["정치반대", "관심없음"], ["종교반대", "무교"], ["짜장면", "파스타"],
            ["미술전시", "미디어아트"], ["욕설", "줄임말"], ["이름저장안함", "이상하게저장"], ["돼지고기", "소고기"], ["뮤직페스티벌", "맥주축제"], ["뱀키우기", "거미키우기"], ["노래", "춤"], ["매일야근", "매일회식"], ["카톡만", "전화만"], ["10억받고 헤어지기", "그냥 계속 사귀기"]
        ]
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
            if st.button("🎁 결과 확인 (풍선 팡!)", use_container_width=True):
                if b_ans == g_ans: st.balloons(); st.success(f"찌찌뽕! **[{b_ans}]** ❤️")
                else: st.info(f"👦 남친: {b_ans} / 👧 수기: {g_ans}")

    # 4. 🎵 주크박스 (듀얼 채널 원상 복구)
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
            if b_id: st.markdown("👦 **남친 Pick**"); st.video(yt_safe + b_id)
        with cg:
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.markdown("👧 **수기 Pick**"); st.video(yt_safe + g_id)

    # 5. 📸 추억저장소 (아이폰 다중 선택 / 갤럭시 장바구니 듀얼 시스템)
    with tabs[4]:
        st.subheader("📸 추억 보관함")
        with st.expander("✨ 새로운 추억 보관하기"):
            mode = st.radio("업로드 방식", ["🍎 아이폰 (여러 장 한 번에)", "🤖 안드로이드 (1장씩 장바구니)"], horizontal=True)
            col_a, col_b = st.columns([0.4, 0.6])
            ev_d = col_a.date_input("날짜", key="ph_d")
            ev_n = col_b.text_input("제목", placeholder="예: 해운대 바다", key="ph_n")
            
            if "아이폰" in mode:
                img_fs = st.file_uploader("사진을 여러 장 쭈욱 선택하세요", type=['jpg','png','jpeg'], accept_multiple_files=True)
                if st.button("☁️ 한 번에 업로드", use_container_width=True):
                    if img_fs:
                        with st.spinner("드라이브로 전송 중..."):
                            for f in img_fs:
                                try:
                                    img = Image.open(f); img = ImageOps.exif_transpose(img)
                                    img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                                    safe_name = f"{ev_d}_{user_name_only}_{ev_n}_{random.randint(1000,9999)}.jpg"
                                    upload_photo_to_drive(out.getvalue(), safe_name, "image/jpeg")
                                except: pass
                            st.success("업로드 완료!"); st.rerun()
            else:
                new_f = st.file_uploader("1장씩 고르기", type=['jpg','png','jpeg'], accept_multiple_files=False)
                if st.button("🛒 장바구니 담기") and new_f:
                    st.session_state.photo_cart.append(new_f.getvalue()); st.toast("🛒 담김!"); st.rerun()
                if st.session_state.photo_cart:
                    st.info(f"현재 {len(st.session_state.photo_cart)}장 대기 중")
                    if st.button("☁️ 장바구니 모두 전송", use_container_width=True):
                        with st.spinner("전송 중..."):
                            for fb in st.session_state.photo_cart:
                                img = Image.open(io.BytesIO(fb)); img.thumbnail((1920, 1920)); out = io.BytesIO(); img.save(out, format="JPEG", quality=85)
                                safe_name = f"{ev_d}_{user_name_only}_{ev_n}_{random.randint(1000,9999)}.jpg"
                                upload_photo_to_drive(out.getvalue(), safe_name, "image/jpeg")
                            st.session_state.photo_cart = []; st.rerun()

        st.divider()
        photos = load_photos_from_drive(st.session_state.photo_limit)
        grouped = {}
        for p in photos:
            pts = p['name'].split('_'); key = f"🗓️ {pts[0]} | 📂 {pts[2]}" if len(pts)>=3 else "기록 없는 추억"
            grouped.setdefault(key, []).append(p)
        for k, pl in grouped.items():
            with st.expander(f"{k} ({len(pl)}장)"):
                cols = st.columns(2)
                for idx, p in enumerate(pl):
                    try:
                        img_b = get_image_bytes(p['id'])
                        cols[idx%2].image(img_b, use_container_width=True)
                        if cols[idx%2].button("🗑️ 삭제", key=f"del_{p['id']}"):
                            if delete_photo_from_drive(p['id']): st.rerun()
                    except: pass
        if len(photos) >= st.session_state.photo_limit:
            if st.button("⬇️ 과거 사진 더 보기"): st.session_state.photo_limit += 20; st.rerun()

    # 6. ⏳ 타임라인
    with tabs[5]:
        st.subheader("⏳ 타임라인")
        with st.form("t_form", clear_on_submit=True):
            td = st.date_input("날짜"); te = st.text_input("사건")
            if st.form_submit_button("기록"):
                st.session_state.timeline.insert(0, {"date": str(td), "event": te, "by": user_name_only}); save_large_data("time", st.session_state.timeline); st.rerun()
        for t in st.session_state.timeline:
            st.markdown(f"<div class='card'><b>{t.get('date','')}</b>: {t.get('event','')}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록 (🚨 UI 및 대댓글 시스템 완벽 복원)
    with tabs[6]:
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form"):
            wp = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가"):
                st.session_state.wishlist.append({"place": wp, "visited": False, "by": user_name_only}); save_large_data("wish", st.session_state.wishlist); st.rerun()
        for i, w in enumerate(st.session_state.wishlist):
            v = w.get('visited', False)
            with st.expander(f"{'✅' if v else '📍'} {w.get('place','')}"):
                if st.checkbox("다녀왔어요!", value=v, key=f"chk_{i}") != v:
                    st.session_state.wishlist[i]['visited'] = not v; save_large_data("wish", st.session_state.wishlist); st.rerun()
                if st.button("삭제", key=f"del_w_{i}"):
                    st.session_state.wishlist.pop(i); save_large_data("wish", st.session_state.wishlist); st.rerun()
        
        st.divider()
        st.subheader("📝 데이트 후기")
        with st.form("r_form", clear_on_submit=True):
            r_date = st.date_input("방문 날짜 🗓️", value=now_kst.date())
            r_name = st.text_input("장소명 📍")
            r_cat = st.selectbox("종류 🏷️", ["음식점", "카페", "공원", "기타"])
            r_rating = st.selectbox("별점 ⭐", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
            r_comment = st.text_area("후기 내용 📝")
            if st.form_submit_button("후기 등록"):
                st.session_state.reviews.insert(0, {"name": r_name, "cat": r_cat, "rating": r_rating, "comment": r_comment, "date": str(r_date), "by": user_name_only, "comments": []})
                save_large_data("review", st.session_state.reviews); st.rerun()
        
        for i, r in enumerate(st.session_state.reviews):
            with st.container():
                st.markdown(f"""
                    <div class='card'>
                        <div style='display:flex; justify-content:space-between;'>
                            <span class='review-badge'>{r.get('cat','기타')}</span>
                            <span style='color:gray; font-size:0.8em;'>{r.get('date','')} by {r.get('by','')}</span>
                        </div>
                        <h4 style='margin:10px 0 5px 0;'>{r.get('name','')} {r.get('rating','')}</h4>
                        <p>{r.get('comment','')}</p>
                    </div>
                """, unsafe_allow_html=True)
                for c_idx, c in enumerate(r.setdefault("comments", [])):
                    st.markdown(f"<div class='review-comment'><b>{c.get('user')}</b>: {c.get('text')}</div>", unsafe_allow_html=True)
                    if c.get('user') == user_name_only:
                        if st.button("❌ 내 댓글 삭제", key=f"dc_{i}_{c_idx}"):
                            r["comments"].pop(c_idx); save_large_data("review", st.session_state.reviews); st.rerun()
                
                with st.expander("💬 댓글 남기기 / 원본 관리"):
                    nc = st.text_input("댓글 쓰기", key=f"nc_{i}")
                    if st.button("전송", key=f"nb_{i}"):
                        r["comments"].append({"user": user_name_only, "text": nc}); save_large_data("review", st.session_state.reviews); st.rerun()
                    if r.get('by') == user_name_only:
                        if st.button("🗑️ 후기 원본 삭제", key=f"rb_{i}"):
                            st.session_state.reviews.pop(i); save_large_data("review", st.session_state.reviews); st.rerun()

    # 8. 🎁 타임캡슐
    with tabs[7]:
        st.subheader("🎁 미래의 우리에게")
        with st.form("cap_form"):
            ct = st.text_input("제목"); cd = st.date_input("열어볼 날짜", min_value=now_kst.date() + datetime.timedelta(days=1)); cc = st.text_area("내용")
            if st.form_submit_button("⛏️ 묻기"):
                st.session_state.time_capsules.append({"title": ct, "open_date": str(cd), "content": cc, "by": user_name_only}); save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()
        for i, cap in enumerate(st.session_state.time_capsules):
            if today_str >= cap.get('open_date', ''):
                with st.expander(f"🎉 [열림] {cap.get('title')}"):
                    st.write(cap.get('content'))
                    if st.button("🗑️ 삭제", key=f"del_cap_{i}"): st.session_state.time_capsules.pop(i); save_data_to_cell("capsule", st.session_state.time_capsules); st.rerun()
            else:
                st.warning(f"🔒 [잠김] {cap.get('title')} ({cap.get('open_date')} 개봉 예정)")

    # 9. 🎡 만능 룰렛 (🚨 스피너 딜레이 및 폭죽 로직 완전 복구)
    with tabs[8]:
        st.subheader("🎡 결정장애 해결사")
        opts = st.text_input("선택지를 쉼표(,)로 구분해서 적어주세요", placeholder="예: 마라탕, 초밥, 삼겹살")
        if st.button("🎲 룰렛 돌리기!", use_container_width=True) and opts:
            with st.spinner("두구두구두구... 🎲"):
                time.sleep(1.5)
            st.success(f"🎉 오늘의 선택: **{random.choice([o.strip() for o in opts.split(',') if o.strip()])}** ‼️")
            st.balloons()
