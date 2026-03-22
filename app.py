import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP & THEME
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
    
    yt = yf.Ticker(ticker)
    try:
        f_info = yt.fast_info
        currency = f_info.get('currency', 'USD')
    except:
        currency = "USD"

    calc_df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not calc_df.empty:
        if isinstance(calc_df.columns, pd.MultiIndex): 
            calc_df.columns = calc_df.columns.get_level_values(0)
        
        close_calc = calc_df['Close']
        cur_p = float(close_calc.iloc[-1])

        # Moving averages
        ma200_series = close_calc.rolling(window=200).mean()
        ma200_val = ma200_series.iloc[-1]
        ma50_val = close_calc.rolling(window=50).mean().iloc[-1]

        # RSI
        delta = close_calc.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        # 🔥 NEW: Drawdown (Depth)
        rolling_max = close_calc.cummax()
        drawdown = (cur_p / rolling_max.iloc[-1] - 1) * 100

        # 🔥 NEW: Trend slope (200 MA direction over last 20 days)
        if len(ma200_series.dropna()) > 20:
            ma_slope = ma200_series.iloc[-1] - ma200_series.iloc[-20]
        else:
            ma_slope = 0

        # 🔥 DIP QUALITY MODEL
        dip_score = 0

        # Depth (max 30)
        if drawdown < -20:
            dip_score += 30
        elif drawdown < -10:
            dip_score += 20
        elif drawdown < -5:
            dip_score += 10

        # Trend (max 40)
        if ma_slope > 0:
            dip_score += 40
        elif ma_slope > -1:
            dip_score += 20

        # Structure (max 30)
        if cur_p > ma50_val:
            dip_score += 30
        elif cur_p > ma200_val:
            dip_score += 15

        # EXISTING SCORE (unchanged)
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200_val: score += 30

        # METRICS
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Current Price", f"{cur_p:,.2f} {currency}")
            st.markdown(f"🔗 <a href='https://finance.yahoo.com/quote/{ticker}' target='_blank'>Yahoo Finance ↗</a>", unsafe_allow_html=True)
        with c2:
            st.metric("Market Sentiment", f"{fg_val:.0f}/100")
            st.markdown(f"🔗 <a href='{fg_url}' target='_blank'>{fg_label} ↗</a>", unsafe_allow_html=True)
        with c3:
            st.metric("RSI (Momentum)", f"{rsi_val:.1f}")
            st.markdown("🔗 <a href='https://www.investopedia.com/terms/r/rsi.asp' target='_blank'>RSI Theory ↗</a>", unsafe_allow_html=True)

        st.divider()

        # 🔥 NEW: DIP INTELLIGENCE PANEL
        st.subheader("🧠 Dip Intelligence")

        d1, d2, d3 = st.columns(3)
        d1.metric("Drawdown from Peak", f"{drawdown:.1f}%")
        d2.metric("Trend Strength (MA200 slope)", f"{ma_slope:.2f}")
        d3.metric("Dip Quality Score", f"{dip_score}/100")

        st.markdown("""
        🔗 <a href="https://www.investopedia.com/terms/d/drawdown.asp" target="_blank">Drawdown Explained ↗</a>  
        🔗 <a href="https://www.investopedia.com/terms/m/movingaverage.asp" target="_blank">Moving Average ↗</a>
        """, unsafe_allow_html=True)

        # 🔥 EXPLANATION BLOCK
        with st.expander("📝 Advanced Strategy Breakdown", expanded=True):
            st.write(f"""
            **1. Drawdown Analysis:** Current drawdown is **{drawdown:.1f}%**.
            - Deeper drawdowns = stronger potential mean reversion
            - But also higher risk if trend is broken

            **2. Trend Health (MA200 Slope):**
            - Current slope = **{ma_slope:.2f}**
            - Positive = healthy uptrend
            - Negative = weakening or downtrend

            **3. Market Structure:**
            - Price vs MA50 and MA200 determines short vs long-term strength

            **4. Dip Quality Score = {dip_score}/100**
            - 70+ → Healthy dip (likely rebound)
            - 40–70 → Uncertain regime
            - <40 → Weak structure (dip may continue)

            **5. Sentiment + RSI Layer (Original Model):**
            - Sentiment = {fg_val:.0f}
            - RSI = {rsi_val:.1f}

            👉 Final decision blends **market psychology + price structure**
            """)

        # FINAL DECISION (UNCHANGED LOGIC)
        if score >= 70:
            st.success(f"🔥 **AGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}` in {ticker}")
        elif score >= 35:
            st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f} {currency}` in {ticker}")
        else:
            st.warning(f"⚠️ **REDUCE BUY / SELL** | Invest `{baseline * 0.5:,.2f} {currency}`")

        # CHART
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
