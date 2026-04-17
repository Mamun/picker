"""
AI forecast model — pure data logic + multi-provider LLM call.

Supported providers:
  - "anthropic"  → Claude (requires ANTHROPIC_API_KEY)
  - "groq"       → Llama 3.3 70B via Groq free tier (requires GROQ_API_KEY)
  - "gemini"     → Gemini 2.0 Flash via Google free tier (requires GOOGLE_API_KEY)
"""

import json
import os
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from stockiq.cache_ttl import CACHE_TTL


# ── Provider metadata ─────────────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {
    "groq": {
        "label":   "Llama 3.3 70B (Groq)",
        "model":   "llama-3.3-70b-versatile",
        "env_var": "GROQ_API_KEY",
        "free":    True,
    },
    "gemini": {
        "label":   "Gemini 2.0 Flash (Google)",
        "model":   "gemini-2.0-flash",
        "env_var": "GOOGLE_API_KEY",
        "free":    True,
    },
    "anthropic": {
        "label":   "Claude (Anthropic)",
        "model":   "claude-opus-4-6",
        "env_var": "ANTHROPIC_API_KEY",
        "free":    False,
    },
}


# ── Secret helper ────────────────────────────────────────────────────────────

def _get_secret(key: str) -> str:
    """Return a secret from os.environ.

    Locally: populated by load_dotenv() in app.py reading .env
    Streamlit Cloud: app.py injects st.secrets into os.environ at startup
    """
    return os.environ.get(key, "")


# ── Market helpers ────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def next_market_open_str() -> str:
    et  = timezone(timedelta(hours=-4))
    now = datetime.now(et)
    days_ahead = 1
    while True:
        candidate = now + timedelta(days=days_ahead)
        if candidate.weekday() < 5:
            break
        days_ahead += 1
    return candidate.strftime("%a %b %-d, 9:30 AM ET")


# ── Context builder ───────────────────────────────────────────────────────────

def build_forecast_context(
    gaps_df: pd.DataFrame,
    quote: dict,
    daily_df: pd.DataFrame | None = None,
    vix_df: pd.DataFrame | None = None,
    pc_data: dict | None = None,
) -> str:
    """Build the JSON context string passed to the AI forecast prompt."""
    completed_gaps = gaps_df.iloc[:-1]
    rows = []
    for dt, row in completed_gaps.tail(15).iterrows():
        rows.append({
            "date":         dt.strftime("%Y-%m-%d"),
            "open":         round(float(row.get("Open", 0)), 2),
            "prev_close":   round(float(row.get("Prev Close", 0)), 2),
            "gap_usd":      round(float(row.get("Gap", 0)), 2),
            "gap_pct":      round(float(row.get("Gap %", 0)), 2),
            "gap_filled":   bool(row.get("Gap Filled", False)),
            "rsi":          round(float(row.get("RSI", 0) or 0), 1),
            "next_day_dir": row.get("Next Day", "—"),
        })

    et      = timezone(timedelta(hours=-4))
    now_et  = datetime.now(et)
    prev_c  = round(quote.get("prev_close", 0), 2)
    day_o   = round(quote.get("day_open",   0), 2)
    today_gap     = round(day_o - prev_c, 2) if day_o and prev_c else 0
    today_gap_pct = round(today_gap / prev_c * 100, 2) if prev_c else 0
    spy_price     = round(quote.get("price", 0), 2)

    context: dict = {
        "today":              now_et.strftime("%Y-%m-%d"),
        "as_of":              now_et.strftime("%Y-%m-%d %H:%M ET"),
        "spy_live_price":     spy_price,
        "spy_prev_close":     prev_c,
        "spy_day_open":       day_o,
        "spy_today_gap_usd":  today_gap,
        "spy_today_gap_pct":  today_gap_pct,
        "spy_day_high":       round(quote.get("day_high", 0), 2),
        "spy_day_low":        round(quote.get("day_low",  0), 2),
        "gap_history":        rows,
    }

    if daily_df is not None and not daily_df.empty and "Close" in daily_df.columns:
        close  = daily_df["Close"].dropna()
        n      = len(close)
        anchor = spy_price or (float(close.iloc[-1]) if n else 0)

        def _ma(p: int) -> float | None:
            return round(float(close.rolling(p).mean().iloc[-1]), 2) if n >= p else None

        def _pct_from(ma_val: float | None) -> float | None:
            if ma_val and anchor:
                return round((anchor - ma_val) / ma_val * 100, 2)
            return None

        ma20, ma50, ma200 = _ma(20), _ma(50), _ma(200)
        context["technicals"] = {
            "ma20":              ma20,
            "pct_from_ma20":     _pct_from(ma20),
            "ma50":              ma50,
            "pct_from_ma50":     _pct_from(ma50),
            "ma200":             ma200,
            "pct_from_ma200":    _pct_from(ma200),
            "above_ma200":       bool(anchor > ma200) if ma200 else None,
            "spy_52w_high":      round(float(close.tail(252).max()), 2),
            "spy_52w_low":       round(float(close.tail(252).min()), 2),
            "pct_from_52w_high": round((anchor / float(close.tail(252).max()) - 1) * 100, 2) if anchor else None,
            "pct_from_52w_low":  round((anchor / float(close.tail(252).min()) - 1) * 100, 2) if anchor else None,
        }

        if "Volume" in daily_df.columns:
            vol       = daily_df["Volume"].dropna()
            avg_vol   = float(vol.rolling(20).mean().iloc[-1]) if len(vol) >= 20 else None
            today_vol = float(vol.iloc[-1]) if len(vol) else None
            context["technicals"]["avg_volume_20d"]        = int(avg_vol) if avg_vol else None
            context["technicals"]["today_volume"]          = int(today_vol) if today_vol else None
            context["technicals"]["volume_vs_20d_avg_pct"] = (
                round((today_vol / avg_vol - 1) * 100, 1) if avg_vol and today_vol else None
            )

    if vix_df is not None and not vix_df.empty and "VIX" in vix_df.columns:
        vix     = vix_df["VIX"].dropna()
        vix_now = float(vix.iloc[-1])
        vix_5d  = float(vix.iloc[-6]) if len(vix) >= 6 else float(vix.iloc[0])
        vix_avg = float(vix.mean())
        if vix_now < 15:
            regime = "Calm"
        elif vix_now < 20:
            regime = "Normal"
        elif vix_now < 30:
            regime = "Elevated"
        else:
            regime = "Extreme Fear"
        context["vix"] = {
            "vix_now":       round(vix_now, 2),
            "vix_regime":    regime,
            "vix_5d_change": round(vix_now - vix_5d, 2),
            "vix_1y_avg":    round(vix_avg, 2),
            "vix_vs_1y_avg": round(vix_now - vix_avg, 2),
        }

    if pc_data:
        context["put_call_ratio"] = {
            "ratio":  pc_data["ratio"],
            "signal": pc_data["signal"],
        }

    return json.dumps(context)


# ── Shared prompt strings ─────────────────────────────────────────────────────

_SYSTEM = (
    "You are a quantitative SPY (S&P 500 ETF) analyst producing short-term price forecasts. "
    "Weight signals in this priority order: "
    "(1) VIX regime and 5-day trend — rising VIX compresses rallies; Extreme Fear widens all ranges; "
    "(2) Price vs MA200 — the primary bull/bear regime separator; below MA200 = structurally bearish; "
    "(3) Price vs MA50 and MA20 — short-term momentum and mean-reversion zones; "
    "(4) RSI — overbought ≥ 70, oversold ≤ 30; "
    "(5) Gap magnetism — unfilled gaps act as price targets; "
    "(6) Volume confirmation — high volume on a directional move adds conviction; "
    "(7) Put/call ratio — above 1.0 = excess put hedging = contrarian bullish; below 0.7 = complacency = contrarian bearish. "
    "In Elevated or Extreme Fear VIX regimes, prefer Low or Medium confidence and widen range_low/range_high. "
    "Do not guess macro events. Reason only from the data provided. "
    "Your output must be a valid JSON array — nothing else, no markdown, no explanation."
)

_USER_TMPL = """\
Given the following SPY market data (last 15 trading days of gap history, live quote, technicals, and VIX):

{context_json}

Produce a 10-trading-day price forecast. Day 1 is today ("today" field). Use spy_live_price as the anchor.

Rules:
- Day 1 = today. Day 2 = next trading day, and so on — skip weekends and US market holidays.
- Unfilled gaps in gap_history act as price magnets; factor them into est_close targets.
- RSI ≥ 70 = overbought risk; RSI ≤ 30 = oversold bounce potential.
- Range width must widen as day number increases (uncertainty grows).
- In vix_regime "Elevated" or "Extreme Fear", apply a bearish lean unless technicals strongly disagree.
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


# ── Provider-specific callers ─────────────────────────────────────────────────

def _call_anthropic(context_json: str, user_key: str = "") -> list[dict]:
    import anthropic
    api_key = user_key or _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    client = anthropic.Anthropic(api_key=api_key)
    raw = client.messages.create(
        model=PROVIDERS["anthropic"]["model"],
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _USER_TMPL.format(context_json=context_json)}],
    )
    text = next((b.text for b in raw.content if b.type == "text"), "")
    return _parse_json(text) if text else []


def _call_groq(context_json: str, user_key: str = "") -> list[dict]:
    from groq import Groq
    api_key = user_key or _get_secret("GROQ_API_KEY")
    if not api_key:
        return []
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=PROVIDERS["groq"]["model"],
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _USER_TMPL.format(context_json=context_json)},
        ],
    )
    text = resp.choices[0].message.content or ""
    return _parse_json(text) if text else []


def _call_gemini(context_json: str, user_key: str = "") -> list[dict]:
    from google import genai
    from google.genai import types
    api_key = user_key or _get_secret("GOOGLE_API_KEY")
    if not api_key:
        return []
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=PROVIDERS["gemini"]["model"],
        contents=_USER_TMPL.format(context_json=context_json),
        config=types.GenerateContentConfig(system_instruction=_SYSTEM, max_output_tokens=4096),
    )
    text = resp.text or ""
    return _parse_json(text) if text else []


# ── Unified cached entry point ────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL["fetch_ai_prediction"], show_spinner=False)
def fetch_ai_prediction(
    cache_key: str,
    _context_json: str,
    provider: str = "groq",
    _user_key: str = "",
) -> list[dict]:
    """Fetch a 10-day SPY forecast from the selected AI provider.

    cache_key  = "YYYY-MM-DD-HH-<provider>" — stable for one hour.
    _context_json and _user_key are excluded from the cache key (leading _)
    so the user's key is never stored in or exposed via the cache.
    """
    callers = {
        "anthropic": _call_anthropic,
        "groq":      _call_groq,
        "gemini":    _call_gemini,
    }
    caller = callers.get(provider)
    if caller is None:
        raise ValueError(f"Unknown provider: {provider!r}")
    return caller(_context_json, user_key=_user_key)
