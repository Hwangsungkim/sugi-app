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
# ⚡️ 데이터 엔진 (청크 분산 처리 & 방어막 시스템 유지)
# ==========================================
def get_chunked_data(sheet_obj, default_val):
    if not sheet_obj: return default_val
    try:
        vals = sheet_obj.col_values(1)
        if not vals: return default_val
        if len(vals) > 1 and (vals[1].startswith('{') or vals[1].startswith('[')):
            return json.loads("".join(vals[1:]))
        if vals[0].startswith('{') or vals[0].startswith('['):
            return json.loads(vals[0])
        return default_val
    except: return default_val

def save_large_data(sheet_key, data):
    if services and services.get(sheet_key):
        json_str = json.dumps(data)
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cell_values = [[chunk] for chunk in chunks]
        services[sheet_key].batch_clear(['A2:A'])
        services[sheet_key].update(values=cell_values, range_name='A2', value_input_option='RAW')

def load_data():
    main_data = get_chunked_data(services["main"], {})
    return {
        "notice": main_data.get("notice", "오늘 하루도 화이팅! ✨"),
        "promises": main_data.get("promises", [{"text": "서운한 건 그날 바로 말하기 🗣️", "by": "수기남자친구"}]),
        "moods": main_data.get("moods", {"수기남자친구": "🙂", "수기": "🙂"}),
        "mood_history": main_data.get("mood_history", []),
        "current_mood_date": main_data.get("current_mood_date", today_str),
        "menu_list": main_data.get("menu_list", ["삼겹살", "초밥"]),
        "memo_history": get_chunked_data(services["memo"], []),
        "timeline": get_chunked_data(services["time"], []),
        "date_schedules": get_chunked_data(services["date"], []),
        "wishlist": get_chunked_data(services["wish"], []),
        "reviews": get_chunked_data(services["review"], []),
        "qna_data": get_chunked_data(services["qna"], {}),
        "time_capsules": get_chunked_data(services["capsule"], []),
        "tele_data": get_chunked_data(services["tele"], {}),
        "jukebox_data": get_chunked_data(services["jukebox"], {"hodl": None, "sugi": None})
    }

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
        if st.session_state.current_mood_date != today_str: 
            st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}
            st.session_state.current_mood_date = today_str
            rm = get_chunked_data(services["main"], {})
            rm["moods"] = st.session_state.moods
            rm["current_mood_date"] = today_str
            save_large_data("main", rm)

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
        .review-badge {{ background-color: rgba(128,128,128,0.2); padding: 3px 8px; border-radius: 5px; font-size: 0.8rem; margin-right: 5px; color: {text_color}; }}
        .review-comment {{ background-color: rgba(255,255,255,0.8); padding: 8px 12px; border-radius: 8px; margin-top: 5px; border: 1px solid rgba(0,0,0,0.05); }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: rgba(255,255,255,0.9) !important; color: {text_color} !important; border: 1px solid rgba(0,0,0,0.1) !important; }}
        </style>
    """, unsafe_allow_html=True)

    # 🚨 날씨 이모티콘 최상단 우측 고정
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
            if col_p2.button("X", key=f"del_p_{i}"): 
                target_p_text = p['text'] if isinstance(p, dict) else p
                rm = get_chunked_data(services["main"], {})
                rp = rm.get("promises", [])
                for idx, rem_p in enumerate(rp):
                    rem_p_text = rem_p['text'] if isinstance(rem_p, dict) else rem_p
                    if rem_p_text == target_p_text:
                        rp.pop(idx); break
                rm["promises"] = rp; st.session_state.promises = rp
                save_large_data("main", rm); st.rerun()
                
        with st.expander("약속 추가하기 ✍️"):
            new_p = st.text_input("새로운 다짐", key="side_p_in")
            if st.button("저장", key="side_p_btn") and new_p: 
                rm = get_chunked_data(services["main"], {})
                rp = rm.get("promises", [])
                rp.append({"text": new_p, "by": user_name_only})
                rm["promises"] = rp; st.session_state.promises = rp
                save_large_data("main", rm); st.rerun()
        st.divider()
        if st.button("로그아웃 🚪", use_container_width=True): st.query_params.clear(); st.session_state.clear(); st.rerun()

    # --- 메인 헤더 ---
    col_h1, col_h2 = st.columns([0.85, 0.15])
    col_h1.markdown(f"<h2 style='color: #FF85A2; margin:0;'>♥ 수기 커플 노트</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄 리셋"): st.session_state.clear(); st.rerun()

    st.success(f"📢 {st.session_state.notice}")
    with st.expander("✏️ 공지 수정"):
        new_notice = st.text_input("공지 내용", value=st.session_state.notice)
        if st.button("공지 확정"): 
            rm = get_chunked_data(services["main"], {})
            rm["notice"] = new_notice; st.session_state.notice = new_notice
            save_large_data("main", rm); st.rerun()

    # ==========================================
    # 🚨 9개 탭 구성 (시즌 2 문답 & 텔레파시 업데이트 완료)
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "⏳ 타임라인", "📍 장소/기록", "🎁 타임캡슐", "🎡 만능룰렛"])

    # 1. 💕 데이트
    with tabs[0]:
        past_records = [m for m in st.session_state.memo_history if m.get('date', '').endswith(now_kst.strftime("-%m-%d")) and m.get('date') != today_str]
        if past_records:
            st.warning(f"🕰️ **과거에서 온 추억:** 예전 오늘, 이런 마음을 남겼었네요!")
            with st.expander("열어보기"):
                for p in past_records: st.info(f"[{p['date']}] {p['user']}: {p['content']}")

        # 🚨 [문답 시즌 2] 1번 ~ 160번 전면 확장 데이터 (기존 기록 100% 보존)
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
            "76. 나랑 같이 꼭 타보고 싶은 놀이기구는?", "77. 나의 어떤 점이 가장 든든하고 의지가 돼?", "78. 나랑 같이 꼭 해보고 싶은 봉사활동이나 의미 있는 일은?", "79. 만약 내가 연예인이 된다면 어떤 반응을 보일 거야?", "80. 지금 이 순간, 나한테 가장 해주고 싶은 짧은 한마디는?",
            
            # --- 여기서부터 시즌 2 (81~160) ---
            "81. 우리가 함께 살 집을 꾸민다면 가장 공들이고 싶은 공간은 어디야?", "82. 상대방을 생각할 때 떠오르는 나만의 소울푸드가 있다면?", "83. 주말 아침에 눈을 떴을 때 가장 먼저 같이 하고 싶은 일은?", "84. 우리가 처음으로 같이 1박 이상 여행을 갔던 날, 가장 기억에 남는 장면은?", "85. 스트레스를 너무 많이 받은 날, 내가 너에게 어떻게 해줬으면 좋겠어?",
            "86. 나를 만나기 전과 후, 스스로 생각하기에 가장 크게 달라진 점은 뭐야?", "87. 우리가 만약 예능 프로그램에 나간다면 어떤 성격의 커플로 비칠까?", "88. 나 몰래 준비하다가 들킬 뻔했던 깜찍한 일화가 있다면?", "89. 나의 스킨십 중 '이건 진짜 반칙이다' 싶을 정도로 설레는 행동은?", "90. 우리가 길에서 우연히 옛날 친구를 만난다면 나를 어떻게 소개할 거야?",
            "91. 100억 로또에 당첨된다면 우리의 첫 번째 플렉스는 무엇일까?", "92. 살면서 서로에게 절대 들키고 싶지 않은 아주 사소한 비밀이 있다면?", "93. 만약 우리가 타임머신을 타고 과거로 돌아간다면 언제로 가서 뭘 하고 싶어?", "94. 나를 보면서 '이 사람은 진짜 내 편이구나'라고 뼛속 깊이 느꼈던 순간은?", "95. 내가 평소에 자주 쓰는 말이나 입버릇 중에 가장 귀엽다고 생각하는 건?",
            "96. 서로의 경제관념(돈 쓰는 방식)에 대해 솔직하게 어떻게 생각해?", "97. 우리가 나중에 강아지나 고양이를 키운다면 이름을 뭐라고 짓고 싶어?", "98. 상대방이 가장 섹시해 보이는 찰나의 표정이나 눈빛은?", "99. 지금까지 함께 찍은 사진 중 당장 액자로 뽑아서 걸어두고 싶은 사진은?", "100. 나랑 같이 밤새 술 마시면서 허심탄회하게 털어놓고 싶은 이야기가 있다면?",
            "101. 우리가 아무리 바빠도 이것만큼은 서로의 일상에서 포기하지 말자고 정할 것은?", "102. 내가 아주 가끔 미워 보일 때, 그걸 어떻게 속으로 삭이고 넘겨?", "103. 상대방의 이름 삼행시로 세상에서 가장 달콤하게 마음을 표현해 본다면?", "104. 우리가 비행기를 타고 10시간 이상 가야 하는 곳으로 떠난다면 기내에서 뭘 할까?", "105. 나를 처음 봤을 때 속으로 했던 아주 솔직한 평가(점수)는 몇 점이었어?",
            "106. 살면서 가장 크게 울었던 날, 내 존재가 너에게 어떤 의미였어?", "107. 만약 내가 어느 날 짐을 싹 다 싸서 도망치자고 한다면 군말 없이 따라와 줄 거야?", "108. 나한테 가장 듣고 싶은 애칭이나 호칭이 있다면 뭐야?", "109. 서로의 부모님을 처음 뵈었을 때(혹은 뵐 때) 가장 떨렸던/떨릴 것 같은 포인트는?", "110. 내가 해주는 마사지나 안마 중에 제일 피로가 풀리는 부위는?",
            "111. 만약 내가 며칠 동안 아파서 누워있다면 나를 위해 뭘 해줄 수 있어?", "112. 상대방의 핸드폰에 내 번호를 다시 저장할 수 있다면 뭐라고 저장하고 싶어?", "113. 우리 연애의 '명장면'을 딱 하나만 꼽아서 영화 포스터로 만든다면?", "114. 만약 우리가 지금 당장 차를 끌고 야간 드라이브를 간다면 틀고 싶은 노래는?", "115. 서로의 취향 중 도저히 이해가 안 되지만 사랑으로 품어주는 것은?",
            "116. 내가 아주 어릴 적 꼬마였을 때 내 모습을 직접 본다면 어떨 것 같아?", "117. 우리가 만약 사극 시대(조선시대)에 태어났다면 우리는 어떤 신분의 커플이었을까?", "118. 나에게 꼭 추천해주고 싶은 인생 책이나 인생 영화가 있다면?", "119. 살면서 나랑 꼭 한 번쯤은 미친 척하고 일탈해보고 싶은 것이 있다면?", "120. 내가 너의 자존감을 가장 팍팍 올려주었던 칭찬 한마디는 뭐야?",
            "121. 나의 신체 부위 중 네가 가장 매력을 느끼고 좋아하는 곳은?", "122. 평범한 일상 속에서 '아, 이 사람이랑 결혼하고 싶다'고 문득 느꼈던 순간은?", "123. 우리가 만약 다이어트를 같이 한다면 성공할 수 있을까? 아니면 야식의 유혹에 질까?", "124. 상대방이 술에 취해서 한 행동 중 가장 어이없었지만 웃겼던 것은?", "125. 나랑 평생 딱 한 가지 메뉴만 시켜 먹을 수 있다면 무엇을 고를 거야?",
            "126. 내가 가장 열정적으로 일하거나 무언가에 집중할 때, 옆에서 보면 어때?", "127. 만약 내일 당장 지구가 멸망한다면, 오늘 하루 나랑 뭐하면서 보낼 거야?", "128. 서로의 단점이나 약점을 감싸주면서 느꼈던 뭉클한 감정이 있다면?", "129. 내가 너에게 보냈던 수많은 카톡 중에 가장 설레서 캡처해두고 싶었던 문구는?", "130. 우리의 50주년 기념일에는 어디서 뭘 하면서 축하하고 있을까?",
            "131. 우리가 만약 나중에 아이를 낳는다면, 나를 닮았으면 하는 부분과 너를 닮았으면 하는 부분은?", "132. 내가 평소에 입는 옷 스타일 중 '이건 앞으로도 계속 입어줬으면 좋겠다' 하는 것은?", "133. 만약 내가 갑자기 유튜브를 시작하겠다고 하면 어떤 콘텐츠를 추천해 줄 거야?", "134. 둘이서만 아는 아주 웃긴 비밀 은어/암호가 있다면 만들어볼까?", "135. 상대방의 냄새를 가장 깊이 맡을 수 있는 포옹 타이밍은 언제야?",
            "136. 내가 만약 100만 유튜버나 연예인으로 유명해진다면, 너는 뒤에서 어떻게 지지해 줄 거야?", "137. 가장 좋아하는 데이트 시간대(아침, 점심, 초저녁, 늦은 밤, 새벽)와 그 이유는?", "138. 나랑 같이 늙어간다는 것을 상상할 때 가장 기대되는 포근한 장면은?", "139. 서로의 입술이 닿기 직전 1초, 그 짧은 찰나에 드는 생각은 뭐야?", "140. 내가 너한테 서운하게 했을 때, 그걸 말하기 전에 혼자서 어떤 생각을 해?",
            "141. 우리가 만약 캠핑을 가서 텐트 안에 단둘이 누워있다면 무슨 대화를 나눌까?", "142. 상대방의 매력 포인트 3가지를 지금 당장 5초 안에 말해본다면?", "143. 내가 너를 생각하면서 혼자 몰래 미소 지었던 적이 있다면 언제일 것 같아?", "144. 둘이서만 조용히 걷기 좋은 밤 산책 코스를 하나만 꼽는다면?", "145. 내 목소리가 가장 달콤하게 들렸던 때는 전화 통화할 때야, 아니면 바로 옆에서 말할 때야?",
            "146. 만약 우리가 며칠 동안 크게 다투고 연락을 안 한다면, 너는 어떤 마음으로 나를 기다릴까?", "147. 내가 가장 좋아하는 너의 사소한 습관이나 버릇이 있다면 뭔지 알아?", "148. 우리가 함께 찍은 동영상 중 가장 많이 돌려본 영상은 뭐야?", "149. 상대방에게 절대 상처 주고 싶지 않아서 꾹 참았던 말이 혹시 있다면?", "150. 나랑 같이 요리를 한다면 내가 어떤 역할을 맡아주면 좋겠어?",
            "151. 내가 만약 힘든 일로 좌절해서 엉엉 울고 있다면 나를 어떻게 달래줄 거야?", "152. 서로의 눈을 1분 동안 아무 말 없이 빤히 쳐다본다면 누가 먼저 부끄러워서 웃을까?", "153. 나를 위해 기꺼이 희생할 수 있다고 느꼈던 진심 어린 순간이 있어?", "154. 우리가 처음으로 같이 맞이했던 생일이나 기념일에 서로 어떤 기분이었어?", "155. 상대방의 온기가 가장 그립고 보고 싶을 때는 언제야?",
            "156. 내가 너의 머리를 쓰다듬어 주거나 등을 토닥여 줄 때 어떤 기분이 들어?", "157. 만약 우리가 하루 동안 스마트폰 없이 데이트를 한다면 짜증이 날까, 아니면 더 좋을까?", "158. 나에게 꼭 받아보고 싶은 깜짝 이벤트나 프로포즈 로망이 있다면?", "159. 지금까지 우리가 함께한 모든 날을 한 문장으로 요약한다면?", "160. 다음 1년 동안 나랑 꼭 이루고 싶은 우리만의 버킷리스트 1위는 뭐야?"
        ]
        
        # 🚨 [시즌 2 트리거 로직] - 내일(2026-06-06)부터 정확히 81번(index 80)으로 시작되도록 핀셋 교정
        season2_start_ord = datetime.date(2026, 6, 6).toordinal()
        today_ord = now_kst.toordinal()
        if today_ord >= season2_start_ord:
            q_idx = 80 + ((today_ord - season2_start_ord) % 80) # 80~159 루프
        else:
            q_idx = today_ord % 80 # 오늘까지는 원래의 루프 (13번 등) 유지
            
        q_key = f"qna_{q_idx}"
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
                remote_qna = get_chunked_data(services["qna"], {})
                if q_key not in remote_qna: remote_qna[q_key] = {"hodl": "", "sugi": ""}
                if user_name_only == "수기남자친구": remote_qna[q_key]["hodl"] = n_ans_b
                else: remote_qna[q_key]["sugi"] = n_ans_g
                st.session_state.qna_data = remote_qna
                save_large_data("qna", remote_qna)
                st.rerun()

        st.divider()
        st.subheader("🎭 오늘 우리의 기분 점수")
        mood_opts = ["😢", "☁️", "🙂", "🥰", "🔥"]
        mood_desc = {"😢": "피곤함/우울", "☁️": "그저그럼", "🙂": "보통/평온", "🥰": "기분좋음", "🔥": "최고/열정!"}
        
        my_mood = st.select_slider(f"{user_name_only}의 기분 선택", options=mood_opts, value=st.session_state.moods.get(user_name_only, "🙂"))
        if st.button("기분 업데이트 ✨"):
            rm = get_chunked_data(services["main"], {})
            r_moods = rm.get("moods", {"수기남자친구": "🙂", "수기": "🙂"})
            r_hist = rm.get("mood_history", [])
            
            r_moods[user_name_only] = my_mood
            m_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
            today_rec = next((item for item in r_hist if item["date"] == today_str), None)
            if today_rec: today_rec[f"{user_name_only}_score"] = m_score[my_mood]
            else:
                new_rec = {"date": today_str, "수기남자친구_score": m_score[r_moods.get("수기남자친구", "🙂")], "수기_score": m_score[r_moods.get("수기", "🙂")]}
                new_rec[f"{user_name_only}_score"] = m_score[my_mood]
                r_hist.append(new_rec)
                
            rm["moods"] = r_moods
            rm["mood_history"] = r_hist
            rm["current_mood_date"] = today_str
            st.session_state.moods = r_moods
            st.session_state.mood_history = r_hist
            save_large_data("main", rm)
            st.rerun()

        b_md = st.session_state.moods.get('수기남자친구', '🙂')
        g_md = st.session_state.moods.get('수기', '🙂')
        st.markdown(f"👦 **수기남자친구:** {b_md} ({mood_desc[b_md]})")
        st.markdown(f"👩 **수기:** {g_md} ({mood_desc[g_md]})")

        if len(st.session_state.mood_history) >= 2:
            df = pd.DataFrame(st.session_state.mood_history).set_index('date')
            if '수기남자친구_score' in df.columns and '수기_score' in df.columns:
                df = df[['수기남자친구_score', '수기_score']]
                df.columns = ['👦 수기남자친구 점수', '👧 수기 점수']
                st.line_chart(df, color=["#4B89FF", "#FF85A2"])
        
        st.divider()
        st.subheader("🗓️ 데이트 일정")
        with st.form("sch_form", clear_on_submit=True):
            sd = st.date_input("날짜"); sp = st.text_input("어디서 무얼 할까요?")
            if st.form_submit_button("일정 추가") and sp:
                remote_d = get_chunked_data(services["date"], [])
                remote_d.append({"date": str(sd), "plan": sp, "by": user_name_only})
                st.session_state.date_schedules = remote_d
                save_large_data("date", remote_d); st.rerun()
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 {s['date']} {s['plan']}"):
                if st.button("삭제", key=f"ds_{i}"): 
                    target_s = s
                    remote_d = get_chunked_data(services["date"], [])
                    for idx, rem_s in enumerate(remote_d):
                        if rem_s.get('date') == target_s['date'] and rem_s.get('plan') == target_s['plan']:
                            remote_d.pop(idx); break
                    st.session_state.date_schedules = remote_d
                    save_large_data("date", remote_d); st.rerun()

    # 2. 💌 쪽지함
    with tabs[1]:
        st.subheader("💌 오늘의 한마디")
        content = st.text_area("마음 전하기", key="memo_in")
        if st.button("보내기 ✈️") and content:
            remote_m = get_chunked_data(services["memo"], [])
            existing_idx = -1
            for idx, m in enumerate(remote_m):
                if m.get('date') == today_str and m.get('user') == user_name_only:
                    existing_idx = idx; break
            
            if existing_idx != -1:
                remote_m[existing_idx]['content'] = content
                remote_m[existing_idx]['time'] = current_time_str
                st.toast("오늘의 쪽지가 수정되었습니다! ✏️")
            else:
                remote_m.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
                st.toast("오늘의 쪽지가 등록되었습니다! ✈️")
            st.session_state.memo_history = remote_m
            save_large_data("memo", remote_m); st.rerun()
            
        for m in st.session_state.memo_history[:st.session_state.memo_limit]:
            cls = "user-boy" if "수기남자친구" in m.get('user','') else "user-girl"
            st.markdown(f"<div class='card {cls}'><b>{m.get('user','')}</b> | {m.get('date','')}<br>{m.get('content','')}</div>", unsafe_allow_html=True)
        if len(st.session_state.memo_history) > st.session_state.memo_limit:
            if st.button("더 보기 ⬇️"): st.session_state.memo_limit += 10; st.rerun()

    # 3. 🌸 텔레파시 (🚨 100% 리얼 현실 밀착형 커플 밸런스 게임 리뉴얼)
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시")
        tele_qs = [
            ["1시간 동안 말없이 꽉 안고 있기", "1시간 동안 눈 맞추고 대화하기"], ["완벽하게 짜인 J의 계획 데이트", "발길 닿는 대로 다니는 P의 데이트"], ["싸웠을 때 무조건 당장 대화로 풀기", "감정 추스를 시간 1~2시간 갖기"], ["정성이 꾹꾹 담긴 장문의 손편지", "평소 갖고 싶었던 실용적인 선물"], ["비 오는 날 집에서 파전+넷플릭스", "비 오는 날 분위기 좋은 카페에서 물멍"],
            ["야식으로 매콤달달 떡볶이", "바삭한 치킨에 시원한 맥주"], ["기념일에 럭셔리한 파인다이닝", "기념일에 프라이빗한 글램핑"], ["애인이 내 과거 연애사 다 알기", "내가 애인 과거 연애사 다 알기"], ["스킨십 없는 플라토닉 사랑", "대화 안 통하는 스킨십 폭발 사랑"], ["하루에 연락 100번 이상 꼬박꼬박", "하루에 연락 딱 3번만 길고 깊게"],
            ["애인의 남/여사친과 셋이서 술 마시기", "애인이 남/여사친과 단둘이 커피 마시기"], ["한 달에 한 번씩 호캉스 가기", "1년 모아서 유럽 여행 가기"], ["내 생일에 애인이 요리해 주기", "내 생일에 고급 레스토랑 예약하기"], ["평생 내가 더 사랑하기", "평생 내가 더 사랑받기"], ["애인 핸드폰 24시간 공유하기", "내 핸드폰 24시간 공유하기"],
            ["서운한 거 생길 때마다 팩폭하기", "서운한 거 돌려 말하거나 참기"], ["애인이 길에서 번호 따였는데 거절함", "애인이 길에서 번호 따였는데 그냥 줌"], ["한여름에 에어컨 없이 껴안고 자기", "한겨울에 보일러 없이 떨어져서 자기"], ["같이 공포 영화 보며 소리 지르기", "같이 슬픈 영화 보며 엉엉 울기"], ["쉬는 날 아무것도 안 하고 잠만 자기", "쉬는 날 밀린 집안일 대청소하기"],
            ["경제권은 각자 따로 관리하기", "한 명이 전담해서 합치기"], ["딩크족으로 둘이서 여유롭게 살기", "아이 둘 낳고 시끌벅적하게 살기"], ["친구들 모임에 애인 무조건 데려가기", "친구들 모임엔 무조건 친구들끼리만"], ["연락 끊기고 12시간 푹 자기", "연락하면서 3시간 자고 출근하기"], ["애인이 게임에 푹 빠져서 연락 안 됨", "애인이 친구랑 술 마시느라 연락 안 됨"],
            ["로또 당첨금 나 혼자 독식하기", "애인이랑 무조건 5:5로 반 나누기"], ["기분 안 좋을 때 혼자 내버려 두기", "기분 안 좋을 때 계속 옆에서 위로해 주기"], ["애인이 이성에게 친절하게 웃어주기", "애인이 모든 이성에게 차갑게 대하기"], ["내 입맛에 애인이 무조건 맞추기", "애인 입맛에 내가 무조건 맞추기"], ["피곤할 때 스킨십 요구하면 받아준다", "피곤할 땐 단호하게 거절한다"],
            ["애인과 함께 유튜브/인스타 운영하기", "절대 비밀 연애 유지하기"], ["결혼식은 스몰웨딩으로 가족들만", "결혼식은 크고 화려하게 호텔 예식"], ["가장 듣기 좋은 말 '사랑해'", "가장 듣기 좋은 말 '고마워'"], ["내가 잘못했을 때 애교로 넘어가기", "내가 잘못했을 때 논리적으로 사과하기"], ["술 마시고 엉엉 우는 애인 달래기", "술 마시고 길바닥에 자는 애인 업기"],
            ["애인의 방귀/트림 터버리기", "평생 신비주의 유지하기"], ["둘 중 한 명은 평생 백수(내가 벌기)", "둘 다 맞벌이하면서 풍족하게 살기"], ["같이 다이어트하며 샐러드만 먹기", "다이어트 포기하고 매일 맛집 탐방"], ["연애 초반의 불타는 설렘", "오래된 연인의 편안하고 깊은 안정감"], ["데이트 비용은 데이트 통장으로", "데이트 비용은 그때그때 번갈아 내기"],
            ["크리스마스엔 북적이는 번화가 데이트", "크리스마스엔 조용한 우리 집 홈파티"], ["상대방이 잔소리/잔소리꾼 되는 것", "상대방이 나에게 무관심해지는 것"], ["애인 옷 스타일 내 마음대로 바꾸기", "애인 옷 스타일에 내가 완벽히 맞추기"], ["잠잘 때 팔베개해주기", "잠잘 때 등 돌리고 편하게 자기"], ["기념일을 깜빡한 애인 용서하기", "생일을 깜빡한 애인 용서하기"],
            ["매일 퇴근 후 10분 짧은 만남", "주말에 하루 종일 찰딱 붙어있기"], ["내가 애인 머리 감겨주고 말려주기", "애인이 내 머리 감겨주고 말려주기"], ["바다 여행 가서 액티비티 즐기기", "숲속 펜션 가서 하루 종일 낮잠 자기"], ["애인이 예쁜 이성 쳐다보는 것 잡기", "내가 멋진 이성 쳐다보는 것 들키기"], ["사랑니 뽑고 부은 애인 간호하기", "장염 걸린 애인 흰죽 끓여주기"],
            ["화장 안 한 민낯이 더 예쁘다/멋있다", "풀세팅으로 꾸민 날이 더 매력적이다"], ["애인이랑 나란히 앉아서 밥 먹기", "애인이랑 마주 보고 앉아서 밥 먹기"], ["새벽 2시에 갑자기 보고 싶다고 찾아오기", "새벽 2시에 깊은 속마음 장문 카톡 오기"], ["애인이 내 방 비밀번호 알고 수시로 옴", "서로의 프라이버시는 철저히 지키기"], ["애인이 다른 이성에게 깻잎 떼어주기", "애인이 다른 이성 패딩 지퍼 올려주기"],
            ["애인이랑 PC방에서 5시간 게임하기", "애인이랑 카페에서 5시간 수다 떨기"], ["기억 상실증에 걸려 날 잊은 애인", "내가 기억 상실증에 걸려 애인 잊기"], ["애인 부모님과 단둘이 1박 2일 여행", "내 부모님과 애인이 단둘이 1박 2일 여행"], ["애인한테 내 통장 잔고 다 공개하기", "애인 통장 잔고 다 공개받기"], ["애인이 전 애인과 찍은 사진 발견", "내가 전 애인과 찍은 사진 들키기"],
            ["만약 환생한다면 지금 애인과 또 연애", "환생하면 새로운 인연과 연애해 보기"], ["내가 애인보다 10년 먼저 죽기", "애인이 나보다 10년 먼저 죽기"], ["애인한테 서프라이즈 파티해주기", "애인한테 서프라이즈 파티받기"], ["애인이 내 친구 뒷담화하는 거 듣기", "내가 애인 친구 뒷담화하다 걸리기"], ["나 없이 애인 혼자 클럽 가기", "나 없이 애인 혼자 헌팅 포차 가기"],
            ["내가 매일 아침 차려주기", "애인이 매일 아침 차려주기"], ["애인이랑 무서운 놀이기구 다 타기", "애인이랑 회전목마만 계속 타기"], ["둘이서 유튜브 보며 같이 웃기", "둘이서 좋아하는 노래 부르며 놀기"], ["스킨십 할 때 내가 먼저 리드하기", "스킨십 할 때 상대방이 리드해 주기"], ["애인이 나 몰래 1,000만 원 주식 투자", "내가 나 몰래 1,000만 원 주식 투자"],
            ["서로의 위치 추적 앱 항상 켜두기", "서로 어디 있는지 안 묻고 믿어주기"], ["우리가 만약 헤어진다면 미련 없이 끝", "헤어지더라도 친구로 연락하며 지내기"], ["결혼 전 동거는 필수 코스다", "결혼 전 동거는 절대 반대한다"], ["애인 앞에서 방귀 뀌다 똥 지리기", "애인이 내 앞에서 방귀 뀌다 똥 지리기"], ["애인의 겨드랑이 냄새 맡기", "애인한테 내 발 냄새 맡게 하기"],
            ["내가 화났을 때 맛있는 음식 사주기", "내가 화났을 때 귀여운 짓으로 풀기"], ["평생 애인의 칭찬 봇 되기", "평생 애인의 팩폭 조언자 되기"], ["우리 커플의 가장 큰 무기는 '외모'", "우리 커플의 가장 큰 무기는 '성격'"], ["내가 제일 좋아하는 별명으로 불리기", "내가 직접 지어준 애칭으로 부르기"], ["매일매일 서로에게 '사랑해' 말하기", "매일매일 서로를 꼭 껴안아 주기"],
            ["만약 내가 좀비로 변한다면 나를 죽이기", "만약 내가 좀비로 변하면 같이 좀비 되기"], ["애인이 내가 싫어하는 행동 계속하기", "내가 애인이 싫어하는 행동 계속하기"], ["애인이 나보다 돈을 3배 더 많이 벌기", "내가 애인보다 돈을 3배 더 많이 벌기"], ["나의 가장 큰 콤플렉스 당당히 보여주기", "애인의 가장 큰 콤플렉스 감싸 안아주기"], ["비 오는 날 우산 하나로 꼭 붙어서 걷기", "비 오는 날 각자 우산 쓰고 편하게 걷기"],
            ["애인이랑 만화카페 가서 라면 먹기", "애인이랑 오락실 가서 내기 게임하기"], ["서로의 흑역사 앨범 밤새도록 보기", "서로의 미래 버킷리스트 밤새도록 짜기"], ["지금 당장 애인 입술에 짧게 뽀뽀하기", "지금 당장 애인 볼에 깊게 뽀뽀하기"], ["우리 사랑의 유효기간은 100년", "우리 사랑의 유효기간은 영원히"], ["마지막으로, 지금 애인이 제일 보고 싶다", "마지막으로, 지금 당장 안아주고 싶다"]
        ]
        t_idx = now_kst.toordinal() % len(tele_qs); q_pair = tele_qs[t_idx]
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        ans = st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"]
        c1, c2 = st.columns(2)
        if c1.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
            remote_t = get_chunked_data(services["tele"], {})
            if today_str not in remote_t: remote_t[today_str] = {"hodl": None, "sugi": None}
            remote_t[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[0]
            st.session_state.tele_data = remote_t
            save_large_data("tele", remote_t); st.rerun()
        if c2.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
            remote_t = get_chunked_data(services["tele"], {})
            if today_str not in remote_t: remote_t[today_str] = {"hodl": None, "sugi": None}
            remote_t[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[1]
            st.session_state.tele_data = remote_t
            save_large_data("tele", remote_t); st.rerun()
        
        b_ans = st.session_state.tele_data[today_str].get("hodl"); g_ans = st.session_state.tele_data[today_str].get("sugi")
        if b_ans and g_ans:
            if st.button("🎁 결과 확인 (풍선 팡!)", use_container_width=True):
                if b_ans == g_ans: st.balloons(); st.success(f"찌찌뽕! **[{b_ans}]** ❤️")
                else: st.info(f"👦 수기남자친구: {b_ans} / 👧 수기: {g_ans}")

    # 4. 🎵 주크박스
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        if isinstance(st.session_state.jukebox_data, list): st.session_state.jukebox_data = {"hodl": None, "sugi": None}
        yt_safe = "https://www.youtube.com/watch?v="
        
        with st.form("dj_dual"):
            link = st.text_input("유튜브 링크")
            if st.form_submit_button("내 곡 신청하기 🎧"):
                remote_j = get_chunked_data(services["jukebox"], {"hodl": None, "sugi": None})
                if isinstance(remote_j, list): remote_j = {"hodl": None, "sugi": None}
                remote_j["hodl" if user_name_only == "수기남자친구" else "sugi"] = link
                st.session_state.jukebox_data = remote_j
                save_large_data("jukebox", remote_j); st.rerun()
        
        cb, cg = st.columns(2)
        with cb:
            st.markdown("<div class='user-boy' style='padding:8px; border-radius:8px; margin-bottom:10px;'>👦 <b>수기남자친구 Pick</b></div>", unsafe_allow_html=True)
            b_id = extract_youtube_id(st.session_state.jukebox_data.get("hodl", ""))
            if b_id: st.video(yt_safe + b_id)
            else: st.info("아직 신청한 곡이 없어요!")
        with cg:
            st.markdown("<div class='user-girl' style='padding:8px; border-radius:8px; margin-bottom:10px;'>👧 <b>수기 Pick</b></div>", unsafe_allow_html=True)
            g_id = extract_youtube_id(st.session_state.jukebox_data.get("sugi", ""))
            if g_id: st.video(yt_safe + g_id)
            else: st.info("아직 신청한 곡이 없어요!")

    # 5. 📸 추억저장소
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
                remote_t = get_chunked_data(services["time"], [])
                remote_t.insert(0, {"date": str(td), "event": te, "by": user_name_only})
                st.session_state.timeline = remote_t
                save_large_data("time", remote_t); st.rerun()
        for t in st.session_state.timeline:
            st.markdown(f"<div class='card'><b>{t.get('date','')}</b>: {t.get('event','')}</div>", unsafe_allow_html=True)

    # 7. 📍 장소/기록
    with tabs[6]:
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form", clear_on_submit=True):
            wp = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가"):
                remote_w = get_chunked_data(services["wish"], [])
                remote_w.append({"place": wp, "visited": False, "by": user_name_only})
                st.session_state.wishlist = remote_w
                save_large_data("wish", remote_w); st.rerun()
        for i, w in enumerate(st.session_state.wishlist):
            v = w.get('visited', False)
            with st.expander(f"{'✅' if v else '📍'} {w.get('place','')}"):
                if st.checkbox("다녀왔어요!", value=v, key=f"chk_{i}") != v:
                    target_place = w.get('place')
                    remote_w = get_chunked_data(services["wish"], [])
                    for idx, rem_w in enumerate(remote_w):
                        if rem_w.get('place') == target_place:
                            remote_w[idx]['visited'] = not v; break
                    st.session_state.wishlist = remote_w
                    save_large_data("wish", remote_w); st.rerun()
                if st.button("삭제", key=f"del_w_{i}"):
                    target_place = w.get('place')
                    remote_w = get_chunked_data(services["wish"], [])
                    for idx, rem_w in enumerate(remote_w):
                        if rem_w.get('place') == target_place:
                            remote_w.pop(idx); break
                    st.session_state.wishlist = remote_w
                    save_large_data("wish", remote_w); st.rerun()
        
        st.divider()
        st.subheader("📝 데이트 후기")
        with st.form("r_form", clear_on_submit=True):
            r_date = st.date_input("방문 날짜 🗓️", value=now_kst.date())
            r_name = st.text_input("장소명 📍")
            r_cat = st.selectbox("종류 🏷️", ["음식점", "카페", "공원", "기타"])
            r_rating = st.selectbox("별점 ⭐", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
            r_comment = st.text_area("후기 내용 📝")
            if st.form_submit_button("후기 등록"):
                remote_r = get_chunked_data(services["review"], [])
                remote_r.insert(0, {"name": r_name, "cat": r_cat, "rating": r_rating, "comment": r_comment, "date": str(r_date), "by": user_name_only, "comments": []})
                st.session_state.reviews = remote_r
                save_large_data("review", remote_r); st.rerun()
        
        for i, r in enumerate(st.session_state.reviews):
            with st.container():
                st.markdown(f"""
                    <div class="card" style="margin-bottom: 5px;">
                        <span class="review-badge">{r.get('cat', '')}</span>
                        <span style="font-size: 0.8rem; color: gray;"> {r.get('date', '')} by {r.get('by', '')}</span>
                        <br><b>{r.get('name', '')}</b> {r.get('rating', '')}<br><br>
                        <p style="margin: 0; color:{text_color};">{r.get('comment', '')}</p>
                    </div>
                """, unsafe_allow_html=True)
                for c_idx, c in enumerate(r.setdefault("comments", [])):
                    st.markdown(f"<div class='review-comment'><b>{c.get('user')}</b>: {c.get('text')}</div>", unsafe_allow_html=True)
                    if c.get('user') == user_name_only:
                        if st.button("❌ 내 댓글 삭제", key=f"dc_{i}_{c_idx}"):
                            target_name = r.get('name'); target_date = r.get('date')
                            remote_r = get_chunked_data(services["review"], [])
                            for idx, rem_r in enumerate(remote_r):
                                if rem_r.get('name') == target_name and rem_r.get('date') == target_date:
                                    if c_idx < len(rem_r.get("comments", [])): rem_r["comments"].pop(c_idx)
                                    break
                            st.session_state.reviews = remote_r
                            save_large_data("review", remote_r); st.rerun()
                
                with st.expander("💬 댓글 남기기 / 원본 관리"):
                    nc = st.text_input("댓글 쓰기", key=f"nc_{i}")
                    if st.button("전송", key=f"nb_{i}"):
                        target_name = r.get('name'); target_date = r.get('date')
                        remote_r = get_chunked_data(services["review"], [])
                        for idx, rem_r in enumerate(remote_r):
                            if rem_r.get('name') == target_name and rem_r.get('date') == target_date:
                                rem_r.setdefault("comments", []).append({"user": user_name_only, "text": nc})
                                break
                        st.session_state.reviews = remote_r
                        save_large_data("review", remote_r); st.rerun()
                    if r.get('by') == user_name_only:
                        if st.button("🗑️ 후기 원본 삭제", key=f"rb_{i}"):
                            target_name = r.get('name'); target_date = r.get('date')
                            remote_r = get_chunked_data(services["review"], [])
                            for idx, rem_r in enumerate(remote_r):
                                if rem_r.get('name') == target_name and rem_r.get('date') == target_date:
                                    remote_r.pop(idx); break
                            st.session_state.reviews = remote_r
                            save_large_data("review", remote_r); st.rerun()

    # 8. 🎁 타임캡슐
    with tabs[7]:
        st.subheader("🎁 미래의 우리에게")
        with st.form("cap_form"):
            ct = st.text_input("제목"); cd = st.date_input("열어볼 날짜", min_value=now_kst.date() + datetime.timedelta(days=1)); cc = st.text_area("내용")
            if st.form_submit_button("⛏️ 묻기"):
                remote_c = get_chunked_data(services["capsule"], [])
                remote_c.append({"title": ct, "open_date": str(cd), "content": cc, "by": user_name_only})
                st.session_state.time_capsules = remote_c
                save_large_data("capsule", remote_c); st.rerun()
        for i, cap in enumerate(st.session_state.time_capsules):
            if today_str >= cap.get('open_date', ''):
                with st.expander(f"🎉 [열림] {cap.get('title')}"):
                    st.write(cap.get('content'))
                    if st.button("🗑️ 삭제", key=f"del_cap_{i}"): 
                        target_title = cap.get('title')
                        remote_c = get_chunked_data(services["capsule"], [])
                        for idx, rem_c in enumerate(remote_c):
                            if rem_c.get('title') == target_title:
                                remote_c.pop(idx); break
                        st.session_state.time_capsules = remote_c
                        save_large_data("capsule", remote_c); st.rerun()
            else:
                st.warning(f"🔒 [잠김] {cap.get('title')} ({cap.get('open_date')} 개봉 예정)")

    # 9. 🎡 만능 룰렛
    with tabs[8]:
        st.subheader("🎡 결정장애 해결사 (메뉴 룰렛)")
        
        with st.form("roulette_form", clear_on_submit=True):
            new_menu = st.text_input("새로운 메뉴/선택지 추가")
            if st.form_submit_button("추가") and new_menu:
                rm = get_chunked_data(services["main"], {})
                r_menu = rm.get("menu_list", [])
                if new_menu not in r_menu:
                    r_menu.append(new_menu)
                    rm["menu_list"] = r_menu
                    st.session_state.menu_list = r_menu
                    save_large_data("main", rm); st.rerun()

        st.write("🍽️ **현재 등록된 메뉴 후보**")
        for i, menu in enumerate(st.session_state.menu_list):
            col_m1, col_m2 = st.columns([0.8, 0.2])
            col_m1.write(f"- {menu}")
            if col_m2.button("❌", key=f"del_menu_{i}"):
                rm = get_chunked_data(services["main"], {})
                r_menu = rm.get("menu_list", [])
                if menu in r_menu: r_menu.remove(menu)
                rm["menu_list"] = r_menu
                st.session_state.menu_list = r_menu
                save_large_data("main", rm); st.rerun()
                
        st.divider()
        
        if st.session_state.menu_list:
            if st.button("🎲 룰렛 돌리기!", use_container_width=True):
                with st.spinner("두구두구두구... 🎲"):
                    time.sleep(1.5)
                result = random.choice(st.session_state.menu_list)
                st.success(f"🎉 오늘의 선택: **{result}** ‼️")
                st.balloons()
        else:
            st.warning("메뉴를 먼저 추가해주세요!")
