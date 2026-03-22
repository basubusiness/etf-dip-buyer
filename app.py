import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP & UI
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Name, Ticker, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        search = yf.Search(user_input, max_results=20)
        search_results = search.quotes
        if search_results:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search_results}
            selected_label = st.selectbox("Select Asset:", options.keys())
            ticker = options[selected_label]
        else:
            ticker = user_input.upper()
    
    baseline = st.number_input("Monthly Base Investment", value=1000)
    
    st.divider()
    debug_mode = st.checkbox("Show Debug Logs", value=False)

# 3. ROBUST FEAR & GREED ENGINE (Critique Fix)
@st.cache_data(ttl=300)
def get_fear_greed():
    """Fetch CNN Fear & Greed Index using the stable graphdata endpoint."""
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed"
        }
        
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()

        # Extract latest score
        fg_val = float(data["fear_and_greed"]["score"])

        # Nuanced Rating Mapping
        if fg_val <= 25: fg_text = "Extreme Fear"
        elif fg_val <= 45: fg_text = "Fear"
        elif fg_val <= 55: fg_text = "Neutral"
        elif fg_val <= 75: fg_text = "Greed"
        else: fg_text = "Extreme Greed"

        return fg_val, fg_text, data if debug_mode else None
    except Exception as e:
        return 50.0, f"Sync Error: {str(e)[:15]}", None

# 4. LIGHTWEIGHT TICKER ENGINE
@st.cache_data(ttl=600)
def fetch_ticker_data(symbol):
    """Fetch price history and metadata without heavy .info calls."""
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    
    yt = yf.Ticker(symbol)
    try:
        f_info = yt.fast_info
        currency = f_info.get('currency', 'USD')
        exchange = f_info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
        
    return df, currency, exchange

# 5. EXECUTION & ANALYSIS
if ticker:
    # A. Get Sentiment
    fg_val, fg_text, debug_data = get_fear_greed()
    if debug_mode and debug_data:
        st.write("### F&G API Debug", debug_data)
    
    # B. Get Market Data
    try:
        df, currency, exchange = fetch_ticker_data(ticker)

        if not df.empty and len(df) > 20:
            # Handle yfinance 2026 MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df['Close']
            ma200 = close.rolling(window=200).mean()
            
            # RSI Math
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

            cur_p = float(close.iloc[-1])
            cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
            
            # C. NUANCED SCORING (Per Critique)
            # Sentiment (Max 45)
            sentiment_score = 0
            if fg_val < 20: sentiment_score = 45   # Extreme Panic
            elif fg_val < 35: sentiment_score = 30 # General Fear
            elif fg_val < 50: sentiment_score = 10 # Slight Pessimism

            # Technicals (Max 55)
            tech_score = 0
            if rsi_val < 35: tech_score += 25     # Oversold
            if cur_p < cur_ma: tech_score += 30   # Below Trend

            total_score = sentiment_score + tech_score

            # D. DASHBOARD UI
            st.subheader(f"{ticker} Analysis")
            st.caption(f"Exchange: {exchange} | Currency: {currency} | [Verify on Yahoo Finance ↗](https://finance.yahoo.com/quote/{ticker})")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Live Price", f"{cur_p:,.2f} {currency}")
            col2.metric("Fear & Greed", f"{fg_val:.0f}", help=fg_text)
            col2.markdown(f"**Rating:** {fg_text} [Live CNN ↗](https://edition.cnn.com/markets/fear-and-greed)")
            col3.metric("RSI (14-Day)", f"{rsi_val:.1f}")

            st.divider()

            # FINAL RECOMMENDATION
            if total_score > 70:
                st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
            elif total_score > 35:
                st.info(f"⚖️ **STRATEGY: STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
            else:
                st.warning(f"⚠️ **STRATEGY: CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

            # Chart
            st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
            
        else:
            st.error("Historical data for this ticker is currently blocked or unavailable.")
            
    except Exception as e:
        st.error(f"Error fetching data: {e}. Please wait 1 minute and refresh.")
else:
    st.info("Enter a name or ticker in the sidebar to start.")
