"""Bounce radar screener — SPX stocks near their 200-day MA."""

from ._shared import (
    ttl_cache, CACHE_TTL, SPX_TICKERS,
    np, pd, datetime, timedelta,
    get_metadata, _batch_download, _rsi_last,
)


@ttl_cache(CACHE_TTL["fetch_spx_bounce_radar_scan"])
def fetch_spx_bounce_radar_scan(threshold_pct: float = 5.0, top_n: int = 30) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for stocks within ±threshold_pct of their 200-day MA.
    Bounce score rewards: proximity to MA200 + oversold RSI + below-MA200 support.
    Returns top_n rows sorted by bounce score descending.

    Uses a single batch OHLC download (no per-ticker calls) + GCS metadata for names.
    """
    results  = []
    gcs_meta = get_metadata()

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=320)

    raw = _batch_download(
        SPX_TICKERS,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )
    if raw.empty:
        return pd.DataFrame()

    def _get_ticker_df(ticker: str) -> pd.DataFrame:
        try:
            df = raw[ticker].copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna(subset=["Close"])
        except Exception:
            return pd.DataFrame()

    for ticker in SPX_TICKERS:
        try:
            df = _get_ticker_df(ticker)
            if df.empty or len(df) < 201:
                continue

            price = float(df["Close"].iloc[-1])
            ma200 = float(df["Close"].rolling(200).mean().iloc[-1])
            ma50  = float(df["Close"].rolling(50).mean().iloc[-1])

            if np.isnan(ma200):
                continue

            dist_pct = (price - ma200) / ma200 * 100
            if abs(dist_pct) > threshold_pct:
                continue

            rsi   = _rsi_last(df)
            trend = "📈 Uptrend" if ma50 > ma200 else "📉 Downtrend"

            proximity_bonus = (threshold_pct - abs(dist_pct)) * 2
            oversold_bonus  = max(0, 50 - rsi)
            support_bonus   = 8 if dist_pct < 0 else 0
            bounce_score    = proximity_bonus + oversold_bonus + support_bonus

            if rsi <= 30:
                rsi_label = "🟢 Oversold"
            elif rsi >= 70:
                rsi_label = "🔴 Overbought"
            else:
                rsi_label = "⚪ Neutral"

            meta         = gcs_meta.get(ticker)
            company_name = meta["name"] if meta else ticker

            results.append({
                "Ticker":       ticker,
                "Company":      company_name,
                "Price":        round(price, 2),
                "MA 200":       round(ma200, 2),
                "Distance %":   round(dist_pct, 2),
                "RSI":          round(rsi, 1),
                "RSI Zone":     rsi_label,
                "Trend":        trend,
                "Bounce Score": round(bounce_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Bounce Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
