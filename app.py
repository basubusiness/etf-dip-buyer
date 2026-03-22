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
        # (3) Result limit set to 100
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
    # Attempt CNN Fear & Greed
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    # VIX Fallback - Real-time fetch
    vix = yf.Ticker("^VIX")
    vix_val = vix.fast_info['last_price']
    
    # Mapping VIX to a 0-100 Fear/Greed scale (Inverse)
    # VIX 10 = Greed (90), VIX 20 = Neutral (50), VIX 30+ = Extreme Fear (<20)
    fg_val = max(0, min(100, 100 - (vix_val * 2.5))) 
    return fg_val, f"VIX-Derived Sentiment ({vix_val:.2f})", "https://finance.yahoo.com/quote/^VIX"

# 4. EXECUTION
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    df = yf.download(ticker, period="1y", interval="1d", progress=False)
    
    if not df.empty:
        # Fix for multi-index columns in newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        cur_p = float(df['Close'].iloc[-1])
        ma200 = df['Close'].rolling(window=200).mean().iloc[-1]
        
        # RSI Calculation
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        # (4) Tooltip Formula
        rsi_math = "RSI = 100 - [100 / (1 + (AvgGain/AvgLoss))]"

        # UI LAYOUT
        st.subheader(f"Terminal Output: {ticker}")
        
        # (2) Precise Reference Links
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.metric("Last Price", f"{cur_p:,.2f}")
            st.markdown(f"🔗 [Live Data: {ticker} ↗](https://finance.yahoo.com/quote/{ticker})")
            
        with c2:
            st.metric("Market Mood", f"{fg_val:.0f}/100")
            st.markdown(f"🔗 [Source: {fg_label} ↗]({fg_url})")
            
        with c3:
            st.metric("RSI (14D)", f"{rsi_val:.1f}", help=rsi_math)
            st.markdown("🔗 [RSI Education ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        # Scoring & Logic
        score = 0
        if fg_val < 30: score += 40  # High Fear = High Buy Score
        if rsi_val < 35: score += 30 # Oversold
        if cur_p < ma200: score += 30 # Below Trend
        
        st.divider()
        st.write(f"**Terminal Signal Score:** `{score}/100` (Calculated {datetime.now().strftime('%Y-%m-%d %H:%M')})")
        
        if score >= 70:
            st.success(f"💎 **ACTION: HEAVY DIP BUY** | Suggested: `{baseline * 2:,.2f}`")
        else:
            st.info(f"🧘 **ACTION: STANDARD DCA** | Suggested: `{baseline:,.2f}`")
