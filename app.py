import streamlit as st
import yfinance as yf
import pandas as pd
import requests

ticker = None

st.set_page_config(page_title="ETF Dip-Terminal v2.4", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.4")

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

    # Moving Averages (MA)
    ma200 = close.rolling(200).mean()
    ma50 = close.rolling(50).mean()

    ma200_val = ma200.iloc[-1]
    ma50_val = ma50.iloc[-1]

    # RSI (Relative Strength Index)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

    # Drawdown
    peak = close.cummax().iloc[-1]
    drawdown = (cur_p / peak - 1) * 100

    # Trend using MA
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

    fg_source = "Live" if fg_live else "Default"
    pe_source = "Live"

    # ----------------------------------
    # INPUT PANEL
    # ----------------------------------
    with st.expander("⚙️ Data Inputs (Optional)", expanded=False):

        if not fg_live:
            st.warning("Fear & Greed not available")
            st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

            fg_val = st.number_input("Enter Fear & Greed Index (0–100)", 0, 100, 50)
            fg_source = "Manual"
            st.success("Using manual Fear & Greed input")

        if fg_val is None:
            fg_val = 50
            fg_source = "Default"

        try:
            pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
        except:
            pe_ratio = None
            pe_source = "Unavailable"

        if not pe_ratio:
            st.warning("P/E not available")

            if len(user_input) == 12:
                st.markdown(f"🔗 https://www.justetf.com/en/etf-profile.html?isin={user_input}")

            pe_input = st.number_input("Enter P/E Ratio (optional)", 0.0, value=0.0)

            if pe_input > 0:
                pe_ratio = pe_input
                pe_source = "Manual"
                st.success("Using manual P/E input")
            else:
                pe_source = "Not used"

    # ----------------------------------
    # DATA STATUS (NEW)
    # ----------------------------------
    st.subheader("📊 Data Status")

    st.caption(f"Fear & Greed: {fg_source} ({fg_val:.0f})")
    st.caption(f"Volatility Index (VIX): {'Live' if vix_val else 'Unavailable'} ({vix_val if vix_val else 'N/A'})")
    st.caption(f"P/E Ratio: {pe_source}")

    st.divider()

    # ----------------------------------
    # SCORING
    # ----------------------------------
    score = 0

    if fg_val < 35: score += 40
    if rsi_val < 40: score += 30
    if cur_p < ma200_val: score += 30

    final_score = score

    # ----------------------------------
    # ALIGNMENT
    # ----------------------------------
    positives = 0
    if fg_val < 35: positives += 1
    if rsi_val < 35: positives += 1
    if ma_slope > 0: positives += 1

    if positives == 3:
        alignment_text = "All signals aligned → high conviction"
    elif positives == 2:
        alignment_text = "Mixed signals → moderate conviction"
    else:
        alignment_text = "Weak alignment → low conviction"

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

    st.write(f"Driven by Fear & Greed ({fg_val:.0f}) + RSI ({rsi_val:.1f})")
    st.caption(alignment_text)

    st.divider()

    # ----------------------------------
    # SIGNALS
    # ----------------------------------
    st.subheader("🧠 Market Signals")

    col1, col2 = st.columns(2)

    # Fear & Greed
    with col1:
        st.markdown("### 😨 Fear & Greed Index")
        st.write(f"{fg_val:.0f}")
        st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

        if fg_val < 35:
            st.success("Market fear → better entry zone")

        with st.expander("🔍 Explanation"):
            st.write("Composite sentiment indicator (fear vs greed in market)")

    # VIX
    with col2:
        st.markdown("### 📊 Volatility Index (VIX)")
        if vix_val:
            st.write(f"{vix_val:.1f}")
            st.markdown("🔗 https://finance.yahoo.com/quote/%5EVIX")
            st.write("Measures expected market volatility (fear gauge)")

            if vix_val > 25:
                st.success("Elevated volatility → fear in market")

    col3, col4 = st.columns(2)

    # RSI
    with col3:
        st.markdown("### 📉 Relative Strength Index (RSI)")
        st.write(f"{rsi_val:.1f}")
        st.markdown("🔗 https://www.investopedia.com/terms/r/rsi.asp")

        if rsi_val < 35:
            st.success("Oversold → rebound potential")

        with st.expander("🔍 Math"):
            st.write(f"""
RSI = 100 - (100 / (1 + RS))

RS (Relative Strength) = avg(gains) / avg(losses)

Current RS: {rs.iloc[-1]:.2f}
RSI: {rsi_val:.2f}
""")

    # Trend
    with col4:
        st.markdown("### 📈 Long-term Trend (200-day Moving Average)")
        st.write(f"{ma_slope:.2f}%")

        if ma_slope > 0:
            st.success("Long-term trend rising → dip likely temporary")

        with st.expander("🔍 Math"):
            st.write(f"""
Moving Average (MA) = average price over time

Slope = (MA_today - MA_20d_ago) / MA_20d_ago

MA today: {ma200.iloc[-1]:.2f}
MA 20d ago: {ma200.iloc[-20]:.2f}
Slope: {ma_slope:.2f}%
""")

    # ----------------------------------
    # CONTEXT
    # ----------------------------------
    st.subheader("📎 Context")

    if pe_ratio:
        st.write(f"P/E Ratio: {pe_ratio:.2f}")
    else:
        st.write("P/E not available or not used")

    # ----------------------------------
    # CHART
    # ----------------------------------
    st.subheader("📊 Price")
    st.line_chart(close)

else:
    st.info("Enter a ticker to begin")
