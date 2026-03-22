import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal v1.0", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal v1.0")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')}": r['symbol'] for r in search.quotes if 'symbol' in r}
            selected_label = st.selectbox("Select Asset:", options.keys())
            ticker = options[selected_label]
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()
    with st.expander("💡 Novice Corner: Value Buying"):
        st.write("Buying a dip is good, but buying a 'Value Dip' is better. This means the price dropped faster than the company's earnings power.")

# 3. SENTIMENT ENGINE (Frozen)
@st.cache_data(ttl=300)
def get_market_sentiment():
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/graphdata", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass
    vix = yf.Ticker("^VIX").fast_info['last_price']
    return max(0, min(100, 100 - (vix * 2.5))), f"VIX-Derived ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"

# 4. NEW: FUNDAMENTAL ENGINE
def get_fundamentals(ticker_obj):
    try:
        info = ticker_obj.info
        pe = info.get('trailingPE') or info.get('forwardPE')
        # Distance from 52-Week High
        hi_52 = info.get('fiftyTwoWeekHigh')
        return pe, hi_52
    except:
        return None, None

# 5. EXECUTION
if ticker:
    yt = yf.Ticker(ticker)
    fg_val, fg_label, fg_url = get_market_sentiment()
    
    # Calculation Data (1Y Daily)
    df_calc = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not df_calc.empty:
        if isinstance(df_calc.columns, pd.MultiIndex): df_calc.columns = df_calc.columns.get_level_values(0)
        
        cur_p = float(df_calc['Close'].iloc[-1])
        ma200 = df_calc['Close'].rolling(window=200).mean().iloc[-1]
        
        # RSI
        delta = df_calc['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)).iloc[-1]))

        # Fundamentals & Valuation
        pe_ratio, high_52 = get_fundamentals(yt)
        drawdown = ((cur_p - high_52) / high_52) * 100 if high_52 else 0

        # TOP METRICS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"{cur_p:,.2f}")
        c2.metric("Market Sentiment", f"{fg_val:.0f}/100")
        c3.metric("RSI (Momentum)", f"{rsi_val:.1f}")
        c4.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")

        # EXPLANATORY UI
        with st.expander("📝 Strategy & Fundamentals Breakdown", expanded=True):
            st.write(f"**1. Valuation (P/E):** The P/E is **{pe_ratio if pe_ratio else 'N/A'}**. A lower P/E during a dip suggests the asset is fundamentally 'on sale' relative to its earnings.")
            st.write(f"**2. Drawdown:** This asset is currently **{drawdown:.1f}%** below its 52-week high. [Check History ↗](https://finance.yahoo.com/quote/{ticker}/history)")
            st.write(f"**3. RSI & Sentiment:** Sentiment ({fg_val:.0f}) and RSI ({rsi_val:.1f}) track short-term panic. Combined with P/E, we define the 'Value-Dip'.")

        # SCORING v1.0 (Added Valuation Weight)
        score = 0
        if fg_val < 35: score += 30
        if rsi_val < 40: score += 20
        if cur_p < ma200: score += 25
        if drawdown < -10: score += 25  # Bonus for significant historical correction

        st.divider()
        currency = yt.fast_info.get('currency', 'USD')
        if score >= 75:
            st.success(f"🔥 **ACTION: VALUE-DIP BUY** | Invest `{baseline * 2:,.2f} {currency}`")
        elif score >= 40:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
        else:
            st.warning(f"⚠️ **ACTION: CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

        # CHARTING
        st.subheader("Price Performance")
        view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
        
        # Download View Data
        mapping = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
        p, i = mapping.get(view)
        df_view = yf.download(ticker, period=p, interval=i, progress=False)
        
        if not df_view.empty:
            if isinstance(df_view.columns, pd.MultiIndex): df_view.columns = df_view.columns.get_level_values(0)
            chart_data = pd.DataFrame({"Price": df_view['Close']})
            if view in ["1Y", "5Y", "MAX"]:
                chart_data["200-Day Trend"] = df_view['Close'].rolling(window=200).mean()
            st.line_chart(chart_data)
