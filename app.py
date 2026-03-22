import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - SMART SEARCH
with st.sidebar:
    st.header("Smart Search")
    query = st.text_input("Type Name or Ticker", value="VOO")
    
    # TICKER LOOKUP LOGIC
    search_results = yf.Search(query, max_results=5).quotes
    if search_results:
        options = {f"{r['symbol']} - {r.get('longname', 'Unknown')}": r['symbol'] for r in search_results}
        selected_label = st.selectbox("Select the correct asset:", options.keys())
        ticker = options[selected_label]
    else:
        ticker = query.upper().strip()

    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    # FIXED VERIFICATION LINKS
    st.write("🔍 **Verification Links**")
    st.link_button(f"Morningstar Search: {ticker}", f"https://www.morningstar.com/search?query={ticker}")
    st.link_button(f"Yahoo Finance: {ticker}", f"https://finance.yahoo.com/quote/{ticker}")

# 3. DATA ENGINE
@st.cache_data(ttl=600)
def fetch_market_data(symbol):
    df = yf.download(symbol, period="1y", progress=False)
    
    # Fear & Greed Scraper with fallback
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        data = requests.get(url, headers=headers, timeout=5).json()
        fg_val, fg_text = float(data['now']['value']), data['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Neutral (Sync Unavailable)"
    
    return df, fg_val, fg_text

df, fg_val, fg_text = fetch_market_data(ticker)

# 4. PROCESSING
if not df.empty and len(df) > 20:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    ma200 = close.rolling(window=200).mean()
    
    # RSI Calculation
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_val = float((100 - (100 / (1 + (gain/loss)))).iloc[-1])

    cur_p = float(close.iloc[-1])
    cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
    
    # SCORE LOGIC
    score = 0
    if fg_val < 30: score += 40
    if rsi_val < 35: score += 30
    if cur_p < cur_ma: score += 30

    # 5. UI
    st.subheader(f"Analyzing: {ticker}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Live Price", f"${cur_p:,.2f}")
    c2.metric("Market Sentiment", f"{fg_val:.0f}", help=fg_text)
    c3.metric("RSI (Momentum)", f"{rsi_val:.1f}")

    if score > 70:
        st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Deploy `${baseline * 2:,.2f}`")
    elif score > 35:
        st.info(f"⚖️ **STRATEGY: DCA** | Deploy `${baseline:,.2f}`")
    else:
        st.warning(f"⚠️ **STRATEGY: CAUTION** | Deploy `${baseline * 0.5:,.2f}`")

    st.line_chart(pd.DataFrame({"Price": close, "200MA": ma200}))
else:
    st.error("No data found. Select a valid ticker from the sidebar.")
