import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="ETF Dip-Terminal v2.6", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.6")

ticker = None

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
# FUNCTIONS
# ----------------------------------
def get_data(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1d", progress=False)
    if df.empty:
        return None
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
    # FORCE INPUT IF FAILED
    # ----------------------------------
    if fg_status != "Live":
        st.warning("⚠️ Fear & Greed unavailable — please input manually")
        st.markdown("https://edition.cnn.com/markets/fear-and-greed")

        fg_val = st.number_input("Enter Fear & Greed (0–100)", 0, 100, 50)
        fg_status = "Manual"

    # ----------------------------------
    # CALCULATE BUTTON
    # ----------------------------------
    run = st.button("Run Analysis")

    if run:

        df = get_data(ticker)
        if df is None:
            st.error("No data found")
            st.stop()

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

        # P/E
        try:
            pe_ratio = yt.info.get("trailingPE") or yt.info.get("forwardPE")
            pe_source = "yfinance"
        except:
            pe_ratio = None
            pe_source = "Unavailable"

        # ----------------------------------
        # DATA STATUS
        # ----------------------------------
        st.subheader("📊 Data Status")
        st.caption(f"Fear & Greed: {fg_status} ({fg_val})")
        st.caption(f"VIX: {round(vix_val,1) if vix_val else 'N/A'}")
        st.caption(f"P/E: {pe_source}")

        st.divider()

        # ----------------------------------
        # DECISION
        # ----------------------------------
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200.iloc[-1]: score += 30

        st.subheader("🎯 Decision")

        if score >= 70:
            st.success("🔥 AGGRESSIVE BUY")
        elif score >= 40:
            st.info("⚖️ STEADY BUY")
        else:
            st.warning("⚠️ CAUTION")

        st.write(f"Driven by F&G ({fg_val}) + RSI ({rsi_val:.1f})")

        st.divider()

        # ----------------------------------
        # SIGNALS
        # ----------------------------------
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 😨 Fear & Greed")
            st.write(fg_val)

        with col2:
            st.markdown("### 📊 VIX")
            if vix_val:
                st.write(round(vix_val,1))
                if vix_change > 0:
                    st.warning("Rising fear")
                else:
                    st.success("Cooling")

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("### 📉 RSI")
            st.write(f"{rsi_val:.1f}")

            with st.expander("Math"):
                st.write(f"""
RS = {rs.iloc[-1]:.2f}
RSI = {rsi_val:.2f}
""")

        with col4:
            st.markdown("### 📈 Trend (200-day MA)")
            st.write(f"{ma_slope:.2f}%")

            with st.expander("Math"):
                st.write(f"""
MA today = {ma200.iloc[-1]:.2f}
MA 20d ago = {prev:.2f}
Slope = {ma_slope:.2f}%
""")

        # ----------------------------------
        # CHART
        # ----------------------------------
        st.subheader("📊 Price History")

        chart_data = pd.DataFrame({
            "Price": close,
            "200D MA": ma200
        })

        st.line_chart(chart_data)

else:
    st.info("Enter a ticker to begin")
