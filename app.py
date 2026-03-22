import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="ETF Dip-Terminal v2.8", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.8")

ticker = None
isin = None  # <-- important

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
            # detect ISIN early
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

                # preserve best ISIN source
                isin = isin or selected_data.get("isin")

            else:
                ticker = user_input.upper()

        except:
            ticker = user_input.upper()

    baseline = st.number_input("Monthly Investment", value=1000)

# ----------------------------------
# FUNCTIONS
# ----------------------------------
def get_data(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1d", progress=False)
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

    # ----------------------------------
    # FORCE INPUT IF API FAILS
    # ----------------------------------
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
        # DECISION
        # ----------------------------------
        st.subheader("🎯 Decision")

        yf_link = f"https://finance.yahoo.com/quote/{ticker}"

        st.caption(f"""
Ticker: {ticker}  
ISIN: {isin if isin else "Not available"}  
🔗 Yahoo Finance: {yf_link}
""")

        # add justETF if ISIN exists
        if isin:
            st.caption(f"🔗 https://www.justetf.com/en/etf-profile.html?isin={isin}")

        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200.iloc[-1]: score += 30

        if score >= 70:
            st.success("🔥 AGGRESSIVE BUY")
        elif score >= 40:
            st.info("⚖️ STEADY BUY")
        else:
            st.warning("⚠️ CAUTION")

        st.caption(f"Driven by Fear & Greed ({fg_val}) + RSI ({rsi_val:.1f})")

        st.divider()

        # ----------------------------------
        # SIGNALS
        # ----------------------------------
        st.subheader("🧠 Market Signals")

        col1, col2 = st.columns(2)

        # F&G
        with col1:
            st.markdown("### 😨 Fear & Greed Index")
            st.write(f"**{fg_val}**")
            st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

        # VIX
        with col2:
            st.markdown("### 📊 Volatility Index (VIX)")
            if vix_val:
                st.write(f"**{round(vix_val,1)}**")
                st.markdown("🔗 https://finance.yahoo.com/quote/%5EVIX")

                if vix_change > 0:
                    st.warning(f"Rising volatility (+{vix_change:.1f}) → increasing fear")
                else:
                    st.success(f"Falling volatility ({vix_change:.1f}) → calming market")

        col3, col4 = st.columns(2)

        # RSI
        with col3:
            st.markdown("### 📉 Relative Strength Index (RSI)")
            st.write(f"**{rsi_val:.1f}**")

        # Trend
        with col4:
            st.markdown("### 📈 Long-term Trend (200-day Moving Average)")
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
