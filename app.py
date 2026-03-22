import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# ----------------------------------
# 0. SAFE INIT (prevents NameError)
# ----------------------------------
ticker = None

# ----------------------------------
# 1. SETUP
# ----------------------------------
st.set_page_config(page_title="ETF Dip-Terminal v1.4", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal v1.4")

# ----------------------------------
# 2. SIDEBAR (ALWAYS FIRST)
# ----------------------------------
with st.sidebar:
    st.header("Search & Settings")

    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()

    if user_input:
        try:
            search = yf.Search(user_input, max_results=100)
            if search.quotes:
                options = {
                    f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol']
                    for r in search.quotes if 'symbol' in r
                }
                selected_label = st.selectbox("Select Asset", options.keys())
                ticker = options[selected_label]
            else:
                ticker = user_input.upper()
        except:
            ticker = user_input.upper()
    else:
        st.info("👋 Enter a ticker to begin.")

    baseline = st.number_input("Monthly Base Investment", value=1000)

# ----------------------------------
# 3. SENTIMENT ENGINE
# ----------------------------------
@st.cache_data(ttl=300)
def get_market_sentiment():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    try:
        vix = yf.Ticker("^VIX").fast_info['last_price']

        if vix < 13: fg_val = 80
        elif vix < 18: fg_val = 65
        elif vix < 23: fg_val = 50
        elif vix < 30: fg_val = 35
        elif vix < 40: fg_val = 20
        else: fg_val = 10

        return fg_val, f"VIX Sentiment ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral", "https://finance.yahoo.com"

# ----------------------------------
# 4. DATA ENGINE
# ----------------------------------
def get_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df

# ----------------------------------
# 5. MAIN APP
# ----------------------------------
if ticker:

    df = get_data(ticker)

    if df is None:
        st.error("No data found. Try another ticker.")
        st.stop()

    # --- Basic info
    yt = yf.Ticker(ticker)
    try:
        currency = yt.fast_info.get("currency", "USD")
        pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
    except:
        currency = "USD"
        pe_ratio = None

    # --- Price data
    close = df["Close"]
    cur_p = float(close.iloc[-1])

    ma200 = close.rolling(200).mean()
    ma50 = close.rolling(50).mean()

    ma200_val = ma200.iloc[-1]
    ma50_val = ma50.iloc[-1]

    # --- RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

    # --- Drawdown
    rolling_max = close.cummax()
    drawdown = (cur_p / rolling_max.iloc[-1] - 1) * 100

    # --- Slope (%)
    if len(ma200.dropna()) > 20:
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100
    else:
        ma_slope = 0

    # --- Sentiment
    fg_val, fg_label, fg_url = get_market_sentiment()

    # ----------------------------------
    # SCORING
    # ----------------------------------
    dip_score = 0

    if drawdown < -20: dip_score += 30
    elif drawdown < -10: dip_score += 20
    elif drawdown < -5: dip_score += 10

    if drawdown < -15: dip_score += 10

    if ma_slope > 0: dip_score += 40
    elif ma_slope > -0.5: dip_score += 15

    if cur_p > ma50_val: dip_score += 30
    elif cur_p > ma200_val: dip_score += 15

    score = 0
    if fg_val < 35: score += 40
    if rsi_val < 40: score += 30
    if cur_p < ma200_val: score += 30

    final_score = 0.65 * score + 0.35 * dip_score

    st.divider()

    # =========================================
    # (1) SHOULD YOU BUY
    # =========================================
    st.subheader("🎯 Should You Buy?")

    if final_score >= 70:
        st.success(f"🔥 AGGRESSIVE BUY | Invest `{baseline * 2:,.2f} {currency}`")
    elif final_score >= 40:
        st.info(f"⚖️ STEADY BUY | Invest `{baseline:,.2f} {currency}`")
    else:
        st.warning(f"⚠️ CAUTION | Invest `{baseline * 0.5:,.2f} {currency}`")

    # =========================================
    # (2) WHY (SIMPLE)
    # =========================================
    st.subheader("🧠 Why this recommendation")

    reasons = []

    if fg_val < 35:
        reasons.append("Market is fearful → better buying conditions")
    if rsi_val < 35:
        reasons.append("Price dropped recently → possible rebound")
    if drawdown < -10:
        reasons.append("Significant dip from recent highs")
    if ma_slope > 0:
        reasons.append("Long-term trend is still healthy")
    elif ma_slope < 0:
        reasons.append("Trend is weakening → higher risk")

    if not reasons:
        reasons.append("Market conditions are neutral")

    for r in reasons:
        st.write(f"• {r}")

    # =========================================
    # (3) DETAILS
    # =========================================
    st.subheader("📊 Check Details")

    c1, c2, c3 = st.columns(3)
    c1.metric("Price", f"{cur_p:,.2f} {currency}")
    c2.metric("Sentiment", f"{fg_val:.0f}")
    c3.metric("RSI", f"{rsi_val:.1f}")

    d1, d2, d3 = st.columns(3)
    d1.metric("Drawdown", f"{drawdown:.1f}%")
    d2.metric("Trend", f"{ma_slope:.2f}%")
    d3.metric("Dip Score", f"{dip_score}/100")

    # =========================================
    # (4) OTHER CONSIDERATIONS
    # =========================================
    st.subheader("📎 Other Considerations")

    if pe_ratio:
        st.write(f"**P/E Ratio:** {pe_ratio:.2f}")
    else:
        st.write("**P/E Ratio:** Not available for this ETF")

        if len(user_input) == 12:
            link = f"https://www.justetf.com/en/etf-profile.html?isin={user_input}"
            st.markdown(f"🔗 [View ETF Fundamentals ↗]({link})")

    st.write("""
    • Valuation is long-term context  
    • Not useful for short-term dip timing  
    """)

    # ----------------------------------
    # CHART
    # ----------------------------------
    st.subheader("Price Performance")
    st.line_chart(close)

else:
    st.info("Enter a ticker to begin.")
