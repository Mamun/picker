"""LLM prompt templates and JSON output parser for SPY forecasts."""

import json


_SYSTEM = (
    "You are a quantitative SPY (S&P 500 ETF) analyst producing short-term price forecasts. "

    # ── Signal weights (highest → lowest influence) ──────────────────────────
    "Apply signals in this priority order: "
    "(1) Expected Move — expected_move covers expected_move_dte calendar days (1-sigma, ~68% probability). "
    "Scale it to a daily sigma using σ_day = expected_move / √expected_move_dte. "
    "For day N of the forecast, set range = ±(σ_day × √N) around est_close. "
    "If expected_move or expected_move_dte is null, fall back to VIX-implied volatility for range sizing. "
    "(2) GEX regime — positive total_gex_b: dealers long gamma, moves self-damp (mean-revert); "
    "negative total_gex_b: dealers short gamma, moves can accelerate (trend). "
    "Use gex_peak_support as a key support/resistance level. "
    "When total_gex_b < -2.0, widen all ranges further and cap confidence at Medium. "
    "(3) VIX regime and 5-day trend — rising VIX compresses rallies; "
    "Elevated or Extreme Fear → bearish lean, Low or Medium confidence, wider ranges. "
    "(4) Price vs MA200 — primary bull/bear regime separator; below MA200 = structurally bearish. "
    "(5) Price vs MA50 / MA20 — short-term momentum and mean-reversion zones. "
    "(6) Gap magnetism — unfilled gaps act as price magnets; factor into est_close targets. "
    "(7) RSI — overbought ≥ 70 = elevated reversal risk; oversold ≤ 30 = bounce potential. "
    "(8) Put/Call ratio — above 1.0 = excess put hedging = contrarian bullish; "
    "below 0.7 = complacency = contrarian bearish. "
    "(9) Volume — high volume on a directional day adds conviction to that direction. "

    # ── Hard constraints ─────────────────────────────────────────────────────
    "Range width must strictly widen with each successive day. "
    "Do not invent macro events. Reason only from the data provided. "
    "Output must be a valid JSON array — no markdown, no explanation, nothing else."
)

_USER_TMPL = """\
SPY market data — gap history (last 15 days), live quote, technicals, VIX, and options flow:

{context_json}

Apply your signal weights from the system instructions. Produce a 10-trading-day forecast anchored to spy_live_price.

Output rules:
- Day 1 = today. Day 2 = next trading day — skip weekends and US market holidays.
- Return ONLY a JSON array of exactly 10 objects with these keys:
  "date"       : "YYYY-MM-DD"
  "direction"  : "Bullish" | "Bearish" | "Neutral"
  "est_close"  : number (estimated EOD close, 2 decimal places)
  "range_low"  : number (intraday low estimate, 2 decimal places)
  "range_high" : number (intraday high estimate, 2 decimal places)
  "confidence" : "High" | "Medium" | "Low"
  "reason"     : string (one sentence, max 12 words, cite the dominant signal)
"""


def _parse_json(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
