import streamlit as st
import datetime
import pytz
import pandas as pd
import random
import json
import gspread
from google.oauth2.credentials import Credentials

# 1. 앱 기본 설정 (홈화면 추가 시 하트 아이콘이 잡히도록 설정)
st.set_page_config(page_title="수기 커플 노트", page_icon="❤️", layout="centered")

# --- 🌐 한국 시간(KST) 설정 ---
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(KST)
today_str = str(now_kst.date())
current_time_str = now_kst.strftime("%H:%M")

# --- 🎨 감성 UI/UX 및 아이콘 깨짐 방지 CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');
    
    /* 텍스트 요소들에만 부드럽게 폰트 적용 (!important를 제거하여 아이콘 충돌 방지) */
    html, body, p, div, h1, h2, h3, h4, h5, h6, span, label, button, input, textarea, select {
        font-family: 'Gowun Dodum', sans-serif;
    }
    
    /* 스트림릿 아이콘(Material Symbols) 강제 복구 및 보호 */
    .material-symbols-rounded, [data-testid="stIconMaterial"], .st-emotion-cache-1r6slb6 {
        font-family: 'Material Symbols Rounded' !important;
    }
    
    .card { background-color: rgba(128, 128, 128, 0.05); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); border: 1px solid rgba(128, 128, 128, 0.1); }
    .user-boy { border-left: 5px solid #4B89FF; text-align: left; }
    .user-girl { border-right: 5px solid #FF4B4B; text-align: right; }
    .time-text { font-size: 0.8rem; color: gray; }
    
    /* 둥근 버튼 및 입력창 */
    div.stButton > button { border-radius: 20px; }
    div.stTextInput > div > div > input { border-radius: 10px; }
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

def load_data():
    try:
        val = sheet.acell('A1').value
        if val:
            data = json.loads(val)
            if "date_schedules" not in data: data["date_schedules"] = []
            if "mood_history" not in data: data["mood_history"] = []
            if "current_mood_date" not in data: data["current_mood_date"] = ""
            return data
    except:
        pass
    return {
        "notice": "비타민 챙겨 먹기! 오늘 하루도 화이팅 ✨",
        "promises": [{"text": "서운한 건 그날 바로 말하기 🗣️", "by": "수기남자친구"}],
        "memo_history": [],
        "timeline": [],
        "moods": {"수기남자친구": "🙂", "수기": "🙂"},
        "mood_history": [],
        "current_mood_date": today_str,
        "wishlist": [],
        "reviews": [],
        "menu_list": ["삼겹살", "초밥"],
        "date_schedules": []
    }

def save_data():
    data_to_save = {
        "notice": st.session_state.notice,
        "promises": st.session_state.promises,
        "memo_history": st.session_state.memo_history,
        "timeline": st.session_state.timeline,
        "moods": st.session_state.moods,
        "mood_history": st.session_state.mood_history,
        "current_mood_date": st.session_state.current_mood_date,
        "wishlist": st.session_state.wishlist,
        "reviews": st.session_state.reviews,
        "menu_list": st.session_state.menu_list,
        "date_schedules": st.session_state.date_schedules
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
        
        # 기분 초기화 로직
        if st.session_state.current_mood_date != today_str:
            st.session_state.moods = {"수기남자친구": "🙂", "수기": "🙂"}
            st.session_state.current_mood_date = today_str
            save_data()
            
        # 첫 접속 시 모바일 사이드바 안내 알림창 띄우기
        st.toast("👈 폰에서는 왼쪽 위 [ > ] 버튼을 누르면 메뉴가 열려요!", icon="💡")

    # 상단 헤더 & 모바일 최적화 사이드바 안내
    col_h1, col_h2 = st.columns([0.85, 0.15])
    col_h1.markdown(f"<h2 style='color: #ff4b4b;'>❤️ 수기 커플 노트</h2>", unsafe_allow_html=True)
    if col_h2.button("🔄"):
        st.session_state.clear()
        st.rerun()

    # 스마트폰 사용자를 위한 직관적인 사이드바 안내 문구
    st.info("👈 **스마트폰이신가요?** 왼쪽 상단의 **[ > ]** 모양 버튼을 누르면 우리의 디데이와 약속을 볼 수 있어요!")

    # 공지사항
    st.success(f"📢 {st.session_state.notice}")

    # ==========================================
    # 📌 사이드바 (메인 통합 요소)
    # ==========================================
    with st.sidebar:
        user_type = st.radio("👤 접속자", ["수기남자친구 👦", "수기 👧"])
        user_name_only = "수기남자친구" if "남자친구" in user_type else "수기"
        st.success(f"**{user_name_only}** 접속 중 👋")
        
        st.divider()
        
        # 1. 우리의 D-Day
        start_date = datetime.date(2026, 1, 1) # 사귄 날짜 (나중에 수정하세요!)
        days_passed = (now_kst.date() - start_date).days
        st.markdown(f"### 🌸 우리의 D-Day")
        st.write(f"**연애 시작일:** {start_date}")
        st.write(f"**D + {days_passed}일** ❤️")
        
        st.divider()
        
        # 2. 오늘 데이트 일정
        st.markdown("### 🗓️ 오늘 데이트 일정")
        today_plans = [p for p in st.session_state.date_schedules if p['date'] == today_str]
        if today_plans:
            for p in today_plans:
                st.write(f"✨ {p['plan']}")
        else:
            st.caption("오늘 등록된 일정이 없어요!")
            
        st.divider()
        
        # 3. 우리가 지키기로 한 약속
        st.markdown("### 📜 우리의 약속")
        for i, p in enumerate(st.session_state.promises):
            p_text = p['text'] if isinstance(p, dict) else p
            st.write(f"{i+1}. {p_text}")
            
        with st.expander("약속 추가하기 ✍️"):
            new_promise = st.text_input("새로운 약속", key="new_promise_input")
            if st.button("추가") and new_promise:
                st.session_state.promises.append({"text": new_promise, "by": user_name_only})
                save_data()
                st.rerun()
            
        st.divider()
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

    # ==========================================
    # 📌 메인 탭 구성
    # ==========================================
    tabs = st.tabs(["💕 데이트", "💌 쪽지함", "📸 사진첩", "⏳ 타임라인", "😋 오늘 뭐 먹지?", "📍 장소/기록"])

    # --- 탭 1: 데이트 (일정 + 기분/날씨) ---
    with tabs[0]:
        st.subheader("🗓️ 우리의 데이트 일정")
        with st.form("schedule_form", clear_on_submit=True):
            s_date = st.date_input("데이트 날짜")
            s_plan = st.text_input("무엇을 할까요?")
            if st.form_submit_button("일정 추가") and s_plan:
                st.session_state.date_schedules.append({"date": str(s_date), "plan": s_plan, "by": user_name_only})
                st.session_state.date_schedules.sort(key=lambda x: x['date'])
                save_data()
                st.rerun()
                
        # [모바일 최적화] 데이트 일정 목록 (서랍장 UX)
        for i, s in enumerate(st.session_state.date_schedules):
            with st.expander(f"📌 [{s['date']}] {s['plan']}"):
                edit_s = st.text_input("일정 수정", value=s['plan'], key=f"edit_s_{i}")
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("수정 완료", key=f"btn_s_edit_{i}"):
                    st.session_state.date_schedules[i]['plan'] = edit_s
                    save_data()
                    st.rerun()
                if col_s2.button("삭제하기 🗑️", key=f"btn_s_del_{i}"):
                    st.session_state.date_schedules.pop(i)
                    save_data()
                    st.rerun()
                
        st.divider()
        
        # 기분 및 날씨
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
            
            save_data()
            st.toast(f"{user_name_only}님의 기분이 업데이트 되었습니다! 💖")
            st.rerun()

        st.write(f"👦 수기남자친구: {st.session_state.moods['수기남자친구']} ({mood_desc[st.session_state.moods['수기남자친구']]})")
        st.write(f"👧 수기: {st.session_state.moods['수기']} ({mood_desc[st.session_state.moods['수기']]})")
        
        # 기분 그래프
        if st.session_state.mood_history:
            st.write("📈 **최근 기분 변화 그래프**")
            df_mood = pd.DataFrame(st.session_state.mood_history[-7:])
            if not df_mood.empty:
                df_mood.set_index('date', inplace=True)
                st.line_chart(df_mood)

    # --- 탭 2: 쪽지함 ---
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
                        save_data()
                        st.rerun()
            else:
                with st.form("new_memo_form"):
                    content = st.text_area("오늘 하루, 하고 싶은 말은?")
                    if st.form_submit_button("남기기") and content:
                        st.session_state.memo_history.insert(0, {"date": today_str, "time": current_time_str, "user": user_name_only, "content": content, "edited": False})
                        save_data()
                        st.rerun()

        st.divider()
        for m in st.session_state.memo_history:
            is_boy = "수기남자친구" in m['user']
            align_cls = "user-boy" if is_boy else "user-girl"
            st.markdown(f'<div class="card {align_cls}"><small><b>{m["user"]}</b> | {m["date"]}</small><p>{m["content"]}</p><span class="time-text">{m["time"]}</span></div>', unsafe_allow_html=True)

    # --- 탭 3: 사진첩 ---
    with tabs[2]:
        st.subheader("📸 임시 사진첩")
        img_file = st.file_uploader("사진 올리기", type=["jpg", "png"])
        if img_file and st.button("업로드"):
            st.session_state.photos.insert(0, {"img": img_file.getvalue(), "date": today_str, "user": user_name_only})
            st.rerun()
        for p in st.session_state.photos:
            st.image(p['img'], caption=f"{p['date']} by {p['user']}", use_container_width=True)

    # --- 탭 4: 타임라인 ---
    with tabs[3]:
        st.subheader("⏳ 타임라인")
        with st.form("timeline_form", clear_on_submit=True):
            t_date = st.date_input("날짜")
            t_event = st.text_input("기록할 사건")
            if st.form_submit_button("저장") and t_event:
                st.session_state.timeline.append({"date": str(t_date), "event": t_event, "by": user_name_only})
                st.session_state.timeline.sort(key=lambda x: x['date'], reverse=True)
                save_data()
                st.rerun()
        for item in st.session_state.timeline:
            st.markdown(f'<div class="card"><b>{item["date"]}</b> ({item.get("by", "")})<br>{item["event"]}</div>', unsafe_allow_html=True)

    # --- 탭 5: 오늘 뭐 먹지? ---
    with tabs[4]:
        st.subheader("🎰 메뉴 돌림판")
        if st.button("메뉴 랜덤 뽑기! 🎲"):
            st.warning(f"오늘의 추천: **{random.choice(st.session_state.menu_list)}** 😋")
            st.toast("메뉴가 선택되었습니다!", icon="🍽️")
            
        with st.form("menu_form", clear_on_submit=True):
            new_menu = st.text_input("새로운 메뉴 리스트 추가")
            if st.form_submit_button("메뉴 추가") and new_menu:
                st.session_state.menu_list.append(new_menu)
                save_data()
                st.rerun()
                
        st.write("👇 **메뉴를 터치하면 수정/삭제할 수 있어요!**")
        for i, menu in enumerate(st.session_state.menu_list):
            with st.expander(f"🍽️ {menu}"):
                edit_m = st.text_input(f"메뉴 이름 수정", value=menu, key=f"edit_m_{i}")
                col_m1, col_m2 = st.columns(2)
                if col_m1.button("수정 완료", key=f"btn_m_edit_{i}"):
                    st.session_state.menu_list[i] = edit_m
                    save_data()
                    st.rerun()
                if col_m2.button("삭제하기 🗑️", key=f"btn_m_del_{i}"):
                    st.session_state.menu_list.pop(i)
                    save_data()
                    st.rerun()

    # --- 탭 6: 장소/기록 ---
    with tabs[5]:
        st.subheader("📍 우리의 위시리스트")
        with st.form("w_form", clear_on_submit=True):
            w_place = st.text_input("가고 싶은 곳")
            if st.form_submit_button("추가") and w_place:
                st.session_state.wishlist.append({"place": w_place, "visited": False, "by": user_name_only})
                save_data()
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
                    save_data()
                    st.rerun()
                
                if not new_visited:
                    edit_w = st.text_input("장소명 수정", value=w['place'], key=f"edit_w_{i}")
                    col_w1, col_w2 = st.columns(2)
                    if col_w1.button("수정 완료", key=f"btn_w_edit_{i}"):
                        st.session_state.wishlist[i]['place'] = edit_w
                        save_data()
                        st.rerun()
                    if col_w2.button("삭제하기 🗑️", key=f"btn_w_del_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_data()
                        st.rerun()
                else:
                    if st.button("목록에서 완전히 삭제하기 🗑️", key=f"btn_w_del_v_{i}"):
                        st.session_state.wishlist.pop(i)
                        save_data()
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
                save_data()
                st.rerun()
        
        for r in st.session_state.reviews:
            link_html = f"<br><a href='{r.get('link', '#')}' target='_blank'>🔗 지도에서 보기</a>" if r.get('link') else ""
            st.markdown(f"""
                <div class="card">
                    <span style="background-color:#eee; padding:2px 5px; border-radius:5px; font-size:0.8rem; color:#333;">{r['cat']}</span>
                    <b>{r['name']}</b> {r['rating']} ({r['date']})
                    {link_html} <br><br>
                    {r['comment']}
                </div>
                """, unsafe_allow_html=True)
