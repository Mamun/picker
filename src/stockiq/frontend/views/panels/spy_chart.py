"""SPY chart panel: period selector, VWAP + key-level computation, chart render."""

import pandas as pd
import streamlit as st

from stockiq.backend.services.spy_service import get_spy_chart_df, get_spy_options_analysis
from stockiq.frontend.views.components.spy_charts import spy_candle_chart


def render_spy_chart_section(quote: dict) -> None:
    period_map = {
        "Today": ("1d",  "5m",  [],            True),
        "5D":    ("5d",  "30m", [],            True),
        "1M":    ("1mo", "1d",  [20],          False),
        "3M":    ("3mo", "1d",  [20, 50],      False),
        "6M":    ("6mo", "1d",  [20, 50, 200], False),
        "1Y":    ("1y",  "1d",  [20, 50, 200], False),
    }
    keys = list(period_map)
    _qp  = st.query_params.get("period", "1Y")
    default_idx = keys.index(_qp) if _qp in keys else 5

    period_col, rsi_col = st.columns([6, 1])
    with period_col:
        choice = st.radio("Period", keys, horizontal=True, key="spy_period", index=default_idx)
    show_rsi = rsi_col.checkbox("RSI", value=True)
    st.query_params["period"] = choice

    yf_period, interval, mas, show_prev = period_map[choice]
    chart_df = get_spy_chart_df(period=yf_period, interval=interval)
    if chart_df.empty:
        st.info("Chart data unavailable — the market may be closed or data is delayed.")
        return

    prev_close_line = quote["prev_close"] if show_prev else None

    vwap = vwap_u1 = vwap_l1 = vwap_u2 = vwap_l2 = None
    if choice == "Today" and "Volume" in chart_df.columns and not chart_df["Volume"].isna().all():
        vwap, vwap_u1, vwap_l1, vwap_u2, vwap_l2 = _compute_vwap_bands(chart_df)

    pdh = pdl = pivot = r1 = s1 = None
    if choice in ("Today", "5D"):
        pdh, pdl, pivot, r1, s1 = _compute_pivot_levels()

    or_high = or_low = None
    if choice == "Today" and len(chart_df) >= 4:
        _or = chart_df.head(6)
        or_high = float(_or["High"].max())
        or_low  = float(_or["Low"].min())

    max_pain = call_wall = put_wall = None
    if not show_prev:
        try:
            seed = get_spy_options_analysis(expiration="", current_price=quote["price"])
            if seed:
                max_pain = seed["max_pain"]
                oi_df    = seed["oi_df"]
                if not oi_df.empty:
                    call_wall = float(oi_df.loc[oi_df["call_oi"].idxmax(), "strike"])
                    put_wall  = float(oi_df.loc[oi_df["put_oi"].idxmax(), "strike"])
        except Exception:
            pass

    st.plotly_chart(
        spy_candle_chart(
            chart_df, mas, prev_close_line, show_rsi=show_rsi,
            vwap=vwap, max_pain=max_pain,
            call_wall=call_wall, put_wall=put_wall,
            or_high=or_high, or_low=or_low,
            pdh=pdh, pdl=pdl, pivot=pivot, r1=r1, s1=s1,
            vwap_u1=vwap_u1, vwap_l1=vwap_l1,
            vwap_u2=vwap_u2, vwap_l2=vwap_l2,
        ),
        width="stretch",
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _compute_vwap_bands(df: pd.DataFrame):
    tp     = (df["High"] + df["Low"] + df["Close"]) / 3
    cumvol = df["Volume"].cumsum()
    vwap   = (tp * df["Volume"]).cumsum() / cumvol.replace(0, float("nan"))
    tp_dev_sq = ((tp - vwap) ** 2 * df["Volume"]).cumsum()
    vwap_std  = (tp_dev_sq / cumvol.replace(0, float("nan"))).pow(0.5)
    return (
        vwap,
        vwap + vwap_std,     vwap - vwap_std,
        vwap + 2 * vwap_std, vwap - 2 * vwap_std,
    )


def _compute_pivot_levels():
    try:
        daily = get_spy_chart_df(period="5d", interval="1d")
        if len(daily) >= 2:
            pd_row = daily.iloc[-2]
            pdh    = float(pd_row["High"])
            pdl    = float(pd_row["Low"])
            pdc    = float(pd_row["Close"])
            pivot  = (pdh + pdl + pdc) / 3
            return pdh, pdl, pivot, 2 * pivot - pdl, 2 * pivot - pdh
    except Exception:
        pass
    return None, None, None, None, None
