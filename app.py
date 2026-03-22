import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. PAGE CONFIG
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - UNIVERSAL SEARCH & SETTINGS
with st.sidebar:
    st.header("Search & Settings")
    # Ticker Input
    ticker = st.text_input("Enter Ticker Symbol (e.g., VOO, QQQ, AAPL)", value="VOO").upper().strip()
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    
    # Manual Trigger Button
    run_button = st.button("Run Analysis / Sync Data")
    
    st.divider()
    st.write("🔍 **External Verification Links**")
    # Dynamic links that change with your input
    st.link_button(f"Morningstar: {ticker}", f"https://www.morningstar.com/etfs/arcx/{ticker}/quote")
    st.link_button(f"Yahoo Finance: {ticker}", f"https://finance.yahoo.com/quote/{ticker}")
    st.link_button(f"Seeking Alpha: {ticker}", f"https://seekingalpha.com/symbol/{ticker}")

# 3. DATA ENGINE (With Improved Scraper)
@st.cache_data(ttl=600) # Refresh every 10 mins
def fetch_market_data(symbol):
    # Fetch Price Data
    df = yf.download(symbol, period="1y", progress=False)
    
    # Improved CNN Fear & Greed Scraper
    try:
        # Using a more robust User-Agent to avoid 'Sync Error'
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Origin': 'https://www.cnn.com',
            'Referer': 'https://www.cnn.com/'
        }
        response = requests.get(url, headers=headers, timeout=10)
        fg_data = response.json()
        fg_val = float(fg_data['now']['value'])
        fg_text = fg_data['now']['rating']
    except Exception as e:
        fg_val, fg_text = 50.0, f"Sync Error: {str(e)[:20]}"
    
    return df, fg_val, fg_text

# Execute Fetch
df, fg_val, fg_text = fetch_market_data(ticker)

# 4. DATA PROCESSING
if not df.empty and len(df) > 20:
    # Flatten 2026 Multi-Index headers
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close_series = df['Close']
    
    # Calculate Indicators
    ma200_series = close_series.rolling(window=200).mean()
    current_price = float(close_series.iloc[-1])
    current_ma200 = float(ma200_series.iloc[-1]) if not pd.isna(ma200_series.iloc[-1]) else current_price
    
    # RSI
    delta = close_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

    # 5. SCORING LOGIC
    score = 0
    if fg_val < 30: score += 40
    if rsi_val < 35: score += 30
    if current_price < current_ma200: score += 30

    # 6. DASHBOARD
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{ticker} Price", f"${current_price:,.2f}")
    c2.metric("Fear & Greed", f"{fg_val:.0f}", help=f"Rating: {fg_text}")
    c3.metric("RSI (Oversold)", f"{rsi_val:.1f}")

    st.divider()

    # 7. DECISION BOX
    if score > 70:
        st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Score: {score}/100")
        multiplier = 2.0
    elif score > 35:
        st.info(f"⚖️ **STRATEGY: DOLLAR COST AVERAGE** | Score: {score}/100")
        multiplier = 1.0
    else:
        st.warning(f"⚠️ **STRATEGY: MINIMUM EXPOSURE** | Score: {score}/100")
        multiplier = 0.5
    
    st.subheader(f"Recommended Buy: `${baseline * multiplier:,.2f}`")
    
    # 8. VISUAL CHART
    chart_data = pd.DataFrame({
        "Price": close_series, 
        "200-Day Trend": ma200_series
    })
    st.line_chart(chart_data)

else:
    st.error(f"No data found for '{ticker}'. Check the symbol and click 'Run Analysis'.")
