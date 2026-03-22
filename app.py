import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - (1) IMPROVED SEARCH & (3) NOVICE EXPLANATION
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # Increase search limit to 100
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search.quotes if 'symbol' in r}
            selected_label = st.selectbox("Select Asset (Top 100):", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    # (3) Novice Corner
    with st.expander("💡 Novice Corner: What is 'Value Selling'?"):
        st.write("""
        Standard DCA means buying the same amount every month. 
        **Value Selling/Reduction** means when the market is in 'Greed', we reduce our buy to save cash. 
        When the market is in 'Fear', we use that saved cash to buy more. 
        This lowers your average cost significantly over time.
        """)

# 3. SENTIMENT ENGINE (2) MATH EXPLAINED
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
        # (2) VIX Math: VIX measures volatility (Fear). 
        # We use: 100 - (VIX * 2.5). If VIX is 20, Score is 50. If VIX is 40, Score is 0.
        fg_val = max(0, min(100, 100 - (vix * 2.5))) 
        return fg_val, f"VIX-Derived ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Default)", "https://finance.yahoo.com"

# 4. DATA ENGINE (4) TIMEFRAME FIX
def get_period_data(symbol, view):
    # Mapping for yfinance
    mapping = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
    p, i = mapping.get(view, ("1y", "1d"))
    df = yf.download(symbol, period=p, interval=i, progress=False)
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# 5. EXECUTION
if ticker:
    # (4) Timeframe View Selector - Placed logically above graph
    view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
    
    fg_val, fg_label, fg_url = get_market_sentiment()
    df = get_period_data(ticker, view)

    if not df.empty and len(df) > 1:
        # Metrics Calculations
        close = df['Close']
        cur_p = float(close.iloc[-1])
        ma200 = close.rolling(window=200).mean()
        
        # RSI Calculation
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])
        
        # (2) RSI Tooltip Explaination
        rsi_help = "RSI measures if the price is 'over-stretched'. Below 35 means it's likely to bounce back up."

        # UI LAYOUT
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Price", f"{cur_p:,.2f}")
        c2.metric("Market Mood", f"{fg_val:.0f}/100", help=fg_label)
        c3.metric("RSI (Momentum)", f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "N/A", help=rsi_help)

        # (2) Math Descriptions
        with st.expander("📝 Strategy & Math Breakdown", expanded=True):
            st.write(f"**Sentiment Math:** Using {fg_label}. Formula: $100 - (VIX \\times 2.5)$. Low scores mean high fear.")
            st.write(f"**RSI Influence:** RSI is {rsi_val:.1f}. This tells us if the dip is 'exhausted' yet.")

        # RECOMMENDATION
        score = 0
        if fg_val < 35: score += 40
        if not pd.isna(rsi_val) and rsi_val < 40: score += 30
        if cur_p < (ma200.iloc[-1] if not pd.isna(ma200.iloc[-1]) else cur_p): score += 30

        st.divider()
        if score >= 70:
            st.success(f"🔥 **AGRESSIVE BUY** | Invest `{baseline * 2:,.2f}` in {ticker}")
        elif score >= 35:
            st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f}` in {ticker}")
        else:
            st.warning(f"⚠️ **REDUCE BUY** | Invest `{baseline * 0.5:,.2f}` (Market Expensive)")

        # (4) GRAPH (Start to End Point, no blank spaces)
        chart_df = pd.DataFrame({"Price": close})
        if view in ["1Y", "5Y", "MAX"]:
            chart_df["200-Day Trend"] = ma200
        
        st.line_chart(chart_df, use_container_width=True)
        st.caption(f"Showing {view} View | [Reference: {fg_label} ↗]({fg_url})")
    else:
        st.error("Insufficient data for this timeframe. Please select '1Y' or another asset.")
