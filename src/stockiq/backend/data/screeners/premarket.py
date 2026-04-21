"""Pre-market movers screener — NASDAQ-100 pre-market prices and volume."""

from ._shared import (
    ttl_cache, CACHE_TTL, NASDAQ_100_TICKERS,
    pd, yf,
    _NASDAQ_COMPANY_NAMES,
)


@ttl_cache(CACHE_TTL["fetch_nasdaq_premarket_scan"])
def fetch_nasdaq_premarket_scan() -> pd.DataFrame:
    """Scans NASDAQ-100 for today's pre-market movers."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    try:
        daily = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if daily.empty:
        return pd.DataFrame()

    is_d         = isinstance(daily.columns, pd.MultiIndex)
    daily_close  = daily["Close"]  if is_d else daily
    daily_volume = daily["Volume"] if is_d else None

    intra_close  = pd.DataFrame()
    intra_volume = pd.DataFrame()
    try:
        intra = yf.download(
            tickers, period="2d", interval="5m",
            prepost=True, auto_adjust=True, progress=False,
        )
        if not intra.empty:
            is_i         = isinstance(intra.columns, pd.MultiIndex)
            intra_close  = intra["Close"]  if is_i else intra
            intra_volume = intra["Volume"] if is_i else pd.DataFrame()
    except Exception:
        pass

    pm_close_df  = pd.DataFrame()
    pm_volume_df = pd.DataFrame()

    if not intra_close.empty:
        now_et    = pd.Timestamp.now(tz="America/New_York")
        today_str = now_et.strftime("%Y-%m-%d")
        idx       = intra_close.index
        idx_et    = (
            idx.tz_convert("America/New_York") if idx.tzinfo is not None
            else idx.tz_localize("UTC").tz_convert("America/New_York")
        )
        pm_mask = (
            (idx_et.strftime("%Y-%m-%d") == today_str) &
            (idx_et.hour >= 4) &
            ((idx_et.hour < 9) | ((idx_et.hour == 9) & (idx_et.minute < 30)))
        )
        pm_close_df = intra_close[pm_mask]
        if not intra_volume.empty:
            pm_volume_df = intra_volume[pm_mask]

    results = []
    for ticker in tickers:
        try:
            if ticker not in daily_close.columns:
                continue
            d_closes = daily_close[ticker].dropna()
            if len(d_closes) < 2:
                continue

            prev_close = float(d_closes.iloc[-1])
            ref        = float(d_closes.iloc[max(0, len(d_closes) - 8)])
            chg_7d     = round((prev_close - ref) / ref * 100, 2) if ref > 0 else None

            avg_dvol = None
            if daily_volume is not None and ticker in daily_volume.columns:
                dvols = daily_volume[ticker].dropna()
                if len(dvols) >= 5:
                    avg_dvol = float(dvols.iloc[-10:].mean())

            pm_price   = None
            pm_chg     = None
            pm_vol_pct = None

            if not pm_close_df.empty and ticker in pm_close_df.columns:
                pm_bars = pm_close_df[ticker].dropna()
                if not pm_bars.empty:
                    pm_price = round(float(pm_bars.iloc[-1]), 2)
                    pm_chg   = round((pm_price - prev_close) / prev_close * 100, 2)
                    if not pm_volume_df.empty and ticker in pm_volume_df.columns:
                        pm_vol = float(pm_volume_df[ticker].fillna(0).sum())
                        if avg_dvol and avg_dvol > 0:
                            pm_vol_pct = round(pm_vol / avg_dvol * 100, 1)

            results.append({
                "Ticker":     ticker,
                "PM Price":   pm_price,
                "PM Chg %":   pm_chg,
                "PM Vol %":   pm_vol_pct,
                "Prev Close": round(prev_close, 2),
                "7D Chg %":   chg_7d,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df["_has_pm"]  = df["PM Chg %"].notna().astype(int)
    df["_abs_chg"] = pd.to_numeric(df["PM Chg %"], errors="coerce").abs().fillna(-1)
    df = (
        df.sort_values(["_has_pm", "_abs_chg"], ascending=[False, False])
          .drop(columns=["_has_pm", "_abs_chg"])
          .reset_index(drop=True)
    )
    df.insert(1, "Company", df["Ticker"].map(_NASDAQ_COMPANY_NAMES).fillna("—"))
    return df


@ttl_cache(CACHE_TTL["fetch_nasdaq_premarket_history"])
def fetch_nasdaq_premarket_history() -> pd.DataFrame:
    """Returns the last 7 trading days of daily close prices for all NASDAQ-100 stocks."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]
    try:
        raw = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    is_multi = isinstance(raw.columns, pd.MultiIndex)
    close_df = raw["Close"] if is_multi else raw
    close_df = close_df.dropna(how="all").tail(7)
    close_df.index = pd.to_datetime(close_df.index).strftime("%b %d")

    result = close_df.T.round(2)
    result.index.name = "Ticker"
    return result
