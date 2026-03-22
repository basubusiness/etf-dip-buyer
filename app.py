import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - ISIN & SEARCH
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # (3) Search limit 100
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {
                f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] 
                for r in search.quotes
            }
            selected_label = st.selectbox("Select Asset:", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()

# 3. SENTIMENT ENGINE (No Hardcoding)
@st.cache_data(ttl=300)
def get_market_sentiment():
    # Attempt CNN
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    # VIX Fallback (The 35 score is calculated from live VIX price)
    try:
        vix = yf.Ticker("^VIX")
        vix_val = vix.fast_info['last_price']
        # Map VIX to 0-100: VIX 20 -> ~50, VIX 30 -> ~25
        fg_val = max(0, min(100, 100 - (vix_val * 2.5))) 
        return fg_val, f"VIX-Derived Sentiment ({vix_val:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Default)", "https://finance.yahoo.com"

# 4. FIXED DATA ENGINE
@st.cache_data(ttl=600)
def fetch_ticker_data(symbol):
    # Download 1y data
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    
    if df.empty:
        return pd.DataFrame(), "USD", "N/A"

    # CRITICAL: Flatten MultiIndex columns (Fixes the "missing graph" issue)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Get Metadata
    yt = yf.Ticker(symbol)
    try:
        info = yt.fast_info
        currency = info.get('currency', 'USD')
        exchange = info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
        
    return df, currency, exchange

# 5. DASHBOARD
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    df, curr, exch = fetch_ticker_data(ticker)

    if not df.empty and len(df) > 20:
        # DATA PREP
        close_series = df['Close'].copy()
        ma200 = close_series.rolling(window=200).mean()
        cur_p = float(close_series.iloc[-1])
        cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
        
        # RSI (14D)
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        # (4) RSI Tooltip
        rsi_math = "RSI = 100 - [100 / (1 + (Avg Gain / Avg Loss))]"

        # UI LAYOUT
        st.subheader(f"Strategy Terminal: {ticker}")
        st.caption(f"Exchange: {exch} | Currency: {curr} | Data: [Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker})")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Live Price", f"{cur_p:,.2f} {curr}")
            st.markdown(f"🔗 [History ↗](https://finance.yahoo.com/quote/{ticker}/history)")
        with col2:
            st.metric("Market Mood", f"{fg_val:.0f}/100")
            st.markdown(f"🔗 [{fg_label} ↗]({fg_url})")
        with col3:
            st.metric("RSI (14D)", f"{rsi_val:.1f}", help=rsi_math)
            st.markdown("🔗 [RSI Theory ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        # SCORING Logic
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 35: score += 30
        if cur_p < cur_ma: score += 30

        st.divider()
        
        # (2) Recommendations with clear links
        if score >= 70:
            st.success(f"🔥 **ACTION: HEAVY DIP BUY** | Suggested Investment: `{baseline * 2:,.2f} {curr}`")
        elif score >= 35:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Suggested Investment: `{baseline:,.2f} {curr}`")
        else:
            st.warning(f"⚠️ **ACTION: HOLD / CAUTION** | Suggested Investment: `{baseline * 0.5:,.2f} {curr}`")

        # THE GRAPH (Restored)
        chart_data = pd.DataFrame({
            "Price": close_series,
            "200-Day Trend": ma200
        })
        st.line_chart(chart_data)
        
    else:
        st.error(f"Could not load data for {ticker}. Check ticker or ISIN.")
