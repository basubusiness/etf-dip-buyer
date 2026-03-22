import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - ADVANCED SEARCH
with st.sidebar:
    st.header("Search & Settings")
    # (1) ISIN Search is supported here by the yf.Search engine
    user_input = st.text_input("Enter Ticker, Name, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # (3) Increase search result limit to 100
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

# 3. SENTIMENT ENGINE
@st.cache_data(ttl=300)
def get_market_sentiment():
    """Tries CNN (Composite). Falls back to VIX (Fear Gauge)."""
    # CNN Primary
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://edition.cnn.com/markets/fear-and-greed"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            val = float(res.json()["fear_and_greed"]["score"])
            return val, "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except:
        pass

    # VIX Fallback
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False)
        vix_val = float(vix_df['Close'].iloc[-1])
        if vix_val > 30:   fg_val, label = 20, "Extreme Fear (VIX)"
        elif vix_val > 22: fg_val, label = 35, "Fear (VIX)"
        elif vix_val > 15: fg_val, label = 55, "Neutral (VIX)"
        else:              fg_val, label = 75, "Greed (VIX)"
        return fg_val, label, "https://finance.yahoo.com/quote/^VIX"
    except:
        return 50.0, "Neutral (Manual)", "https://finance.yahoo.com"

# 4. DATA ENGINE
@st.cache_data(ttl=600)
def fetch_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    yt = yf.Ticker(symbol)
    try:
        info = yt.fast_info
        currency = info.get('currency', 'USD')
        exchange = info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
    return df, currency, exchange

# 5. EXECUTION & UI
if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    df, curr, exch = fetch_data(ticker)

    if not df.empty and len(df) > 20:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close = df['Close']
        ma200 = close.rolling(window=200).mean()
        cur_p = float(close.iloc[-1])
        cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
        
        # RSI Calculation
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        # (4) RSI Tooltip Formula
        rsi_tooltip = (
            "Formula: 100 - [100 / (1 + RS)]\n"
            "Where RS = Avg Gain / Avg Loss over 14 days.\n"
            "Current score identifies momentum exhaustion."
        )

        # SCORING Logic
        score = 0
        if fg_val < 25: score += 45
        elif fg_val < 45: score += 30
        if rsi_val < 35: score += 25
        if cur_p < cur_ma: score += 30

        # DISPLAY DASHBOARD
        st.subheader(f"Analysis for {ticker}")
        
        # (2) Reference links exactly against the displayed values
        st.markdown(
            f"**Exchange:** {exch} | **Currency:** {curr} | "
            f"**Data Source:** [Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker})"
        )
        
        c1, c2, c3 = st.columns(3)
        
        # Price Metric
        c1.metric("Live Price", f"{cur_p:,.2f} {curr}")
        c1.markdown(f"[Price History ↗](https://finance.yahoo.com/quote/{ticker}/history)")
        
        # Sentiment Metric
        c2.metric("Market Sentiment", f"{fg_val:.0f}", help=f"Source: {fg_label}")
        c2.markdown(f"[{fg_label} ↗]({fg_url})")
        
        # RSI Metric
        c3.metric("RSI (14D)", f"{rsi_val:.1f}", help=rsi_tooltip)
        c3.markdown("[RSI Theory ↗](https://www.investopedia.com/terms/r/rsi.asp)")

        st.divider()

        # ALLOCATION BOX
        if score >= 70:
            st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {curr}`")
        elif score >= 35:
            st.info(f"⚖️ **STRATEGY: STEADY DCA** | Invest `{baseline:,.2f} {curr}`")
        else:
            st.warning(f"⚠️ **STRATEGY: HOLD / CAUTION** | Invest `{baseline * 0.5:,.2f} {curr}`")

        st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
    else:
        st.error("Historical data unavailable. Try a higher volume ticker (e.g., SPY, QQQ).")
else:
    st.info("### Search for an asset in the sidebar to begin.")
