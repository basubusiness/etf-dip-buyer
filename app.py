import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 1. LIVE DATA SCRAPER (The 'Secret Sauce')
def get_live_fear_greed():
    """Scrapes CNN Fear & Greed directly from their site."""
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers).json()
        return float(r['now']['value']), r['now']['rating']
    except:
        return 50.0, "Neutral (Data Sync Error)"

# 2. APP CONFIG
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Dip-Terminal v2.0")

# 3. SEARCHABLE ETF DATABASE (AJAX-like Search)
etf_db = {
    "Vanguard S&P 500 (VOO)": "VOO",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Total Stock Market (VTI)": "VTI",
    "Dividend Appreciation (VIG)": "VIG",
    "Growth ETF (VUG)": "VUG",
    "S&P 500 (SPY)": "SPY",
    "Semiconductor Sector (SMH)": "SMH"
}

with st.sidebar:
    st.header("Settings")
    # Search-as-you-type search bar
    search_choice = st.selectbox("Search ETF Name:", options=list(etf_db.keys()))
    ticker = etf_db[search_choice]
    
    baseline = st.number_input("Monthly Base ($)", value=1000)
    
    st.divider()
    # Live Sync Display
    fg_val, fg_text = get_live_fear_greed()
    st.write(f"**Live Sentiment:** {fg_text}")
    st.progress(fg_val/100)

# 4. FETCH MARKET DATA
df = yf.download(ticker, period="1y")

if not df.empty:
    # Logic: 200-Day MA & RSI
    df['MA200'] = df['Close'].rolling(window=200).mean()
    current_price = float(df['Close'].iloc[-1])
    ma200 = float(df['MA200'].iloc[-1])
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]

    # 5. THE DIP ALGORITHM
    # Higher Score = Better "Dip"
    score = 0
    if fg_val < 30: score += 40  # Panic is high
    if rsi < 35: score += 30     # Oversold
    if current_price < ma200: score += 30 # Below trend
    
    # 6. UI
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${current_price:,.2f}")
    c2.metric("Market Sentiment", f"{fg_val:.0f}", help=fg_text)
    c3.metric("RSI Score", f"{rsi:.1f}")

    st.subheader(f"Strategy: {'🔥 AGGRESSIVE BUY' if score > 70 else '⚖️ DOLLAR COST AVERAGE'}")
    
    multiplier = 2 if score > 70 else (1 if score > 30 else 0.5)
    st.write(f"**Recommended Buy today:** `${baseline * multiplier:,.2f}`")
    
    st.line_chart(df[['Close', 'MA200']])
