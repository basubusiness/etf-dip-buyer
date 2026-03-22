import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP & UI
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")
st.write(f"Current Market Date: {pd.Timestamp.now().strftime('%B %d, %y')}")

# 2. UNIVERSAL SEARCH & SETTINGS
with st.sidebar:
    st.header("Search & Settings")
    # Universal Input: Type any ticker (VOO, QQQ, AAPL, etc.)
    ticker = st.text_input("Enter Ticker Symbol", value="VOO").upper().strip()
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    
    st.divider()
    # 3. DYNAMIC REFERENCE LINKS
    st.write("🔍 **Verify on Public Sources**")
    # These links automatically update based on the ticker you typed
    st.link_button(f"Morningstar: {ticker}", f"https://www.morningstar.com/etfs/arcx/{ticker}/quote")
    st.link_button(f"Yahoo Finance: {ticker}", f"https://finance.yahoo.com/quote/{ticker}")
    st.link_button(f"Seeking Alpha: {ticker}", f"https://seekingalpha.com/symbol/{ticker}")

# 4. DATA ENGINE
@st.cache_data(ttl=3600)
def fetch_market_data(symbol):
    # Fetching 1 year of data
    df = yf.download(symbol, period="1y")
    
    # Live Sentiment Sync (CNN Fear & Greed API)
    try:
        fg_url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        fg_data = requests.get(fg_url, headers={'User-Agent': 'Mozilla/5.0'}).json()
        fg_val = float(fg_data['now']['value'])
        fg_text = fg_data['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Neutral (Sync Error)"
    
    return df, fg_val, fg_text

df, fg_val, fg_text = fetch_market_data(ticker)

# 5. PROCESSING & LOGIC
if not df.empty and len(df) > 20:
    # Flatten 2026 Multi-Index headers
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close_series = df['Close']
    
    # Calculate Indicators as single numbers (Scalars)
    ma200_series = close_series.rolling(window=200).mean()
    current_price = float(close_series.iloc[-1])
    # Handle cases where ETF is newer than 200 days
    current_ma200 = float(ma200_series.iloc[-1]) if not pd.isna(ma200_series.iloc[-1]) else current_price
    
    # RSI Calculation
    delta = close_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

    # 6. THE SCORING ALGORITHM (Weighted)
    score = 0
    if fg_val < 30: score += 40      # 40 pts for Market Panic
    if rsi_val < 35: score += 30     # 30 pts for Oversold
    if current_price < current_ma200: score += 30 # 30 pts for "Below Trend"

    # 7. MAIN DASHBOARD DISPLAY
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{ticker} Price", f"${current_price:,.2f}")
    c2.metric("Market Sentiment", f"{fg_val:.0f}", help=fg_text)
    c3.metric("RSI (Oversold)", f"{rsi_val:.1f}")

    st.divider()

    # 8. INVESTMENT DECISION
    if score > 70:
        st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY**")
        st.write(f"The market is in **Extreme Fear** and {ticker} is technically oversold.")
        multiplier = 2.0
    elif score > 35:
        st.info(f"⚖️ **STRATEGY: DOLLAR COST AVERAGE**")
        st.write("Conditions are standard. Stick to your baseline plan.")
        multiplier = 1.0
    else:
        st.warning(f"⚠️ **STRATEGY: MINIMUM EXPOSURE**")
        st.write("Market shows signs of greed or overextension. Be cautious with new cash.")
        multiplier = 0.5
    
    st.subheader(f"Recommended Action: Invest `${baseline * multiplier:,.2f}` today.")
    
    # Visual Chart
    plot_df = pd.DataFrame({"Price": close_series, "200-Day Trend": ma200_series})
    st.line_chart(plot_df)

else:
    st.error(f"Could not retrieve data for '{ticker}'. Please ensure the ticker is correct.")
