import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# ----------------------------------
# SAFE INIT
# ----------------------------------
ticker = None

# ----------------------------------
# SETUP
# ----------------------------------
st.set_page_config(page_title="ETF Dip-Terminal v2.0", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.0")

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
# SENTIMENT ENGINE
# ----------------------------------
@st.cache_data(ttl=300)
def get_sentiment():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"])
    except:
        pass

    try:
        vix = yf.Ticker("^VIX").fast_info["last_price"]
        if vix < 13: return 80
        elif vix < 18: return 65
        elif vix < 23: return 50
        elif vix < 30: return 35
        elif vix < 40: return 20
        else: return 10
    except:
        return 50

# ----------------------------------
# DATA FETCH
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

    try:
        currency = yt.fast_info.get("currency", "USD")
        pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
    except:
        currency = "USD"
        pe_ratio = None

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
    rolling_max = close.cummax()
    peak = rolling_max.iloc[-1]
    drawdown = (cur_p / peak - 1) * 100

    # Trend slope
    if len(ma200.dropna()) > 20:
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100
    else:
        ma_slope = 0

    # Sentiment
    fg_val = get_sentiment()

    # 1Y return
    one_year_return = (cur_p / close.iloc[0] - 1) * 100

    # ----------------------------------
    # SCORING
    # ----------------------------------
    score = 0
    if fg_val < 35: score += 40
    if rsi_val < 40: score += 30
    if cur_p < ma200_val: score += 30

    dip_score = 0
    if drawdown < -10: dip_score += 20
    if ma_slope > 0: dip_score += 40
    if cur_p > ma50_val: dip_score += 30

    final_score = 0.65 * score + 0.35 * dip_score

    # ----------------------------------
    # DECISION
    # ----------------------------------
    st.subheader("🎯 Decision")

    if final_score >= 70:
        st.success(f"🔥 AGGRESSIVE BUY → {baseline*2:,.0f} {currency}")
    elif final_score >= 40:
        st.info(f"⚖️ STEADY BUY → {baseline:,.0f} {currency}")
    else:
        st.warning(f"⚠️ CAUTION → {baseline*0.5:,.0f} {currency}")

    st.divider()

    # ----------------------------------
    # SIGNAL CARDS
    # ----------------------------------
    st.subheader("🧠 Market Signals")

    col1, col2 = st.columns(2)

    # SENTIMENT
    with col1:
        st.markdown("### 😨 Sentiment")

        if fg_val < 35:
            st.error(f"Market is fearful ({fg_val:.0f})")
        else:
            st.info(f"Market neutral/greedy ({fg_val:.0f})")

        st.write("Low sentiment = better buying opportunities")

        with st.expander("Math & Source"):
            st.write("""
Source:
- CNN Fear & Greed OR VIX fallback

Mapping (VIX → sentiment):
<13 → 80  
18 → 65  
30 → 35  
40+ → 10
""")

    # RSI
    with col2:
        st.markdown("### 📉 Momentum")

        if rsi_val < 35:
            st.success(f"Oversold (RSI {rsi_val:.1f})")
        else:
            st.info(f"Neutral RSI ({rsi_val:.1f})")

        st.write("Low RSI = recent drop → possible rebound")

        with st.expander("Math"):
            st.write(f"""
RSI = 100 - (100 / (1 + RS))

RS = avg(gains) / avg(losses)
Window = 14 days

Current RSI: {rsi_val:.2f}
""")

    col3, col4 = st.columns(2)

    # TREND
    with col3:
        st.markdown("### 📈 Trend")

        if ma_slope > 0:
            st.success(f"Uptrend (+{ma_slope:.2f}%)")
        else:
            st.warning(f"Weak trend ({ma_slope:.2f}%)")

        st.write("Positive trend = safer dips")

        with st.expander("Math"):
            st.write(f"""
Slope = (MA_today - MA_20d_ago) / MA_20d_ago

Current slope: {ma_slope:.2f}%
""")

    # DRAWDOWN
    with col4:
        st.markdown("### 📉 Drawdown")

        st.info(f"{drawdown:.1f}% from peak")

        st.write("Bigger drop = better opportunity (with risk)")

        with st.expander("Math"):
            st.write(f"""
Drawdown = (Current / Peak) - 1

Current: {cur_p:.2f}
Peak: {peak:.2f}
""")

    # ----------------------------------
    # CONTEXT
    # ----------------------------------
    st.subheader("📎 Context")

    st.write(f"📅 1Y Return: {one_year_return:.1f}%")

    if pe_ratio:
        st.write(f"💰 P/E Ratio: {pe_ratio:.2f}")
    else:
        st.write("💰 P/E: Not available")

    # ----------------------------------
    # CHART
    # ----------------------------------
    st.subheader("📊 Price")
    st.line_chart(close)

else:
    st.info("Enter a ticker to begin")
