import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# App Styling
st.set_page_config(page_title="ETF Dip-Buyer Tool", layout="wide")
st.title("📈 ETF Dip-Buyer & Allocation Optimizer")
st.write("Calculates if today is a good day to deploy 'extra' cash based on 2026 market metrics.")

# 1. SIDEBAR INPUTS
ticker = st.sidebar.text_input("Enter ETF Ticker (e.g., VOO, QQQ, VTI)", value="VOO")
baseline_monthly = st.sidebar.number_input("Your Base Monthly Investment ($)", value=1000)

# 2. DATA FETCHING
@st.cache_data(ttl=3600) # Refreshes every hour
def get_data(ticker):
    data = yf.download(ticker, period="1y")
    return data

df = get_data(ticker)

# 3. CALCULATE INDICATORS
# 200-Day Moving Average
df['MA200'] = df['Close'].rolling(window=200).mean()
current_price = df['Close'].iloc[-1]
ma200_price = df['MA200'].iloc[-1]

# RSI (14-Day)
delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs)).iloc[-1]

# Mock Fear & Greed (In a real app, you'd scrape CNN or use a specialized API)
# For this demo, we'll use a slider or a fixed '2026' value based on your context.
fg_index = st.sidebar.slider("Current Fear & Greed (17 = Extreme Fear)", 0, 100, 17)

# 4. LOGIC: THE DIP SCORE (0-100)
rsi_score = max(0, (70 - rsi) / 40) * 100  # High score if RSI is low
ma_score = 100 if current_price < ma200_price else 0
fg_score = (100 - fg_index)

total_score = (fg_score * 0.4) + (rsi_score * 0.3) + (ma_score * 0.3)

# 5. UI DISPLAY
col1, col2, col3 = st.columns(3)
col1.metric("Current Price", f"${current_price:,.2f}")
col2.metric("RSI (14-Day)", f"{rsi:.1f}", delta="- Oversold" if rsi < 30 else None)
col3.metric("Dip Score", f"{total_score:.1f}/100")

st.divider()

# INVESTMENT DECISION
if total_score > 70:
    st.success(f"🔥 **STRONG BUY SIGNAL:** Market is in panic. Consider deploying 2x your baseline.")
    investment = baseline_monthly * 2
elif total_score > 40:
    st.info("✅ **ACCUMULATE:** Prices are fair. Stick to your baseline.")
    investment = baseline_monthly
else:
    st.warning("⚠️ **OVERBOUGHT:** Market is greedy. Consider holding cash or minimum investment.")
    investment = baseline_monthly * 0.5

st.header(f"Recommended Investment: ${investment:,.2f}")
st.line_chart(df[['Close', 'MA200']])
