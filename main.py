# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import StringIO

st.set_page_config(page_title="대한민국 고용률 · 전망 대시보드", page_icon="📈", layout="wide")

# ---------------------- 헤더 ----------------------
st.title("📈 대한민국 고용률 · 전망 대시보드")
st.caption("데이터: 국가데이터처(경제활동인구조사) · 샘플구간 2015–2024")

st.markdown("""
이 앱은 연도별 **대한민국 고용률(15세 이상)**을 보여주고, 간단한 회귀 기반으로 **향후 전망(예측)**을 표시합니다.  
좌측에서 CSV를 업로드하거나 기본 샘플 데이터를 사용할 수 있습니다.
""")

# ---------------------- 사이드바: 데이터 입력 ----------------------
with st.sidebar:
    st.header("① 데이터 불러오기")
    up = st.file_uploader("CSV 업로드 (컬럼: year, employment_rate_15plus_percent)", type=["csv"])

# 기본 샘플(업로드 없을 때 사용)
def load_default():
    years = list(range(2015, 2025))
    rates = [60.5, 60.6, 60.8, 60.7, 60.9, 60.1, 60.5, 62.1, 62.6, 62.7]
    return pd.DataFrame({"year": years, "employment_rate_15plus_percent": rates})

if up is not None:
    try:
        df = pd.read_csv(up)
    except Exception as e:
        st.error(f"CSV 로드 실패: {e}")
        st.stop()
else:
    df = load_default()

# 유효성 검사 & 정제
req_cols = {"year", "employment_rate_15plus_percent"}
if not req_cols.issubset(df.columns):
    st.error("필수 컬럼이 없습니다. 필요한 컬럼: year, employment_rate_15plus_percent")
    st.stop()

df = df.copy()
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df["employment_rate_15plus_percent"] = pd.to_numeric(df["employment_rate_15plus_percent"], errors="coerce")
df = df.dropna().sort_values("year")
df = df.drop_duplicates(subset=["year"])

# ---------------------- 사이드바: 예측 설정 ----------------------
with st.sidebar:
    st.header("② 전망(예측) 설정")
    model_type = st.selectbox("모델 선택", ["선형(Linear)", "2차 다항식(Quadratic)"])
    horizon = st.slider("예측 연수", min_value=1, max_value=5, value=3)
    show_ci = st.toggle("신뢰 대역(±1.96×RMSE) 표시", value=True)
    st.caption("※ 간단한 회귀 기반 예측이며, 실제 통계 예측이 아닌 **참고용**입니다.")

st.divider()

# ---------------------- 본문 레이아웃 ----------------------
left, right = st.columns([1.2, 1])

# ---------------------- 차트: 실제 값 ----------------------
with left:
    st.subheader("🇰🇷 연간 고용률(15세 이상)")
    base_chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("year:O", title="연도"),
            y=alt.Y("employment_rate_15plus_percent:Q", title="고용률(%)"),
            tooltip=[
                alt.Tooltip("year:O", title="연도"),
                alt.Tooltip("employment_rate_15plus_percent:Q", title="고용률(%)", format=".2f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(base_chart, use_container_width=True)

# ---------------------- 간단 KPI ----------------------
with right:
    st.subheader("요약 지표")
    latest_year = int(df["year"].max())
    earliest_year = int(df["year"].min())
    latest_val = float(df.loc[df["year"] == latest_year, "employment_rate_15plus_percent"].iloc[0])
    first_val = float(df.loc[df["year"] == earliest_year, "employment_rate_15plus_percent"].iloc[0])
    growth = latest_val - first_val
    yoy = latest_val - float(df.loc[df["year"] == latest_year - 1, "employment_rate_15plus_percent"].iloc[0]) if (latest_year - 1) in df["year"].values else np.nan

    c1, c2 = st.columns(2)
    c1.metric("최근 연도 고용률", f"{latest_val:.2f}%", f"{(yoy if not np.isnan(yoy) else 0):+.2f}p YoY")
    c2.metric("기간 변화(처음→최근)", f"{growth:+.2f}p", f"{earliest_year}→{latest_year}")

    st.markdown("---")
    st.subheader("CSV 다운로드")
    st.download_button("⬇️ 현재 데이터 저장", data=df.to_csv(index=False, encoding="utf-8-sig"),
                       file_name="korea_employment_rate.csv", mime="text/csv")

st.divider()

# ---------------------- 예측(회귀) ----------------------
# x를 0부터 시작하는 스케일로 변환(수치 안정성)
x = df["year"].values
x0 = x - x.min()
y = df["employment_rate_15plus_percent"].values

# 회귀 적합
if model_type.startswith("2차"):
    deg = 2
else:
    deg = 1

coef = np.polyfit(x0, y, deg=deg)
poly = np.poly1d(coef)

# 예측 구간 생성
future_years = np.arange(df["year"].max() + 1, df["year"].max() + 1 + horizon)
pred_years = np.concatenate([df["year"].values, future_years])
pred_x0 = pred_years - x.min()
pred_y = poly(pred_x0)

# RMSE 기반 간단 신뢰대역(잔차 표준편차)
fit_y = poly(x0)
rmse = np.sqrt(np.mean((y - fit_y) ** 2)) if len(y) > deg else 0.0
ci_hi = pred_y + 1.96 * rmse
ci_lo = pred_y - 1.96 * rmse

pred_df = pd.DataFrame({
    "year": pred_years,
    "pred": pred_y,
    "ci_lo": ci_lo,
    "ci_hi": ci_hi,
    "구분": ["관측"] * len(df) + ["예측"] * len(future_years)
})

st.subheader("🔮 고용률 전망(예측)")

# 관측선 + 예측선 + 신뢰대역
line_obs = (
    alt.Chart(df)
    .mark_line(point=True)
    .encode(
        x=alt.X("year:O", title="연도"),
        y=alt.Y("employment_rate_15plus_percent:Q", title="고용률(%)"),
        color=alt.value("#4c78a8"),
        tooltip=["year", alt.Tooltip("employment_rate_15plus_percent", title="고용률(%)", format=".2f")]
    )
)

line_pred = (
    alt.Chart(pred_df[pred_df["구분"] == "예측"])
    .mark_line(point=True, strokeDash=[6,3])
    .encode(
        x=alt.X("year:O"),
        y=alt.Y("pred:Q", title="고용률(%)"),
        color=alt.value("#f58518"),
        tooltip=["year", alt.Tooltip("pred", title="예측(%)", format=".2f")]
    )
)

layers = line_obs + line_pred

if show_ci and rmse > 0:
    band = (
        alt.Chart(pred_df)
        .mark_area(opacity=0.2)
        .encode(
            x=alt.X("year:O"),
            y=alt.Y("ci_lo:Q"),
            y2="ci_hi:Q",
        )
    )
    layers = band + layers

st.altair_chart(layers.properties(height=420), use_container_width=True)

# ---------------------- 해석 도움말 ----------------------
with st.expander("해석 가이드"):
    st.markdown(f"""
- **모델**: {model_type} 회귀(NumPy polyfit)로 단순 추세선을 학습합니다.
- **신뢰 대역**: 과거 데이터 잔차의 RMSE를 이용해 ±1.96×RMSE를 그립니다.  
  이는 통계적 엄밀한 예측구간이라기보다 **변동성 참고용** 범위입니다.
- **권장**: 정책/경기 요인, 인구구조 변화 등 외생 변수를 포함한 전문 모형(예: 시계열, 구조모형, 서베이)을 사용하면 더 신뢰도 높은 전망을 얻을 수 있습니다.
""")

st.caption("© 2025 VibeCoding · Streamlit + Altair · 참고용 전망")
