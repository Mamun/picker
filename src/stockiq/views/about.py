import pandas as pd
import streamlit as st


def render_about_tab() -> None:
    st.title("ℹ️ About StockIQ")
    st.markdown("""
    **StockIQ** is a free, open-source technical analysis tool designed to help traders and investors
    make informed decisions with real-time market data — no login, no subscription required.

    **Key Features:**
    - **Moving Averages**: Track price trends with 5, 20, 50, 100, and 200-day moving averages
    - **Fibonacci Retracement**: Identify potential support and resistance levels
    - **Reversal Pattern Detection**: Automatic detection of 7 candlestick reversal patterns
    - **Golden/Death Cross Signals**: Major trend reversal indicators based on MA50 and MA200 crossovers
    - **Buy/Sell Signal Score**: Scoring system combining multiple technical indicators
    - **Weekly Trend Analysis**: 200-week moving average for long-term secular trend confirmation
    - **SPY Dashboard**: Live SPY price, VIX fear gauge, gap table, and put/call ratio
    - **AI SPY Outlook**: 10-day SPY forecast powered by Llama 3.3, Gemini 2.0, or Claude
    - **Pre-Market & NASDAQ RSI Scanner**: Catch momentum before and during market hours
    - **Short Squeeze Scanner**: Identify high short-interest stocks with rising RSI
    - **MA200 Bounce Radar**: Find stocks pulling back to key long-term support
    - **Munger Value Picks & Analyst Signals**: Quality screeners inspired by institutional thinking

    **How It Works:**
    1. Use the **Search by Company** tab to find a stock by name or enter a ticker directly
    2. Select your preferred historical period
    3. Choose which indicators to display
    4. Click **Analyze** to generate real-time technical analysis

    All data is sourced from Yahoo Finance and updated in real-time.
    """)

    st.markdown("---")
    st.markdown("**Supported Reversal Patterns:**")
    st.dataframe(pd.DataFrame([
        {"Pattern": "Hammer",            "Type": "Bullish", "Description": "Small body at top, long lower wick — signals potential reversal from downtrend"},
        {"Pattern": "Bullish Engulfing", "Type": "Bullish", "Description": "Green candle fully engulfs prior red candle — strong reversal signal"},
        {"Pattern": "Morning Star",      "Type": "Bullish", "Description": "3-candle pattern: bearish → indecision → bullish — reversal from downtrend"},
        {"Pattern": "Shooting Star",     "Type": "Bearish", "Description": "Small body at bottom, long upper wick — signals potential reversal from uptrend"},
        {"Pattern": "Bearish Engulfing", "Type": "Bearish", "Description": "Red candle fully engulfs prior green candle — strong reversal signal"},
        {"Pattern": "Evening Star",      "Type": "Bearish", "Description": "3-candle pattern: bullish → indecision → bearish — reversal from uptrend"},
        {"Pattern": "Doji",              "Type": "Neutral", "Description": "Open ≈ Close — market indecision, potential trend change"},
    ]), width='stretch', hide_index=True, height=8 * 35 + 4)

    # ── Builder Bio ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
<div style="
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 32px 36px;
    margin-top: 8px;
    font-family: sans-serif;
">
    <div style="display:flex; align-items:center; gap:16px; margin-bottom:20px;">
        <div style="
            width:52px; height:52px;
            background: #22C55E;
            border-radius:50%;
            display:flex; align-items:center; justify-content:center;
            font-size:1.5rem; font-weight:700; color:#0F172A;
            flex-shrink:0;
        ">M</div>
        <div>
            <div style="font-size:1.2rem; font-weight:700; color:#F8FAFC;">Mamun</div>
            <div style="font-size:0.875rem; color:#22C55E; margin-top:2px;">
                Builder · Financial Data · AI · Cloud
            </div>
        </div>
    </div>

    <p style="color:#CBD5E1; font-size:0.95rem; line-height:1.75; margin:0 0 18px 0;">
        I build rapid, practical tools at the intersection of <strong style="color:#F8FAFC;">financial data</strong>
        and <strong style="color:#F8FAFC;">AI</strong>. StockIQ started as a personal project to surface
        institutional-grade technical signals for everyday traders — without a paywall.
    </p>

    <p style="color:#CBD5E1; font-size:0.95rem; line-height:1.75; margin:0 0 24px 0;">
        My focus is on turning complex APIs and models into clean, usable interfaces fast.
        I prototype quickly, ship often, and keep things free and open source wherever possible.
    </p>

    <div style="display:flex; flex-wrap:wrap; gap:10px; margin-bottom:24px;">
        <span style="background:#0F2A1A; border:1px solid #16A34A; color:#86EFAC; padding:5px 14px; border-radius:20px; font-size:0.82rem; font-weight:600;">
            Yahoo Finance API
        </span>
        <span style="background:#0F2A1A; border:1px solid #16A34A; color:#86EFAC; padding:5px 14px; border-radius:20px; font-size:0.82rem; font-weight:600;">
            GenAI APIs — Claude · Llama · Gemini
        </span>
        <span style="background:#0F2A1A; border:1px solid #16A34A; color:#86EFAC; padding:5px 14px; border-radius:20px; font-size:0.82rem; font-weight:600;">
            Cloud Deployment
        </span>
        <span style="background:#0F2A1A; border:1px solid #16A34A; color:#86EFAC; padding:5px 14px; border-radius:20px; font-size:0.82rem; font-weight:600;">
            Rapid Prototyping
        </span>
        <span style="background:#0F2A1A; border:1px solid #16A34A; color:#86EFAC; padding:5px 14px; border-radius:20px; font-size:0.82rem; font-weight:600;">
            Python · Streamlit
        </span>
    </div>

    <div style="display:flex; gap:14px; flex-wrap:wrap;">
        <a href="https://github.com/Mamun/stockIQ" target="_blank" rel="noopener noreferrer"
           style="
               display:inline-flex; align-items:center; gap:6px;
               background:#22C55E; color:#0F172A;
               font-weight:700; font-size:0.875rem;
               padding:9px 20px; border-radius:7px;
               text-decoration:none;
           ">
            View Source on GitHub
        </a>
        <a href="https://github.com/sponsors/Mamun" target="_blank" rel="noopener noreferrer"
           style="
               display:inline-flex; align-items:center; gap:6px;
               background:transparent; color:#F1C40F;
               border:1px solid #F1C40F;
               font-weight:600; font-size:0.875rem;
               padding:9px 20px; border-radius:7px;
               text-decoration:none;
           ">
            ⭐ Sponsor this project
        </a>
    </div>
</div>
""", unsafe_allow_html=True)


render_about_tab()
