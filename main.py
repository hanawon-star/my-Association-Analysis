import re
from collections import Counter
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="급식 연관 규칙 분석", layout="wide")


@st.cache_data
def load_and_process_data():
    url = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"
    df = pd.read_csv(url, encoding="utf-8")

    total_days = len(df)
    baskets = []
    all_items = set()

    for raw_menu in df["메뉴"].dropna():
        # 세로줄(|)로 분리 후 괄호 및 괄호 안 내용 제거, 공백 제거
        items = []
        for item in str(raw_menu).split("|"):
            cleaned = re.sub(r"\(.*?\)", "", item).strip()
            if cleaned:
                items.append(cleaned)

        # 중복 메뉴 제거 후 장바구니에 추가
        unique_items = sorted(list(set(items)))
        if unique_items:
            baskets.append(unique_items)
            all_items.update(unique_items)

    # 지지도/신뢰도 계산을 위한 빈도 집계
    item_counts = Counter()
    pair_counts = Counter()

    for basket in baskets:
        for item in basket:
            item_counts[item] += 1
        for p1, p2 in combinations(basket, 2):
            pair_counts[(p1, p2)] += 1
            pair_counts[(p2, p1)] += 1  # (조건, 결과) 바꾼 방향도 집계

    # 연관 규칙 데이터프레임 생성
    rules_list = []
    for (antecedent, consequent), pair_freq in pair_counts.items():
        support = pair_freq / total_days
        confidence = pair_freq / item_counts[antecedent]
        lift = confidence / (item_counts[consequent] / total_days)

        rules_list.append(
            {
                "조건": antecedent,
                "결과": consequent,
                "동시": pair_freq,
                "지지도": round(support, 4),
                "신뢰도": round(confidence, 4),
                "향상도": round(lift, 4),
            }
        )

    rules_df = pd.DataFrame(rules_list)

    # 무방향 유니크 메뉴 쌍 수 계산
    unique_pairs_count = len(pair_counts) // 2

    return (
        rules_df,
        total_days,
        len(all_items),
        unique_pairs_count,
        sorted(list(all_items)),
        item_counts,
        pair_counts,
    )


# 데이터 로드
(
    rules_df,
    total_days,
    num_items,
    num_pairs,
    item_list,
    item_counts,
    pair_counts,
) = load_and_process_data()

st.title("🍚 송탄고 급식 메뉴 연관 규칙 분석")

# 한 줄 요약 메트릭 표시
st.write(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {num_items}개 | **함께 나온 적이 있는 메뉴 쌍 수:** {num_pairs}개"
)
st.divider()

# 사이드바 컨트롤
st.sidebar.header("조회 및 정렬 설정")

selected_menu = st.sidebar.selectbox(
    "메뉴 선택 (전체 보기: '전체')", options=["전체"] + item_list
)

sort_option = st.sidebar.radio(
    "정렬 기준 선택", options=["향상도 순", "신뢰도 순", "동시 순"]
)

# 최소 동시 일수 슬라이더 추가
min_cooccur = st.sidebar.slider(
    "최소 동시 일수 설정", min_value=1, max_value=10, value=1, step=1
)

sort_column_map = {"향상도 순": "향상도", "신뢰도 순": "신뢰도", "동시 순": "동시"}

# 필터링 적용 (메뉴 선택 및 최소 동시 일수)
filtered_df = rules_df[rules_df["동시"] >= min_cooccur].copy()

if selected_menu != "전체":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ].copy()

# 정렬 적용
sort_col = sort_column_map[sort_option]
filtered_df = filtered_df.sort_values(
    by=[sort_col, "동시"], ascending=[False, False]
).reset_index(drop=True)

# 남은 규칙 수 한 줄 표시
st.write(
    f"🔍 **필터링 후 남은 규칙 수:** `{len(filtered_df)}`개 (최소 동시 일수: {min_cooccur}일 이상)"
)

# Plotly 가로 막대그래프 (향상도 상위 10개)
st.subheader("📊 향상도 상위 10개 규칙")
if not filtered_df.empty:
    top10_lift = filtered_df.sort_values(by="향상도", ascending=False).head(10)
    top10_lift["규칙"] = top10_lift["조건"] + " ➔ " + top10_lift["결과"]

    fig = px.bar(
        top10_lift,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        labels={"규칙": "연관 규칙 (조건 ➔ 결과)", "향상도": "향상도 (Lift)"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("조건에 맞는 규칙이 없습니다.")

# 규칙 표 출력
st.subheader("📋 연관 규칙 목록")
st.dataframe(filtered_df, use_container_width=True)

st.divider()

# 함께 나온 적 없는 짝 화면 영역
st.subheader("🚫 함께 나온 적 없는 짝 검색")

unpaired_target_menu = st.selectbox(
    "함께 나온 적 없는 메뉴를 검색할 대상 메뉴를 선택하세요:",
    options=item_list,
    key="unpaired_menu_select",
)

target_days = item_counts[unpaired_target_menu]
st.write(
    f"📌 **'{unpaired_target_menu}'** 메뉴가 나온 총 일수: **{target_days}일**"
)

# 해당 메뉴와 단 한 번도 함께 나오지 않은 메뉴 탐색 (혼자서는 10일 이상 나온 메뉴 대상)
unpaired_list = []
for other_item in item_list:
    if other_item == unpaired_target_menu:
        continue

    # 같이 나온 횟수 검사
    together_count = pair_counts.get((unpaired_target_menu, other_item), 0)
    other_item_days = item_counts[other_item]

    if together_count == 0 and other_item_days >= 10:
        unpaired_list.append(
            {"메뉴": other_item, "단독 등장 일수": other_item_days}
        )

unpaired_df = pd.DataFrame(unpaired_list)

if not unpaired_df.empty:
    unpaired_df = unpaired_df.sort_values(
        by="단독 등장 일수", ascending=False
    ).reset_index(drop=True)
    st.dataframe(unpaired_df, use_container_width=True)
else:
    st.info(
        f"'{unpaired_target_menu}' 메뉴와 함께 나온 적이 없으면서 단독으로 10일 이상 나온 메뉴가 없습니다."
    )
