import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - SMART SEARCH (Name, Ticker, or ISIN)
with st.sidebar:
    st.header("Smart Search")
    user_input = st.text_input("Enter Name, Ticker, or ISIN", value="VOO").strip()
    
    # ISIN Detection (12-character alphanumeric starting with 2 letters)
    is_isin = bool(re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$/i", user_input))
    
    # SEARCH ENGINE
    # We use yf.Search to find the best-matched Ticker for the input
    search = yf.Search(user_input, max_results=5)
    search_results = search.quotes
    
    if search_results:
        # Create a dropdown to handle multiple matches (Common with Morningstar/Yahoo mismatches)
        options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search_results}
        selected_label = st.selectbox("Select the exact asset:", options.keys())
        ticker = options[selected_label]
    else:
        st.warning("No direct match. Using raw input as Ticker.")
        ticker = user_input.upper()

    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    # 3. VERIFICATION LINKS
    st.write("🔍 **Verification Links**")
    # Morningstar: If we have a ticker, search by that ticker on their site
    st.link_button(f"Morningstar: {ticker}", f"https://www.morningstar.com/search?query={ticker}")
    st.link_button(f"Yahoo Finance: {ticker}", f"https://finance.yahoo.com/quote/{ticker}")

# 4. DATA ENGINE
@st.cache_data(ttl=600)
def fetch_market_data(symbol):
    df = yf.download(symbol, period="1y", progress=False)
    
    # Fear & Greed Scraper
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=5).json()
        fg_val, fg_text = float(data['now']['value']), data['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Neutral (Sync Unavailable)"
    
    return df, fg_val, fg_text

df, fg_val, fg_text = fetch_market_data(ticker)

# 5. DATA PROCESSING & ANALYSIS
if not df.empty and len(df) > 20:
    # Flattening headers for 2026 format
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    ma200 = close.rolling(window=200).mean()
    
    # RSI Logic
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_val = float((100 - (100 / (1 + (gain/loss)))).iloc[-1])

    cur_p = float(close.iloc[-1])
    cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
    
    # SCORING (Fear & Greed + RSI + Trend)
    score = 0
    if fg_val < 35: score += 40
    if rsi_val < 35: score += 30
    if cur_p < cur_ma: score += 30

    # 6. DASHBOARD
    st.subheader(f"Dashboard: {ticker}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Live Price", f"${cur_p:,.2f}")
    c2.metric("Market Sentiment", f"{fg_val:.0f}", help=fg_text)
    c3.metric("RSI Score", f"{rsi_val:.1f}")

    # DECISION LOGIC
    if score > 70:
        st.success(f"🔥 **AGRESSIVE BUY** | Deploy `${baseline * 2:,.2f}`")
    elif score > 35:
        st.info(f"⚖️ **DCA / STEADY** | Deploy `${baseline:,.2f}`")
    else:
        st.warning(f"⚠️ **CAUTION / HOLD** | Deploy `${baseline * 0.5:,.2f}`")

    # Trend Chart
    st.line_chart(pd.DataFrame({"Price": close, "200MA": ma200}))
else:
    st.error("Select a valid asset from the sidebar to display data.")
