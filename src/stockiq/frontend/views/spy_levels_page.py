"""Standalone SPY Key Levels page — shareable URL at /spy-levels."""

import streamlit as st

from stockiq.backend.services.spy_service import get_spy_quote
from stockiq.frontend.views.panels.spy_chart import _levels_table_html, compute_spy_levels


def render_spy_levels_page() -> None:
    st.title("📐 SPY Key Levels")
    st.caption(
        "All key intraday levels in one place — VWAP bands · Options walls · "
        "Pivot · Opening Range · EMA 21 · Prev Close"
    )

    with st.expander("How to read this table", expanded=False):
        st.markdown("""
**Level** — the indicator name with a colour-coded dot matching the chart overlay.

**Price** — exact price of the level.

**Dist** — distance from current price: % on top, $ amount below.
Green = level is above current price · Red = level is below.

**Type** — which overlay the level belongs to: Options, VWAP, Technical, OR, Trend.

**Role** — what the level *means* for price action:
| Role | Meaning |
|---|---|
| Resistance | Price may stall or reverse down here |
| Support | Price may bounce up from here |
| Target | Neutral magnet — options max-pain gravity |
| Bound | Expected-move edge — breakout trigger |
| Breakout / Breakdown | Opening range edge — momentum signal |
| Overbought / Oversold | VWAP extension — mean-reversion signal |
| Mean Rev | VWAP itself — intraday fair value |
| Trend | EMA 21 daily anchor |
| Pivot | Classic floor-trader pivot point |
| Reference | Prev close — overnight gap reference |

> **Nearest above / below bar** shows the closest levels bracketing current price.
""")

    # ── Fetch + compute ───────────────────────────────────────────────────────
    with st.spinner("Fetching live SPY data…"):
        quote  = get_spy_quote()
        levels = compute_spy_levels(quote)

    price = quote.get("price") or 0
    if not price:
        st.error("Could not fetch SPY price. Try again shortly.")
        return

    # ── Price metric strip ────────────────────────────────────────────────────
    prev  = quote.get("prev_close") or price
    chg   = price - prev
    chg_p = chg / prev * 100 if prev else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("SPY Price",    f"${price:,.2f}", f"{chg:+.2f} ({chg_p:+.2f}%)")
    m2.metric("Day High",     f"${quote.get('day_high') or 0:,.2f}")
    m3.metric("Day Low",      f"${quote.get('day_low')  or 0:,.2f}")
    m4.metric("Prev Close",   f"${prev:,.2f}")

    st.markdown("---")

    # ── Levels table ──────────────────────────────────────────────────────────
    _table = _levels_table_html(current_price=price, **levels)
    if _table:
        st.html(_table)
    else:
        st.info("No levels available right now — data may still be loading.")

    # ── Share / refresh strip ─────────────────────────────────────────────────
    st.markdown("---")
    c1, c2 = st.columns([3, 1])
    with c1:
        st.caption(
            "Bookmark or share this page: **`/spy-levels`** — "
            "levels are computed fresh on every load."
        )
    with c2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


render_spy_levels_page()
