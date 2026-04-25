"""Single-stock analysis service."""

import pandas as pd

from stockiq.backend.data.yf_fetch import fetch_ohlcv, get_company_name, search_companies
from stockiq.backend.models.indicators import (
    compute_buying_pressure,
    compute_daily_gaps,
    compute_fibonacci,
    compute_mas,
    compute_rsi,
    compute_weekly_ma200,
    detect_reversal_patterns,
    patch_today_gap,
)
from stockiq.backend.models.signals import find_crosses, overall_signal, signal_score


def search_stocks(query: str) -> list[dict]:
    """Yahoo Finance company search. Returns list of {symbol, name, exchange, type}."""
    return search_companies(query)


def get_stock_df(ticker: str) -> pd.DataFrame:
    """
    5-year OHLCV with all indicators pre-computed (MAs, weekly MA200, RSI, patterns).
    Raises on fetch failure; returns empty DataFrame if no data.
    """
    raw = fetch_ohlcv(ticker, 1825)
    if raw.empty:
        return raw
    df = compute_mas(raw)
    df["MA200W"] = compute_weekly_ma200(df)
    df["RSI"]    = compute_rsi(df)
    df           = detect_reversal_patterns(df)
    return df


def get_stock_signal(df: pd.DataFrame) -> dict:
    """
    Compute buy/sell signal from the latest two rows of a pre-computed indicator df.

    Returns:
        {score, label, color, reasons, latest (Series), prev (Series)}
    """
    latest = df.iloc[-1]
    prev   = df.iloc[-2]
    score, reasons = signal_score(latest, prev)
    label, color   = overall_signal(score)
    return {
        "score":   score,
        "label":   label,
        "color":   color,
        "reasons": reasons,
        "latest":  latest,
        "prev":    prev,
    }


def get_stock_fibonacci(df: pd.DataFrame) -> dict:
    """Fibonacci retracement levels for the given OHLCV DataFrame."""
    return compute_fibonacci(df)


def get_stock_gaps(df: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Daily gap history with today's gap patched from a live quote dict."""
    return patch_today_gap(compute_daily_gaps(df), quote)


def get_stock_crosses(df: pd.DataFrame) -> tuple:
    """Golden-cross and death-cross dates for the given indicator DataFrame."""
    return find_crosses(df)


def get_buying_pressure(df: pd.DataFrame, timeframe: str = "monthly") -> dict:
    """BX signal for the given timeframe: 'monthly' | 'weekly' | 'daily'."""
    return compute_buying_pressure(df, timeframe)


def get_company_display_name(ticker: str) -> str:
    """Fetch long company name; falls back to ticker on error."""
    return get_company_name(ticker)


def get_ticker_fundamentals(ticker: str) -> dict:
    """
    Return valuation + analyst data for a single ticker.

    Strategy:
      • SPX tickers (in local cache): served instantly from JSON files.
        Market cap fetched via fast_info (lightweight).
      • All other tickers: one yfinance .info call.
      • Sector median forward P/E computed from the full cache for context.
    """
    import statistics
    import yfinance as yf

    from stockiq.backend.data.cache.screener_analyst import get_analyst_consensus
    from stockiq.backend.data.cache.screener_forward_pe import get_forward_pe
    from stockiq.backend.data.cache.screener_metadata import get_metadata

    fpe_cache     = get_forward_pe()
    analyst_cache = get_analyst_consensus()
    meta_cache    = get_metadata()

    in_cache = ticker in fpe_cache and ticker in analyst_cache

    # Sector median P/E from the full 300-ticker cache (context line in card)
    meta   = meta_cache.get(ticker, {})
    sector = meta.get("sector") if meta else None
    sector_median_pe: float | None = None
    if sector and fpe_cache:
        peers = [
            v["forwardPE"] for t, v in fpe_cache.items()
            if meta_cache.get(t, {}).get("sector") == sector
            and v.get("forwardPE") and v["forwardPE"] > 0
        ]
        if peers:
            sector_median_pe = round(statistics.median(peers), 1)

    if in_cache:
        fpe = fpe_cache[ticker]
        anl = analyst_cache[ticker]
        market_cap = None
        try:
            market_cap = yf.Ticker(ticker).fast_info.market_cap
        except Exception:
            pass
        return {
            "sector":           sector,
            "sector_median_pe": sector_median_pe,
            "market_cap":       market_cap,
            "forward_pe":       fpe.get("forwardPE"),
            "trailing_pe":      fpe.get("trailingPE"),
            "eps_growth":       fpe.get("earningsGrowth"),
            "peg":              fpe.get("pegRatio"),
            "rating":           anl.get("recommendationMean"),
            "num_analysts":     anl.get("numberOfAnalystOpinions"),
            "target_mean":      anl.get("targetMeanPrice"),
            "target_high":      anl.get("targetHighPrice"),
            "target_low":       anl.get("targetLowPrice"),
        }

    # Fallback: full .info for non-SPX tickers
    try:
        info = yf.Ticker(ticker).info
        return {
            "sector":           info.get("sector", sector),
            "sector_median_pe": sector_median_pe,
            "market_cap":       info.get("marketCap"),
            "forward_pe":       info.get("forwardPE"),
            "trailing_pe":      info.get("trailingPE"),
            "eps_growth":       info.get("earningsGrowth"),
            "peg":              info.get("pegRatio"),
            "rating":           info.get("recommendationMean"),
            "num_analysts":     info.get("numberOfAnalystOpinions"),
            "target_mean":      info.get("targetMeanPrice"),
            "target_high":      info.get("targetHighPrice"),
            "target_low":       info.get("targetLowPrice"),
        }
    except Exception:
        return {}
