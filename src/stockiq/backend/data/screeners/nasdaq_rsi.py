"""NASDAQ-100 RSI screener — RSI, moving averages, trend, and volume ratio."""

from ._shared import (
    ttl_cache, CACHE_TTL, NASDAQ_100_TICKERS,
    pd, datetime, timedelta, compute_rsi,
    _batch_download,
)


@ttl_cache(CACHE_TTL["fetch_nasdaq_rsi_scan"])
def fetch_nasdaq_rsi_scan() -> pd.DataFrame:
    """
    Scan all NASDAQ-100 stocks in a single batch download.
    Returns every stock with RSI, moving averages, trend, day change,
    volume ratio, and overbought/oversold status.
    """
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=300)
    tickers    = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    raw = _batch_download(
        tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        return pd.DataFrame()

    try:
        is_multi  = isinstance(raw.columns, pd.MultiIndex)
        close_df  = raw["Close"]  if is_multi else raw
        volume_df = raw["Volume"] if is_multi else None
    except Exception:
        return pd.DataFrame()

    results = []
    for ticker in NASDAQ_100_TICKERS:
        try:
            if not isinstance(ticker, str) or ticker not in close_df.columns:
                continue
            closes = close_df[ticker].dropna()
            if len(closes) < 15:
                continue

            price = float(closes.iloc[-1])
            rsi   = float(compute_rsi(closes.to_frame("Close")).iloc[-1])

            ma50  = float(closes.iloc[-50:].mean())  if len(closes) >= 50  else None
            ma200 = float(closes.iloc[-200:].mean()) if len(closes) >= 200 else None

            pct_ma50  = round((price - ma50)  / ma50  * 100, 1) if ma50  else None
            pct_ma200 = round((price - ma200) / ma200 * 100, 1) if ma200 else None

            day_chg = round((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2) \
                      if len(closes) >= 2 else None

            if ma50 and ma200:
                trend = "📈 Uptrend" if ma50 > ma200 else "📉 Downtrend"
            else:
                trend = "—"

            vol_ratio = None
            if volume_df is not None and ticker in volume_df.columns:
                vols = volume_df[ticker].dropna()
                if len(vols) >= 21:
                    avg_vol   = float(vols.iloc[-21:-1].mean())
                    today_vol = float(vols.iloc[-1])
                    vol_ratio = round(today_vol / avg_vol, 2) if avg_vol > 0 else None

            if rsi >= 70:
                status = "🔴 Overbought"
            elif rsi <= 30:
                status = "🟢 Oversold"
            else:
                status = "⚪ Neutral"

            results.append({
                "Ticker":     ticker,
                "Price":      round(price, 2),
                "Day Chg %":  day_chg,
                "RSI":        round(rsi, 1),
                "% vs MA50":  pct_ma50,
                "% vs MA200": pct_ma200,
                "Trend":      trend,
                "Vol Ratio":  vol_ratio,
                "Status":     status,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("RSI", ascending=False)
        .reset_index(drop=True)
    )
