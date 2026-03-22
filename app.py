import streamlit as st
import yfinance as yf
import pandas as pd
import requests

ticker = None

st.set_page_config(page_title="ETF Dip-Terminal v2.2", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.2")

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
# SENTIMENT
# ----------------------------------
def get_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), True
    except:
        pass
    return None, False

def get_vix():
    try:
        return yf.Ticker("^VIX").fast_info["last_price"]
    except:
        return None

# ----------------------------------
# MAIN
# ----------------------------------
if ticker:

    df = get_data(ticker)
    if df is None:
        st.error("No data found")
        st.stop()

    yt = yf.Ticker(ticker)

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
    # FETCH SIGNALS
    # ----------------------------------
    fg_val, fg_live = get_fear_greed()
    vix_val = get_vix()

    # ----------------------------------
    # INPUT PANEL (COLLAPSED)
    # ----------------------------------
    with st.expander("⚙️ Data Inputs (Optional)", expanded=False):

        if not fg_live:
            st.warning("F&G not available")
            st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

            fg_val = st.number_input("Enter F&G (0–100)", 0, 100, 50)
            st.success("Using manual F&G input")

        if fg_val is None:
            fg_val = 50  # conservative default

        try:
            pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
        except:
            pe_ratio = None

        if not pe_ratio:
            st.warning("P/E not available")

            if len(user_input) == 12:
                st.markdown(f"https://www.justetf.com/en/etf-profile.html?isin={user_input}")

            pe_input = st.number_input("Enter P/E (optional)", 0.0, value=0.0)

            if pe_input > 0:
                pe_ratio = pe_input
                st.success("Using manual P/E input")

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
        st.write(f"Driven by fear ({fg_val:.0f}) + oversold RSI ({rsi_val:.1f})")
    elif final_score >= 40:
        st.info("⚖️ STEADY BUY")
    else:
        st.warning("⚠️ CAUTION")

    st.divider()

    # ----------------------------------
    # SIGNALS
    # ----------------------------------
    st.subheader("🧠 Market Signals")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 😨 Fear & Greed")
        st.write(f"{fg_val:.0f}")

        if fg_val < 35:
            st.success("Fear → better entry zone")
        elif fg_val > 65:
            st.warning("Greed → expensive market")

    with col2:
        st.markdown("### 📊 VIX")
        if vix_val:
            st.write(f"{vix_val:.1f}")

            if vix_val > 30:
                st.success("High volatility → fear")
            elif vix_val < 15:
                st.warning("Low volatility → complacency")

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("### 📉 RSI")
        st.write(f"{rsi_val:.1f}")

        if rsi_val < 35:
            st.success("Oversold → rebound potential")

    with col4:
        st.markdown("### 📈 Trend")
        st.write(f"{ma_slope:.2f}%")

        if ma_slope > 0:
            st.success("Uptrend intact")
        else:
            st.warning("Weak trend")

    # ----------------------------------
    # CHART
    # ----------------------------------
    st.subheader("📊 Price")
    st.line_chart(close)

else:
    st.info("Enter a ticker to begin")
