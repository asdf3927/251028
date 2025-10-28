# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="대한민국 고용률 · 노동지표 대시보드", page_icon="📈", layout="wide")
st.title("📈 대한민국 고용률 · 노동지표 대시보드")

st.markdown("""
좌측에서 CSV를 업로드하세요.
- **고용률 CSV**: `year, employment_rate_15plus_percent`
- **노동지표 CSV (선택)**: long(`year, indicator, value`) 또는 wide(행=지표, 열=연도)
""")

# -------------------- 사이드바: 업로드 --------------------
with st.sidebar:
    st.header("① 데이터 불러오기")
    up_emp = st.file_uploader("고용률 CSV 업로드", type=["csv"])
    up_labor = st.file_uploader("노동지표 CSV(선택, long 또는 wide)", type=["csv"])

# 기본 샘플(고용률)
def default_emp():
    years = list(range(2015, 2025))
    rates = [60.5, 60.6, 60.8, 60.7, 60.9, 60.1, 60.5, 62.1, 62.6, 62.7]
    return pd.DataFrame({"year": years, "employment_rate_15plus_percent": rates})

# 고용률 로드
if up_emp:
    emp = pd.read_csv(up_emp)
else:
    emp = default_emp()

# 컬럼 확인/정제
req_emp = {"year", "employment_rate_15plus_percent"}
if not req_emp.issubset(emp.columns):
    st.error("고용률 CSV는 `year, employment_rate_15plus_percent` 컬럼이 필요합니다.")
    st.stop()

emp = emp.copy()
emp["year"] = pd.to_numeric(emp["year"], errors="coerce")
emp["employment_rate_15plus_percent"] = pd.to_numeric(emp["employment_rate_15plus_percent"], errors="coerce")
emp = emp.dropna().drop_duplicates(subset=["year"]).sort_values("year")

# 노동지표 로드(선택)
labor_long = None
if up_labor:
    lab = pd.read_csv(up_labor)
    # long or wide 판별
    if {"year", "indicator", "value"}.issubset(lab.columns):
        labor_long = lab.copy()
    elif "지표" in lab.columns:
        # wide → long 변환
        wide = lab.copy()
        value_cols = [c for c in wide.columns if c != "지표"]
        labor_long = wide.melt(id_vars=["지표"], value_vars=value_cols, var_name="year", value_name="value")
        labor_long = labor_long.rename(columns={"지표": "indicator"})
    else:
        st.warning("노동지표 CSV는 long(`year, indicator, value`) 또는 wide(첫 열=지표, 나머지 열=연도) 형태여야 합니다.")
        labor_long = None

    if labor_long is not None:
        labor_long["year"] = pd.to_numeric(labor_long["year"], errors="coerce")
        labor_long["value"] = pd.to_numeric(labor_long["value"], errors="coerce")
        labor_long = labor_long.dropna().sort_values(["indicator", "year"])

# -------------------- 상단 미리보기 --------------------
with st.expander("📄 데이터 미리보기"):
    st.write("고용률(필수):")
    st.dataframe(emp.head(20))
    if labor_long is not None:
        st.write("노동지표(선택, long):")
        st.dataframe(labor_long.head(20))

st.divider()

# -------------------- 설정 --------------------
with st.sidebar:
    st.header("② 전망(예측) 설정")
    model_type = st.selectbox("예측 모델", ["선형(Linear)", "2차 다항식(Quadratic)"])
    horizon = st.slider("예측 연수", 1, 5, 3)
    show_ci = st.toggle("신뢰 대역(±1.96×RMSE)", True)

# -------------------- 고용률: 실제값 --------------------
c1, c2 = st.columns([1.2, 1])
with c1:
    st.subheader("🇰🇷 연간 고용률(15세 이상)")
    bar = (
        alt.Chart(emp)
        .mark_bar()
        .encode(
            x=alt.X("year:O", title="연도"),
            y=alt.Y("employment_rate_15plus_percent:Q", title="고용률(%)"),
            tooltip=[alt.Tooltip("year:O", title="연도"),
                     alt.Tooltip("employment_rate_15plus_percent:Q", title="고용률(%)", format=".2f")]
        )
        .properties(height=340)
    )
    st.altair_chart(bar, use_container_width=True)

with c2:
    st.subheader("요약 지표")
    y_min, y_max = int(emp["year"].min()), int(emp["year"].max())
    last = float(emp.loc[emp["year"] == y_max, "employment_rate_15plus_percent"].iloc[0])
    first = float(emp.loc[emp["year"] == y_min, "employment_rate_15plus_percent"].iloc[0])
    yoy = np.nan
    if (y_max - 1) in emp["year"].values:
        yoy = last - float(emp.loc[emp["year"] == y_max - 1, "employment_rate_15plus_percent"].iloc[0])
    a, b = st.columns(2)
    a.metric("최근 고용률", f"{last:.2f}%", f"{(0 if np.isnan(yoy) else yoy):+,.2f}p YoY")
    b.metric("기간 변화", f"{(last-first):+,.2f}p", f"{y_min}→{y_max}")
    st.markdown("---")
    st.download_button("⬇️ 고용률 CSV 저장", data=emp.to_csv(index=False, encoding="utf-8-sig"),
                       file_name="employment_rate_kor.csv", mime="text/csv")

st.divider()

# -------------------- 고용률: 예측 --------------------
x = emp["year"].values
x0 = x - x.min()
y = emp["employment_rate_15plus_percent"].values

deg = 2 if model_type.startswith("2차") else 1
coef = np.polyfit(x0, y, deg=deg)
poly = np.poly1d(coef)

future_years = np.arange(emp["year"].max() + 1, emp["year"].max() + 1 + horizon)
pred_years = np.concatenate([x, future_years])
pred_x0 = pred_years - x.min()
pred_y = poly(pred_x0)

fit_y = poly(x0)
rmse = float(np.sqrt(np.mean((y - fit_y) ** 2))) if len(y) > deg else 0.0
ci_lo = pred_y - 1.96 * rmse
ci_hi = pred_y + 1.96 * rmse

pred_df = pd.DataFrame({"year": pred_years, "pred": pred_y, "ci_lo": ci_lo, "ci_hi": ci_hi})
obs_df = emp.rename(columns={"employment_rate_15plus_percent": "obs"})

st.subheader("🔮 고용률 전망(예측)")
line_obs = (
    alt.Chart(obs_df)
    .mark_line(point=True)
    .encode(x=alt.X("year:O", title="연도"),
            y=alt.Y("obs:Q", title="고용률(%)"),
            color=alt.value("#4c78a8"),
            tooltip=["year", alt.Tooltip("obs", title="관측(%)", format=".2f")])
)
line_pred = (
    alt.Chart(pred_df[pred_df["year"] > emp["year"].max()])
    .mark_line(point=True, strokeDash=[6,3])
    .encode(x="year:O",
            y=alt.Y("pred:Q", title="고용률(%)"),
            color=alt.value("#f58518"),
            tooltip=["year", alt.Tooltip("pred", title="예측(%)", format=".2f")])
)
layers = line_obs + line_pred
if show_ci and rmse > 0:
    band = (
        alt.Chart(pred_df)
        .mark_area(opacity=0.2)
        .encode(x="year:O", y="ci_lo:Q", y2="ci_hi:Q")
    )
    layers = band + layers

st.altair_chart(layers.properties(height=420), use_container_width=True)

# -------------------- 추가: 노동지표 탭 --------------------
if labor_long is not None:
    st.divider()
    st.subheader("📊 기타 노동지표(실업, 청년실업, 취업자 증감 등)")
    with st.sidebar:
        st.header("③ 노동지표 보기")
        inds = sorted(labor_long["indicator"].astype(str).unique())
        pick = st.multiselect("표시할 지표 선택", options=inds, default=inds[:3])
    if pick:
        sub = labor_long[labor_long["indicator"].isin(pick)].copy()
        # 퍼센트/수치 축 자동 라벨
        is_pct = any("%" in s for s in pick)
        y_title = "값(%)" if is_pct else "값(만명)"
        line = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title="연도"),
                y=alt.Y("value:Q", title=y_title),
                color=alt.Color("indicator:N", title="지표"),
                tooltip=["indicator", "year", alt.Tooltip("value:Q", title="값", format=",.2f")]
            )
            .properties(height=380)
        )
        st.altair_chart(line, use_container_width=True)

# -------------------- 도움말 --------------------
with st.expander("해석 가이드"):
    st.markdown("""
- **예측**은 단순 회귀(선형/2차) 기반으로, 정책·경기·인구 등 구조 요인을 반영하지 않으므로 **참고용**입니다.
- 신뢰대역은 과거 잔차의 표준편차로 만든 ±1.96×RMSE 범위로, 통계적 예측구간의 엄밀한 의미와는 다를 수 있습니다.
- 노동지표 CSV는 wide도 올릴 수 있으며, 앱에서 자동으로 long 형태로 변환하여 시계열을 그립니다.
""")

st.caption("© 2025 VibeCoding · Streamlit + Altair")

