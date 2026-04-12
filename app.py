import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Market Analyzer",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Stock Market Analyzer")
st.markdown("Moving Averages · Fibonacci Levels · Buy / Sell Signals")

# ── Session state ─────────────────────────────────────────────────────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "ticker_val" not in st.session_state:
    st.session_state.ticker_val = "MSFT"


def search_companies(query: str) -> list[dict]:
    """Return matching companies from Yahoo Finance search."""
    try:
        quotes = yf.Search(query, max_results=10, news_count=0).quotes
        return [
            {
                "symbol":   r.get("symbol", ""),
                "name":     r.get("shortname") or r.get("longname") or r.get("symbol", ""),
                "exchange": r.get("exchange", ""),
                "type":     r.get("quoteType", ""),
            }
            for r in quotes
            if r.get("symbol") and r.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND", "INDEX")
        ]
    except Exception:
        return []


# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    # ── Company search ────────────────────────────────────────────────────
    st.markdown("**Search by company name**")
    col_q, col_btn = st.columns([3, 1])
    search_query = col_q.text_input(
        "company_search", placeholder="e.g. Microsoft",
        label_visibility="collapsed",
    )
    if col_btn.button("Go", use_container_width=True):
        if search_query.strip():
            with st.spinner("Searching…"):
                st.session_state.search_results = search_companies(search_query.strip())
        else:
            st.session_state.search_results = []

    if st.session_state.search_results:
        labels = [
            f"{r['symbol']}  —  {r['name']}  ({r['exchange']})"
            for r in st.session_state.search_results
        ]
        choice_idx = st.selectbox(
            "Select a company", range(len(labels)),
            format_func=lambda i: labels[i],
        )
        st.session_state.ticker_val = st.session_state.search_results[choice_idx]["symbol"]
    elif search_query and not st.session_state.search_results:
        st.caption("No matches found — try a different name.")

    st.markdown("---")

    # ── Direct ticker entry (pre-filled from search selection) ───────────
    ticker = st.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
    ).upper().strip()

    period_options = {
        "1 Week":   7,
        "2 Weeks":  14,
        "1 Month":  30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year":   365,
        "2 Years":  730,
        "5 Years":  1825,
    }
    period_label = st.selectbox("Historical Period", list(period_options.keys()), index=2)
    period_days = period_options[period_label]
    show_volume = st.checkbox("Show Volume", value=True)
    show_fibonacci = st.checkbox("Show Fibonacci Levels", value=True)
    analyze_btn = st.button("Analyze", use_container_width=True, type="primary")

# ── Signal engine ─────────────────────────────────────────────────────────────

MA_PERIODS = [5, 20, 50, 100, 200]
MA_COLORS = {
    5:   "#F59E0B",   # amber
    20:  "#10B981",   # emerald
    50:  "#3B82F6",   # blue
    100: "#8B5CF6",   # violet
    200: "#EF4444",   # red
}
MA200W_COLOR = "#F0ABFC"   # fuchsia — weekly MA200
FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_COLORS = ["#94A3B8", "#F472B6", "#FB923C", "#FACC15", "#34D399", "#60A5FA", "#94A3B8"]


def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    for p in MA_PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df


def compute_weekly_ma200(daily_df: pd.DataFrame) -> pd.Series:
    """
    Resample daily Close to weekly (Friday close), compute 200-week rolling mean,
    then forward-fill back onto the daily index.
    Returns a daily-indexed Series named 'MA200W'.
    """
    weekly_close = daily_df["Close"].resample("W").last()
    weekly_ma200 = weekly_close.rolling(200).mean()
    # Reindex to daily and forward-fill so every trading day has a value
    daily_ma200w = weekly_ma200.reindex(daily_df.index, method="ffill")
    daily_ma200w.name = "MA200W"
    return daily_ma200w


def compute_fibonacci(df: pd.DataFrame) -> dict[str, float]:
    """Fibonacci retracement on the 200-session range visible in the data."""
    window = df.tail(200)
    high = window["Close"].max()
    low  = window["Close"].min()
    diff = high - low
    return {f"{int(lvl * 100)}%": high - diff * lvl for lvl in FIB_LEVELS}


def signal_score(row: pd.Series, prev_row: pd.Series) -> tuple[int, list[str]]:
    """
    Returns (score, reasons).
    score:  +2 strong buy · +1 buy · 0 neutral · -1 sell · -2 strong sell
    """
    reasons: list[str] = []
    score = 0
    price = row["Close"]

    # ── 1. Price vs each MA ────────────────────────────────────────────────
    above_count = sum(1 for p in MA_PERIODS if price > row.get(f"MA{p}", np.nan))
    below_count = len(MA_PERIODS) - above_count

    if above_count == 5:
        score += 2
        reasons.append("Price above ALL moving averages (5/20/50/100/200) — bullish alignment")
    elif above_count >= 3:
        score += 1
        reasons.append(f"Price above {above_count}/5 moving averages")
    elif below_count == 5:
        score -= 2
        reasons.append("Price below ALL moving averages (5/20/50/100/200) — bearish alignment")
    elif below_count >= 3:
        score -= 1
        reasons.append(f"Price below {below_count}/5 moving averages")

    # ── 2. Golden / Death Cross (MA50 vs MA200) ───────────────────────────
    ma50_now  = row.get("MA50",  np.nan)
    ma200_now = row.get("MA200", np.nan)
    ma50_prev  = prev_row.get("MA50",  np.nan)
    ma200_prev = prev_row.get("MA200", np.nan)

    if all(not np.isnan(v) for v in [ma50_now, ma200_now, ma50_prev, ma200_prev]):
        if ma50_prev <= ma200_prev and ma50_now > ma200_now:
            score += 2
            reasons.append("Golden Cross detected (MA50 crossed above MA200) — strong bullish signal")
        elif ma50_prev >= ma200_prev and ma50_now < ma200_now:
            score -= 2
            reasons.append("Death Cross detected (MA50 crossed below MA200) — strong bearish signal")
        elif ma50_now > ma200_now:
            score += 1
            reasons.append("MA50 above MA200 — bullish trend")
        else:
            score -= 1
            reasons.append("MA50 below MA200 — bearish trend")

    # ── 3. Short-term momentum: MA5 vs MA20 ───────────────────────────────
    ma5_now  = row.get("MA5",  np.nan)
    ma20_now = row.get("MA20", np.nan)
    if not np.isnan(ma5_now) and not np.isnan(ma20_now):
        if ma5_now > ma20_now:
            score += 1
            reasons.append("MA5 above MA20 — short-term momentum positive")
        else:
            score -= 1
            reasons.append("MA5 below MA20 — short-term momentum negative")

    # ── 4. Long-term weekly trend: price vs MA200W ────────────────────────
    ma200w = row.get("MA200W", np.nan)
    if not np.isnan(ma200w):
        if price > ma200w:
            score += 2
            reasons.append("Price above 200-week MA — long-term secular uptrend")
        else:
            score -= 2
            reasons.append("Price below 200-week MA — long-term secular downtrend")

    return score, reasons


def overall_signal(score: int) -> tuple[str, str]:
    """Maps score → (label, css_color)."""
    if score >= 4:
        return "STRONG BUY",  "#16A34A"
    elif score >= 2:
        return "BUY",         "#22C55E"
    elif score >= 0:
        return "NEUTRAL",     "#EAB308"
    elif score >= -2:
        return "SELL",        "#F97316"
    else:
        return "STRONG SELL", "#DC2626"


# ── Chart builder ─────────────────────────────────────────────────────────────

def find_crosses(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """
    Returns (golden_cross_dates, death_cross_dates) within df.
    A golden cross occurs when MA50 crosses above MA200 (prev below, now above).
    A death cross occurs when MA50 crosses below MA200 (prev above, now below).
    """
    ma50  = df["MA50"].dropna()
    ma200 = df["MA200"].dropna()
    common = ma50.index.intersection(ma200.index)
    if len(common) < 2:
        return pd.DatetimeIndex([]), pd.DatetimeIndex([])

    diff = (ma50[common] - ma200[common])          # positive = MA50 above MA200
    sign = diff.apply(lambda x: 1 if x > 0 else -1)
    sign_shift = sign.shift(1)

    golden = common[( sign == 1) & (sign_shift == -1)]
    death  = common[( sign == -1) & (sign_shift ==  1)]
    return golden, death


def build_chart(df: pd.DataFrame, fib_levels: dict, ticker: str, show_vol: bool, show_fib: bool) -> go.Figure:
    rows = 2 if show_vol else 1
    row_heights = [0.7, 0.3] if show_vol else [1.0]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=ticker, increasing_line_color="#22C55E", decreasing_line_color="#EF4444",
    ), row=1, col=1)

    # Moving averages (daily)
    for p in MA_PERIODS:
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=f"MA{p}", line=dict(color=MA_COLORS[p], width=1.5),
                hovertemplate=f"MA{p}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # 200-week MA (weekly, forward-filled to daily)
    if "MA200W" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA200W"],
            name="MA200W", line=dict(color=MA200W_COLOR, width=2.5, dash="dash"),
            hovertemplate="MA200W: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Golden / Death cross markers
    golden_dates, death_dates = find_crosses(df)

    if len(golden_dates):
        fig.add_trace(go.Scatter(
            x=golden_dates,
            y=df.loc[golden_dates, "MA50"],
            mode="markers+text",
            name="Golden Cross",
            marker=dict(symbol="triangle-up", size=16, color="#FFD700",
                        line=dict(color="#B8860B", width=1)),
            text=["Golden Cross"] * len(golden_dates),
            textposition="top center",
            textfont=dict(color="#FFD700", size=10),
            hovertemplate="Golden Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if len(death_dates):
        fig.add_trace(go.Scatter(
            x=death_dates,
            y=df.loc[death_dates, "MA50"],
            mode="markers+text",
            name="Death Cross",
            marker=dict(symbol="triangle-down", size=16, color="#FF4444",
                        line=dict(color="#8B0000", width=1)),
            text=["Death Cross"] * len(death_dates),
            textposition="bottom center",
            textfont=dict(color="#FF4444", size=10),
            hovertemplate="Death Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Fibonacci retracement lines
    if show_fib:
        for (label, price), color in zip(fib_levels.items(), FIB_COLORS):
            fig.add_hline(
                y=price, line_dash="dot", line_color=color, line_width=1,
                annotation_text=f"Fib {label}  ${price:.2f}",
                annotation_position="right",
                annotation_font_size=10,
                row=1, col=1,
            )

    # Volume bars
    if show_vol:
        colors = ["#22C55E" if c >= o else "#EF4444"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"], name="Volume",
            marker_color=colors, showlegend=False,
        ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=700,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=40, r=120, t=40, b=40),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    if show_vol:
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


# ── Main flow ─────────────────────────────────────────────────────────────────

if analyze_btn or ticker:
    if not ticker:
        st.warning("Enter a ticker symbol in the sidebar.")
        st.stop()

    with st.spinner(f"Fetching data for **{ticker}**…"):
        end_date   = datetime.today()
        # Need ~200 weeks (~1400 days) warmup for MA200W plus display period
        start_date = end_date - timedelta(days=period_days + 1450)
        try:
            raw = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"),
                              end=end_date.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        except Exception as e:
            st.error(f"Failed to download data: {e}")
            st.stop()

    if raw.empty:
        st.error(f"No data found for **{ticker}**. Check the ticker symbol and try again.")
        st.stop()

    # Flatten multi-level columns yfinance ≥0.2 may return
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Drop rows where Close is NaN (can happen with invalid/delisted tickers)
    raw = raw.dropna(subset=["Close"])
    if len(raw) < 2:
        st.error(f"**{ticker}** returned insufficient price data. "
                 "It may be an invalid ticker, delisted, or too new. "
                 "Use the company search above to find the correct symbol.")
        st.stop()

    df = compute_mas(raw)
    # Compute 200-week MA on full history, then attach to daily df
    df["MA200W"] = compute_weekly_ma200(df)
    # Trim to requested period for display (warmup rows hidden)
    display_df = df.tail(period_days).copy()

    if len(display_df) < 2:
        st.error(f"Not enough data in the selected period for **{ticker}**. "
                 "Try a longer historical period.")
        st.stop()

    fib = compute_fibonacci(display_df)

    # Signal on the latest row
    latest      = display_df.iloc[-1]
    prev        = display_df.iloc[-2]
    score, why  = signal_score(latest, prev)
    label, color = overall_signal(score)

    # ── KPI row ───────────────────────────────────────────────────────────
    info = yf.Ticker(ticker).fast_info
    company_name = ticker
    try:
        company_name = yf.Ticker(ticker).info.get("longName", ticker)
    except Exception:
        pass

    st.subheader(f"{company_name}  ({ticker})")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    price_now  = float(latest["Close"])
    price_prev = float(prev["Close"])
    change_pct = (price_now - price_prev) / price_prev * 100

    k1.metric("Last Close",    f"${price_now:.2f}", f"{change_pct:+.2f}%")
    k2.metric("MA 5",          f"${latest['MA5']:.2f}"    if not np.isnan(latest['MA5'])    else "N/A")
    k3.metric("MA 20",         f"${latest['MA20']:.2f}"   if not np.isnan(latest['MA20'])   else "N/A")
    k4.metric("MA 50",         f"${latest['MA50']:.2f}"   if not np.isnan(latest['MA50'])   else "N/A")
    k5.metric("MA 200",        f"${latest['MA200']:.2f}"  if not np.isnan(latest['MA200'])  else "N/A")
    k6.metric("MA 200W",       f"${latest['MA200W']:.2f}" if not np.isnan(latest['MA200W']) else "N/A")

    # ── Signal banner ─────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background:{color}22;
            border:2px solid {color};
            border-radius:12px;
            padding:20px 28px;
            margin:16px 0;
        ">
            <span style="font-size:2rem;font-weight:800;color:{color};">{label}</span>
            <span style="font-size:1rem;color:#94A3B8;margin-left:16px;">
                Signal Score: {score:+d}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Reasoning ─────────────────────────────────────────────────────────
    with st.expander("Signal Reasoning", expanded=True):
        for r in why:
            icon = "✅" if "bullish" in r.lower() or "above" in r.lower() or "golden" in r.lower() else "🔴"
            st.markdown(f"- {icon} {r}")

    # ── Chart ─────────────────────────────────────────────────────────────
    fig = build_chart(display_df, fib, ticker, show_volume, show_fibonacci)
    st.plotly_chart(fig, use_container_width=True)

    # ── Fibonacci table ───────────────────────────────────────────────────
    if show_fibonacci:
        st.markdown("#### Fibonacci Retracement Levels (200-session range)")
        fib_df = pd.DataFrame([
            {"Level": k, "Price": f"${v:.2f}",
             "vs Last Close": f"{(v - price_now) / price_now * 100:+.2f}%"}
            for k, v in fib.items()
        ])
        st.dataframe(fib_df, use_container_width=True, hide_index=True)

    # ── MA summary table ──────────────────────────────────────────────────
    st.markdown("#### Moving Average Summary")
    ma_rows = []
    for p in MA_PERIODS:
        val = latest.get(f"MA{p}", np.nan)
        if np.isnan(val):
            continue
        diff_pct = (price_now - val) / val * 100
        stance = "Above" if price_now > val else "Below"
        ma_rows.append({
            "MA Period": f"MA {p} (daily)",
            "Value": f"${val:.2f}",
            "Price vs MA": f"{diff_pct:+.2f}%",
            "Stance": stance,
        })
    # 200-week MA row
    val_w = latest.get("MA200W", np.nan)
    if not np.isnan(val_w):
        diff_pct_w = (price_now - val_w) / val_w * 100
        ma_rows.append({
            "MA Period": "MA 200 (weekly)",
            "Value": f"${val_w:.2f}",
            "Price vs MA": f"{diff_pct_w:+.2f}%",
            "Stance": "Above" if price_now > val_w else "Below",
        })
    ma_df = pd.DataFrame(ma_rows)
    st.dataframe(ma_df, use_container_width=True, hide_index=True)

else:
    st.info("Enter a ticker in the sidebar and click **Analyze**.")
