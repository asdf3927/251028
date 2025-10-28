import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ------------------------ 기본 설정 ------------------------
st.set_page_config(page_title="👻 바이브코딩 웹사이트 제작 😈", page_icon="🎃", layout="wide")

# 약간의 스타일 (Streamlit 기본 테마 안에서만 커스터마이징)
st.markdown("""
<style>
/* 제목 폰트 크기와 간격 조정 */
h1 { margin-bottom: 0.3rem !important; }
.section-title { font-size: 1.2rem; font-weight: 700; margin-top: 0.6rem; }
.small-muted { color: #6b7280; font-size: 0.9rem; }
.card {
  padding: 1rem 1.2rem; border-radius: 16px; border: 1px solid rgba(0,0,0,.08);
  background: linear-gradient(180deg, rgba(255,255,255,.7), rgba(255,255,255,.5));
}
.badge { font-size: .8rem; padding: .2rem .5rem; border-radius: 999px; background: #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# ------------------------ 상단 인사 영역 ------------------------
st.title('👻 바이브코딩 웹사이트 제작 😈')

colA, colB, colC = st.columns([1,1,1])
with colA:
    name = st.text_input('이름을 입력해주세요 : ')
with colB:
    menu = st.selectbox('좋아하는 음식을 선택해주세요:', ['한식🍚','양식🍕','일식🍣','중식🥮','분식🍥'])
with colC:
    if st.button('인사말'):
        if name:
            st.success(f"{name}! 너는 {menu}을 제일 좋아하는구나? 나두 ~ ~ ")
        else:
            st.info("이름을 먼저 입력해줘!")

st.divider()

# ------------------------ 데이터 소스 선택 ------------------------
st.markdown("### 🍽 특정 국가/유형 분석 · **특정 유형이 높은 국가 TOP 10**")
st.markdown('<p class="small-muted">데이터를 업로드하거나, 샘플 데이터를 사용해 시각화할 수 있어요.</p>', unsafe_allow_html=True)

src_col1, src_col2 = st.columns([1,2])
with src_col1:
    src_mode = st.radio("데이터 소스", ["샘플 데이터 사용", "CSV 업로드"], horizontal=True)

def build_sample_data(seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    # 예시 국가 & 유형
    countries = [
        "Korea, Rep.", "Japan", "United States", "Canada", "Germany", "France", "United Kingdom",
        "Italy", "Spain", "Australia", "Netherlands", "Sweden", "Norway", "Finland", "Denmark",
        "China", "India", "Brazil", "Mexico", "South Africa"
    ]
    types = ["만족도", "참여율", "보급률", "성장률", "지표X"]
    rows = []
    for t in types:
        # 국가별로 0~100 사이 난수 + 약간의 편향으로 '유형이 높은 국가'가 생기도록
        base = np.random.uniform(40, 70, size=len(countries))
        bias_idx = np.random.choice(len(countries), size=5, replace=False)
        base[bias_idx] += np.random.uniform(10, 25, size=5)
        for c, v in zip(countries, base + np.random.normal(0, 5, size=len(countries))):
            rows.append({"country": c, "type": t, "value": max(0, min(100, round(float(v), 2)))})
    return pd.DataFrame(rows)

if src_mode == "CSV 업로드":
    with src_col2:
        up = st.file_uploader("CSV 파일을 올려주세요 (필수 컬럼: country, type, value)", type=["csv"])
    if up is not None:
        try:
            df = pd.read_csv(up)
        except Exception as e:
            st.error(f"CSV를 읽는 중 오류가 발생했습니다: {e}")
            st.stop()
    else:
        st.warning("CSV를 업로드하면 분석을 시작할 수 있어요.")
        df = build_sample_data()
else:
    df = build_sample_data()

# ------------------------ 데이터 유효성 검사 ------------------------
required_cols = {"country", "type", "value"}
if not required_cols.issubset(set(df.columns)):
    st.error(f"데이터에 필수 컬럼이 없습니다. 필요한 컬럼: {required_cols}")
    st.stop()

# 타입/범위 정리
df = df.copy()
df["type"] = df["type"].astype(str)
df["country"] = df["country"].astype(str)
# value를 수치로 강제 변환
df["value"] = pd.to_numeric(df["value"], errors="coerce")
df = df.dropna(subset=["value"])

# ------------------------ 사이드바: 컨트롤 ------------------------
with st.sidebar:
    st.markdown("### ⚙️ 분석 옵션")
    selected_type = st.selectbox("분석할 유형(type)을 선택하세요", sorted(df["type"].unique()))
    top_k = st.slider("TOP K", min_value=5, max_value=20, value=10, step=1)
    show_table = st.toggle("표 보기", value=True)
    show_labels = st.toggle("막대에 값 라벨 표시", value=True)
    st.markdown("---")
    st.markdown("**CSV 가이드**")
    st.caption("필수 컬럼: `country`(국가명), `type`(유형명), `value`(값)")

# ------------------------ 데이터 필터링 & 집계 ------------------------
filtered = df[df["type"] == selected_type].copy()

# 만약 동일 국가 중복 로우가 있으면 평균 집계
agg = (filtered
       .groupby("country", as_index=False)["value"]
       .mean())

top = agg.sort_values("value", ascending=False).head(top_k)
top["rank"] = range(1, len(top) + 1)

# ------------------------ 레이아웃 ------------------------
left, right = st.columns([1.1, 1])

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="badge">선택한 유형</div> <div class="section-title">🔎 {selected_type} — 국가별 TOP {len(top)}</div>', unsafe_allow_html=True)

    # Altair 차트 (수평 막대)
    chart = (
        alt.Chart(top)
        .mark_bar(cornerRadius=6)
        .encode(
            x=alt.X("value:Q", title="값 (value)", scale=alt.Scale(zero=True)),
            y=alt.Y("country:N", sort="-x", title="국가"),
            tooltip=[
                alt.Tooltip("rank:O", title="순위"),
                alt.Tooltip("country:N", title="국가"),
                alt.Tooltip("value:Q", title="값", format=".2f")
            ],
            color=alt.Color("country:N", legend=None)
        )
        .properties(height=34 * len(top), width="container")
    )

    if show_labels:
        text = (
            alt.Chart(top)
            .mark_text(align="left", dx=6)
            .encode(
                x="value:Q",
                y=alt.Y("country:N", sort="-x"),
                text=alt.Text("value:Q", format=".2f")
            )
        )
        chart = chart + text

    st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📊 요약</div>', unsafe_allow_html=True)

    if len(top) > 0:
        best_row = top.iloc[0]
        worst_row = top.iloc[-1]
        kpi1, kpi2 = st.columns(2)
        with kpi1:
            st.metric(label="1위 국가", value=f"{best_row['country']}", delta=f"{best_row['value']:.2f}")
        with kpi2:
            st.metric(label=f"Top {len(top)} 평균", value=f"{top['value'].mean():.2f}")

        st.markdown("#### 다운로드")
        csv_bytes = top[["rank", "country", "value"]].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ 현재 결과 CSV 저장",
            data=csv_bytes,
            file_name=f"top_{len(top)}_{selected_type}.csv",
            mime="text/csv"
        )
    else:
        st.info("선택한 유형에 대한 데이터가 없습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ------------------------ 원본/가이드 ------------------------
with st.expander("📁 데이터 형식 가이드 & 원본 미리보기"):
    st.write("데이터 예시 (상위 10행):")
    st.dataframe(df.head(10))
    st.caption("• `country`: 문자열(국가명)  • `type`: 문자열(유형)  • `value`: 숫자형 값")

# 푸터
st.markdown(
    '<p class="small-muted">© 2025 VibeCoding · Streamlit Cloud Ready · Altair Charts</p>',
    unsafe_allow_html=True
)
