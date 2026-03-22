# (Only showing modified MAIN INTERFACE section for clarity)

if ticker:
    fg_val, fg_label, fg_url = get_market_sentiment()
    yt = yf.Ticker(ticker)
    
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

        ma200_series = close_calc.rolling(window=200).mean()
        ma200_val = ma200_series.iloc[-1]
        ma50_val = close_calc.rolling(window=50).mean().iloc[-1]

        delta = close_calc.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_val = float((100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1])

        rolling_max = close_calc.cummax()
        drawdown = (cur_p / rolling_max.iloc[-1] - 1) * 100

        if len(ma200_series.dropna()) > 20:
            prev = ma200_series.iloc[-20]
            ma_slope = ((ma200_series.iloc[-1] - prev) / prev) * 100
        else:
            ma_slope = 0

        # -------------------------
        # SCORING (unchanged logic)
        # -------------------------
        dip_score = 0
        if drawdown < -20: dip_score += 30
        elif drawdown < -10: dip_score += 20
        elif drawdown < -5: dip_score += 10
        if drawdown < -15: dip_score += 10

        if ma_slope > 0: dip_score += 40
        elif ma_slope > -0.5: dip_score += 15

        if cur_p > ma50_val: dip_score += 30
        elif cur_p > ma200_val: dip_score += 15

        score = 0
        if fg_val < 35: score += 40
        if rsi_val < 40: score += 30
        if cur_p < ma200_val: score += 30

        final_score = 0.65 * score + 0.35 * dip_score

        st.divider()

        # =========================================
        # (1) SHOULD WE BUY?
        # =========================================
        st.subheader("🎯 Should You Buy?")

        if final_score >= 70:
            decision = "AGGRESSIVE BUY"
            st.success(f"🔥 {decision} | Invest `{baseline * 2:,.2f} {currency}`")
        elif final_score >= 40:
            decision = "STEADY BUY"
            st.info(f"⚖️ {decision} | Invest `{baseline:,.2f} {currency}`")
        else:
            decision = "CAUTION"
            st.warning(f"⚠️ {decision} | Invest `{baseline * 0.5:,.2f} {currency}`")

        # =========================================
        # (2) WHY (simple language)
        # =========================================
        st.subheader("🧠 Why this recommendation")

        explanation = []

        if fg_val < 35:
            explanation.append("Market is currently fearful (better buying conditions)")
        if rsi_val < 35:
            explanation.append("Asset has recently dropped sharply (may rebound)")
        if drawdown < -10:
            explanation.append("Price is significantly below recent highs")
        if ma_slope > 0:
            explanation.append("Long-term trend is still positive (healthy market)")
        elif ma_slope < 0:
            explanation.append("Trend is weakening (higher risk)")

        if not explanation:
            explanation.append("Market conditions are neutral")

        for e in explanation:
            st.write(f"• {e}")

        # =========================================
        # (3) DETAILS (your existing metrics)
        # =========================================
        st.subheader("📊 Check the Details")

        c1, c2, c3 = st.columns(3)
        c1.metric("Price", f"{cur_p:,.2f} {currency}")
        c2.metric("Sentiment", f"{fg_val:.0f}/100")
        c3.metric("RSI", f"{rsi_val:.1f}")

        d1, d2, d3 = st.columns(3)
        d1.metric("Drawdown", f"{drawdown:.1f}%")
        d2.metric("Trend (Slope)", f"{ma_slope:.2f}%")
        d3.metric("Dip Score", f"{dip_score}/100")

        # =========================================
        # (4) OTHER CONSIDERATIONS
        # =========================================
        st.subheader("📎 Other Considerations")

        if pe_ratio:
            st.write(f"**P/E Ratio:** {pe_ratio:.2f}")
        else:
            st.write("**P/E Ratio:** Not available for this ETF")

            if len(user_input) == 12:
                justetf_link = f"https://www.justetf.com/en/etf-profile.html?isin={user_input}"
                st.markdown(f"🔗 [View ETF Fundamentals ↗]({justetf_link})")

        st.write("""
        • Valuation is a long-term indicator  
        • It does NOT predict short-term dips  
        • Use it as background context only
        """)

        st.divider()

        # CHART (unchanged)
        st.subheader("Price Performance")
        view = st.select_slider("Adjust View Range:", options=["1D", "1W", "YTD", "1Y", "5Y", "MAX"], value="1Y")
        
        chart_df = get_period_data(ticker, view)
        if not chart_df.empty:
            chart_data = pd.DataFrame({"Price": chart_df['Close']})
            if view in ["YTD", "1Y", "5Y", "MAX"]:
                chart_data["200-Day Trend"] = chart_df['Close'].rolling(window=200).mean()
            st.line_chart(chart_data, use_container_width=True)
