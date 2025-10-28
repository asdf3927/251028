# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import StringIO

st.set_page_config(page_title="OECD 경제 지표 대시보드", page_icon="📊", layout="wide")

# -------------------- 헤더 --------------------
st.title("📊 OECD 경제 지표 대시보드")
st.markdown("""
**OECD 공식 CSV**(stats.oecd.org 또는 data.oecd.org의 Export → CSV) **URL을 붙여넣거나 파일을 업로드**하면  
컬럼 매핑만으로 바로 시각화할 수 있어요. (추가 설치 불필요: streamlit, pandas, numpy, altair)
""")

# -------------------- 사이드바: 데이터 입력 --------------------
with st.sidebar:
    st.header("1) 데이터 불러오기")
    mode = st.radio("가져오기 방식", ["CSV URL 붙여넣기", "CSV 파일 업로드"], horizontal=False)

    df = None
    if mode == "CSV URL 붙여넣기":
        csv_url = st.text_input("OECD CSV 다운로드 URL", placeholder="https://stats.oecd.org/.../export.csv")
        st.caption("※ stats.oecd.org에서 원하는 지표 → 우측 상단 Export → CSV 로 받은 URL을 붙여넣으세요.")
        if st.button("URL 불러오기"):
            try:
                # pandas가 내부적으로 urllib로 직접 읽어옴 (추가 라이브러리 X)
                df = pd.read_csv(csv_url)
                st.success("CSV 로드 완료!")
            except Exception as e:
                st.error(f"CSV 로드 실패: {e}")
    else:
        up = st.file_uploader("CSV 업로드", type=["csv"])
        if up is not None:
            try:
                df = pd.read_csv(up)
                st.success("CSV 로드 완료!")
            except Exception as e:
                st.error(f"CSV 로드 실패: {e}")

# 데이터가 없으면 안내 후 종료
if df is None:
    st.info("좌측에서 **OECD CSV URL**을 붙여넣거나 **CSV 파일**을 업로드해 주세요.")
    st.stop()

# -------------------- 원본 미리보기 --------------------
with st.expander("📄 원본 데이터 미리보기 (상위 20행)"):
    st.dataframe(df.head(20))

st.divider()
st.subheader("2) 컬럼 매핑")

cols = list(df.columns)

# OECD CSV는 포맷이 제각각: LOCATION/TIME/Value or Country/Year/Value 등
# → 사용자에게 어떤 컬럼이 무엇인지 매핑 받기
col_country = st.selectbox("국가 컬럼", options=cols, index=0)
col_time = st.selectbox("연도(또는 시점) 컬럼", options=cols, index=min(1, len(cols)-1))

# 지표(분류) 컬럼은 있을 수도 없음(여러 지표가 한 파일 안에 있을 때 구분자)
has_indicator = st.toggle("지표(분류) 컬럼이 있다", value=True)
col_indicator = None
if has_indicator:
    col_indicator = st.selectbox("지표(분류) 컬럼", options=cols)

# 값(숫자) 컬럼 자동 후보
numeric_candidates = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) or c.lower() in ["value", "values", "obs_value"]]
default_value_col = numeric_candidates[0] if numeric_candidates else cols[-1]
col_value = st.selectbox("값(숫자) 컬럼", options=cols, index=cols.index(default_value_col) if default_value_col in cols else 0)

# -------------------- 전처리 --------------------
work = df.copy()
work[col_country] = work[col_country].astype(str)
# 값 컬럼 숫자화
work[col_value] = pd.to_numeric(work[col_value], errors="coerce")
work = work.dropna(subset=[col_value])

# 시간(연도) 숫자 변환 시도(실패 시 문자열로 유지)
time_numeric = pd.to_numeric(work[col_time], errors="coerce")
has_numeric_year = time_numeric.notna().any()
work["_time_num_"] = time_numeric
work["_time_str_"] = work[col_time].astype(str)

# -------------------- 지표 선택 --------------------
st.divider()
st.subheader("3) 필터 · 지표 선택")

if has_indicator:
    indicators = sorted(work[col_indicator].astype(str).unique())
    selected_indicator = st.selectbox("지표 선택", indicators)
    work = work[work[col_indicator].astype(str) == str(selected_indicator)]
    st.caption(f"선택 지표: **{selected_indicator}**")
else:
    selected_indicator = "(단일 지표 파일)"
    st.caption("지표 컬럼이 없는 단일 지표 파일로 처리합니다.")

# -------------------- 기간 선택 --------------------
col_a, col_b = st.columns([1,1])
with col_a:
    if has_numeric_year:
        min_y = int(work["_time_num_"].min())
        max_y = int(work["_time_num_"].max())
        year_range = st.slider("연도 범위 선택", min_value=min_y, max_value=max_y, value=(max(min_y, max_y-5), max_y))
        work = work[(work["_time_num_"] >= year_range[0]) & (work["_time_num_"] <= year_range[1])]
    else:
        years = sorted(work["_time_str_"].unique())
        chosen = st.multiselect("시점 선택(문자열)", options=years, default=years[-1:] if years else [])
        if chosen:
            work = work[work["_time_str_"].isin(chosen)]

with col_b:
    top_k = st.slider("TOP K (막대차트)", min_value=5, max_value=20, value=10, step=1)
    show_table = st.toggle("표 보기", value=True)

# -------------------- 레이아웃 --------------------
st.divider()
left, right = st.columns([1.2, 1])

# -------------------- 최근 시점 TOP K --------------------
with left:
    st.markdown("### 🏆 최근 시점 기준 TOP K 국가")

    # 최근 시점 추출
    if has_numeric_year and work["_time_num_"].notna().any():
        last_year = int(work["_time_num_"].max())
        recent_df = work[work["_time_num_"] == last_year].copy()
        title_year = str(last_year)
    else:
        last_vals = work["_time_str_"].unique().tolist()
        if last_vals:
            last_vals.sort()
            recent_key = last_vals[-1]
            recent_df = work[work["_time_str_"] == recent_key].copy()
            title_year = str(recent_key)
        else:
            recent_df = pd.DataFrame(columns=[col_country, col_value])
            title_year = "latest"

    if recent_df.empty:
        st.info("선택한 범위 내 최근 시점 데이터가 없습니다. 연도/시점을 다시 선택해 주세요.")
    else:
        # 국가별 평균(중복행 있을 수 있으므로)
        top = (recent_df.groupby(col_country, as_index=False)[col_value].mean()
               .sort_values(col_value, ascending=False).head(top_k))
        top["rank"] = range(1, len(top) + 1)

        bar = (
            alt.Chart(top)
            .mark_bar(cornerRadius=6)
            .encode(
                x=alt.X(f"{col_value}:Q", title="값"),
                y=alt.Y(f"{col_country}:N", sort="-x", title="국가"),
                tooltip=[
                    alt.Tooltip("rank:O", title="순위"),
                    alt.Tooltip(f"{col_country}:N", title="국가"),
                    alt.Tooltip(f"{col_value}:Q", title="값", format=",.2f"),
                ],
                color=alt.Color(f"{col_country}:N", legend=None),
            )
            .properties(
                height=36 * len(top),
                title=f"{selected_indicator} — {title_year} TOP {len(top)}"
            )
        )

        label = (
            alt.Chart(top)
            .mark_text(align="left", dx=6)
            .encode(
                x=f"{col_value}:Q",
                y=alt.Y(f"{col_country}:N", sort="-x"),
                text=alt.Text(f"{col_value}:Q", format=",.2f")
            )
        )

        st.altair_chart(bar + label, use_container_width=True)

        # 다운로드
        csv_bytes = top[["rank", col_country, col_value]].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ TOP K 결과 CSV 저장", data=csv_bytes,
                           file_name="oecd_topk.csv", mime="text/csv")

# -------------------- 시계열 추세 --------------------
with right:
    st.markdown("### ⏱ 시계열 추세 비교")
    countries = sorted(work[col_country].astype(str).unique())
    default_sel = countries[:min(3, len(countries))]
    selected_countries = st.multiselect("국가 선택 (최대 6개 권장)", options=countries, default=default_sel)

    ts = work[work[col_country].astype(str).isin(selected_countries)].copy()
    if ts.empty:
        st.info("선택한 국가의 시계열 데이터가 없습니다.")
    else:
        # Altair 호환성 위해 x축은 문자열로 처리
        x_field = "_time_str_"
        line = (
            alt.Chart(ts)
            .mark_line(point=True, interpolate="monotone")
            .encode(
                x=alt.X(f"{x_field}:O", title="시점"),
                y=alt.Y(f"{col_value}:Q", title="값"),
                color=alt.Color(f"{col_country}:N", title="국가"),
                tooltip=[col_country, x_field, alt.Tooltip(col_value, title="값", format=",.2f")],
            )
            .properties(height=380, title=f"{selected_indicator} — 시계열 추세")
        )
        st.altair_chart(line, use_container_width=True)

# -------------------- 도움말 --------------------
st.divider()
with st.expander("🧭 OECD CSV 빠르게 구하는 법"):
    st.markdown("""
1) **stats.oecd.org** 접속 → 원하는 데이터셋 열기  
2) 우측 상단 **Export → CSV file** 클릭  
3) 이 앱에서 **URL 붙여넣기** 또는 **CSV 업로드**  
4) **국가/연도/값(지표) 컬럼 매핑** 지정  
5) TOP K 및 시계열 그래프로 즉시 분석
""")

st.caption("© 2025 VibeCoding · Streamlit + Altair · OECD CSV 바로 사용")
