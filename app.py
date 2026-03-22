import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP & THEME
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - (1) 100 SEARCH RESULTS & (3) NOVICE EXPLANATION
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # High-limit search for ISIN/Ticker variety
        search = yf.Search(user_input, max_results=100)
        if search.quotes:
            options = {
                f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] 
                for r in search.quotes if 'symbol' in r
            }
            selected_label = st.selectbox("Select Asset (Top 100 Results):", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment ($)", value=1000)
    st.divider()
    
    with st.expander("💡 Novice Corner: What is 'Value Selling'?", expanded=False):
        st.write("""
        **Standard DCA:** Investing $1,000 every month regardless of price.
        
        **Value-Adjusted Buying:** This app suggests you 'Reduce' your buy when prices are high (Greed). 
        By investing less when expensive and more when cheap, you lower your **Average Cost** faster than standard DCA. 
        It essentially forces you to 'Buy Low' and 'Save Cash' during highs.
        """)

# 3. SENTIMENT ENGINE (2) VIX MATH EXPLAINED
@st.cache_data(ttl=300)
def get_market_sentiment():
    # Primary: CNN
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass
    # Fallback: VIX
    try:
        vix = yf.Ticker("^VIX").fast_info['last_price']
        # Math: We map VIX to a 0-100 scale. VIX 20 = 50 Score. VIX 40 = 0 Score.
        fg_val = max(0, min(100, 100 - (vix * 2.5))) 
        return fg_val, f"VIX-Derived Sentiment ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Manual)", "https://finance.yahoo.com"

# 4. DATA ENGINE (4) TIME-VIEWS
def get_period_data(symbol, view):
    mapping = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
    p, i = mapping.get(view, ("1y", "1d"))
    df = yf.download(symbol, period=p, interval=i, progress=False)
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# 5. MAIN INTERFACE
if ticker:
    # Timeframe Selector (Placed above metrics for logic flow)
    view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
    
    fg_val, fg_label, fg_url = get_market_sentiment()
    df = get_period_data(ticker, view)

    if not df.empty and len(df) > 1:
        close = df['Close']
        cur_p = float(close.iloc[-1])
        ma200 = close.rolling(window=200).mean()
        
        # RSI Logic
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        # METRICS & REFERENCE LINKS
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Current Price", f"{cur_p:,.2f}")
            st.markdown(f"🔗 [Yahoo Finance History ↗](https://finance.yahoo.com/quote/{ticker}/history)")
        with c2:
            st.metric("Market Sentiment", f"{fg_val:.0f}/100")
            st.markdown(f"🔗 [{fg_label} ↗]({fg_url})")
        with c3:
            st.metric("RSI (Momentum)", f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "N/A")
            st.markdown("🔗 [RSI Strategy Theory ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        # (2) DETAILED STRATEGY TEXT
        with st.expander("📝 Strategy & Math Breakdown", expanded=True):
            st.write(f"""
            **1. Sentiment Math:** We pull the VIX (Volatility Index). Since VIX measures 'expected fear', high VIX means prices are likely at a bottom.
            *Current Logic:* $Sentiment = 100 - (VIX \\times 2.5)$.
            
            **2. RSI Logic:** The Relative Strength Index (RSI) identifies momentum exhaustion. 
            * If RSI < 35: The asset is 'Oversold' (The rubber band is stretched too far down).
            * If RSI > 70: The asset is 'Overbought' (Too many people have already bought).
            
            **3. Influence:** If Sentiment is Fearful (<35) AND RSI is Low (<40), it triggers an **Aggressive Buy**.
            """)

        # ALLOCATION DECISION
        score = 0
        if fg_val < 35: score += 40
        if not pd.isna(rsi_val) and rsi_val < 40: score += 30
        if cur_p < (ma200.iloc[-1] if not pd.isna(ma200.iloc[-1]) else cur_p): score += 30

        st.divider()
        if score >= 70:
            st.success(f"🔥 **ACTION: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f}` in {ticker}")
        elif score >= 35:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Invest `{baseline:,.2f}` in {ticker}")
        else:
            st.warning(f"⚠️ **ACTION: REDUCE BUY / SELL** | Suggested: `{baseline * 0.5:,.2f}` (Market is Overvalued)")

        # GRAPH (Start-to-End, No blank areas)
        chart_df = pd.DataFrame({"Price": close})
        if view in ["YTD", "1Y", "5Y", "MAX"]:
            chart_df["200-Day Trend"] = ma200
        
        st.line_chart(chart_df, use_container_width=True)
    else:
        st.error("No historical data found for this range. Please try '1Y' or a different ticker.")
