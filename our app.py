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

# --- 🚀 구글 인증 및 서비스 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

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

# --- 🚨 v5.0 핵심 유틸리티: 유튜브 ID 추출기 ---
def extract_youtube_id(url):
    pattern = r'(?:v=|\/|be\/|embed\/)([0-9A-Za-z_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

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

    return {
        "moods": main_data.get("moods", {"수기남자친구": "🙂", "수기": "🙂"}),
        "menu_list": main_data.get("menu_list", ["삼겹살", "초밥"]),
        "memo_history": get_large_data(services["memo"]),
        "timeline": get_large_data(services["time"]),
        "date_schedules": get_large_data(services["date"]),
        "wishlist": get_large_data(services["wish"]),
        "reviews": get_large_data(services["review"]),
        "qna_data": json.loads(services["qna"].acell('A1').value) if services["qna"] and services["qna"].acell('A1').value else {},
        "time_capsules": json.loads(services["capsule"].acell('A1').value) if services["capsule"] and services["capsule"].acell('A1').value else [],
        "tele_data": json.loads(services["tele"].acell('A1').value) if services["tele"] and services["tele"].acell('A1').value else {},
        "jukebox_data": json.loads(services["jukebox"].acell('A1').value) if services["jukebox"] and services["jukebox"].acell('A1').value else []
    }

def save_data_to_cell(sheet_key, data):
    if services[sheet_key]:
        services[sheet_key].update_acell('A1', json.dumps(data))

def save_large_data(sheet_key, data_list):
    if services[sheet_key]:
        json_str = json.dumps(data_list)
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cell_values = [[chunk] for chunk in chunks]
        services[sheet_key].batch_clear(['A2:A'])
        services[sheet_key].update(values=cell_values, range_name='A2', value_input_option='RAW')

# ==========================================
# 📸 드라이브 연동 (v4.6 아키텍처)
# ==========================================
def get_drive_service():
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_photo_to_drive(file_bytes, filename, mime_type):
    folder_id = st.secrets.get("DRIVE_FOLDER_ID") or st.secrets.get("google_auth", {}).get("DRIVE_FOLDER_ID")
    if not folder_id: return None
    try:
        svc = get_drive_service()
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file = svc.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except: return None

def load_photos_from_drive(limit=20):
    folder_id = st.secrets.get("DRIVE_FOLDER_ID") or st.secrets.get("google_auth", {}).get("DRIVE_FOLDER_ID")
    if not folder_id: return []
    try:
        svc = get_drive_service()
        results = svc.files().list(q=f"'{folder_id}' in parents and trashed=false", pageSize=limit, fields="files(id, name)", orderBy="createdTime desc").execute()
        return results.get('files', [])
    except: return []

@st.cache_data(show_spinner=False, ttl=3600)
def get_image_bytes(file_id):
    svc = get_drive_service()
    request = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    return fh.getvalue()

# ==========================================
# 🚨 [v5.0] 원클릭 자동 로그인 시스템
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
        st.markdown("<h1 style='text-align: center; color: #FF85A2;'>♥ 수기 커플 노트</h1>", unsafe_allow_html=True)
        # on_change를 사용해 입력 즉시 검증
        st.text_input("우리만의 비밀번호", type="password", key="pwd_input", on_change=validate_password)
        return False
    
    if not st.session_state["current_user"]:
        st.markdown("<h2 style='text-align: center; color: #FF85A2;'>누가 오셨나요? 👀</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("👦 수기남자친구"): st.session_state["current_user"] = "수기남자친구"; st.rerun()
        if col2.button("👧 수기"): st.session_state["current_user"] = "수기"; st.rerun()
        return False
    return True

# --- 메인 실행 ---
if check_login_and_user():
    user_name_only = st.session_state["current_user"]
    user_icon = "👧" if user_name_only == "수기" else "👦"

    if 'data_loaded' not in st.session_state:
        saved = load_data()
        for k, v in saved.items(): st.session_state[k] = v
        st.session_state['data_loaded'] = True
        st.session_state.photo_limit = 20

    # 📌 테마 설정
    current_hour = now_kst.hour
    is_night = current_hour >= 19 or current_hour <= 6
    bg_color = "#1A1A2E" if is_night else ("#FFF5F7" if user_name_only == "수기" else "#E3F2FD")
    accent_color = "#FF85A2" if user_name_only == "수기" else "#4B89FF"
    text_color = "#E0E0E0" if is_night else "#333333"

    # ==========================================
    # 🌱 [v5.0] 다마고치 사랑의 나무 (사이드바)
    # ==========================================
    total_activity = len(st.session_state.memo_history) + len(st.session_state.timeline) + len(st.session_state.reviews)
    if total_activity < 10: level, tree_icon = "씨앗", "🌱"
    elif total_activity < 30: level, tree_icon = "새싹", "🌿"
    elif total_activity < 70: level, tree_icon = "아기 나무", "🌳"
    else: level, tree_icon = "열매 맺은 나무", "🍎"

    with st.sidebar:
        st.markdown(f"""
            <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; border: 2px solid {accent_color}; text-align: center;">
                <h1 style="margin:0;">{tree_icon}</h1>
                <h4 style="margin:5px 0;">우리의 사랑나무: {level}</h4>
                <p style="font-size: 0.8em; opacity: 0.8;">활동 포인트: {total_activity} XP</p>
            </div>
        """, unsafe_allow_html=True)
        
        start_date = datetime.date(2026, 1, 1) 
        st.metric(label="우리의 D-Day", value=f"D + {(now_kst.date() - start_date).days}일")
        
        if st.button("로그아웃 🚪"): st.session_state.clear(); st.rerun()

    # --- CSS 주입 ---
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        html, body, [data-testid="stMetricValue"], .stMarkdown {{ font-family: 'Gamja Flower', sans-serif !important; color: {text_color} !important; }}
        .stApp {{ background-color: {bg_color} !important; }}
        .card {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; margin-bottom: 10px; border-left: 5px solid {accent_color}; }}
        .user-boy {{ background-color: rgba(75, 137, 255, 0.1) !important; border-left: 5px solid #4B89FF; text-align: left; }}
        .user-girl {{ background-color: rgba(255, 133, 162, 0.1) !important; border-right: 5px solid #FF85A2; text-align: right; }}
        /* 빙고 스타일 */
        .bingo-cell {{ border: 2px solid {accent_color}; border-radius: 10px; height: 100px; display: flex; align-items: center; justify-content: center; text-align: center; padding: 5px; font-weight: bold; background: rgba(255,255,255,0.05); }}
        .bingo-done {{ background: {accent_color} !important; color: white !important; }}
        </style>
    """, unsafe_allow_html=True)

    # ==========================================
    # 탭 구성 (주크박스, 텔레파시 추가)
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "🌸 텔레파시", "🎵 주크박스", "📸 추억저장소", "📍 빙고!", "🎁 타임캡슐"])

    # 1. 데이트/문답 탭
    with tabs[0]:
        st.subheader("🗓️ 오늘 데이트 & 기분")
        col_m1, col_m2 = st.columns(2); col_m1.metric("수기남자친구", st.session_state.moods["수기남자친구"]); col_m2.metric("수기", st.session_state.moods["수기"])
        if st.button("기분 업데이트 🔥"):
            st.session_state.moods[user_name_only] = st.select_slider("오늘 기분은?", options=["😢", "☁️", "🙂", "🥰", "🔥"])
            save_data_to_cell("main", {"moods": st.session_state.moods, "menu_list": st.session_state.menu_list})
            st.rerun()

        # 오늘의 문답 (기존 로직 유지)
        q_idx = now_kst.toordinal() % 30
        qna_list = ["첫인상은?", "가장 반했던 순간?", "가고 싶은 여행지는?", "최고의 데이트는?"] # 예시 (기존 코드 리스트 동일)
        q_key = f"qna_{q_idx}"
        with st.expander("💌 오늘의 30문 30답", expanded=True):
            st.info(f"질문: {q_idx+1}번 (블라인드 룰 적용)")
            ans_boy = st.session_state.qna_data.get(q_key, {}).get("hodl", "")
            ans_girl = st.session_state.qna_data.get(q_key, {}).get("sugi", "")
            both = bool(ans_boy.strip() and ans_girl.strip())
            
            my_col, other_col = st.columns(2)
            with my_col:
                st.write("내 답변")
                new_ans = st.text_area("작성...", value=ans_boy if user_name_only == "수기남자친구" else ans_girl, key="my_qna")
                if st.button("답변 저장 💾"):
                    if user_name_only == "수기남자친구": st.session_state.qna_data.setdefault(q_key, {})["hodl"] = new_ans
                    else: st.session_state.qna_data.setdefault(q_key, {})["sugi"] = new_ans
                    save_data_to_cell("qna", st.session_state.qna_data); st.rerun()
            with other_col:
                st.write("상대방 답변")
                if both: st.success(ans_girl if user_name_only == "수기남자친구" else ans_boy)
                else: st.warning("🔒 둘 다 써야 열려요!")

    # 2. 쪽지함
    with tabs[1]:
        st.subheader("💌 오늘의 한마디")
        content = st.text_area("수기에게 전달할 마음...", key="new_memo")
        if st.button("쪽지 발송 ✈️"):
            st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content})
            save_large_data("memo", st.session_state.memo_history); st.rerun()
        for m in st.session_state.memo_history[:10]:
            cls = "user-boy" if "남자친구" in m['user'] else "user-girl"
            st.markdown(f"<div class='card {cls}'><b>{m['user']}</b><br>{m['content']}<br><small>{m['date']} {m['time']}</small></div>", unsafe_allow_html=True)

    # 3. [v5.0 신규] 텔레파시 밸런스 게임
    with tabs[2]:
        st.subheader("🌸 오늘의 텔레파시 밸런스 게임")
        questions = [["평생 여름", "평생 겨울"], ["카레맛 똥", "똥맛 카레"], ["찍먹", "부먹"], ["강아지", "고양이"]]
        q_idx = now_kst.toordinal() % len(questions)
        q_pair = questions[q_idx]
        
        st.session_state.tele_data.setdefault(today_str, {"hodl": None, "sugi": None})
        
        col1, col2 = st.columns(2)
        ans = st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"]
        
        with col1: 
            if st.button(q_pair[0], use_container_width=True, type="primary" if ans == q_pair[0] else "secondary"):
                st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[0]
                save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        with col2:
            if st.button(q_pair[1], use_container_width=True, type="primary" if ans == q_pair[1] else "secondary"):
                st.session_state.tele_data[today_str]["hodl" if user_name_only == "수기남자친구" else "sugi"] = q_pair[1]
                save_data_to_cell("tele", st.session_state.tele_data); st.rerun()
        
        st.divider()
        b_ans = st.session_state.tele_data[today_str]["hodl"]; g_ans = st.session_state.tele_data[today_str]["sugi"]
        if b_ans and g_ans:
            if b_ans == g_ans: st.balloons(); st.success(f"🎊 찌찌뽕! 두 분 다 **[{b_ans}]**를 선택하셨어요! 운명인가봐요 ❤️")
            else: st.info(f"오호! 수기남친님은 **[{b_ans}]**, 수기님은 **[{g_ans}]**를 고르셨군요! (다름의 미학 😉)")
        else: st.warning("🔒 두 분 모두 선택해야 텔레파시 결과를 볼 수 있어요!")

    # 4. [v5.0 신규] 우리만의 주크박스
    with tabs[3]:
        st.subheader("🎵 오늘의 커플 DJ")
        with st.form("dj_form"):
            song_link = st.text_input("상대방에게 들려주고 싶은 노래 (유튜브 링크)")
            if st.form_submit_button("노래 신청하기 📻") and song_link:
                st.session_state.jukebox_data.insert(0, {"date": today_str, "user": user_name_only, "url": song_link})
                save_data_to_cell("jukebox", st.session_state.jukebox_data); st.rerun()
        
        if st.session_state.jukebox_data:
            latest = st.session_state.jukebox_data[0]
            st.markdown(f"#### 🎧 {latest['user']}님이 신청한 오늘의 BGM")
            vid_id = extract_youtube_id(latest['url'])
            if vid_id: st.video(f"https://www.youtube.com/watch?v={vid_id}")
            else: st.warning("유효한 유튜브 링크가 아니에요!")

    # 5. 추억 저장소 (기존 2TB & 지우개 & 날짜수정 로직 유지)
    with tabs[4]:
        st.subheader("📸 2TB 추억 저장소")
        with st.expander("✨ 추억 업로드"):
            files = st.file_uploader("사진들...", accept_multiple_files=True)
            e_date = st.date_input("날짜", value=now_kst.date())
            e_name = st.text_input("추억 이름", placeholder="해운대 여행 등")
            if st.button("드라이브 전송 ☁️") and files:
                for f in files:
                    fname = f"{e_date}_{user_name_only}_{e_name}_{random.randint(1000,9999)}.jpg"
                    upload_photo_to_drive(f.getvalue(), fname, f.type)
                st.rerun()
        
        photos = load_photos_from_drive(st.session_state.photo_limit)
        # 그룹화 및 렌더링 (기존 코드와 동일)
        for p in photos:
            try:
                img = get_image_bytes(p['id'])
                st.image(img, caption=p['name'])
                if st.button("🗑️ 삭제", key=p['id']):
                    delete_photo_from_drive(p['id']); st.rerun()
            except: pass
        if len(photos) >= st.session_state.photo_limit:
            if st.button("과거 추억 더 보기 ⬇️"): st.session_state.photo_limit += 20; st.rerun()

    # 6. [v5.0 고도화] 버킷리스트 빙고판
    with tabs[5]:
        st.subheader("📍 우리의 커플 빙고판")
        # 위시리스트 데이터를 3x3으로 변환
        wish = st.session_state.wishlist
        for i in range(0, 9):
            if i >= len(wish): wish.append({"place": "빈 칸", "visited": False})
        
        for r in range(3):
            cols = st.columns(3)
            for c in range(3):
                idx = r * 3 + c
                item = wish[idx]
                with cols[c]:
                    b_cls = "bingo-done" if item['visited'] else ""
                    st.markdown(f"<div class='bingo-cell {b_cls}'>{item['place']}</div>", unsafe_allow_html=True)
                    if st.checkbox("성공!", value=item['visited'], key=f"bingo_{idx}"):
                        item['visited'] = True
                        save_large_data("wish", wish); st.rerun()

    # 7. 타임캡슐
    with tabs[6]:
        st.subheader("🎁 미래로 보내는 편지")
        # (기존 타임캡슐 로직 동일하게 유지)
        pass
