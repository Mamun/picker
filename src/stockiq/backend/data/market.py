"""Market-wide data fetchers — indices, VIX."""

import logging

import pandas as pd
import yfinance as yf

from stockiq.backend.cache import ttl_cache
from stockiq.backend.config import CACHE_TTL

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


@ttl_cache(CACHE_TTL["fetch_vix_ohlc"])
def fetch_vix_ohlc(period: str = "1y") -> pd.DataFrame:
    """Daily VIX OHLC history (Open, High, Low, Close) for gap analysis. Cached 1 hour."""
    try:
        df = yf.download("^VIX", period=period, interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        cols = ["Open", "High", "Low", "Close"] + (["Volume"] if "Volume" in df.columns else [])
        return df[cols].dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@ttl_cache(CACHE_TTL["fetch_vix_history"])
def fetch_vix_history(period: str = "1y") -> pd.DataFrame:
    """
    Daily VIX close alongside SPY close for dual-axis comparison.
    Returns DataFrame with columns: Date (index), SPY, VIX. Cached 1 hour.
    """
    try:
        raw = yf.download(["SPY", "^VIX"], period=period, interval="1d", progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw[["Close"]].copy()
        close.columns = [c.replace("^VIX", "VIX") for c in close.columns]
        return close.dropna()
    except Exception:
        return pd.DataFrame()


@ttl_cache(CACHE_TTL["fetch_index_snapshot"])
def fetch_index_snapshot() -> pd.DataFrame:
    """
    Day-change snapshot for major indices used in the SPX dashboard. Cached 120 s.

    Strategy:
      1. Try fast_info for each ticker — gives live intraday prices when US market is open.
      2. For any ticker that returns None/0, fall back to a single batch OHLCV download
         so the landing page always shows the last known session close — never empty.
    """
    _SYMBOLS = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq",
        "^DJI":  "Dow Jones",
        "^RUT":  "Russell 2000",
        "SPY":   "SPY",
        "QQQ":   "QQQ",
        "^VIX":  "VIX",
    }

    prices: dict[str, tuple[float, float]] = {}

    needs_fallback = []
    for sym in _SYMBOLS:
        try:
            fi    = yf.Ticker(sym).fast_info
            price = float(fi.last_price or 0)
            prev  = float(fi.previous_close or 0)
            if price > 0 and prev > 0:
                prices[sym] = (price, prev)
            else:
                needs_fallback.append(sym)
        except Exception:
            needs_fallback.append(sym)

    if needs_fallback:
        try:
            hist = yf.download(needs_fallback, period="5d", interval="1d", progress=False, auto_adjust=False)
            if isinstance(hist.columns, pd.MultiIndex):
                closes = hist["Close"]
            else:
                closes = hist[["Close"]].rename(columns={"Close": needs_fallback[0]})
            closes = closes.dropna(how="all")
            for sym in needs_fallback:
                try:
                    col = closes[sym].dropna()
                    if len(col) >= 2:
                        prices[sym] = (float(col.iloc[-1]), float(col.iloc[-2]))
                except Exception:
                    continue
        except Exception:
            pass

    rows = []
    for sym, name in _SYMBOLS.items():
        if sym not in prices:
            continue
        price, prev = prices[sym]
        chg = price - prev
        rows.append({
            "Index":    name,
            "Symbol":   sym,
            "Price":    round(price, 2),
            "Change":   round(chg, 2),
            "Change %": round(chg / prev * 100, 2),
        })
    return pd.DataFrame(rows)
