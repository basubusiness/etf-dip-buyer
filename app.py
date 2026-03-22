import streamlit as st
import yfinance as yf
import pandas as pd
import requests

ticker = None

st.set_page_config(page_title="ETF Dip-Terminal v2.5", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.5")

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
def get_data(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1d", progress=False)
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
            return float(res.json()["fear_and_greed"]["score"]), "Live"
    except:
        pass
    return None, "Unavailable"

def get_vix_data():
    try:
        vix_df = yf.download("^VIX", period="1mo", interval="1d", progress=False)
        if not vix_df.empty:
            latest = float(vix_df["Close"].iloc[-1])
            prev = float(vix_df["Close"].iloc[-5])
            change = latest - prev
            return latest, change
    except:
        pass
    return None, None

# ----------------------------------
# MAIN
# ----------------------------------
if ticker:

    df = get_data(ticker, "1y")
    if df is None:
        st.error("No data found")
        st.stop()

    yt = yf.Ticker(ticker)

    close = df["Close"]
    cur_p = float(close.iloc[-1])

    # Moving averages
    ma200 = close.rolling(200).mean()
    ma200_val = ma200.iloc[-1]

    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

    # Trend
    if len(ma200.dropna()) > 20:
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100
    else:
        ma_slope = 0

    # ----------------------------------
    # SIGNALS
    # ----------------------------------
    fg_val, fg_source = get_fear_greed()
    vix_val, vix_change = get_vix_data()

    # ----------------------------------
    # INPUT PANEL
    # ----------------------------------
    with st.expander("⚙️ Data Inputs (Optional)"):
        if fg_val is None:
            st.warning("Fear & Greed unavailable")
            st.markdown("https://edition.cnn.com/markets/fear-and-greed")

            fg_val = st.number_input("Enter F&G (0–100)", 0, 100, 50)
            fg_source = "Manual"

        if fg_val is None:
            fg_val = 50
            fg_source = "Default (Assumed Neutral)"

        try:
            pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
            pe_source = "yfinance"
        except:
            pe_ratio = None
            pe_source = "Unavailable"

        if not pe_ratio:
            st.warning("P/E not available")
            pe_input = st.number_input("Enter P/E", 0.0, value=0.0)

            if pe_input > 0:
                pe_ratio = pe_input
                pe_source = "Manual"
            else:
                pe_source = "Not used"

    # ----------------------------------
    # DATA STATUS
    # ----------------------------------
    st.subheader("📊 Data Status")
    st.caption(f"Fear & Greed: {fg_source} ({fg_val:.0f})")
    st.caption(f"VIX: {'Live' if vix_val else 'Unavailable'} ({round(vix_val,1) if vix_val else 'N/A'})")
    st.caption(f"P/E Ratio: {pe_source}")

    st.divider()

    # ----------------------------------
    # DECISION
    # ----------------------------------
    score = 0
    if fg_val < 35: score += 40
    if rsi_val < 40: score += 30
    if cur_p < ma200_val: score += 30

    st.subheader("🎯 Decision")

    if score >= 70:
        st.success("🔥 AGGRESSIVE BUY")
    elif score >= 40:
        st.info("⚖️ STEADY BUY")
    else:
        st.warning("⚠️ CAUTION")

    st.write(f"Driven by Fear & Greed ({fg_val:.0f}) + RSI ({rsi_val:.1f})")

    st.divider()

    # ----------------------------------
    # SIGNALS
    # ----------------------------------
    st.subheader("🧠 Market Signals")

    col1, col2 = st.columns(2)

    # F&G
    with col1:
        st.markdown("### 😨 Fear & Greed Index")
        st.write(f"{fg_val:.0f}")

    # VIX
    with col2:
        st.markdown("### 📊 Volatility Index (VIX)")
        if vix_val:
            st.write(f"{round(vix_val,1)}")

            if vix_change:
                if vix_change > 0:
                    st.warning(f"Rising volatility (+{vix_change:.1f}) → increasing fear")
                else:
                    st.success(f"Falling volatility ({vix_change:.1f}) → calming market")

    col3, col4 = st.columns(2)

    # RSI
    with col3:
        st.markdown("### 📉 Relative Strength Index (RSI)")
        st.write(f"{rsi_val:.1f}")

    # Trend
    with col4:
        st.markdown("### 📈 Long-term Trend (200-day MA)")
        st.write(f"{ma_slope:.2f}%")

    # ----------------------------------
    # CHART
    # ----------------------------------
    st.subheader("📊 Price History")

    period = st.selectbox("Select timeframe", ["1M", "3M", "6M", "1Y", "5Y"], index=3)

    period_map = {
        "1M": "1mo",
        "3M": "3mo",
        "6M": "6mo",
        "1Y": "1y",
        "5Y": "5y"
    }

    chart_df = get_data(ticker, period_map[period])

    if chart_df is not None:
        chart_data = pd.DataFrame({
            "Price": chart_df["Close"],
            "200D MA": chart_df["Close"].rolling(200).mean()
        })
        st.line_chart(chart_data)

else:
    st.info("Enter a ticker to begin")
