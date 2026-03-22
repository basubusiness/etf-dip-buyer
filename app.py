import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. SETUP
st.set_page_config(page_title="ETF Dip-Terminal v1.3", layout="wide")
st.title("🏹 ETF Universal Dip-Terminal v1.3")

# Session state initialization
if 'ticker' not in st.session_state: st.session_state.ticker = "VOO"
if 'baseline' not in st.session_state: st.session_state.baseline = 1000

# 2. SIDEBAR
with st.sidebar:
    st.header("Search & Settings")
    user_input = st.text_input("Enter Ticker or ISIN", placeholder="VOO, VWCE.DE...").strip()
    
    if user_input:
        try:
            search = yf.Search(user_input, max_results=10) # Reduced results to save rate limit
            if search.quotes:
                options = {f"{r['symbol']} | {r.get('longname', 'Unknown')}": r['symbol'] for r in search.quotes if 'symbol' in r}
                selected_label = st.selectbox("Select Asset:", options.keys())
                st.session_state.ticker = options[selected_label]
        except:
            st.warning("Search currently limited by Yahoo. Try again in 1 minute.")
    
    st.session_state.baseline = st.number_input("Monthly Base Investment", value=st.session_state.baseline)

# 3. SENTIMENT ENGINE (Frozen)
@st.cache_data(ttl=600) # Increased cache to reduce requests
def get_market_sentiment():
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/feargreed/graphdata", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"
    except: pass
    return 50.0, "Neutral (Default)", ""

# 4. RATE-LIMIT FRIENDLY FUNDAMENTALS
def get_valuation_safe(ticker_obj):
    try:
        # Use .fast_info instead of .info (6x faster, less likely to trigger rate limit)
        f_info = ticker_obj.fast_info
        currency = f_info.get('currency', 'USD')
        # P/E is unfortunately only in the 'heavy' .info. 
        # We wrap it in a separate try to keep the app running if it fails.
        pe = None
        try:
            pe = ticker_obj.info.get('trailingPE')
        except: 
            pe = None # Silent fail for PE to keep dashboard alive
            
        hi_52 = f_info.get('yearHigh')
        return pe, hi_52, currency
    except Exception as e:
        return None, None, "USD"

# 5. EXECUTION
ticker = st.session_state.ticker
if ticker:
    yt = yf.Ticker(ticker)
    fg_val, fg_label, fg_url = get_market_sentiment()
    
    # Download is usually safer than .info for rate limits
    df_calc = yf.download(ticker, period="1y", interval="1d", progress=False)
    
    if not df_calc.empty:
        if isinstance(df_calc.columns, pd.MultiIndex): df_calc.columns = df_calc.columns.get_level_values(0)
        
        cur_p = float(df_calc['Close'].iloc[-1])
        ma200 = df_calc['Close'].rolling(window=200).mean().iloc[-1]
        
        # RSI 
        delta = df_calc['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)).iloc[-1]))

        # Get Valuation (Safe way)
        pe_ratio, high_52, currency = get_valuation_safe(yt)
        drawdown = ((cur_p - high_52) / high_52) * 100 if high_52 else 0

        # UI LAYOUT
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"{cur_p:,.2f} {currency}")
        c2.metric("Market Sentiment", f"{fg_val:.0f}/100")
        c3.metric("RSI (Momentum)", f"{rsi_val:.1f}")
        c4.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")

        if pe_ratio is None:
            st.warning("⚠️ **Yahoo Rate Limit:** P/E Ratio temporarily hidden to prevent app crash.")

        # Scoring Logic
        score = 0
        if fg_val < 35: score += 30
        if rsi_val < 40: score += 20
        if cur_p < ma200: score += 25
        if drawdown < -10: score += 25 

        st.divider()
        if score >= 75:
            st.success(f"🔥 **ACTION: AGGRESSIVE BUY** | Invest `{st.session_state.baseline * 2:,.2f} {currency}`")
        elif score >= 40:
            st.info(f"⚖️ **ACTION: STEADY DCA** | Invest `{st.session_state.baseline:,.2f} {currency}`")
        else:
            st.warning(f"⚠️ **ACTION: REDUCE BUY** | Invest `{st.session_state.baseline * 0.5:,.2f} {currency}`")

        # Range Selector & Graph
        st.subheader("Price Performance")
        view = st.select_slider("Adjust Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
        p_map = {"1D": ("1d", "1m"), "1W": ("5d", "30m"), "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
        p, i = p_map.get(view)
        df_view = yf.download(ticker, period=p, interval=i, progress=False)
        
        if not df_view.empty:
            if isinstance(df_view.columns, pd.MultiIndex): df_view.columns = df_view.columns.get_level_values(0)
            st.line_chart(df_view['Close'])
