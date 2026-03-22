import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - SMART SEARCH
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Name, Ticker, or ISIN", value="VOO").strip()
    
    ticker = None
    
    if user_input:
        # SEARCH DEPTH: Set to 20 per your request
        search = yf.Search(user_input, max_results=20)
        search_results = search.quotes
        
        if search_results:
            # Dropdown with Ticker, Name, and Exchange
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search_results}
            selected_label = st.selectbox("Select the exact asset:", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()

# 3. DATA ENGINE
@st.cache_data(ttl=300) # Faster refresh (5 mins) to keep Fear & Greed in sync
def fetch_market_data(symbol):
    if not symbol: return pd.DataFrame(), 50.0, "N/A", "USD", "N/A", "N/A"
    
    # Get Ticker Metadata
    yt = yf.Ticker(symbol)
    info = yt.info
    currency = info.get('currency', 'USD')
    isin = info.get('isin', 'N/A')
    exchange = info.get('exchange', 'N/A')
    
    # Price Data
    df = yf.download(symbol, period="1y", progress=False)
    
    # FEAR & GREED SCRAPER (Production Endpoint)
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5).json()
        fg_val = float(response['now']['value'])
        fg_text = response['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Sync Issue"
    
    return df, fg_val, fg_text, currency, isin, exchange

# 4. EXECUTION & ANALYSIS
if ticker:
    df, fg_val, fg_text, currency, isin, exchange = fetch_market_data(ticker)

    if not df.empty and len(df) > 20:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close']
        ma200 = close.rolling(window=200).mean()
        
        # RSI calculation
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        cur_p = float(close.iloc[-1])
        cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
        
        # SCORE LOGIC
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 35: score += 30
        if cur_p < cur_ma: score += 30

        # 5. DASHBOARD UI
        st.subheader(f"Asset: {ticker} | Exchange: {exchange}")
        st.caption(f"ISIN: {isin} • Data Currency: {currency}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Live Price", f"{cur_p:,.2f} {currency}")
        
        # Reference Links with Target Blank (Markdown default in Streamlit)
        c2.metric("Fear & Greed", f"{fg_val:.0f}", help=fg_text)
        c2.markdown("[Live CNN Index ↗](https://edition.cnn.com/markets/fear-and-greed)")
        
        c3.metric("RSI Score", f"{rsi_val:.1f}")
        c3.markdown("[RSI Explained ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        st.divider()

        # RECOMMENDATION
        if score > 70:
            st.success(f"🔥 **AGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
        elif score > 35:
            st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
        else:
            st.warning(f"⚠️ **CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

        st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
    else:
        st.error(f"Historical data for {ticker} is currently unavailable.")
else:
    st.info("### Please search for an asset in the sidebar.")
