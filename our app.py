import streamlit as st
import datetime
import pytz
import random
import json
import gspread
import io
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import streamlit.components.v1 as components

# 1. 앱 기본 설정
st.set_page_config(page_title="수기 커플 노트", page_icon="❤️", layout="centered")

# ==========================================
# 🍎 [Task 1-B] 아이폰(iOS) 전용 홈 화면 아이콘 강제 주입
# ==========================================
components.html("""
    <script>
        const link = window.parent.document.createElement('link');
        link.rel = 'apple-touch-icon';
        link.href = 'https://cdn-icons-png.flaticon.com/512/833/833472.png'; 
        window.parent.document.head.appendChild(link);
    </script>
""", height=0, width=0)

# ==========================================
# 📱 [Task 1] PWA 앱 설치 유도 배너
# ==========================================
st.markdown("""
    <style>
    .pwa-banner {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        padding: 12px; border-radius: 10px; text-align: center; 
        font-size: 0.9em; font-weight: bold; color: #fff; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
    <div class="pwa-banner">
        💡 꿀팁: 아이폰 단축어 앱을 사용하면 우리 사진으로 예쁜 아이콘을 만들 수 있어요! ❤️
    </div>
""", unsafe_allow_html=True)


# --- 🌐 한국 시간(KST) 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

# --- 🚀 구글 시트 & 드라이브 API 연동 설정 ---
@st.cache_resource
def get_google_services():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "google_auth" in st.secrets:
        token_info = json.loads(st.secrets["google_auth"]["token"])
        creds = Credentials.from_authorized_user_info(token_info, scopes)
    else:
        creds = Credentials.from_authorized_user_file('token.json', scopes)
    
    client = gspread.authorize(creds)
    drive_svc = build('drive', 'v3', credentials=creds)
    doc = client.open('couple_app_data')
    
    # 🚨 시트 탭 매핑 (방어 로직 적용)
    return {
        "main": doc.worksheet('시트1'),
        "memo": doc.worksheet('쪽지함'),
        "time": doc.worksheet('타임라인'),
        "date": doc.worksheet('데이트일정'),
        "wish": doc.worksheet('위시리스트'),
        "review": doc.worksheet('데이트후기'),
        "qna": doc.worksheet('문답데이터'),      # [v4.0 신규] 물리적 탭 분리!
        "capsule": doc.worksheet('타임캡슐데이터'),  # [v4.0 신규] 물리적 탭 분리!
        "drive": drive_svc
    }

services = get_google_services()
sheet_main = services["main"]
sheet_memo = services["memo"]
sheet_time = services["time"]
sheet_date = services["date"]
sheet_wish = services["wish"]
sheet_review = services["review"]
sheet_qna = services["qna"]
sheet_capsule = services["capsule"]
drive_service = services["drive"]

DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "")

# ==========================================
# ⚡️ [v4.0 초고속 엔진] 데이터 로드 및 아토믹 세이브
# ==========================================
def load_data():
    try:
        val = sheet_main.acell('A1').value
        main_data = json.loads(val) if val else {}
    except: main_data = {}

    try:
        q_val = sheet_qna.acell('A1').value
        qna_data = json.loads(q_val) if q_val else {}
    except: qna_data = {}

    try:
        c_val = sheet_capsule.acell('A1').value
        capsule_data = json.loads(c_val) if c_val else []
    except: capsule_data = []

    def get_large_data(sheet_obj):
        try:
            vals = sheet_obj.col_values(1)[1:]
            if not vals: return []
            return json.loads("".join(vals))
        except Exception as e:
            st.error(f"{sheet_obj.title} 데이터 로드 문제: {e}")
            return []

    return {
        "notice": main_data.get("notice", "비타민 챙겨 먹기! 오늘 하루도 화이팅 ✨"),
        "promises": main_data.get("promises", [{"text": "서운한 건 그날 바로 말하기 🗣️", "by": "수기남자친구"}]),
        "moods": main_data.get("moods", {"수기남자친구": "🙂", "수기": "🙂"}),
        "mood_history": main_data.get("mood_history", []),
        "current_mood_date": main_data.get("current_mood_date", today_str),
        "menu_list": main_data.get("menu_list", ["삼겹살", "초밥"]),
        "memo_history": get_large_data(sheet_memo),
        "timeline": get_large_data(sheet_time),
        "date_schedules": get_large_data(sheet_date),
        "wishlist": get_large_data(sheet_wish),
        "reviews": get_large_data(sheet_review),
        "qna_data": qna_data,           # A1 분리됨
        "time_capsules": capsule_data   # A1 분리됨
    }

# 👇 1개의 전체 저장 대신 핀셋으로 저장하는 Atomic Save 도입 (속도 7배 향상!)
def save_main_data():
    main_data = {
        "notice": st.session_state.notice,
        "promises": st.session_state.promises,
        "moods": st.session_state.moods,
        "mood_history": st.session_state.mood_history,
        "current_mood_date": st.session_state.current_mood_date,
        "menu_list": st.session_state.menu_list,
    }
    sheet_main.update_acell('A1', json.dumps(main_data))

def save_qna_data():
    sheet_qna.update_acell('A1', json.dumps(st.session_state.qna_data))

def save_capsule_data():
    sheet_capsule.update_acell('A1', json.dumps(st.session_state.time_capsules))

def save_specific_large_data(sheet_obj, data_list):
    if not data_list:
        sheet_obj.batch_clear(['A2:A'])
        return
    json_str = json.dumps(data_list)
    chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
    cell_values = [[chunk] for chunk in chunks]
    sheet_obj.batch_clear(['A2:A'])
    sheet_obj.update(values=cell_values, range_name='A2', value_input_option='RAW')

# ==========================================
# 📸 [v4.0] 2TB 구글 드라이브 사진 연동 모듈
# ==========================================
def upload_photo_to_drive(file_bytes, filename):
    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def load_photos_from_drive():
    if not DRIVE_FOLDER_ID: return []
    try:
        results = drive_service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false",
            pageSize=30, fields="files(id, name)", orderBy="createdTime desc" # 최근 30장만
        ).execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"구글 드라이브 접근 에러: {e}")
        return []

@st.cache_data(show_spinner=False, ttl=3600)
def get_image_bytes(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return fh.getvalue()

# --- 보안 설정 ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.markdown("<h1 style='text-align: center; color: #FF85A2;'>♥ 수기 커플 노트</h1>", unsafe_allow_html=True)
    pwd = st.text_input("우리 둘만의 비밀번호", type="password")
    if st.button("사랑으로 열기 ♥"):
        if pwd == "6146":  
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("비밀번호가 틀렸어!")
    return False

# --- 메인 로직 시작 ---
if check_password():
    
    # ✨ [UI F] 전면 토스트 팝업 중앙 제어 시스템
    if "toast_msg" not in st.session_state:
        st.session_state.toast_msg = ""
    if st.session_state.toast_msg:
        st.toast(st.session_state.toast_msg)
        st.session_state.toast_msg = ""

    if 'data_loaded' not in st.session_state:
        saved_data = load_data()
        for key, value in saved_data.items():
            st.session_state[key] = value
        st.session_state['data_loaded'] = True
        
        if st.session_state.current_mood_date != today_str:
            st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}
            st.session_state.current_mood_date = today_str
            save_main_data()

    # ==========================================
    # 💌 [Task 2] 매일매일 30문 30답
    # ==========================================
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

    today_ordinal = datetime.datetime.now(KST).toordinal()
    q_index = today_ordinal % 30
    today_question = qna_list[q_index]
    q_key = f"qna_{q_index}"

    if "qna_data" not in st.session_state:
        st.session_state.qna_data = {}
    if q_key not in st.session_state.qna_data:
        st.session_state.qna_data[q_key] = {"hodl": "", "sugi": ""}

    with st.expander(f"💌 오늘의 문답 (D-{30 - q_index}일 남음)", expanded=True):
        st.subheader(today_question)
        
        col1, col2 = st.columns(2)
        with col1:
            hodl_ans = st.text_area("👦 HODL님의 답변", value=st.session_state.qna_data[q_key]["hodl"], height=100)
        with col2:
            sugi_ans = st.text_area("👩 수기님의 답변", value=st.session_state.qna_data[q_key]["sugi"], height=100)
            
        if st.button("답변 꾹 저장하기 💾"):
            st.session_state.qna_data[q_key]["hodl"] = hodl_ans
            st.session_state.qna_data[q_key]["sugi"] = sugi_ans
            save_qna_data() # Atomic Save 도입
            st.session_state.toast_msg = "두 사람의 소중한 답변이 영구 저장되었습니다! ✨"
            st.rerun()

    # ==========================================
    # 📌 🌙 낮/밤 커플 테마 자동 전환 로직 (UI G)
    # ==========================================
    with st.sidebar:
        user_type = st.radio("👤 접속자", ["수기남자친구 👦", "수기 👧"])
        user_name_only = "수기남자친구" if "남자친구" in user_type else "수기"
        
        current_hour = now_kst.hour
        is_night = current_hour >= 19 or current_hour <= 6
        
        if is_night:
            bg_color = "#1A1A2E"; card_bg = "#16213E"; text_color = "#E0E0E0"
            input_bg = "#0F3460"; border_color = "#2E3B5E"
            accent_color = "#E94560" if user_name_only == "수기" else "#4B89FF"
            user_icon = "👧" if user_name_only == "수기" else "👦"
        else:
            text_color = "#333333"; card_bg = "#ffffff"; input_bg = "#ffffff"; border_color = "#eeeeee"
            if user_name_only == "수기":
                bg_color = "#FFF5F7"; accent_color = "#FF85A2"; user_icon = "👧"
            else:
                bg_color = "#E3F2FD"; accent_color = "#4B89FF"; user_icon = "👦"

    st.markdown(f"""
        <div class="custom-bg-layer" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: {bg_color}; z-index: -99999; pointer-events: none;"></div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Gamja+Flower&display=swap');
        
        html, body, p, h1, h2, h3, h4, h5, h6, span, label, button, input, textarea, select, div[data-testid="stMetricValue"], .stMarkdown, .stText {{
            font-family: 'Gamja Flower', sans-serif !important;
            color: {text_color} !important;
        }}
        .material-symbols-rounded, [data-testid="stIconMaterial"] {{
            font-family: 'Material Symbols Rounded' !important;
            color: {text_color} !important;
        }}

        html, body, .stApp, .main, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"], [data-testid="stHeader"] {{
            background-color: transparent !important;
            background: transparent !important;
        }}
        
        input, textarea, select, div.stTextInput > div > div > input, div.stTextArea > div > div > textarea {{
            background-color: {input_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border_color} !important;
        }}
        
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{ 
            background-color: {card_bg} !important; 
            opacity: 1 !important;
            border-right: 1px solid {border_color} !important;
            box-shadow: 2px 0px 10px rgba(0,0,0,0.05) !important;
        }}
        
        .card, [data-testid="stExpander"] {{ 
            background-color: {card_bg} !important; 
            border-radius: 15px; 
            padding: 15px; 
            margin-bottom: 15px; 
            border: 1px solid {border_color} !important; 
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05); 
        }}
        
        .user-boy {{ border-left: 5px solid #4B89FF; text-align: left; }}
        .user-girl {{ border-right: 5px solid #FF85A2; text-align: right; }}
        .time-text {{ font-size: 0.8rem; color: gray !important; }}
        div.stButton > button {{ border-radius: 20px; font-weight: bold; background-color: {card_bg} !important; border: 1px solid {border_color} !important; color: {text_color} !important; }}
        [data-testid="stMetricValue"] {{ color: {accent_color} !important; }}
        </style>
        """, unsafe_allow_html=True)

    st.markdown(f"""
        <div style="background-color: {card_bg}; padding: 12px; border-radius: 10px; border: 2px dashed #FF85A2; text-align: center; margin-bottom: 15px; box-shadow: 0px 4px 6px rgba(0,0,0,0.05);">
            <span style="font-size: 1.1rem; font-weight: bold; color: #FF85A2;">🚨 스마트폰 접속 시 필독! 🚨</span><br>
            <span style="color: {text_color};">화면 맨 왼쪽 위 <b>[ > ]</b> 모양 버튼을 눌러야<br>우리의 D-Day와 데이트 일정을 볼 수 있어요! 👈</span>
        </div>
        """, unsafe_allow_html=True)

    col_h1, col_h2 = st.columns([0.85, 0.15])
    col_h1.markdown(f"<h2 style='color: #FF85A2; margin:0;'>♥ 수기 커플 노트</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄"):
        st.session_state.clear()
        st.rerun()

    st.success(f"📢 {st.session_state.notice}")
    with st.expander("✏️ 공지사항 수정"):
        new_notice = st.text_input("새로운 공지 내용을 적어주세요.", value=st.session_state.notice)
        if st.button("공지 변경 확정 💾"):
            st.session_state.notice = new_notice
            save_main_data()
            st.session_state.toast_msg = "공지사항이 성공적으로 변경되었습니다! 📢"
            st.rerun()

    # ==========================================
    # 📌 사이드바 (메뉴 구성)
    # ==========================================
    with st.sidebar:
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
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

    # ==========================================
    # 📌 메인 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "📸 사진첩", "⏳ 타임라인", "🎡 만능 룰렛", "📍 장소/기록", "🎁 타임캡슐"])

    with tabs[0]:
        st.subheader("🗓️ 우리의 데이트 일정")
        with st.form("schedule_form", clear_on_submit=True):
            s_date = st.date_input("데이트 날짜")
            s_plan = st.text_input("무엇을 할까요?")
            if st.form_submit_button("일정 추가") and s_plan:
                st.session_state.date_schedules.append({"date": str(s_date), "plan": s_plan, "by": user_name_only})
                st.session_state.date_schedules.sort(key=lambda x: x['date'])
                save_specific_large_data(sheet_date, st.session_state.date_schedules)
                st.session_state.toast_msg = "데이트 일정이 추가되었습니다! 🗓️"
                st.rerun()
                
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 [{s['date']}] {s['plan']}"):
                edit_s = st.text_input("일정 수정", value=s['plan'], key=f"edit_s_{i}")
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("수정 완료", key=f"btn_s_edit_{i}"):
                    st.session_state.date_schedules[i]['plan'] = edit_s
                    save_specific_large_data(sheet_date, st.session_state.date_schedules)
                    st.session_state.toast_msg = "일정이 수정되었습니다! ✨"
                    st.rerun()
                if col_s2.button("삭제하기 🗑️", key=f"btn_s_del_{i}"):
                    st.session_state.date_schedules.pop(i)
                    save_specific_large_data(sheet_date, st.session_state.date_schedules)
                    st.session_state.toast_msg = "일정이 삭제되었습니다. 🗑️"
                    st.rerun()
                
        st.divider()
        st.subheader("🎭 오늘 우리의 기분")
        st.caption("매일 자정(한국시간)에 초기화됩니다.")
        
        mood_options = ["😢", "☁️", "🙂", "🥰", "🔥"]
        mood_desc = {"😢": "피곤함/우울", "☁️": "그저그럼", "🙂": "보통/평온", "🥰": "기분좋음", "🔥": "최고/열정!"}
        
        my_mood = st.select_slider(f"{user_name_only}의 기분 선택", options=mood_options, value=st.session_state.moods[user_name_only])
        st.write(f"👉 선택한 기분: **{mood_desc[my_mood]}**")
        
        if st.button("기분 업데이트"):
            st.session_state.moods[user_name_only] = my_mood
            today_record = next((item for item in st.session_state.mood_history if item["date"] == today_str), None)
            mood_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
            if today_record:
                today_record[f"{user_name_only}_score"] = mood_score[my_mood]
            else:
                new_record = {"date": today_str, "수기남자친구_score": mood_score[st.session_state.moods["수기남자친구"]], "수기_score": mood_score[st.session_state.moods["수기"]]}
                new_record[f"{user_name_only}_score"] = mood_score[my_mood]
                st.session_state.mood_history.append(new_record)
            
            save_main_data()
            st.session_state.toast_msg = f"{user_name_only}님의 기분이 업데이트 되었습니다! 💖"
            st.rerun()

        st.write(f"👦 수기남자친구: {st.session_state.moods['수기남자친구']} ({mood_desc[st.session_state.moods['수기남자친구']]})")
        st.write(f"👧 수기: {st.session_state.moods['수기']} ({mood_desc[st.session_state.moods['수기']]})")

    with tabs[1]:
        st.subheader("💌 오늘의 쪽지 (수정은 당일만!)")
        my_today_memo_idx = None
        for i, m in enumerate(st.session_state.memo_history):
            if m['date'] == today_str and m['user'] == user_name_only:
                my_today_memo_idx = i
                break
        
        with st.container():
            if my_today_memo_idx is not None:
                st.info("오늘의 쪽지를 이미 작성했어요! ✍️")
                with st.form("edit_memo_form"):
                    edit_content = st.text_area("쪽지 내용", value=st.session_state.memo_history[my_today_memo_idx]['content'])
                    if st.form_submit_button("수정 완료"):
                        st.session_state.memo_history[my_today_memo_idx]['content'] = edit_content
                        st.session_state.memo_history[my_today_memo_idx]['edited'] = True
                        save_specific_large_data(sheet_memo, st.session_state.memo_history)
                        st.session_state.toast_msg = "쪽지가 수정되었습니다! 💌"
                        st.rerun()
            else:
                with st.form("new_memo_form"):
                    content = st.text_area("오늘 하루, 하고 싶은 말은?")
                    if st.form_submit_button("남기기") and content:
                        st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content, "edited": False})
                        save_specific_large_data(sheet_memo, st.session_state.memo_history)
                        st.session_state.toast_msg = "오늘의 쪽지를 남겼습니다! 💌"
                        st.rerun()

        st.divider()
        for m in st.session_state.memo_history:
            is_boy = "수기남자친구" in m['user']
            align_cls = "user-boy" if is_boy else "user-girl"
            st.markdown(f'<div class="card {align_cls}"><small><b>{m["user"]}</b> | {m["date"]}</small><p style="margin: 5px 0;">{m["content"]}</p><span class="time-text">{m["time"]}</span></div>', unsafe_allow_html=True)

    # 🚀 [v4.0 핵심] 영구 보존 2TB 구글 드라이브 사진첩 적용!
    with tabs[2]:
        st.subheader("📸 2TB 영구 보존 사진첩")
        img_file = st.file_uploader("사진 올리기 (자동으로 구글 드라이브에 저장됩니다)", type=["jpg", "png", "jpeg"])
        
        if img_file and st.button("☁️ 2TB 드라이브에 안전하게 업로드"):
            with st.spinner("구글 드라이브 궁전으로 사진을 전송하고 있습니다... ⏳"):
                filename = f"{today_str}_{user_name_only}_{random.randint(1000, 9999)}.jpg"
                upload_photo_to_drive(img_file.getvalue(), filename)
                st.session_state.toast_msg = "사진이 드라이브에 영구 저장되었습니다! 🚀"
                st.rerun()
                
        st.divider()
        
        # 드라이브에서 사진 목록 불러와서 화면에 그리기
        photos = load_photos_from_drive()
        if not photos:
            st.caption("아직 구글 드라이브에 업로드된 사진이 없습니다.")
        else:
            for p in photos:
                try:
                    # 사진 파일 바이트를 가져와서 렌더링 (보안 우회)
                    img_bytes = get_image_bytes(p['id'])
                    # 파일명에서 날짜와 작성자 정보 예쁘게 파싱
                    title_info = p['name'].split('_')
                    caption_text = f"{title_info[0]} by {title_info[1]}" if len(title_info) >= 2 else p['name']
                    st.image(img_bytes, caption=caption_text, use_container_width=True)
                except Exception as e:
                    st.error("보안 상의 이유로 이 사진을 화면에 그리지 못했습니다.")

    with tabs[3]:
        st.subheader("⏳ 타임라인")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event, "by": user_name_only})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_specific_large_data(sheet_time, st.session_state.timeline)
                st.session_state.toast_msg = "타임라인이 기록되었습니다! ⏳"
                st.rerun()
        for item in st.session_state.timeline:
            st.markdown(f'<div class="card"><b>{item["date"]}</b> ({item.get("by", "")})<br>{item["event"]}</div>', unsafe_allow_html=True)

    with tabs[4]:
        st.subheader("🎡 결정장애 해결! 만능 룰렛")
        st.markdown("#### 🎯 무엇이든 랜덤 뽑기!")
        st.caption("선택지를 쉼표(,)로 구분해서 적어주세요! (예: 내가 쏘기, 너가 쏘기, 반반)")
        custom_options = st.text_input("선택지 입력", placeholder="치킨, 피자, 족발")
        
        if st.button("결정의 룰렛 돌리기! 🎲"):
            if custom_options.strip():
                opts = [o.strip() for o in custom_options.split(",") if o.strip()]
                if opts:
                    chosen = random.choice(opts)
                    st.success(f"🎉 당첨: **{chosen}** ‼️")
                    st.balloons()
                else: st.warning("선택지를 제대로 입력해주세요!")
            else: st.warning("선택지를 먼저 입력해주세요!")
                
        st.divider()
        st.markdown("#### 😋 저장해둔 메뉴 리스트에서 뽑기")
        if st.button("메뉴 랜덤 뽑기! 🥩"):
            if st.session_state.menu_list:
                chosen_menu = random.choice(st.session_state.menu_list)
                st.warning(f"오늘의 추천 메뉴는 바로: **{chosen_menu}** 😋")
            else: st.error("저장된 메뉴가 없습니다. 아래에서 추가해주세요!")
            
        with st.expander("🍽️ 우리만의 메뉴 리스트 관리"):
            with st.form("menu_form", clear_on_submit=True):
                new_menu = st.text_input("새로운 메뉴 추가")
                if st.form_submit_button("메뉴 추가") and new_menu:
                    st.session_state.menu_list.append(new_menu)
                    save_main_data()
                    st.session_state.toast_msg = "새 메뉴가 리스트에 추가되었습니다! 🍽️"
                    st.rerun()
                    
            for i, menu in enumerate(st.session_state.menu_list):
                col_m1, col_m2 = st.columns([0.7, 0.3])
                col_m1.write(f"- {menu}")
                if col_m2.button("삭제", key=f"btn_m_del_{i}"):
                    st.session_state.menu_list.pop(i)
                    save_main_data()
                    st.session_state.toast_msg = "메뉴가 삭제되었습니다."
                    st.rerun()

    with tabs[5]:
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form", clear_on_submit=True):
            w_place = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가") and w_place:
                st.session_state.wishlist.append({"place": w_place, "visited": False, "by": user_name_only})
                save_specific_large_data(sheet_wish, st.session_state.wishlist)
                st.session_state.toast_msg = "위시리스트에 장소가 추가되었습니다! 📍"
                st.rerun()
                
        st.write("👇 **장소를 터치하여 방문 체크 및 관리하세요!**")
        for i, w in enumerate(st.session_state.wishlist):
            if isinstance(w, str):
                st.session_state.wishlist[i] = {"place": w, "visited": False, "by": "알수없음"}
                w = st.session_state.wishlist[i]
                
            is_visited = w.get('visited', False)
            icon = "✅" if is_visited else "📍"
            status_text = "(다녀옴!) " if is_visited else ""
            
            with st.expander(f"{icon} {status_text}{w['place']}"):
                new_visited = st.checkbox("다녀왔어요! 👣", value=is_visited, key=f"chk_w_{i}")
                if new_visited != is_visited:
                    st.session_state.wishlist[i]['visited'] = new_visited
                    save_specific_large_data(sheet_wish, st.session_state.wishlist)
                    st.session_state.toast_msg = "방문 상태가 저장되었습니다! 👣"
                    st.rerun()
                
                if not new_visited:
                    edit_w = st.text_input("장소명 수정", value=w['place'], key=f"edit_w_{i}")
                    col_w1, col_w2 = st.columns(2)
                    if col_w1.button("수정 완료", key=f"btn_w_edit_{i}"):
                        st.session_state.wishlist[i]['place'] = edit_w
                        save_specific_large_data(sheet_wish, st.session_state.wishlist)
                        st.session_state.toast_msg = "장소명이 수정되었습니다! ✨"
                        st.rerun()
                    if col_w2.button("삭제하기 🗑️", key=f"btn_w_del_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_specific_large_data(sheet_wish, st.session_state.wishlist)
                        st.session_state.toast_msg = "장소가 목록에서 삭제되었습니다."
                        st.rerun()
                else:
                    if st.button("목록에서 완전히 삭제하기 🗑️", key=f"btn_w_del_v_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_specific_large_data(sheet_wish, st.session_state.wishlist)
                        st.session_state.toast_msg = "장소가 완전히 삭제되었습니다."
                        st.rerun()
        
        st.divider()
        st.subheader("📝 데이트 후기")
        with st.form("r_form", clear_on_submit=True):
            r_name = st.text_input("장소명")
            r_link = st.text_input("장소 지도 링크 (URL - 선택사항)")
            r_cat = st.selectbox("종류", ["음식점", "카페", "공원", "기타"])
            r_rating = st.selectbox("별점", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
            r_comment = st.text_area("후기")
            if st.form_submit_button("후기 등록") and r_name:
                st.session_state.reviews.insert(0, {
                    "name": r_name, "link": r_link, "cat": r_cat, "rating": r_rating, 
                    "comment": r_comment, "photo_url": "", "date": today_str, "by": user_name_only
                })
                save_specific_large_data(sheet_review, st.session_state.reviews)
                st.session_state.toast_msg = "정성스러운 데이트 후기가 등록되었습니다! 📝"
                st.rerun()
        
        for r in st.session_state.reviews:
            link_html = f"<br><a href='{r.get('link', '#')}' target='_blank'>🔗 지도에서 보기</a>" if r.get('link') else ""
            st.markdown(f"""
                <div class="card">
                    <span style="background-color:rgba(128,128,128,0.2); padding:2px 5px; border-radius:5px; font-size:0.8rem; color:{text_color};">{r['cat']}</span>
                    <b>{r['name']}</b> {r['rating']} ({r['date']})
                    {link_html} <br><br>
                    <p style="margin: 0; color:{text_color};">{r['comment']}</p>
                </div>
                """, unsafe_allow_html=True)

    with tabs[6]:
        st.subheader("🎁 미래로 보내는 타임캡슐")
        st.write("지정된 날짜가 되기 전까지는 편지를 절대 열어볼 수 없습니다! 🤫")

        with st.form("capsule_form", clear_on_submit=True):
            c_title = st.text_input("타임캡슐 이름 (예: 우리의 1주년)")
            c_date = st.date_input("열어볼 날짜", min_value=now_kst.date() + datetime.timedelta(days=1))
            c_content = st.text_area("미래의 우리에게 남길 편지")
            
            if st.form_submit_button("타임캡슐 묻기 ⛏️") and c_title and c_content:
                st.session_state.time_capsules.append({
                    "title": c_title,
                    "open_date": str(c_date),
                    "content": c_content,
                    "by": user_name_only,
                    "created_date": today_str
                })
                st.session_state.time_capsules.sort(key=lambda x: x['open_date'])
                save_capsule_data() # Atomic Save
                st.session_state.toast_msg = f"{c_date}에 개봉될 타임캡슐을 안전하게 묻었습니다! 🔒"
                st.rerun()

        st.divider()
        st.subheader("묻혀있는 타임캡슐 목록 🗺️")
        
        if not st.session_state.time_capsules:
            st.caption("아직 땅에 묻은 타임캡슐이 없어요!")
            
        for i, cap in enumerate(st.session_state.time_capsules):
            is_open = today_str >= cap['open_date']
            
            if is_open:
                with st.expander(f"🎉 [열림] {cap['title']} (개봉일: {cap['open_date']})"):
                    st.write(f"**📝 작성자:** {cap['by']} (묻은 날: {cap.get('created_date', '과거')})")
                    st.info(cap['content'])
                    if st.button("빈 캡슐 버리기 🗑️", key=f"del_cap_{i}"):
                        st.session_state.time_capsules.pop(i)
                        save_capsule_data()
                        st.session_state.toast_msg = "개봉된 타임캡슐을 삭제했습니다. 🗑️"
                        st.rerun()
            else:
                target_date = datetime.datetime.strptime(cap['open_date'], "%Y-%m-%d").date()
                d_day = (target_date - now_kst.date()).days
                
                with st.expander(f"🔒 [잠김] {cap['title']} (D-{d_day}일)"):
                    st.warning(f"이 캡슐은 **{cap['open_date']} 자정(KST)**에 열쇠가 풀립니다! 🗝️")
                    st.write(f"**📝 작성자:** {cap['by']} (묻은 날: {cap.get('created_date', '과거')})")
