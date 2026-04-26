"""SPY Dashboard page — thin orchestrator that composes panels."""

import urllib.parse

import streamlit as st

from stockiq.backend.services.market_service import get_market_overview
from stockiq.backend.services.spy_service import (
    get_put_call_ratio,
    get_spy_chart_df,
    get_spy_gap_table_data,
    get_spy_quote,
)
from stockiq.frontend.views.components.gap_table import render_gap_table
from stockiq.frontend.views.components.summary_card import render_spy_summary_card
from stockiq.frontend.views.panels.ai_forecast import render_ai_forecast
from stockiq.frontend.views.panels.dte_conditions import render_dte_conditions
from stockiq.frontend.views.panels.options_intelligence import render_options_intelligence
from stockiq.frontend.views.panels.spy_chart import render_spy_chart_section
from stockiq.frontend.views.panels.spy_header import render_spy_header


def render_spy_dashboard_tab() -> None:
    quote = get_spy_quote()
    if not quote:
        st.error("Could not load SPY data. Please try again in a moment.")
        return

    overview = get_market_overview()
    gap_data = get_spy_gap_table_data()

    render_spy_header(quote, overview["indices"])

    # Fetch RSI + P/C once so they can be shared across the summary card,
    # the 0DTE meter, and the chart section without duplicate network calls.
    rsi = _fetch_daily_rsi()
    pc  = _fetch_pc_ratio()

    render_spy_summary_card(
        quote, quote["price"], quote["change"], quote["change_pct"],
        gap_data["daily_df"],
        rsi=rsi,
        vix_snapshot=overview["vix"],
        pc_data=pc,
    )

    st.divider()
    render_spy_chart_section(quote)

    st.divider()
    render_dte_conditions(quote["price"], overview["vix"], rsi, pc)

    st.divider()
    render_options_intelligence(quote["price"])

    st.divider()
    ai_slot = st.empty()

    st.divider()
    _render_gap_section(gap_data)

    try:
        with ai_slot.container():
            render_ai_forecast(gap_data["gaps_df"], gap_data["quote"])
    except Exception:
        pass


# ── Private helpers ────────────────────────────────────────────────────────────

def _fetch_daily_rsi() -> float | None:
    try:
        df = get_spy_chart_df(period="1y", interval="1d")
        if not df.empty and "RSI" in df.columns:
            series = df["RSI"].dropna()
            if not series.empty:
                return float(series.iloc[-1])
    except Exception:
        pass
    return None


def _fetch_pc_ratio() -> dict | None:
    try:
        return get_put_call_ratio(scope="daily")
    except Exception:
        return None


def _render_gap_section(gap_data: dict) -> None:
    gaps_df = gap_data["gaps_df"]
    try:
        parsed    = urllib.parse.urlparse(st.context.url)
        share_url = f"{parsed.scheme}://{parsed.netloc}/spy-gaps"
    except Exception:
        share_url = "/spy-gaps"

    render_gap_table(
        gaps_df,
        title="Daily Gaps (Last 30 Days)",
        show_rsi=True,
        show_next_day=True,
        share_url=share_url,
    )


render_spy_dashboard_tab()
