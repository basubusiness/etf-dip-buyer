import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search.quotes if 'symbol' in r}
            selected_label = st.selectbox("Select Asset (Top 100):", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    with st.expander("💡 Novice Corner: What is 'Value Selling'?"):
        st.write("Value-Adjusted Buying suggests investing less when prices are high (Greed) and more when cheap (Fear) to lower your average cost faster than standard DCA.")

# 3. SENTIMENT ENGINE
@st.cache_data(ttl=300)
def get_market_sentiment():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass
    try:
        vix = yf.Ticker("^VIX").fast_info['last_price']
        fg_val = max(0, min(100, 100 - (vix * 2.5))) 
        return fg_val, f"VIX-Derived ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Default)", "https://finance.yahoo.com"

# 4. DATA FETCHING (Fixed for Charting & RSI)
def get_clean_data(symbol, view):
    mapping = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
    period, interval = mapping.get(view, ("1y", "1d"))
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# 5. UI EXECUTION
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    
    # Header Metrics
    col_p, col_s, col_r = st.columns(3)
    
    # We fetch a standard 1Y daily set for the Metrics calculation to avoid 'nan'
    data_calc = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not data_calc.empty:
        if isinstance(data_calc.columns, pd.MultiIndex): data_calc.columns = data_calc.columns.get_level_values(0)
        
        cur_p = float(data_calc['Close'].iloc[-1])
        ma200 = data_calc['Close'].rolling(window=200).mean()
        
        # RSI Calculation (Daily-based to ensure accuracy)
        delta = data_calc['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)).iloc[-1]))

        col_p.metric("Current Price", f"{cur_p:,.2f}")
        col_s.metric("Market Sentiment", f"{fg_val:.0f}/100", help=fg_label)
        col_r.metric("RSI (Momentum)", f"{rsi_val:.1f}")

        # Descriptions
        with st.expander("📝 Strategy & Math Breakdown", expanded=True):
            st.write(f"1. **Sentiment:** Current Score: {fg_val:.0f}. Formula: $100 - (VIX \\times 2.5)$")
            st.write(f"2. **RSI Logic:** RSI is {rsi_val:.1f}. Below 35 is 'Oversold' (Buy opportunity).")
            st.write("3. **Influence:** High Fear + Low RSI = **Aggressive Buy**.")

        # Recommendation Logic
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200.iloc[-1]: score += 30

        st.divider()
        if score >= 70:
            st.success(f"🔥 **ACTION: AGGRESSIVE BUY** | Buy `{baseline * 2:,.2f}` worth of {ticker}")
        elif score >= 35:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Buy `{baseline:,.2f}` worth of {ticker}")
        else:
            st.warning(f"⚠️ **ACTION: REDUCE BUY** | Buy `{baseline * 0.5:,.2f}` (Market Expensive)")

        # CHARTING SECTION
        st.subheader("Price Performance")
        view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
        
        chart_df = get_clean_data(ticker, view)
        if not chart_df.empty:
            # Add 200MA to the chart if view is YTD or longer
            if view in ["YTD", "1Y", "5Y", "MAX"]:
                chart_df['200-MA'] = chart_df['Close'].rolling(window=200).mean()
                st.line_chart(chart_df[['Close', '200-MA']])
            else:
                st.line_chart(chart_df['Close'])
        
        st.caption(f"Data sourced from [Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker}) | Sentiment: [{fg_label} ↗]({fg_url})")
