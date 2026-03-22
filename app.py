import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# 1. SETUP & THEME
st.set_page_config(page_title="ETF Dip-Terminal v1.1", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal v1.1")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        try:
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
        except:
            ticker = user_input.upper()
    else:
        st.info("👋 Enter a ticker to begin.")
    
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
    except: pass
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
    
    # Currency & PE (context only)
    try:
        f_info = yt.fast_info
        currency = f_info.get('currency', 'USD')
        pe_ratio = yt.info.get('trailingPE') or yt.info.get('forwardPE')
    except:
        currency = "USD"
        pe_ratio = None

    calc_df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not calc_df.empty:
        if isinstance(calc_df.columns, pd.MultiIndex): 
            calc_df.columns = calc_df.columns.get_level_values(0)
        
        close_calc = calc_df['Close']
        cur_p = float(close_calc.iloc[-1])

        # Technicals
        ma200_series = close_calc.rolling(window=200).mean()
        ma200_val = ma200_series.iloc[-1]
        ma50_val = close_calc.rolling(window=50).mean().iloc[-1]

        # RSI
        delta = close_calc.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        # Drawdown
        rolling_max = close_calc.cummax()
        drawdown = (cur_p / rolling_max.iloc[-1] - 1) * 100

        # Improved slope logic
        if len(ma200_series.dropna()) > 20:
            ma_slope = ma200_series.iloc[-1] - ma200_series.iloc[-20]
        else:
            ma_slope = 0

        # DIP SCORE (refined)
        dip_score = 0

        # Depth
        if drawdown < -20: dip_score += 30
        elif drawdown < -10: dip_score += 20
        elif drawdown < -5: dip_score += 10

        # Trend (less optimistic)
        if ma_slope > 0:
            dip_score += 40
        elif ma_slope > -0.5:
            dip_score += 15

        # Structure
        if cur_p > ma50_val:
            dip_score += 30
        elif cur_p > ma200_val:
            dip_score += 15

        # ORIGINAL SCORE
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200_val: score += 30

        # 🔥 FINAL BLENDED SCORE (NEW)
        final_score = 0.7 * score + 0.3 * dip_score

        # UI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"{cur_p:,.2f} {currency}")
        c1.markdown(f"🔗 [Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker})")
        
        c2.metric("Market Sentiment", f"{fg_val:.0f}/100")
        c2.markdown(f"🔗 [{fg_label} ↗]({fg_url})")
        
        c3.metric("RSI (Momentum)", f"{rsi_val:.1f}")
        c3.markdown("🔗 [RSI Theory ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        c4.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
        c4.markdown("🔗 [PE Explained ↗](https://www.investopedia.com/terms/p/price-earningsratio.asp)")

        st.divider()

        # DIP PANEL
        st.subheader("🧠 Dip Intelligence")
        d1, d2, d3 = st.columns(3)
        d1.metric("Drawdown", f"{drawdown:.1f}%")
        d2.metric("Trend Slope", f"{ma_slope:.2f}")
        d3.metric("Dip Score", f"{dip_score}/100")

        with st.expander("📝 Advanced Strategy Breakdown", expanded=True):
            st.write(f"""
            **Dip Score ({dip_score}) → Structure + Trend + Depth**
            **Base Score ({score}) → Sentiment + RSI**

            **Final Score = 70% Base + 30% Dip Intelligence = {final_score:.1f}**

            **P/E ({pe_ratio if pe_ratio else 'N/A'}) is ONLY long-term context.**
            It does NOT predict short-term dips.

            👉 This system distinguishes:
            - Panic inside strength (buy)
            - Weak trend breakdown (caution)
            """)

        st.divider()

        # FINAL DECISION (UPDATED)
        if final_score >= 70:
            st.success(f"🔥 **AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
        elif final_score >= 40:
            st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
        else:
            st.warning(f"⚠️ **CAUTION / REDUCE** | Invest `{baseline * 0.5:,.2f} {currency}`")

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
        st.error("No data found. Try a common ticker like VOO or SPY.")
