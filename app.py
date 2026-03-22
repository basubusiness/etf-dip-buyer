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
    query = st.text_input("Type Name or Ticker (e.g. 'Vanguard S&P' or 'VOO')", value="VOO")
    
    # 3. TICKER LOOKUP LOGIC
    search_results = yf.Search(query, max_results=5).quotes
    if search_results:
        options = {f"{r['symbol']} - {r.get('longname', 'Unknown')}": r['symbol'] for r in search_results}
        selected_label = st.selectbox("Select the correct asset:", options.keys())
        ticker = options[selected_label]
    else:
        st.warning("No matches found. Defaulting to query.")
        ticker = query.upper().strip()

    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    # DYNAMIC LINKS
    st.write("🔍 **Verification Links**")
    st.link_button(f"Morningstar: {ticker}", f"https://www.morningstar.com/search?query={ticker}")
    st.link_button(f"Yahoo Finance: {ticker}", f"https://finance.yahoo.com/quote/{ticker}")

# 4. DATA ENGINE (With Robust Sentiment Scraper)
@st.cache_data(ttl=600)
def fetch_market_data(symbol):
    df = yf.download(symbol, period="1y", progress=False)
    
    # Robust CNN Scraper
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        fg_val = float(data['now']['value'])
        fg_text = data['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Neutral (Sync Issue)"
    
    return df, fg_val, fg_text

df, fg_val, fg_text = fetch_market_data(ticker)

# 5. DATA PROCESSING & LOGIC
if not df.empty and len(df) > 20:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    ma200 = close.rolling(window=200).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_val = float((100 - (100 / (1 + (gain/loss)))).iloc[-1])

    # Analysis
    cur_p = float(close.iloc[-1])
    cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
    
    score = 0
    if fg_val < 30: score += 40
    if rsi_val < 35: score += 30
    if cur_p < cur_ma: score += 30

    # 6. DISPLAY
    st.subheader(f"Analyzing: {ticker}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Price", f"${cur_p:,.2f}")
    c2.metric("Market Sentiment", f"{fg_val:.0f}", help=fg_text)
    c3.metric("RSI", f"{rsi_val:.1f}")

    if score > 70:
        st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Buy `${baseline * 2:,.2f}`")
    elif score > 35:
        st.info(f"⚖️ **STRATEGY: DCA** | Buy `${baseline:,.2f}`")
    else:
        st.warning(f"⚠️ **STRATEGY: MINIMUM** | Buy `${baseline * 0.5:,.2f}`")

    st.line_chart(pd.DataFrame({"Price": close, "200MA": ma200}))
else:
    st.error("Select a valid ticker from the dropdown to start.")
