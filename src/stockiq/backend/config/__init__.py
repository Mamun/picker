"""
Backend configuration — loaded from src/stockiq/backend/config/*.yml.

Exports all constants the backend needs to run independently:
  CACHE_TTL             — per-function cache TTL values (seconds)
  MA_PERIODS            — moving-average window sizes used in calculations
  FIB_LEVELS            — Fibonacci retracement levels used in calculations
  SPX_TICKERS           — S&P 500 ticker universe for scanners
  NASDAQ_100_TICKERS    — NASDAQ-100 ticker universe
  SCREENER_TICKER_COUNT — how many SPX tickers to scan (env-overridable)
"""

import os
from pathlib import Path

import yaml

_dir = Path(__file__).parent

# ── Cache TTLs ─────────────────────────────────────────────────────────────────
with open(_dir / "cache.yml") as _f:
    _cache_raw: dict = yaml.safe_load(_f)

CACHE_TTL: dict[str, int] = {
    fn: ttl
    for section in _cache_raw.values()
    for fn, ttl in section.items()
}

# ── App config ─────────────────────────────────────────────────────────────────
with open(_dir / "app.yml") as _f:
    _app: dict = yaml.safe_load(_f)

MA_PERIODS: list[int] = _app["moving_averages"]["periods"]

FIB_LEVELS: list[float] = _app["fibonacci"]["levels"]

_screener = _app["screener"]
SCREENER_TICKER_COUNT: int = int(
    os.environ.get("SCREENER_TICKER_COUNT", _screener["default_count"])
)
SPX_TICKERS: list[str] = _screener["universe"][:SCREENER_TICKER_COUNT]

NASDAQ_100_TICKERS: list[str] = _app["nasdaq_100"]
