import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="ETF Dip-Terminal v3.0", layout="wide")
st.title("🏹 ETF Dip-Terminal v3.0")

ticker = None
isin = None

# ----------------------------------
# HELPERS
# ----------------------------------
def is_isin(x):
    return len(x) == 12 and x[:2].isalpha()

# ----------------------------------
# SIDEBAR
# ----------------------------------
with st.sidebar:
    st.header("Search")

    user_input = st.text_input("Enter Ticker / ISIN", value="VOO").strip()

    if user_input:
        try:
            if is_isin(user_input):
                isin = user_input.upper()

            search = yf.Search(user_input, max_results=50)

            if search.quotes:
                options = {
                    f"{r['symbol']} | {r.get('longname','')}": {
                        "symbol": r['symbol'],
                        "isin": r.get('isin')
                    }
                    for r in search.quotes if 'symbol' in r
                }

                selected = st.selectbox("Select Asset", options.keys())
                selected_data = options[selected]

                ticker = selected_data["symbol"]
                isin = isin or selected_data.get("isin")

            else:
                ticker = user_input.upper()

        except:
            ticker = user_input.upper()

    baseline = st.number_input("Monthly Investment (€ / $)", value=1000)

# ----------------------------------
# FUNCTIONS
# ----------------------------------
def get_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def get_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "Live"
    except:
        pass
    return None, "Unavailable"

def get_vix():
    try:
        df = yf.download("^VIX", period="1mo", interval="1d", progress=False)
        latest = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-5])
        return latest, latest - prev
    except:
        return None, None

# ----------------------------------
# MAIN
# ----------------------------------
if ticker:

    fg_val, fg_status = get_fear_greed()

    if fg_status != "Live":
        st.warning("⚠️ Fear & Greed unavailable — please input manually")
        st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

        fg_val = st.number_input("Enter Fear & Greed Index (0–100)", 0, 100, 50)
        fg_status = "Manual"

    run = st.button("Run Analysis")

    if run:

        df = get_data(ticker)
        yt = yf.Ticker(ticker)

        close = df["Close"]
        cur_p = float(close.iloc[-1])

        ma200 = close.rolling(200).mean()

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        # Trend
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100

        # VIX
        vix_val, vix_change = get_vix()

        # ----------------------------------
        # 🔥 TRIGGER SYSTEM (FIXED)
        # ----------------------------------
        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
        rsi_prev = float((100 - (100 / (1 + rs))).iloc[-2])

        rsi_rising = rsi_val > rsi_prev
        trend_weak = ma_slope <= 0

        # Dynamic volatility threshold
        volatility = close.pct_change().rolling(20).std().iloc[-1] * 100
        trigger_threshold = max(1.0, volatility * 1.5)

        # State logic
        if rsi_val < 35 and trend_weak:
            state = "WAIT"
        elif price_change > trigger_threshold and rsi_rising:
            state = "TRIGGER"
        else:
            state = "WATCH"

        # ----------------------------------
        # DECISION
        # ----------------------------------
        st.subheader("🎯 Decision")

        yf_link = f"https://finance.yahoo.com/quote/{ticker}"

        st.caption(f"""
Ticker: {ticker}  
ISIN: {isin if isin else "Not available"}  
🔗 {yf_link}
""")

        if isin:
            st.caption(f"🔗 https://www.justetf.com/en/etf-profile.html?isin={isin}")

        # Score (FIXED LINE)
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200.iloc[-1]: score += 30

        # ----------------------------------
        # ENTRY TIMING
        # ----------------------------------
        st.subheader("⏱ Entry Timing")

        reasons = []

        if price_change < 0:
            reasons.append(f"Price falling ({price_change:.2f}%)")
        else:
            reasons.append(f"Price rising ({price_change:.2f}%)")

        reasons.append("RSI rising" if rsi_rising else "RSI still weak")
        reasons.append("Trend supportive" if not trend_weak else "Trend weak")

        if state == "WAIT":
            st.warning("🟡 WAIT → Market still falling")
        elif state == "WATCH":
            st.info("🔵 WATCH → Stabilizing")
        else:
            st.success("🟢 TRIGGER → Reversal detected")

        for r in reasons:
            st.write(f"- {r}")

        st.markdown("### 🔭 What would trigger a BUY?")
        st.write(f"""
- Price increases by **~{trigger_threshold:.2f}%**
- RSI rising
- Price holds above recent low
""")

        # ----------------------------------
        # MATH
        # ----------------------------------
        with st.expander("🔍 Entry Timing Math"):
            st.write(f"""
Price Change = {price_change:.2f}%  
RSI prev = {rsi_prev:.2f} → now {rsi_val:.2f}  
Trend slope = {ma_slope:.2f}%  
Threshold = {trigger_threshold:.2f}%
""")

        # ----------------------------------
        # FINAL DECISION
        # ----------------------------------
        if score >= 70:
            st.success(f"🔥 AGGRESSIVE BUY → Invest ~ {baseline * 2}")
        elif score >= 40:
            st.info(f"⚖️ STEADY BUY → Invest ~ {baseline}")
        else:
            st.warning(f"⚠️ CAUTION → Invest ~ {baseline * 0.5}")

        st.divider()

        # ----------------------------------
        # SIGNALS
        # ----------------------------------
        st.subheader("🧠 Market Signals")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 😨 Fear & Greed Index")
            st.write(f"**{fg_val}**")

        with col2:
            st.markdown("### 📊 VIX")
            if vix_val:
                st.write(f"**{round(vix_val,1)}**")

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("### 📉 RSI")
            st.write(f"**{rsi_val:.1f}**")

            with st.expander("🔍 Full RSI Math"):
                st.write(f"RS = {rs.iloc[-1]:.4f} → RSI = {rsi_val:.2f}")

        with col4:
            st.markdown("### 📈 Trend")
            st.write(f"**{ma_slope:.2f}%**")

        # ----------------------------------
        # CHART
        # ----------------------------------
        st.subheader("📊 Price History (1Y)")

        chart_data = pd.DataFrame({
            "Price": close,
            "200D MA": ma200
        })

        st.line_chart(chart_data)

else:
    st.info("Enter a ticker to begin")
