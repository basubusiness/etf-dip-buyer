import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. SETUP & THEME
st.set_page_config(page_title="ETF Dip-Terminal v2.0", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - ADVANCED SEARCH & SETTINGS
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # (1) High-limit search for ISIN/Ticker variety
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {
                f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] 
                for r in search.quotes if 'symbol' in r
            }
            selected_label = st.selectbox("Select Asset (Top 100 results):", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    # (3) Novice Corner: Dollar Value Selling
    with st.expander("💡 Novice Corner: What is 'Value Selling'?", expanded=False):
        st.write("""
        **Dollar-Cost Averaging (DCA):** Investing the same amount ($1,000) every month regardless of price.
        
        **Value-Adjusted Buying:** This app suggests you 'Sell' or 'Reduce' your buy when prices are too high (Greed). 
        By investing less when expensive and more when cheap, you lower your **Average Cost** faster than standard DCA.
        """)

# 3. SENTIMENT ENGINE (VIX MATH EXPLAINED)
@st.cache_data(ttl=300)
def get_market_sentiment():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    # VIX Fallback Logic
    try:
        vix = yf.Ticker("^VIX")
        vix_p = vix.fast_info['last_price']
        # (2) Math: We use an inverse multiplier. 
        # Market standard: VIX > 30 is high fear. We map VIX 40 to Score 0, VIX 10 to Score 100.
        fg_val = max(0, min(100, 100 - (vix_p * 2.5))) 
        return fg_val, f"VIX-Derived ({vix_p:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Default)", "https://finance.yahoo.com"

# 4. DATA ENGINE (MULTI-TIMEFRAME)
def get_view_params(view):
    # (4) Map View to yFinance Params
    mapping = {
        "1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"),
        "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")
    }
    return mapping.get(view, ("1y", "1d"))

# 5. MAIN INTERFACE
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    
    # Timeframe Selector
    view = st.radio("Select View Range:", ["1D", "1W", "YTD", "1Y", "5Y", "MAX"], index=3, horizontal=True)
    period, interval = get_view_params(view)
    
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close_series = df['Close']
        cur_p = float(close_series.iloc[-1])
        
        # RSI Logic for decision making
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)).iloc[-1]))

        # DASHBOARD
        c1, c2, col_rsi = st.columns(3)
        c1.metric("Current Price", f"{cur_p:,.2f}")
        c2.metric("Market Sentiment", f"{fg_val:.0f}/100", help="100 = Maximum Greed, 0 = Maximum Fear")
        col_rsi.metric("RSI (Momentum)", f"{rsi_val:.1f}")

        # (2) Math & RSI Explanation
        with st.expander("📝 Strategy & Math Breakdown"):
            st.write(f"""
            **1. Sentiment Math:** We take the VIX (currently at {fg_val/2.5:.2f} if using fallback). 
            Since VIX measures 'expected volatility', a high VIX usually means prices are crashing. 
            Formula: $Sentiment = 100 - (VIX \\times 2.5)$
            
            **2. RSI Logic:** The Relative Strength Index (RSI) measures if a 'rubber band' is stretched too far. 
            - If RSI < 35: The market is 'Oversold' (Rubber band stretched down, likely to snap up).
            - If RSI > 70: The market is 'Overbought' (Rubber band stretched up, likely to snap down).
            
            **3. Influence:** If RSI is low AND Sentiment is Fearful, we trigger the **Aggressive Buy**.
            """)

        # ALLOCATION BOX
        st.divider()
        score = 0
        if fg_val < 35: score += 50
        if rsi_val < 40: score += 50
        
        if score >= 80:
            st.success(f"🔥 **ACTION: AGGRESSIVE BUY** | Buy `{baseline * 2:,.2f}` worth of {ticker}")
        elif score >= 50:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Buy `{baseline:,.2f}` worth of {ticker}")
        else:
            # (3) Dollar Value Selling/Reduction
            st.warning(f"⚠️ **ACTION: REDUCE BUY / SELL** | Suggested: `{baseline * 0.5:,.2f}` (Market is too expensive)")

        # (4) PROFESSIONAL GRAPH (Removed margins)
        st.markdown("### Price Performance")
        st.line_chart(close_series, use_container_width=True)
        
        st.caption(f"Showing {view} View. Reference: [{fg_label} ↗]({fg_url}) | [Full Data ↗](https://finance.yahoo.com/quote/{ticker})")
    else:
        st.error("No data found for this period. Try '1Y' or a different ticker.")
