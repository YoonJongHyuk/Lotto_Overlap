# ------------------- 라이브러리 임포트 -------------------
import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import os

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
    url = "https://dhlottery.co.kr/common.do?method=main"
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

    
# ------------------- Streamlit UI 시작 -------------------
LAST_ROUND = get_latest_round_number()

st.set_page_config(page_title="로또 중복수 찾기", layout="wide")

# 세션 초기화
if 'combinations' not in st.session_state:
    st.session_state.combinations = []

st.sidebar.header("현재 최신 회차")
st.sidebar.write(f"{LAST_ROUND}회차")

fixed_numbers = st.sidebar.multiselect(
    "번호 선택", options=list(range(1, 46)), default=[]
)

if st.sidebar.button("로또 중복수 체크"):
    if not fixed_numbers:
        st.error("번호를 선택해주세요.")
    else:
        df = load_lotto_data()
        df = update_latest_lotto_data(df)

        st.session_state.combinations = df[[f"번호{i}" for i in range(1, 7)]].values.tolist()

        # ✅ 일치 개수별로 결과 분류할 딕셔너리 초기화
        match_results = {i: [] for i in range(2, 7)}  # 2~6개 일치만 표시

        # ✅ 조합 비교
        for idx, combo in enumerate(st.session_state.combinations):
            match_count = sum(num in combo for num in fixed_numbers)
            if match_count in match_results:
                round_no = df.iloc[idx]["회차"]
                draw_date = df.iloc[idx]["추첨일"]
                match_results[match_count].append((round_no, draw_date, combo))  # 회차, 날짜, 번호 리스트

        # ✅ 결과 출력
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

                # ✅ fixed_numbers 강조 적용
                styled_df = result_df.style.applymap(highlight_matches, subset=[f"번호 {i+1}" for i in range(6)])

                # ✅ 강조된 표 출력
                st.dataframe(styled_df, use_container_width=True, hide_index=True)


        if not found_any:
            st.warning("2개 이상 일치하는 조합이 없습니다.")





