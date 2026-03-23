import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="ETF Dip-Terminal v3.2", layout="wide")
st.title("🏹 ETF Dip-Terminal v3.2")

ticker = None
isin = None

# ----------------------------------
# HELPERS
# ----------------------------------
def is_isin(x):
    return len(x) == 12 and x[:2].isalpha()

# ----------------------------------
# SIDEBAR
# ----------------------------------
with st.sidebar:
    st.header("Search")

    user_input = st.text_input("Enter Ticker / ISIN", value="VOO").strip()

    if user_input:
        try:
            if is_isin(user_input):
                isin = user_input.upper()

            search = yf.Search(user_input, max_results=50)

            if search.quotes:
                options = {
                    f"{r['symbol']} | {r.get('longname','')}": {
                        "symbol": r['symbol'],
                        "isin": r.get('isin')
                    }
                    for r in search.quotes if 'symbol' in r
                }

                selected = st.selectbox("Select Asset", options.keys())
                selected_data = options[selected]

                ticker = selected_data["symbol"]
                isin = isin or selected_data.get("isin")
                asset_name = selected.lower()

            else:
                ticker = user_input.upper()
                asset_name = ticker.lower()

        except:
            ticker = user_input.upper()
            asset_name = ticker.lower()

    baseline = st.number_input("Monthly Investment (€ / $)", value=1000)

# ----------------------------------
# FUNCTIONS
# ----------------------------------
def get_data(symbol):
    df = yf.download(symbol, period="1y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def get_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            return float(res.json()["fear_and_greed"]["score"]), "Live"
    except:
        pass
    return None, "Unavailable"

def get_vix():
    try:
        df = yf.download("^VIX", period="1mo", interval="1d", progress=False)
        latest = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-5])
        return latest, latest - prev
    except:
        return None, None

# ----------------------------------
# MAIN
# ----------------------------------
if ticker:

    fg_val, fg_status = get_fear_greed()

    if fg_status != "Live":
        st.warning("⚠️ Fear & Greed unavailable — please input manually")
        st.markdown("🔗 https://edition.cnn.com/markets/fear-and-greed")

        fg_val = st.number_input("Enter Fear & Greed Index (0–100)", 0, 100, 50)

    run = st.button("Run Analysis")

    if run:

        df = get_data(ticker)
        yt = yf.Ticker(ticker)

        close = df["Close"]
        cur_p = float(close.iloc[-1])

        # ----------------------------------
        # DATA QUALITY CHECK
        # ----------------------------------
        if close.nunique() < 5:
            st.warning("⚠️ Price has barely moved recently — signals may be unreliable")
        
        elif close.isna().sum() > len(close) * 0.2:
            st.warning("⚠️ Missing data detected — indicators may be unreliable")

        ma200 = close.rolling(200).mean()

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])
        rs_prev = rs.iloc[-2]
        rsi_prev = float(100 - (100 / (1 + rs_prev)))

        # Trend
        prev = ma200.iloc[-20]
        ma_slope = ((ma200.iloc[-1] - prev) / prev) * 100

        # VIX
        vix_val, vix_change = get_vix()

        # ----------------------------------
        # ENTRY TIMING
        # ----------------------------------
        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
        rsi_rising = rsi_val > rsi_prev
        trend_weak = ma_slope <= 0

        volatility = close.pct_change().rolling(20).std().iloc[-1] * 100
        trigger_threshold = max(1.0, volatility * 1.5)

        if rsi_val < 35 and trend_weak:
            state = "WAIT"
        elif price_change > trigger_threshold and rsi_rising:
            state = "TRIGGER"
        else:
            state = "WATCH"

        # ----------------------------------
        # DECISION
        # ----------------------------------
        st.subheader("🎯 Decision")

        yf_link = f"https://finance.yahoo.com/quote/{ticker}"

        st.caption(f"""
Ticker: {ticker}  
ISIN: {isin if isin else "Not available"}  
🔗 {yf_link}
""")

        if isin:
            st.caption(f"🔗 https://www.justetf.com/en/etf-profile.html?isin={isin}")

        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200.iloc[-1]: score += 30

        # ----------------------------------
        # ENTRY TIMING UI
        # ----------------------------------
        st.subheader("⏱ Entry Timing")
        st.caption(f"""
        Context:
        
        - Price move: {price_change:.2f}% (vs threshold {trigger_threshold:.2f}%)
        - RSI momentum: {"Improving" if rsi_rising else "Weakening"}
        - Trend: {"Supportive" if not trend_weak else "Weak"}
        
        👉 Decision is based on alignment of these three signals
        """)

        if state == "WAIT":
            st.warning("🟡 WAIT → Market still falling")
        elif state == "WATCH":
            st.info("🔵 WATCH → Stabilizing")
        else:
            st.success("🟢 TRIGGER → Reversal")

        with st.expander("🔍 Entry Timing Explanation"):
            st.write(f"""
        ### 1️⃣ Price Movement
        Price Change = (Today - Yesterday) / Yesterday  
        = **{price_change:.2f}%**
        
        👉 Shows immediate direction of market
        
        ---
        
        ### 2️⃣ Volatility (Normal Movement)
        Volatility = std dev of last 20 daily returns  
        = **{volatility:.2f}%**
        
        👉 Typical daily fluctuation
        
        ---
        
        ### 3️⃣ Trigger Threshold
        Threshold = max(1%, 1.5 × volatility)  
        = **{trigger_threshold:.2f}%**
        
        👉 Filters out noise — only meaningful moves count
        
        ---
        
        ### 4️⃣ RSI Momentum (How it's derived)
        
        RS (Relative Strength) compares upward vs downward price moves over the last 14 days.

        For each day:
        - If price goes up → that amount counts as "Gain"
        - If price goes down → that amount counts as "Loss"
        
        Then:
        Average Gain = mean of all gains over 14 days  
        Average Loss = mean of all losses over 14 days  
        
        RS = Average Gain / Average Loss
        Based on this:
        
        Previous (yesterday's) RS = {rs_prev:.4f}  
        Current (today's) RS = {rs.iloc[-1]:.4f}
        
        RSI formula:
        RSI = 100 - (100 / (1 + RS))
        
        Previous RSI = {rsi_prev:.2f}  
        Current RSI = {rsi_val:.2f}
        
        Accordingly, RSI Rising = {rsi_rising}
        
        👉 This tells us whether selling pressure is easing or intensifying

        - RSI rising → TRUE - selling pressure easing
        - RSI rising → FALSE - selling pressure increasing
        
        ---
        
        ### 5️⃣ Trend Context
        Trend slope (200D Mving Average - MA) = **{ma_slope:.2f}%**  
        Trend weak = {trend_weak}
        
        👉 Trend weak helps distinguish between market regimes:

        - True  → Weak market (falling trend → higher risk)  
        - False → Healthy dip (rising trend → better buying opportunity)
        
        ---
        
        ### 🧠 How Final State is decided
        
        We combine 3 signals to understand market behavior:

        1. Price movement → Are buyers stepping in today?  
        2. RSI momentum → Is selling pressure increasing or easing?  
        3. Long-term trend → Is the broader market healthy or weakening?  
        
        👉 Together, these tell us:
        
        - Short-term direction (falling or stabilizing)  
        - Long-term strength (healthy trend or structural decline)  
        
        👉 Based on this combination, the system classifies the market as:
        WAIT → Still falling  
        WATCH → Stabilizing  
        TRIGGER → Reversal starting  

        👉 Key idea:
        We prefer to buy when:
        - Short-term weakness starts reversing  
        - AND long-term trend remains intact  
        
        This avoids:
        - Buying too early in falling markets  
        - Missing strong recoveries
        
        ---
        
        ➡️ Final State = **{state}**
        
        - WAIT → falling + weak trend  
        - WATCH → stabilizing  
        - TRIGGER → confirmed reversal  
        """)

        # ----------------------------------
        # FINAL DECISION
        # ----------------------------------
        if score >= 70:
            st.success(f"🔥 AGGRESSIVE BUY → Invest ~ {baseline * 2}")
        elif score >= 40:
            st.info(f"⚖️ STEADY BUY → Invest ~ {baseline}")
        else:
            st.warning(f"⚠️ CAUTION → Invest ~ {baseline * 0.5}")

        with st.expander("🔍 Why this recommendation?", expanded=False):
            st.write("""
        This recommendation is based on a combination of:
        
        - Market sentiment (Fear & Greed)  
        - Momentum (RSI)  
        - Long-term trend (200-day average)  
        
        👉 Investment level is adjusted based on signal strength of the above three metrics:

        - Strong buy signals (fear + oversold + healthy trend) → invest more  
        - Mixed signals → invest normal amount  
        - Weak signals → reduce exposure  
        """)

        st.divider()

        # ----------------------------------
        # SIGNALS WITH FULL EXPLANATION
        # ----------------------------------
        st.subheader("🧠 Market Signals")

        col1, col2 = st.columns(2)

        # Fear & Greed
        with col1:
            st.markdown("### 😨 Fear & Greed Index")
            st.write(f"**{fg_val}**")

            with st.expander("🔍 Explanation"):
                st.write("""
0–25 → Extreme Fear (best opportunities)  
25–50 → Fear  
50–75 → Greed  
75–100 → Extreme Greed (overvalued)
""")

        # VIX 
        with col2:
            st.markdown("### 📊 Volatility Index (VIX)")
            st.markdown("🔗 https://finance.yahoo.com/quote/%5EVIX")
        
            if vix_val:
                st.write(f"**{round(vix_val,1)}** ({vix_change:.2f}%)")
        
                with st.expander("🔍 Explanation"):
                    st.write(f"""
        **What is VIX?**  
        VIX measures expected volatility of S&P 500 over next 30 days.
        
        
        **Change Calculation**  
        We compare today's value vs ~5 trading days ago:
        
        Change = Current - Value 5 days ago  
        = {vix_val:.2f} - {(vix_val - vix_change):.2f}  
        = {vix_change:.2f}
        
        **Interpretation**
        - High VIX → fear  
        - Rising VIX → fear increasing  
        - Falling VIX → calming market
        """)

        

        col3, col4 = st.columns(2)

        # RSI FULL
        with col3:
            st.markdown("### 📉 RSI (Momentum)")
            st.write(f"**{rsi_val:.1f}**")

            with st.expander("🔍 Full RSI Calculation"):
                st.write(f"""
            ### What RSI measures
            RSI compares how strong upward vs downward price moves have been over the last 14 days.
            
            ---
            
            ### Step 1: Daily Price Change (Delta)
            Delta = Today Close - Yesterday Close  
            = **{delta.iloc[-1]:.4f}**
            
            👉 If positive → counts as Gain  
            👉 If negative → counts as Loss  
            
            ---
            
            ### Step 2: Average Gains vs Losses (14 days)
            
            Average Gain = **{gain.iloc[-1]:.4f}**  
            Average Loss = **{loss.iloc[-1]:.4f}**
            
            👉 Over the last 14 days:
            - Gains are averaged from positive days  
            - Losses are averaged from negative days  
            
            👉 Here, losses are larger → market has been falling
            
            ---
            
            ### Step 3: Relative Strength (RS)
            
            RS = Avg Gain / Avg Loss  
            = {gain.iloc[-1]:.4f} / {loss.iloc[-1]:.4f}  
            = **{rs.iloc[-1]:.4f}**
            
            👉 RS < 1 → losses dominate  
            👉 RS > 1 → gains dominate  
            
            ---
            
            ### Step 4: RSI Conversion
            
            RSI = 100 - (100 / (1 + RS))  
            
            = 100 - (100 / (1 + {rs.iloc[-1]:.4f}))  
            = **{rsi_val:.2f}**
            
            ---
            
            ### Step 5: Interpretation
            
            RSI = {rsi_val:.2f}
            
            - <30 → Oversold (strong selling, possible rebound zone)  
            - 30–70 → Neutral  
            - >70 → Overbought (strong buying, may cool off)  
            
            👉 RSI is based on a 14-day average, so it reflects trend — not just today
            """)

        # TREND FULL
        with col4:
            st.markdown("### 📈 Trend (200-day MA)")
            st.write(f"**{ma_slope:.2f}%**")

            with st.expander("🔍 Full Trend Math"):
                st.write(f"""
MA Today = {ma200.iloc[-1]:.2f}  
MA 20d Ago = {prev:.2f}

Slope = (Today - Past) / Past  
= {ma_slope:.2f}%

Interpretation:
Positive → Uptrend  
Negative → Downtrend  
Magnitude tells you how strong the trend is:

~0% to 0.5%   → Flat / weak trend  
0.5% to 2%    → Mild trend  
2% to 5%      → Strong trend  
>5%           → Very strong trend
""")

        # ----------------------------------
        # CHART
        # ----------------------------------
        st.subheader("📊 Price History (1Y)")

        chart_data = pd.DataFrame({
            "Price": close,
            "200D MA": ma200
        })

        st.line_chart(chart_data)

else:
    st.info("Enter a ticker to begin")
