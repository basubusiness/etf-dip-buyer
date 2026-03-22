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

# 3. SENTIMENT ENGINE (Multi-Source Fallback)
def get_fear_greed_alt():
    """Fallback using alternative.me (Crypto F&G as a high-risk proxy)."""
    try:
        url = "https://api.alternative.me/fng/"
        res = requests.get(url, timeout=5)
        data = res.json()
        val = float(data["data"][0]["value"])
        label = data["data"][0]["value_classification"]
        return val, f"{label} (Alt Source)"
    except:
        return None, None

@st.cache_data(ttl=300)
def get_fear_greed():
    """Primary CNN fetch with automated fallback logic."""
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed"
        }
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            raise ValueError(f"Status {res.status_code}")

        data = res.json()
        fg_val = float(data["fear_and_greed"]["score"])
        
        if fg_val <= 25: fg_text = "Extreme Fear"
        elif fg_val <= 45: fg_text = "Fear"
        elif fg_val <= 55: fg_text = "Neutral"
        elif fg_val <= 75: fg_text = "Greed"
        else: fg_text = "Extreme Greed"
        
        return fg_val, fg_text, "CNN Business"
    
    except Exception as e:
        alt_val, alt_text = get_fear_greed_alt()
        if alt_val is not None:
            return alt_val, alt_text, "Alternative.me (Fallback)"
        return 50.0, "Neutral (All Sources Failed)", "None"

# 4. LIGHTWEIGHT TICKER ENGINE
@st.cache_data(ttl=600)
def fetch_ticker_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    yt = yf.Ticker(symbol)
    try:
        f_info = yt.fast_info
        currency = f_info.get('currency', 'USD')
        exchange = f_info.get('exchange', 'N/A')
    except:
        currency, exchange = "USD", "N/A"
    return df, currency, exchange

# 5. EXECUTION
if ticker:
    # A. Get Sentiment
    fg_val, fg_text, source_name = get_fear_greed()
    
    # B. Get Market Data
    try:
        df, currency, exchange = fetch_ticker_data(ticker)

        if not df.empty and len(df) > 20:
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
            
            # C. SCORING (Institutional Nuance)
            sentiment_score = 0
            if fg_val < 20: sentiment_score = 45   # Extreme Panic
            elif fg_val < 35: sentiment_score = 30 # General Fear
            elif fg_val < 50: sentiment_score = 10 # Slight Pessimism

            tech_score = 0
            if rsi_val < 35: tech_score += 25     
            if cur_p < cur_ma: tech_score += 30   

            total_score = sentiment_score + tech_score

            # D. DASHBOARD UI
            st.subheader(f"Terminal: {ticker}")
            st.caption(f"Exchange: {exchange} | Currency: {currency} | Source: {source_name}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Live Price", f"{cur_p:,.2f} {currency}")
            c2.metric("Market Sentiment", f"{fg_val:.0f}", help=f"Source: {source_name}")
            c2.write(f"**Rating:** {fg_text}")
            c3.metric("RSI (14-Day)", f"{rsi_val:.1f}")

            st.divider()

            # RECOMMENDATION
            if total_score > 70:
                st.success(f"🔥 **AGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
            elif total_score > 35:
                st.info(f"⚖️ **STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
            else:
                st.warning(f"⚠️ **CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

            st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
            
        else:
            st.error("Data currently unavailable due to provider limits. Try a different ticker.")
    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("Enter an asset in the sidebar to begin.")
