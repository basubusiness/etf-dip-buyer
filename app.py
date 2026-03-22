import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal")

# 2. SIDEBAR - SMART SEARCH
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Name, Ticker, or ISIN", value="VOO").strip()
    
    ticker = None
    
    if user_input:
        # UPDATED: Increased max_results to 20
        search = yf.Search(user_input, max_results=20)
        search_results = search.quotes
        
        if search_results:
            options = {f"{r['symbol']} | {r.get('longname', 'Unknown')} ({r.get('exchange')})": r['symbol'] for r in search_results}
            selected_label = st.selectbox("Select the exact asset:", options.keys())
            ticker = options[selected_label]
        else:
            st.warning("No matches found. Using raw input.")
            ticker = user_input.upper()
    else:
        st.info("Enter a search term to begin.")

    baseline = st.number_input("Monthly Base Investment", value=1000)
    st.divider()
    
    # 3. VERIFICATION LINKS
    if ticker:
        st.write("🔍 **External Verification**")
        st.link_button(f"View {ticker} on Yahoo Finance", f"https://finance.yahoo.com/quote/{ticker}")

# 4. DATA ENGINE
@st.cache_data(ttl=600)
def fetch_market_data(symbol):
    if not symbol:
        return pd.DataFrame(), 50.0, "No Symbol", "USD"
    
    # Get Ticker Info for Currency
    yt = yf.Ticker(symbol)
    currency = yt.fast_info.get('currency', 'USD')
    
    df = yf.download(symbol, period="1y", progress=False)
    
    # Fear & Greed Scraper
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/static/daily"
        headers = {'User-Agent': 'Mozilla/5.0'}
        data = requests.get(url, headers=headers, timeout=5).json()
        fg_val, fg_text = float(data['now']['value']), data['now']['rating']
    except:
        fg_val, fg_text = 50.0, "Neutral (Sync Issue)"
    
    return df, fg_val, fg_text, currency

# 5. EXECUTION & ANALYSIS
if ticker:
    df, fg_val, fg_text, currency = fetch_market_data(ticker)

    if not df.empty and len(df) > 20:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close']
        ma200 = close.rolling(window=200).mean()
        
        # RSI Logic
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])

        cur_p = float(close.iloc[-1])
        cur_ma = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else cur_p
        
        # SCORING
        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 35: score += 30
        if cur_p < cur_ma: score += 30

        # 6. DASHBOARD UI
        st.subheader(f"Analysis for: {ticker} (Currency: {currency})")
        c1, c2, c3 = st.columns(3)
        
        # DISPLAY WITH DYNAMIC CURRENCY
        c1.metric("Live Price", f"{cur_p:,.2f} {currency}")
        
        # Fear & Greed with External Link
        c2.metric("Fear & Greed", f"{fg_val:.0f}", help=fg_text)
        c2.write("[What is this?](https://edition.cnn.com/markets/fear-and-greed)")
        
        # RSI with External Link
        c3.metric("RSI Score", f"{rsi_val:.1f}")
        c3.write("[What is this?](https://www.investopedia.com/terms/r/rsi.asp)")

        st.divider()

        # DECISION
        if score > 70:
            st.success(f"🔥 **STRATEGY: AGGRESSIVE BUY** | Invest `{baseline * 2:,.2f} {currency}`")
        elif score > 35:
            st.info(f"⚖️ **STRATEGY: STEADY DCA** | Invest `{baseline:,.2f} {currency}`")
        else:
            st.warning(f"⚠️ **STRATEGY: CAUTION / HOLD** | Invest `{baseline * 0.5:,.2f} {currency}`")

        st.line_chart(pd.DataFrame({"Price": close, "200-Day Trend": ma200}))
    else:
        st.error(f"Insufficient historical data for {ticker}.")
else:
    st.write("### Please enter an asset in the sidebar.")
