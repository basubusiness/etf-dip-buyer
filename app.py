import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP & THEME
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - 100 SEARCH RESULTS & NOVICE EXPLANATION
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
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
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()
    
    with st.expander("💡 Novice Corner: What is 'Value Selling'?", expanded=False):
        st.write("""
        **Standard DCA:** Investing the same amount every month regardless of price.
        
        **Value-Adjusted Buying:** This app suggests you 'Reduce' your buy when prices are high (Greed). 
        By investing less when expensive and more when cheap, you lower your **Average Cost** faster than standard DCA.
        """)

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
        return fg_val, f"VIX-Derived Sentiment ({vix:.2f})", "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Manual)", "https://finance.yahoo.com"

# 4. DATA ENGINE
def get_period_data(symbol, view):
    mapping = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
    p, i = mapping.get(view, ("1y", "1d"))
    df = yf.download(symbol, period=p, interval=i, progress=False)
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# 5. MAIN INTERFACE
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    
    # Fetch Meta & Baseline Data
    yt = yf.Ticker(ticker)
    try:
        f_info = yt.fast_info
        currency = f_info.get('currency', 'USD')
    except:
        currency = "USD"

    # Fetch 1Y Daily for Metrics to avoid 'nan' on short timeframes
    calc_df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not calc_df.empty:
        if isinstance(calc_df.columns, pd.MultiIndex): calc_df.columns = calc_df.columns.get_level_values(0)
        
        close_calc = calc_df['Close']
        cur_p = float(close_calc.iloc[-1])
        ma200_val = close_calc.rolling(window=200).mean().iloc[-1]
        
        # RSI Calculation
        delta = close_calc.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        # METRICS & REFERENCE LINKS
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Current Price", f"{cur_p:,.2f} {currency}")
            st.markdown(f"🔗 [Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker})")
        with c2:
            st.metric("Market Sentiment", f"{fg_val:.0f}/100")
            st.markdown(f"🔗 [{fg_label} ↗]({fg_url})")
        with c3:
            st.metric("RSI (Momentum)", f"{rsi_val:.1f}")
            st.markdown("🔗 [RSI Theory ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        # DYNAMIC MATH BREAKDOWN
        with st.expander("📝 Strategy & Math Breakdown", expanded=True):
            st.write(f"**1. Sentiment Math:** Using {fg_label}. Formula: $100 - (VIX \\times 2.5)$. Low scores indicate extreme panic.")
            st.write(f"**2. RSI Logic:** RSI is currently **{rsi_val:.1f}**. Below 35 is 'Oversold'.")
            
            # (4) Dynamic Influence Calculation
            rsi_impact = "High (Oversold)" if rsi_val < 35 else "Low (Overbought)" if rsi_val > 70 else "Neutral"
            st.write(f"**3. Influence:** For **{ticker}**, the current RSI impact is **{rsi_impact}**. "
                     f"Combined with a Sentiment score of **{fg_val:.0f}**, the system determines the specific buying weight below.")

        # ALLOCATION DECISION
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200_val: score += 30

        st.divider()
        if score >= 70:
            st.success(f"🔥 **AGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}` in {ticker}")
        elif score >= 35:
            st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f} {currency}` in {ticker}")
        else:
            st.warning(f"⚠️ **REDUCE BUY / SELL** | Invest `{baseline * 0.5:,.2f} {currency}` (Market Expensive)")

        # GRAPHING SECTION - (2) RANGE SELECTOR ABOVE GRAPH
        st.subheader("Price Performance")
        view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
        
        chart_df = get_period_data(ticker, view)
        if not chart_df.empty:
            chart_data = pd.DataFrame({"Price": chart_df['Close']})
            if view in ["YTD", "1Y", "5Y", "MAX"]:
                chart_data["200-Day Trend"] = chart_df['Close'].rolling(window=200).mean()
            st.line_chart(chart_data, use_container_width=True)
    else:
        st.error("Historical data restricted. Try a different ticker.")
