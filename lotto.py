# ------------------- 라이브러리 임포트 -------------------
import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from bs4 import BeautifulSoup
import os
import altair as alt

CSV_PATH = "lotto_data.csv"

# ------------------- 회차 번호별 정보 가져오기 -------------------
def getLottoNumber(draw_number):
    DHLOTERY_API_URL = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={draw_number}"  # 로또 회차 번호
    try:
        result = requests.get(DHLOTERY_API_URL)
        result.raise_for_status()
        data = result.json()
        return data
    except:
        print(f"{draw_number}회차 실패")
        return

# ------------------- 최신 회차 번호 가져오기 -------------------
def get_latest_round_number():
    url = "https://dhlottery.co.kr/common.do?method=main&mainMode=default"
    try:
        html = requests.get(url).text
        soup = BeautifulSoup(html, "html.parser")
        max_numb = soup.find(name="strong", attrs={"id": "lottoDrwNo"}).text
        return int(max_numb)
    except Exception as e:
        print("최신 회차 가져오기 실패:", e)

# ------------------- combinations 리스트에서 로또 번호 불러오기 -------------------
def get_combination_by_round(round_number):
    index = round_number - 1
    return st.session_state.combinations[index]


# ------------------- 로또 데이터 CSV 파일 불러오기 -------------------
def load_lotto_data():
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        return df
    else:
        return pd.DataFrame(columns=["회차", "번호1", "번호2", "번호3", "번호4", "번호5", "번호6", "추첨일"])


# ------------------- 최신 로또 데이터 업데이트 -------------------
def update_latest_lotto_data(df):
    last_saved_round = df["회차"].max() if not df.empty else 0
    latest_round = get_latest_round_number()

    if last_saved_round < latest_round:
        new_rows = []
        for i in range(last_saved_round + 1, latest_round + 1):
            data = getLottoNumber(i)
            if data and data.get("returnValue") == "success":
                numbers = [data[f"drwtNo{j}"] for j in range(1, 7)]
                draw_date = data["drwNoDate"]
                new_rows.append([i] + numbers + [draw_date])

        if new_rows:
            new_df = pd.DataFrame(new_rows, columns=df.columns)
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(CSV_PATH, index=False)
            print(f"{len(new_rows)}개 회차가 새로 추가되었습니다.")
    return df


# ------------------- 일치하는 번호 강조 표시 함수 -------------------
def highlight_matches(val):
    if isinstance(val, int) and val in fixed_numbers:
        return "color: red; font-weight: bold;"
    return ""


# ------------------- 최근 N회 출현 빈도표 계산 -------------------
def top_numbers_by_recent(df: pd.DataFrame, recent_n: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["번호", "출현횟수", "등장비율(%)"])
    # 최신 회차부터 recent_n개 추출
    recent_df = df.sort_values("회차", ascending=False).head(recent_n)
    # 번호1~번호6 펼쳐서 빈도 계산
    nums = recent_df[[f"번호{i}" for i in range(1, 7)]].values.ravel()
    s = pd.Series(nums, dtype="int64")
    counts = s.value_counts().sort_index()  # 번호 오름차 정렬 후
    # 출현횟수 기준 내림차 + 번호 오름차 정렬
    out = counts.reset_index()
    out.columns = ["번호", "출현횟수"]
    out["등장비율(%)"] = (out["출현횟수"] / (recent_n * 6) * 100).round(2)
    out = out.sort_values(["출현횟수", "번호"], ascending=[False, True]).reset_index(drop=True)
    return out

# 공용: 최신 데이터 준비(필요 시)
def ensure_latest_df():
    df = load_lotto_data()
    df = update_latest_lotto_data(df)
    return df

# ================== 🔟 끝수 분석 관련 함수들 ==================

# 최근 N회 끝수(0~9) 전체 빈도 (필요하면 그래프용으로 사용)
def last_digit_freq_by_recent(df: pd.DataFrame, recent_n: int) -> pd.DataFrame:
    """
    최근 recent_n 회차(최신 회차부터)에서 추출된 6개 번호들의 끝수(0~9) 빈도를 집계.
    반환: index=끝수(0~9), columns=['count'] DataFrame
    """
    if df.empty or recent_n <= 0:
        return pd.DataFrame({"count": [0]*10}, index=list(range(10)))

    recent_df = df.sort_values("회차", ascending=False).head(recent_n)
    nums = recent_df[[f"번호{i}" for i in range(1, 7)]].values.ravel()

    tail = pd.Series(nums % 10, dtype="int64")
    counts = tail.value_counts().reindex(range(10), fill_value=0).sort_index()
    return counts.to_frame(name="count")


# 최근 N회 회차별 끝수 분포표 + 끝수합
def last_digit_matrix_by_recent(df: pd.DataFrame, recent_n: int) -> pd.DataFrame:
    """
    최근 N회(최신 회차부터) 각 회차별 끝수(0~9) 분포를 표로 반환.
    셀 값: 해당 회차에서 끝수가 몇 번 등장했는지 (0~6)
    '끝수합': 그 회차에서 한 번이라도 나온 끝수들의 합
             예) 0,1,2,4,5,6 이 나오면 0+1+2+4+5+6 = 18
    """
    if df.empty or recent_n <= 0:
        return pd.DataFrame()

    recent_df = df.sort_values("회차", ascending=False).head(recent_n)
    rows = []

    for _, row in recent_df.iterrows():
        nums = [row[f"번호{i}"] for i in range(1, 7)]
        tails = [n % 10 for n in nums]

        # 각 끝수별 등장 횟수
        counts = {t: tails.count(t) for t in range(10)}

        # 끝수합: 한 번이라도 나온 끝수들의 자리값 합
        tail_sum = sum(t for t, cnt in counts.items() if cnt > 0)

        row_data = {"회차": int(row["회차"])}
        row_data.update(counts)      
        row_data["끝수합"] = tail_sum
        rows.append(row_data)

    out = pd.DataFrame(rows)
    out = out.sort_values("회차", ascending=False).reset_index(drop=True)
    return out


def style_tail(df: pd.DataFrame):
    digit_cols = [c for c in df.columns if isinstance(c, int)]

    styler = (
        df.style
        # ✅ 전체 배경 흰색 고정
        .set_properties(
            **{
                "background-color": "white",
                "color": "black",
            }
        )
        # ✅ 끝수 셀만 초록 그라데이션 적용
        .background_gradient(
            axis=None,
            cmap="Greens",
            subset=digit_cols
        )
        # ✅ 숫자 표시 (0은 빈칸)
        .format(
            lambda v: "" if v == 0 else str(v),
            subset=digit_cols
        )
        # ✅ 끝수합은 검정 텍스트 + 연한 회색 배경
        .set_properties(
            subset=["끝수합"],
            **{
                "background-color": "#f2f2f2",
                "color": "black",
                "font-weight": "bold",
            }
        )
        # ✅ 표 스타일 정리
        .set_properties(
            **{
                "text-align": "center",
                "padding": "6px",
                "border": "1px solid #ddd",
            }
        )
    )

    return styler

# ------------------- 로또 공 색상 함수 -------------------
def get_ball_color(num: int) -> str:
    """로또 번호 색상 (국민로또 기준)"""
    if 1 <= num <= 10:
        return "#FBC400"  # 노랑
    elif 11 <= num <= 20:
        return "#69C8F2"  # 파랑
    elif 21 <= num <= 30:
        return "#FF7272"  # 빨강
    elif 31 <= num <= 40:
        return "#AAAAAA"  # 회색
    elif 41 <= num <= 45:
        return "#B0D840"  # 초록
    else:
        return "#FFFFFF"  # 예외

# ------------------- 회차별 로또볼 렌더링 -------------------
def render_round_balls(row):
    main_nums = [int(row[f"번호{i}"]) for i in range(1, 7)]

    def ball_html(n: int) -> str:
        color = get_ball_color(n)
        return f"""
        <div style="
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background-color: {color};
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            color: #ffffff;
        ">{n}</div>
        """

    balls_html = "".join(ball_html(n) for n in main_nums)

    html = f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
    ">
        <div style="width: 60px; font-weight: 600; text-align: right;">
            {int(row['회차'])}회
        </div>
        {balls_html}
    </div>
    """

    components.html(html, height=50)



    
# ------------------- Streamlit UI 시작 -------------------
LAST_ROUND = get_latest_round_number()

st.set_page_config(page_title="로또 중복수 찾기", layout="wide")

# 세션 초기화
if 'combinations' not in st.session_state:
    st.session_state.combinations = []

# ✅ 표시 모드와 회귀 N 기본값
if 'show_mode' not in st.session_state:
    st.session_state.show_mode = None
if 'reg_n' not in st.session_state:
    st.session_state.reg_n = None
# ✅ 끝수 분석용 최근 N 회
if 'tail_n' not in st.session_state:
    st.session_state.tail_n = None

# ✅ 사이드바 내부 탭 UI
with st.sidebar:
    st.header("현재 최신 회차")
    st.write(f"{LAST_ROUND}회차")

    tab_dup, tab_reg, tab_tail = st.tabs(["🔁 중복수", "↩️ 회귀수", "🔟 끝수"])


    with tab_dup:
        fixed_numbers = st.multiselect("번호 선택", options=list(range(1, 46)), default=[])
        dup_button = st.button("로또 중복수 체크", key="btn_dup_check")
        if dup_button:
            # ▶ 중복수만 보이도록 모드 전환
            st.session_state.show_mode = "dup"

    with tab_reg:
        st.subheader("회귀수 분석")
        st.caption("최근 N회(숫자) 기준으로 많이 나온 번호를 내림차순으로 보여줍니다.")

        # ✅ 숫자 입력 (숫자만 받도록 number_input 사용)
        reg_n_input = st.number_input(
            "최근 N회 (양의 정수)", min_value=1, max_value=LAST_ROUND, step=1, key="reg_n_input"
        )
        reg_button = st.button("회귀수 구하기", key="btn_reg_check")

        if reg_button:
            # 입력값 확인
            if reg_n_input is None:
                st.warning("숫자를 입력하세요.")
            else:
                # 최신 데이터 확보 후 실제 보유 회차 수로 2차 검사
                df_check = ensure_latest_df()
                max_available = len(df_check)  # CSV에 저장된(업데이트된) 실제 회차 수

                if reg_n_input > max_available:
                    st.warning(f"최근 N회 값이 너무 큽니다. (현재 보유 데이터: {max_available}회)")
                else:
                    # ✅ 모드 전환 + 값 저장 → 본문에서 렌더링
                    st.session_state.reg_n = int(reg_n_input)
                    st.session_state.show_mode = "reg"

    with tab_tail:
        st.subheader("끝수 분석 (0~9)")
        st.caption("최근 N회(숫자)를 입력하면, 최신 회차부터 N회 내의 끝수(0~9) 빈도를 그래프로 보여줍니다.")

        tail_n_input = st.number_input(
            "최근 N회 (양의 정수)", min_value=1, max_value=LAST_ROUND, step=1, key="tail_n_input"
        )
        tail_button = st.button("끝수 분석 실행", key="btn_tail_check")

        if tail_button:
            if tail_n_input is None:
                st.warning("숫자를 입력하세요.")
            else:
                df_check = ensure_latest_df()
                max_available = len(df_check)  # CSV 내 보유된 실제 회차 수
                if tail_n_input > max_available:
                    st.warning(f"최근 N회 값이 너무 큽니다. (현재 보유 데이터: {max_available}회)")
                else:
                    st.session_state.tail_n = int(tail_n_input)
                    st.session_state.show_mode = "tail"  # ▶ 본문 렌더링 전환





# ✅ 버튼 누르면 본문에 결과 출력
if st.session_state.get("show_mode") == "dup":
    if not fixed_numbers:
        st.error("번호를 선택해주세요.")
    else:
        df = ensure_latest_df()
        st.session_state.combinations = df[[f"번호{i}" for i in range(1, 7)]].values.tolist()

        match_results = {i: [] for i in range(2, 7)}
        for idx, combo in enumerate(st.session_state.combinations):
            match_count = sum(num in combo for num in fixed_numbers)
            if match_count in match_results:
                round_no = df.iloc[idx]["회차"]
                draw_date = df.iloc[idx]["추첨일"]
                match_results[match_count].append((round_no, draw_date, combo))

        found_any = False
        for match_count in sorted(match_results.keys(), reverse=True):
            matches = match_results[match_count]
            if matches:
                found_any = True
                st.subheader(f"🎯 {match_count}개 번호 일치 ({len(matches)}건)")
                result_df = pd.DataFrame(
                    [[round_no, draw_date] + numbers for round_no, draw_date, numbers in matches],
                    columns=["회차", "추첨일"] + [f"번호 {i+1}" for i in range(6)]
                )
                styled_df = result_df.style.applymap(
                    highlight_matches, subset=[f"번호 {i+1}" for i in range(6)]
                )
                st.dataframe(styled_df, use_container_width=True, hide_index=True)

        if not found_any:
            st.warning("2개 이상 일치하는 조합이 없습니다.")


# ───────── 본문: 회귀수 결과 (입력 N회) ─────────
if st.session_state.get("show_mode") == "reg":
    if not st.session_state.get("reg_n"):
        st.warning("회귀수 N을 입력하고 버튼을 눌러주세요.")
    else:
        df = ensure_latest_df()
        n = st.session_state.reg_n
        st.subheader(f"↩️ 회귀수 결과 (최근 {n}회)")

        try:
            dfN = top_numbers_by_recent(df, n)
            st.dataframe(dfN, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"회귀수 계산 중 오류: {e}")

# ================== 🔟 끝수 분석: 본문 출력 ==================

if st.session_state.get("show_mode") == "tail":
    df = ensure_latest_df()
    n = st.session_state.tail_n

    st.subheader(f"🔟 끝수 분포 (최근 {n}회)")

    matrix_df = last_digit_matrix_by_recent(df, n)
    styled = style_tail(matrix_df)

    # ✅ 여기에서 표를 그려주기만 하면 됨
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown(f"### 🎱 최근 {n}회 당첨 번호")

    recent_rows = df.sort_values("회차", ascending=False).head(n)

    for _, r in recent_rows.iterrows():
        render_round_balls(r)   # 함수 내부에서 이미 st.markdown(html, ...) 호출




