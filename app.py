import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import random

# 1. SETUP & UI
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Name, Ticker, or ISIN", value="VOO").strip()
    
    ticker = None
    if user_input:
        # Increase results to 20 for better visibility
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
    st.info("💡 **Pro Tip:** If you see a Rate Limit error, wait 60 seconds. Streamlit's shared IP is likely busy.")

# 3. ROBUST DATA FETCHING
@st.cache_data(ttl=300)
def get_fear_greed():
    """Fetches the live CNN Fear & Greed value from their data endpoint."""
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        # Impersonate a browser to avoid blocks
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        data = requests.get(url, headers=headers, timeout=10).json()
        return float(data['now']['value']), data['now']['rating']
    except:
        return 50.0, "Neutral (Sync Unavailable)"

@st.cache_data(ttl=600)
def fetch_ticker_data(symbol):
    """Fetches price history and essential metadata without heavy .info calls."""
    # Fetch 1 year of daily data
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    
    # Get currency/exchange via fast_info (lightweight)
    yt = yf.Ticker(symbol)
    try:
        currency = yt.fast_info.get('currency', 'USD')
        exchange = yt.fast_info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
        
    return df, currency, exchange

# 4. EXECUTION
if ticker:
    # Get Market Sentiment
    fg_val, fg_text = get_fear_greed()
    
    # Get Stock Data
    try:
        df, currency, exchange = fetch_ticker_data(ticker)

        if not df.empty and len(df) > 20:
            # Flatten multi-index if present (yfinance 2026 style)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df['Close']
            ma200 = close.rolling(window=200).mean()
            
            # RSI Calculation
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

            cur_p = float(close.iloc[-1])
            cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
            
            # SCORING SYSTEM
            score = 0
            if fg_val < 35: score += 40  # Panic is good for buying
            if rsi_val < 35: score += 30 # Oversold is good
            if cur_p < cur_ma: score += 30 # Below long-term trend

            # DASHBOARD UI
            st.subheader(f"{ticker} Analysis")
            st.caption(f"Exchange: {exchange} | Currency: {currency}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Live Price", f"{cur_p:,.2f} {currency}")
            
            # Fear & Greed with live link
            col2.metric("Fear & Greed", f"{fg_val:.0f}", help=fg_text)
            col2.markdown(f"[Live CNN Index ↗](https://edition.cnn.com/markets/fear-and-greed)")
            
            col3.metric("RSI (14-Day)", f"{rsi_val:.1f}")
            col3.markdown("[What is RSI? ↗](https://www.investopedia.com/terms/r/rsi.asp)")

            st.divider()

            # FINAL RECOMMENDATION
            if score > 70:
                st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
            elif score > 35:
                st.info(f"⚖️ **STRATEGY: STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
            else:
                st.warning(f"⚠️ **STRATEGY: CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

            st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
            st.caption(f"Verification: [Open {ticker} on Yahoo Finance](https://finance.yahoo.com/quote/{ticker})")
            
        else:
            st.error("No historical data found. Ticker might be delisted or invalid.")
            
    except Exception as e:
        if "Rate Limit" in str(e) or "429" in str(e):
            st.error("🛑 Yahoo Finance Rate Limit reached. Please wait 1-2 minutes and refresh.")
        else:
            st.error(f"Error fetching data: {e}")
else:
    st.info("Enter a name or ticker in the sidebar to start.")
