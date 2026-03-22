import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# ----------------------------------
# INIT
# ----------------------------------
ticker = None

st.set_page_config(page_title="ETF Dip-Terminal v2.1", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.1")

# ----------------------------------
# SIDEBAR
# ----------------------------------
with st.sidebar:
    st.header("Search")

    user_input = st.text_input("Enter Ticker / ISIN", value="VOO").strip()

    if user_input:
        try:
            search = yf.Search(user_input, max_results=50)
            if search.quotes:
                options = {
                    f"{r['symbol']} | {r.get('longname','')}": r['symbol']
                    for r in search.quotes if 'symbol' in r
                }
                selected = st.selectbox("Select Asset", options.keys())
                ticker = options[selected]
            else:
                ticker = user_input.upper()
        except:
            ticker = user_input.upper()

    baseline = st.number_input("Monthly Investment", value=1000)

# ----------------------------------
# SENTIMENT ENGINE (WITH FALLBACK)
# ----------------------------------
def get_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "live"
    except:
        pass

    return None, "failed"

# ----------------------------------
# DATA
# ----------------------------------
def get_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# ----------------------------------
# MAIN
# ----------------------------------
if ticker:

    df = get_data(ticker)
    if df is None:
        st.error("No data found")
        st.stop()

    yt = yf.Ticker(ticker)

    # -----------------------------
    # FEAR & GREED
    # -----------------------------
    fg_val, fg_status = get_fear_greed()

    if fg_status == "failed":
        st.warning("⚠️ Unable to fetch Fear & Greed index")

        st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

        fg_val = st.number_input(
            "Enter Fear & Greed Index (0–100)",
            min_value=0,
            max_value=100,
            value=50
        )

    # -----------------------------
    # PE RATIO
    # -----------------------------
    try:
        pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
    except:
        pe_ratio = None

    if not pe_ratio:
        st.warning("⚠️ P/E not available")

        if len(user_input) == 12:
            st.markdown(f"🔗 https://www.justetf.com/en/etf-profile.html?isin={user_input}")

        pe_ratio = st.number_input(
            "Enter P/E Ratio (optional)",
            min_value=0.0,
            value=0.0
        )

        if pe_ratio == 0:
            pe_ratio = None

    # -----------------------------
    # CALCULATIONS
    # -----------------------------
    close = df["Close"]
    cur_p = float(close.iloc[-1])

    ma200 = close.rolling(200).mean()
    ma50 = close.rolling(50).mean()

    ma200_val = ma200.iloc[-1]
    ma50_val = ma50.iloc[-1]

    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

    # Drawdown
    peak = close.cummax().iloc[-1]
    drawdown = (cur_p / peak - 1) * 100

    # Trend
    if len(ma200.dropna()) > 20:
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100
    else:
        ma_slope = 0

    # ----------------------------------
    # SCORING
    # ----------------------------------
    score = 0
    if fg_val < 35: score += 40
    if rsi_val < 40: score += 30
    if cur_p < ma200_val: score += 30

    final_score = score

    # ----------------------------------
    # DECISION
    # ----------------------------------
    st.subheader("🎯 Decision")

    if final_score >= 70:
        st.success("🔥 AGGRESSIVE BUY")
    elif final_score >= 40:
        st.info("⚖️ STEADY BUY")
    else:
        st.warning("⚠️ CAUTION")

    # ----------------------------------
    # SIGNAL CARDS
    # ----------------------------------
    st.subheader("🧠 Market Signals")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 😨 Sentiment")
        st.write(f"Fear & Greed: {fg_val}")

    with col2:
        st.markdown("### 📉 RSI")
        st.write(f"{rsi_val:.1f}")

    # ----------------------------------
    # CONTEXT
    # ----------------------------------
    st.subheader("📎 Context")

    if pe_ratio:
        st.write(f"P/E: {pe_ratio:.2f}")
    else:
        st.write("P/E not provided")

    st.subheader("📊 Price")
    st.line_chart(close)

else:
    st.info("Enter a ticker to begin")
