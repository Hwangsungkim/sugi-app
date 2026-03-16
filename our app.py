import streamlit as st
from datetime import date, datetime
import pandas as pd
import random
import json
import gspread
from google.oauth2.credentials import Credentials

# 1. 앱 기본 설정
st.set_page_config(page_title="수기 커플 노트", page_icon="🌸", layout="centered")

# --- 커스텀 CSS ---
st.markdown("""
    <style>
    .main { background-color: #fff5f5; }
    .stButton>button { border-radius: 20px; width: 100%; }
    .notice-board { background-color: #fffbe6; padding: 15px; border-radius: 12px; border-left: 6px solid #ffcc00; margin-bottom: 20px; color: #856404; font-weight: bold; }
    .promise-card { background-color: #ffffff; padding: 25px; border-radius: 20px; border: 2px solid #ff4b4b; margin-bottom: 20px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .promise-text { font-size: 1.1rem; font-weight: bold; color: #333; margin-bottom: 10px; }
    .timeline-item { border-left: 3px solid #ff4b4b; padding-left: 20px; margin-bottom: 25px; }
    .review-card { background: white; padding: 15px; border-radius: 15px; border: 1px solid #ffebeb; margin-bottom: 10px; box-shadow: 2px 2px 8px rgba(0,0,0,0.05); }
    .tag { background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-right: 5px; }
    .memo-card { background-color: #ffffff; padding: 15px; border-radius: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .user-boy { border-left: 5px solid #4B89FF; text-align: left; }
    .user-girl { border-right: 5px solid #FF4B4B; text-align: right; }
    .time-text { font-size: 0.8rem; color: #888; }
    </style>
    """, unsafe_allow_html=True)

# --- 🚀 구글 시트 연동 설정 ---
@st.cache_resource
def get_google_sheet():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # 서버(Secrets)에 저장된 토큰 정보를 읽어옵니다.
    # 만약 서버에 정보가 없다면 내 컴퓨터의 token.json을 읽습니다.
    if "google_auth" in st.secrets:
        token_info = json.loads(st.secrets["google_auth"]["token"])
        creds = Credentials.from_authorized_user_info(token_info, scopes)
    else:
        creds = Credentials.from_authorized_user_file('token.json', scopes)
        
    client = gspread.authorize(creds)
    return client.open('couple_app_data').sheet1

sheet = get_google_sheet()

# 데이터 불러오기 함수
def load_data():
    try:
        val = sheet.acell('A1').value
        if val:
            return json.loads(val)
    except:
        pass
    # 데이터가 없으면 기본값 반환
    return {
        "notice": "비타민 챙겨 먹기! 오늘 하루도 화이팅 ✨",
        "promises": ["서운한 건 그날 바로 말하기 🗣️", "하루에 한 번은 사랑한다고 말하기 ❤️", "싸워도 연락 끊지 않기 📱"],
        "daily_memo": None,
        "timeline": [{"date": "2026-01-01", "event": "우리 사귀기 시작한 날! ❤️"}],
        "moods": {"수기남자친구": "🙂", "수기": "🙂"},
        "challenges": [],
        "wishlist": [],
        "reviews": [],
        "menu_list": ["삼겹살", "초밥", "파스타", "치킨", "떡볶이"]
    }

# 데이터 저장하기 함수
def save_data():
    # 현재 세션 상태의 데이터를 딕셔너리로 모아서 시트 A1 칸에 저장 (사진 제외)
    data_to_save = {
        "notice": st.session_state.notice,
        "promises": st.session_state.promises,
        "daily_memo": st.session_state.daily_memo,
        "timeline": st.session_state.timeline,
        "moods": st.session_state.moods,
        "challenges": st.session_state.challenges,
        "wishlist": st.session_state.wishlist,
        "reviews": st.session_state.reviews,
        "menu_list": st.session_state.menu_list
    }
    sheet.update_acell('A1', json.dumps(data_to_save))

# --- 보안 설정 ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.title("🔐 수기 커플 노트")
    pwd = st.text_input("우리 둘만의 비밀번호", type="password")
    if st.button("사랑으로 열기 ❤️"):
        if pwd == "6146":  
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("비밀번호가 틀렸어!")
    return False

# --- 메인 로직 시작 ---
if check_password():
    # 1. 앱 시작 시 구글 시트에서 데이터 쫙 불러오기
    if 'data_loaded' not in st.session_state:
        saved_data = load_data()
        for key, value in saved_data.items():
            st.session_state[key] = value
        st.session_state['photos'] = [] # 사진은 세션에서만 임시 보관
        st.session_state['data_loaded'] = True

    # 사이드바
    with st.sidebar:
        st.title("👤 접속자 설정")
        user_type = st.radio("당신은?", ["수기남자친구 👦", "수기 👧"])
        st.divider()
        if st.button("로그아웃"):
            st.session_state["password_correct"] = False
            st.rerun()

    # 1. 수기 전용 알림판
    st.markdown(f'<div class="notice-board">📢 수기 알림판: {st.session_state.notice}</div>', unsafe_allow_html=True)
    with st.expander("🔔 알림판 문구 수정하기"):
        updated_notice = st.text_input("수정할 공지", value=st.session_state.notice)
        if st.button("수정 완료"):
            st.session_state.notice = updated_notice
            save_data() # 변경될 때마다 시트에 저장!
            st.rerun()

    st.markdown(f"<h1 style='text-align: center; color: #ff4b4b;'>❤️ 수기 커플 노트</h1>", unsafe_allow_html=True)
    
    # --- 탭 구성 ---
    tabs = st.tabs(["🤝 약속", "💌 쪽지함", "📸 사진첩", "📅 타임라인", "🎭 기분/날씨", "🎰 챌린지/랜덤", "📍 장소/기록"])

    # --- 탭 1: 약속 & D-Day ---
    with tabs[0]:
        start_date = date(2026, 1, 1) # 실제 사귄 날짜로 수정하세요!
        days_passed = (date.today() - start_date).days
        next_100d = 100 - (days_passed % 100)
        
        col_d1, col_d2 = st.columns(2)
        col_d1.metric(label="우리가 사랑한 지", value=f"{days_passed}일")
        col_d2.metric(label="다음 100일 기념일까지", value=f"{next_100d}일")
        st.divider()
        
        st.subheader("📜 우리가 꼭 지키기로 한 약속")
        st.markdown('<div class="promise-card">', unsafe_allow_html=True)
        for i, p in enumerate(st.session_state.promises):
            st.markdown(f'<div class="promise-text">{i+1}. {p}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("✨ 약속 추가 및 수정하기"):
            new_promise = st.text_input("새로운 약속 추가", placeholder="예: 한 달에 한 번은 여행 가기")
            if st.button("새 약속 저장") and new_promise:
                st.session_state.promises.append(new_promise)
                save_data()
                st.rerun()
            
            st.divider()
            st.write("✏️ **기존 약속 수정 / 삭제**")
            for i, p in enumerate(st.session_state.promises):
                col_p1, col_p2, col_p3 = st.columns([0.6, 0.2, 0.2])
                edit_p = col_p1.text_input(f"약속 {i+1}", value=p, key=f"edit_{i}", label_visibility="collapsed")
                if col_p2.button("수정", key=f"btn_edit_{i}"):
                    st.session_state.promises[i] = edit_p
                    save_data()
                    st.rerun()
                if col_p3.button("삭제", key=f"btn_del_{i}"):
                    st.session_state.promises.pop(i)
                    save_data()
                    st.rerun()

    # --- 탭 2: 쪽지함 ---
    with tabs[1]:
        st.subheader("💌 오늘의 쪽지")
        if st.session_state.daily_memo:
            m = st.session_state.daily_memo
            is_boy = "수기남자친구" in m['user']
            alignment_class = "user-boy" if is_boy else "user-girl"
            
            st.markdown(f"""
                <div class="memo-card {alignment_class}">
                    <small><b>{m['user']}</b></small>
                    <p style="font-size:1.1rem; margin:5px 0;">{m['content']}</p>
                    <span class="time-text">{m['time']} {"(수정됨)" if m['edited'] else ""}</span>
                </div>
                """, unsafe_allow_html=True)
            
            if not m['edited']:
                with st.expander("딱 한 번 수정하기"):
                    edit_content = st.text_input("내용 수정", value=m['content'])
                    if st.button("쪽지 수정 완료"):
                        st.session_state.daily_memo.update({"content": edit_content, "edited": True, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        save_data()
                        st.rerun()
        else:
            with st.form("memo_form", clear_on_submit=True):
                content = st.text_input("오늘의 한마디를 남겨줘")
                if st.form_submit_button("쪽지 남기기") and content:
                    st.session_state.daily_memo = {"content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "user": user_type, "edited": False}
                    save_data()
                    st.rerun()

    # --- 탭 3: 사진첩 ---
    with tabs[2]:
        st.subheader("📸 우리들의 사진첩 (임시 보관)")
        st.caption("⚠️ 사진은 구글 시트 용량 제한으로 접속 중일 때만 보관됩니다.")
        img_file = st.file_uploader("사진 올리기", type=["jpg", "png"])
        img_cap = st.text_input("사진 설명")
        if st.button("사진첩 저장"):
            if img_file:
                st.session_state.photos.insert(0, {"img": img_file.getvalue(), "cap": img_cap, "date": date.today(), "user": user_type})
                st.rerun()
        for p in st.session_state.photos:
            st.image(p['img'], caption=f"{p['date']} | {p['cap']} (by {p['user']})", use_container_width=True)

    # --- 탭 4: 타임라인 ---
    with tabs[3]:
        st.subheader("⏳ 우리만의 역사")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("사건 저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_data()
                st.rerun()
        for item in st.session_state.timeline:
            st.markdown(f'<div class="timeline-item"><b>{item["date"]}</b><br>{item["event"]}</div>', unsafe_allow_html=True)

    # --- 탭 5: 기분 & 날씨 ---
    with tabs[4]:
        st.subheader("🎭 오늘 우리의 기분")
        user_key = "수기남자친구" if "남자친구" in user_type else "수기"
        my_mood = st.select_slider(f"{user_key}의 기분", options=["😢", "☁️", "🙂", "🥰", "🔥"])
        if st.button("기분 업데이트"):
            st.session_state.moods[user_key] = my_mood
            save_data()
            st.rerun()
        
        mood_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
        avg = (mood_score[st.session_state.moods["수기남자친구"]] + mood_score[st.session_state.moods["수기"]]) / 2
        weather = "☀️ 맑음" if avg >= 4 else "⛅ 구름조금" if avg >= 3 else "☔ 흐림/비"
        st.info(f"오늘 우리 사이 날씨: **{weather}**")

    # --- 탭 6: 챌린지 & 랜덤메뉴 ---
    with tabs[5]:
        st.subheader("🏆 우리만의 챌린지")
        with st.form("c_form", clear_on_submit=True):
            new_c = st.text_input("새 챌린지")
            if st.form_submit_button("추가") and new_c:
                st.session_state.challenges.append({"name": new_c, "count": 0})
                save_data()
                st.rerun()
        for i, c in enumerate(st.session_state.challenges):
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(f"**{c['name']}** ({c['count']}회)")
            if col2.button("+1", key=f"c_{i}"):
                st.session_state.challenges[i]['count'] += 1
                save_data()
                st.rerun()
        
        st.divider()
        st.subheader("🎰 메뉴 돌림판")
        if st.button("메뉴 랜덤 뽑기! 🎲"):
            st.warning(f"오늘의 추천 메뉴: **{random.choice(st.session_state.menu_list)}**")
        with st.expander("🍴 메뉴 리스트 관리"):
            new_menu = st.text_input("새 메뉴 추가")
            if st.button("메뉴 추가") and new_menu:
                st.session_state.menu_list.append(new_menu)
                save_data()
                st.rerun()
            st.write(f"현재 메뉴: {', '.join(st.session_state.menu_list)}")

    # --- 탭 7: 장소 위시리스트, 후기 & 통계 ---
    with tabs[6]:
        col_w, col_r = st.columns(2)
        with col_w:
            st.subheader("📍 위시리스트")
            with st.form("w_form", clear_on_submit=True):
                w_place = st.text_input("가고 싶은 곳")
                if st.form_submit_button("저장") and w_place:
                    st.session_state.wishlist.append(w_place)
                    save_data()
                    st.rerun()
            for w in st.session_state.wishlist: st.write(f"· {w}")
            
        with col_r:
            st.subheader("📝 데이트 후기")
            with st.form("r_form", clear_on_submit=True):
                r_name = st.text_input("장소명")
                r_cat = st.selectbox("종류", ["음식점", "카페", "공원", "기타"])
                r_rating = st.selectbox("별점", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
                r_comment = st.text_area("후기")
                if st.form_submit_button("후기 등록") and r_name:
                    st.session_state.reviews.insert(0, {"name": r_name, "cat": r_cat, "rating": r_rating, "comment": r_comment, "date": date.today()})
                    save_data()
                    st.rerun()
        
        st.divider()
        for r in st.session_state.reviews:
            st.markdown(f"""<div class="review-card"><span class="tag">{r['cat']}</span><b>{r['name']}</b> {r['rating']} ({r['date']})<br>{r['comment']}</div>""", unsafe_allow_html=True)
            
        st.divider()
        st.subheader("📊 수기 커플 통계")
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("기록된 역사", f"{len(st.session_state.timeline)}건")
        s_col2.metric("보관된 사진", f"{len(st.session_state.photos)}장")
        s_col3.metric("다녀온 장소", f"{len(st.session_state.reviews)}곳")
