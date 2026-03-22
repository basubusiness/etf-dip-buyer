import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker or Name", value="VOO").strip()
    
    ticker = None
    if user_input:
        search = yf.Search(user_input, max_results=10)
        if search.quotes:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')}": r['symbol'] for r in search.quotes}
            selected_label = st.selectbox("Select Asset:", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()
    st.info("🔄 **Reliability Update:** App now uses VIX (CBOE Volatility) as a fail-safe sentiment source.")

# 3. INSTITUTIONAL SENTIMENT ENGINE
@st.cache_data(ttl=300)
def get_market_sentiment():
    """Tries CNN (Composite). Falls back to VIX (Fear Gauge) if blocked."""
    # Attempt Primary: CNN
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://edition.cnn.com/markets/fear-and-greed"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    # Fallback: VIX (The 'Fear Gauge') - Direct from yFinance
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False)
        vix_val = float(vix_df['Close'].iloc[-1])
        
        # Institutional Mapping: High VIX = Low Sentiment Score (Fear)
        if vix_val > 30:   fg_val, label = 20, "Extreme Fear (VIX)"
        elif vix_val > 22: fg_val, label = 35, "Fear (VIX)"
        elif vix_val > 15: fg_val, label = 55, "Neutral (VIX)"
        else:              fg_val, label = 75, "Greed (VIX)"
        
        return fg_val, label, "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (No Data)", "https://finance.yahoo.com"

# 4. LIGHTWEIGHT DATA ENGINE
@st.cache_data(ttl=600)
def fetch_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    # Use fast_info to avoid Yahoo 429 rate limits
    yt = yf.Ticker(symbol)
    try:
        info = yt.fast_info
        currency, exchange = info.get('currency', 'USD'), info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
    return df, currency, exchange

# 5. ANALYSIS & DASHBOARD
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    df, curr, exch = fetch_data(ticker)

    if not df.empty and len(df) > 20:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # Technicals
        close = df['Close']
        ma200 = close.rolling(window=200).mean()
        cur_p = float(close.iloc[-1])
        cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        # SCORING (Max 100)
        score = 0
        if fg_val < 25: score += 45   # Extreme Panic (Strongest Buy Signal)
        elif fg_val < 45: score += 30 # General Fear
        if rsi_val < 35: score += 25  # Technical Oversold
        if cur_p < cur_ma: score += 30 # Value Play (Price < 200MA)

        # UI
        st.subheader(f"Strategy: {ticker}")
        st.caption(f"Source: {fg_label} | Exchange: {exch} | [View Index ↗]({fg_url})")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Live Price", f"{cur_p:,.2f} {curr}")
        c2.metric("Fear & Greed", f"{fg_val:.0f}", help=fg_label)
        c3.metric("RSI (14D)", f"{rsi_val:.1f}")

        st.divider()

        if score >= 70:
            st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {curr}`")
        elif score >= 35:
            st.info(f"⚖️ **STRATEGY: STEADY DCA** | Invest `{baseline:,.2f} {curr}`")
        else:
            st.warning(f"⚠️ **STRATEGY: HOLD / CAUTION** | Invest `{baseline * 0.5:,.2f} {curr}`")

        st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
    else:
        st.error("Historical data restricted. Try a higher volume ticker (e.g., SPY, QQQ).")
