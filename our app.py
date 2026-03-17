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
    .timeline-item { border-left: 3px solid #ff4b4b; padding-left: 20px; margin-bottom: 25px; background: white; padding: 15px; border-radius: 10px; box-shadow: 1px 1px 5px rgba(0,0,0,0.05); }
    .review-card { background: white; padding: 15px; border-radius: 15px; border: 1px solid #ffebeb; margin-bottom: 10px; box-shadow: 2px 2px 8px rgba(0,0,0,0.05); }
    .tag { background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-right: 5px; }
    .memo-card { background-color: #ffffff; padding: 15px; border-radius: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .user-boy { border-left: 5px solid #4B89FF; text-align: left; }
    .user-girl { border-right: 5px solid #FF4B4B; text-align: right; }
    .time-text { font-size: 0.8rem; color: #888; }
    .creator-tag { font-size: 0.75rem; color: #999; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# --- 🚀 구글 시트 연동 설정 ---
@st.cache_resource
def get_google_sheet():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    if "google_auth" in st.secrets:
        token_info = json.loads(st.secrets["google_auth"]["token"])
        creds = Credentials.from_authorized_user_info(token_info, scopes)
    else:
        creds = Credentials.from_authorized_user_file('token.json', scopes)
    client = gspread.authorize(creds)
    return client.open('couple_app_data').sheet1

sheet = get_google_sheet()

# 데이터 불러오기 함수 (구조 업데이트 적용)
def load_data():
    try:
        val = sheet.acell('A1').value
        if val:
            data = json.loads(val)
            # 이전 버전 호환 및 새 리스트 기본값 설정
            if "memo_history" not in data: data["memo_history"] = []
            return data
    except:
        pass
    # 데이터가 없거나 에러 시 기본값
    return {
        "notice": "비타민 챙겨 먹기! 오늘 하루도 화이팅 ✨",
        "promises": [{"text": "서운한 건 그날 바로 말하기 🗣️", "by": "수기남자친구"}],
        "memo_history": [],
        "timeline": [{"date": "2026-01-01", "event": "우리 사귀기 시작한 날! ❤️", "by": "시스템"}],
        "moods": {"수기남자친구": "🙂", "수기": "🙂"},
        "challenges": [],
        "wishlist": [],
        "reviews": [],
        "menu_list": ["삼겹살", "초밥", "파스타", "치킨", "떡볶이"]
    }

def save_data():
    data_to_save = {
        "notice": st.session_state.notice,
        "promises": st.session_state.promises,
        "memo_history": st.session_state.memo_history,
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
    if 'data_loaded' not in st.session_state:
        saved_data = load_data()
        for key, value in saved_data.items():
            st.session_state[key] = value
        st.session_state['photos'] = [] 
        st.session_state['data_loaded'] = True

    # 사이드바 (접속자 확실히 표시!)
    with st.sidebar:
        st.title("👤 접속 설정")
        user_type = st.radio("당신은 누구인가요?", ["수기남자친구 👦", "수기 👧"])
        # 접속자 족적 및 알림 강조
        user_name_only = "수기남자친구" if "남자친구" in user_type else "수기"
        st.success(f"현재 **{user_name_only}**님으로 로그인 중입니다! 👋")
        
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
            save_data() 
            st.rerun()

    st.markdown(f"<h1 style='text-align: center; color: #ff4b4b;'>❤️ 수기 커플 노트</h1>", unsafe_allow_html=True)
    
    tabs = st.tabs(["🤝 약속", "💌 쪽지함", "📸 사진첩", "📅 타임라인", "🎭 기분/날씨", "🎰 챌린지/랜덤", "📍 장소/기록"])

    # --- 탭 1: 약속 (작성자 표시) ---
    with tabs[0]:
        start_date = date(2026, 1, 1) # 사귄 날짜 수정 필요!
        days_passed = (date.today() - start_date).days
        next_100d = 100 - (days_passed % 100)
        
        col_d1, col_d2 = st.columns(2)
        col_d1.metric(label="우리가 사랑한 지", value=f"{days_passed}일")
        col_d2.metric(label="다음 100일 기념일까지", value=f"{next_100d}일")
        st.divider()
        
        st.subheader("📜 우리가 꼭 지키기로 한 약속")
        st.markdown('<div class="promise-card">', unsafe_allow_html=True)
        # 딕셔너리와 문자열 모두 호환되도록 처리 (과거 데이터 방어)
        for i, p in enumerate(st.session_state.promises):
            if isinstance(p, dict):
                p_text, p_by = p['text'], p.get('by', '알수없음')
            else:
                p_text, p_by = p, '이전기록'
            st.markdown(f'<div class="promise-text">{i+1}. {p_text} <span class="creator-tag">({p_by})</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("✨ 약속 추가 및 수정하기"):
            new_promise = st.text_input("새로운 약속 추가", placeholder="예: 한 달에 한 번은 여행 가기")
            if st.button("새 약속 저장") and new_promise:
                st.session_state.promises.append({"text": new_promise, "by": user_name_only})
                save_data()
                st.rerun()
            
            st.divider()
            for i, p in enumerate(st.session_state.promises):
                current_text = p['text'] if isinstance(p, dict) else p
                col_p1, col_p2, col_p3 = st.columns([0.6, 0.2, 0.2])
                edit_p = col_p1.text_input(f"약속 {i+1}", value=current_text, key=f"edit_p_{i}", label_visibility="collapsed")
                if col_p2.button("수정", key=f"btn_edit_p_{i}"):
                    if isinstance(st.session_state.promises[i], dict):
                        st.session_state.promises[i]['text'] = edit_p
                        st.session_state.promises[i]['by'] = user_name_only + "(수정됨)"
                    else:
                        st.session_state.promises[i] = {"text": edit_p, "by": user_name_only + "(수정됨)"}
                    save_data()
                    st.rerun()
                if col_p3.button("삭제", key=f"btn_del_p_{i}"):
                    st.session_state.promises.pop(i)
                    save_data()
                    st.rerun()

    # --- 탭 2: 쪽지함 (히스토리 & 하루 1회 & 당일 수정) ---
    with tabs[1]:
        st.subheader("💌 우리의 쪽지함")
        today_str = str(date.today())
        
        # 오늘 내가 쓴 쪽지가 있는지 찾기
        my_today_memo_idx = None
        for i, m in enumerate(st.session_state.memo_history):
            if m['date'] == today_str and m['user'] == user_name_only:
                my_today_memo_idx = i
                break
        
        # 입력 폼 (당일 작성/수정)
        with st.container():
            if my_today_memo_idx is not None:
                st.info("오늘의 쪽지를 이미 작성했어요! 오늘 자정 전까지는 내용을 수정할 수 있습니다. ✍️")
                with st.form("edit_memo_form"):
                    edit_content = st.text_area("오늘의 쪽지 수정", value=st.session_state.memo_history[my_today_memo_idx]['content'])
                    if st.form_submit_button("쪽지 수정 완료"):
                        st.session_state.memo_history[my_today_memo_idx]['content'] = edit_content
                        st.session_state.memo_history[my_today_memo_idx]['edited'] = True
                        save_data()
                        st.rerun()
            else:
                with st.form("new_memo_form"):
                    content = st.text_area("오늘 하루, 상대방에게 하고 싶은 말은? (하루 한 번만 작성 가능!)")
                    if st.form_submit_button("쪽지 남기기") and content:
                        new_memo = {
                            "date": today_str,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "user": user_name_only,
                            "content": content,
                            "edited": False
                        }
                        st.session_state.memo_history.insert(0, new_memo) # 최신순 정렬
                        save_data()
                        st.rerun()

        st.divider()
        st.write("📖 **지난 쪽지 기록** (과거 쪽지는 수정/삭제 불가)")
        
        for m in st.session_state.memo_history:
            is_boy = "수기남자친구" in m['user']
            alignment_class = "user-boy" if is_boy else "user-girl"
            edited_mark = "(수정됨)" if m.get('edited', False) else ""
            
            st.markdown(f"""
                <div class="memo-card {alignment_class}">
                    <small><b>{m['user']}</b> | {m['date']}</small>
                    <p style="font-size:1.1rem; margin:5px 0;">{m['content']}</p>
                    <span class="time-text">{m['time']} {edited_mark}</span>
                </div>
                """, unsafe_allow_html=True)

    # --- 탭 3: 사진첩 ---
    with tabs[2]:
        st.subheader("📸 우리들의 사진첩 (임시 보관)")
        st.caption("⚠️ 사진은 구글 시트 용량 제한으로 접속 중일 때만 보관됩니다. (드라이브 연동 업데이트 대기 중!)")
        img_file = st.file_uploader("사진 올리기", type=["jpg", "png"])
        img_cap = st.text_input("사진 설명")
        if st.button("사진첩 저장"):
            if img_file:
                st.session_state.photos.insert(0, {"img": img_file.getvalue(), "cap": img_cap, "date": date.today(), "user": user_name_only})
                st.rerun()
        for p in st.session_state.photos:
            st.image(p['img'], caption=f"{p['date']} | {p['cap']} (by {p['user']})", use_container_width=True)

    # --- 탭 4: 타임라인 (작성자 표시) ---
    with tabs[3]:
        st.subheader("⏳ 우리만의 역사")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("사건 저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event, "by": user_name_only})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_data()
                st.rerun()
        for item in st.session_state.timeline:
            writer = item.get('by', '이전기록')
            st.markdown(f'<div class="timeline-item"><b>{item["date"]}</b> <span class="creator-tag">({writer})</span><br>{item["event"]}</div>', unsafe_allow_html=True)

    # --- 탭 5: 기분 & 날씨 (알림 효과 추가) ---
    with tabs[4]:
        st.subheader("🎭 오늘 우리의 기분")
        my_mood = st.select_slider(f"{user_name_only}의 기분", options=["😢", "☁️", "🙂", "🥰", "🔥"], value=st.session_state.moods[user_name_only])
        if st.button("기분 업데이트"):
            st.session_state.moods[user_name_only] = my_mood
            save_data()
            st.toast(f"{user_name_only}님의 기분이 업데이트 되었습니다! 💖", icon="✨") # 토스트 알림 추가!

        st.divider()
        mood_score = {"😢": 1, "☁️": 2, "🙂": 3, "🥰": 4, "🔥": 5}
        avg = (mood_score[st.session_state.moods["수기남자친구"]] + mood_score[st.session_state.moods["수기"]]) / 2
        weather = "☀️ 맑음" if avg >= 4 else "⛅ 구름조금" if avg >= 3 else "☔ 흐림/비 (서로 따뜻한 말이 필요해요)"
        
        st.write(f"👦 수기남자친구: {st.session_state.moods['수기남자친구']} / 👧 수기: {st.session_state.moods['수기']}")
        st.info(f"오늘 우리 사이 날씨: **{weather}**")

    # --- 탭 6: 챌린지 & 랜덤메뉴 (수정/삭제 기능 추가) ---
    with tabs[5]:
        st.subheader("🏆 우리만의 챌린지")
        with st.form("c_form", clear_on_submit=True):
            new_c = st.text_input("새 챌린지")
            if st.form_submit_button("추가") and new_c:
                st.session_state.challenges.append({"name": new_c, "count": 0, "by": user_name_only})
                save_data()
                st.rerun()
        
        for i, c in enumerate(st.session_state.challenges):
            col1, col2, col3, col4 = st.columns([0.5, 0.15, 0.15, 0.2])
            col1.write(f"**{c['name']}** ({c['count']}회)")
            if col2.button("+1", key=f"c_add_{i}"):
                st.session_state.challenges[i]['count'] += 1
                save_data()
                st.rerun()
            if col3.button("-1", key=f"c_sub_{i}"):
                st.session_state.challenges[i]['count'] = max(0, st.session_state.challenges[i]['count'] - 1)
                save_data()
                st.rerun()
            if col4.button("삭제", key=f"c_del_{i}"):
                st.session_state.challenges.pop(i)
                save_data()
                st.rerun()
        
        st.divider()
        st.subheader("🎰 메뉴 돌림판")
        if st.button("메뉴 랜덤 뽑기! 🎲"):
            st.warning(f"오늘의 추천 메뉴: **{random.choice(st.session_state.menu_list)}** 😋")
            st.toast("메뉴가 선택되었습니다!", icon="🍽️")
            
        with st.expander("🍴 메뉴 리스트 관리 (추가/수정/삭제)"):
            new_menu = st.text_input("새 메뉴 추가")
            if st.button("메뉴 추가") and new_menu:
                st.session_state.menu_list.append(new_menu)
                save_data()
                st.rerun()
                
            st.write("---")
            for i, menu in enumerate(st.session_state.menu_list):
                col_m1, col_m2, col_m3 = st.columns([0.6, 0.2, 0.2])
                edit_m = col_m1.text_input(f"메뉴 {i}", value=menu, key=f"edit_m_{i}", label_visibility="collapsed")
                if col_m2.button("수정", key=f"btn_m_edit_{i}"):
                    st.session_state.menu_list[i] = edit_m
                    save_data()
                    st.rerun()
                if col_m3.button("삭제", key=f"btn_m_del_{i}"):
                    st.session_state.menu_list.pop(i)
                    save_data()
                    st.rerun()

    # --- 탭 7: 장소 위시리스트, 후기 ---
    with tabs[6]:
        col_w, col_r = st.columns(2)
        with col_w:
            st.subheader("📍 위시리스트")
            with st.form("w_form", clear_on_submit=True):
                w_place = st.text_input("가고 싶은 곳")
                if st.form_submit_button("저장") and w_place:
                    st.session_state.wishlist.append({"place": w_place, "by": user_name_only})
                    save_data()
                    st.rerun()
            for i, w in enumerate(st.session_state.wishlist):
                # 구버전(문자열)과 신버전(딕셔너리) 호환
                p_name = w['place'] if isinstance(w, dict) else w
                p_by = w.get('by', '이전기록') if isinstance(w, dict) else '이전기록'
                
                col_w1, col_w2 = st.columns([0.8, 0.2])
                col_w1.write(f"· {p_name} <span class='creator-tag'>({p_by})</span>", unsafe_allow_html=True)
                if col_w2.button("X", key=f"del_w_{i}"):
                    st.session_state.wishlist.pop(i)
                    save_data()
                    st.rerun()
            
        with col_r:
            st.subheader("📝 데이트 후기")
            with st.form("r_form", clear_on_submit=True):
                r_name = st.text_input("장소명")
                r_cat = st.selectbox("종류", ["음식점", "카페", "공원", "기타"])
                r_rating = st.selectbox("별점", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])
                r_comment = st.text_area("후기")
                if st.form_submit_button("후기 등록") and r_name:
                    st.session_state.reviews.insert(0, {"name": r_name, "cat": r_cat, "rating": r_rating, "comment": r_comment, "date": str(date.today()), "by": user_name_only})
                    save_data()
                    st.rerun()
        
        st.divider()
        for r in st.session_state.reviews:
            r_by = r.get('by', '이전기록')
            st.markdown(f"""<div class="review-card"><span class="tag">{r['cat']}</span><b>{r['name']}</b> {r['rating']} ({r['date']}) <span class="creator-tag">by {r_by}</span><br>{r['comment']}</div>""", unsafe_allow_html=True)
