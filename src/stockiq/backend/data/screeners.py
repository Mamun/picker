import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from stockiq.backend.cache import ttl_cache
from stockiq.backend.models.indicators import compute_rsi
from stockiq.backend.config import CACHE_TTL, NASDAQ_100_TICKERS, SPX_TICKERS

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_NASDAQ_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "META": "Meta Platforms", "GOOGL": "Alphabet A", "GOOG": "Alphabet C",
    "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
    "AMD": "Advanced Micro Devices", "ADBE": "Adobe", "QCOM": "Qualcomm",
    "TXN": "Texas Instruments", "CSCO": "Cisco", "INTU": "Intuit",
    "AMGN": "Amgen", "ISRG": "Intuitive Surgical", "CMCSA": "Comcast",
    "REGN": "Regeneron", "VRTX": "Vertex Pharma", "MDLZ": "Mondelez",
    "GILD": "Gilead Sciences", "MU": "Micron Technology", "LRCX": "Lam Research",
    "KLAC": "KLA Corp", "AMAT": "Applied Materials", "PANW": "Palo Alto Networks",
    "SNPS": "Synopsys", "CDNS": "Cadence Design", "ADI": "Analog Devices",
    "MRVL": "Marvell Technology", "ASML": "ASML Holding", "MELI": "MercadoLibre",
    "ADP": "Automatic Data Processing", "PYPL": "PayPal", "WDAY": "Workday",
    "DDOG": "Datadog", "CRWD": "CrowdStrike", "ZS": "Zscaler", "FTNT": "Fortinet",
    "MNST": "Monster Beverage", "ROST": "Ross Stores", "AEP": "American Electric Power",
    "IDXX": "IDEXX Laboratories", "PCAR": "PACCAR", "EXC": "Exelon",
    "GEHC": "GE HealthCare", "ODFL": "Old Dominion Freight", "FAST": "Fastenal",
    "VRSK": "Verisk Analytics", "CTSH": "Cognizant", "DLTR": "Dollar Tree",
    "EA": "Electronic Arts", "ALGN": "Align Technology", "ANSS": "ANSYS",
    "TEAM": "Atlassian", "NXPI": "NXP Semiconductors", "PAYX": "Paychex",
    "CHTR": "Charter Communications", "CPRT": "Copart", "CTAS": "Cintas",
    "LULU": "Lululemon", "BKNG": "Booking Holdings", "KHC": "Kraft Heinz",
    "CEG": "Constellation Energy", "DXCM": "Dexcom", "MRNA": "Moderna",
    "TTD": "The Trade Desk", "NDAQ": "Nasdaq Inc", "INTC": "Intel",
    "SBUX": "Starbucks", "MAR": "Marriott", "ORLY": "O'Reilly Auto",
    "KDP": "Keurig Dr Pepper", "FANG": "Diamondback Energy", "ON": "ON Semiconductor",
    "BIIB": "Biogen", "OKTA": "Okta", "WBD": "Warner Bros Discovery",
    "ABNB": "Airbnb", "ENPH": "Enphase Energy", "FSLR": "First Solar",
    "TTWO": "Take-Two Interactive", "EBAY": "eBay", "ILMN": "Illumina",
    "ZM": "Zoom Video", "FISV": "Fiserv", "SMCI": "Super Micro Computer",
    "HON": "Honeywell", "PDD": "PDD Holdings", "JD": "JD.com",
    "SIRI": "Sirius XM", "MTCH": "Match Group", "GFS": "GlobalFoundries",
    "RIVN": "Rivian", "LCID": "Lucid Group", "MSTR": "MicroStrategy", "ARM": "Arm Holdings",
}


def _rsi_last(df: pd.DataFrame) -> float:
    """Return the latest RSI-14 value for a DataFrame with a Close column."""
    return float(compute_rsi(df).iloc[-1])


@ttl_cache(CACHE_TTL["fetch_candle_momentum_scan"])
def fetch_candle_momentum_scan() -> pd.DataFrame:
    """
    Weekly/monthly candle screener for SPX_TICKERS.

    Per ticker:
      • 4-week & 4-month green candle counts → 5-tier signal (Strong Buy → Sell)
      • 1W / 1M / 3M price returns + performance vs SPY (1M relative strength)
      • Volume trend (5-day avg vs 20-day avg)
      • RSI-14
      • Sector
    """
    recommendations = []

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=270)
    start_str  = start_date.strftime("%Y-%m-%d")
    end_str    = end_date.strftime("%Y-%m-%d")

    spx_ret_1m = 0.0
    try:
        spx = yf.download("SPY", start=start_str, end=end_str, progress=False, auto_adjust=True)
        if isinstance(spx.columns, pd.MultiIndex):
            spx.columns = spx.columns.get_level_values(0)
        spx = spx.dropna(subset=["Close"])
        if len(spx) >= 22:
            spx_ret_1m = (
                (float(spx["Close"].iloc[-1]) - float(spx["Close"].iloc[-22]))
                / float(spx["Close"].iloc[-22]) * 100
            )
    except Exception:
        pass

    for ticker in SPX_TICKERS:
        try:
            df = yf.download(ticker, start=start_str, end=end_str, progress=False, auto_adjust=True)
            if df.empty or len(df) < 20:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 20:
                continue

            info         = yf.Ticker(ticker).info
            company_name = info.get("longName", ticker)
            sector       = info.get("sector", "—")
            last_price   = float(df["Close"].iloc[-1])

            def _ret(n: int):
                if len(df) > n:
                    prev = float(df["Close"].iloc[-(n + 1)])
                    return (last_price - prev) / prev * 100
                return None

            ret_1w = _ret(5)
            ret_1m = _ret(21)
            ret_3m = _ret(63)
            vs_spx = round(ret_1m - spx_ret_1m, 1) if ret_1m is not None else None

            avg_vol_5  = float(df["Volume"].tail(5).mean())
            avg_vol_20 = float(df["Volume"].tail(20).mean())
            if avg_vol_20 > 0:
                ratio     = avg_vol_5 / avg_vol_20
                vol_trend = "🔼" if ratio > 1.1 else "🔽" if ratio < 0.9 else "➡️"
            else:
                vol_trend = "—"

            rsi = _rsi_last(df)

            weekly_df    = df[["Open", "Close"]].resample("W").agg({"Open": "first", "Close": "last"})
            w4           = weekly_df.tail(4)
            weekly_green = sum(1 for _, r in w4.iterrows() if r["Close"] > r["Open"])
            weekly_dots  = ["🟢" if r["Close"] > r["Open"] else "🔴" for _, r in w4.iterrows()]

            monthly_df    = df[["Open", "Close"]].resample("ME").agg({"Open": "first", "Close": "last"})
            m4            = monthly_df.tail(4)
            monthly_green = sum(1 for _, r in m4.iterrows() if r["Close"] > r["Open"])
            monthly_dots  = ["🟢" if r["Close"] > r["Open"] else "🔴" for _, r in m4.iterrows()]

            if weekly_green == 4 and monthly_green == 4:
                signal, sig_order = "🟢 Strong Buy", 1
            elif weekly_green == 4 and monthly_green >= 3:
                signal, sig_order = "🟢 Buy", 2
            elif weekly_green >= 3 and monthly_green >= 3:
                signal, sig_order = "🟡 Accumulate", 3
            elif weekly_green >= 2:
                signal, sig_order = "🟠 Caution", 4
            else:
                signal, sig_order = "🔴 Sell", 5

            recommendations.append({
                "Ticker":    ticker,
                "Company":   company_name,
                "Sector":    sector,
                "Price":     round(last_price, 2),
                "1W %":      round(ret_1w, 1) if ret_1w is not None else None,
                "1M %":      round(ret_1m, 1) if ret_1m is not None else None,
                "3M %":      round(ret_3m, 1) if ret_3m is not None else None,
                "vs SPX":    vs_spx,
                "Vol":       vol_trend,
                "RSI":       round(rsi, 1),
                "🔷 Weeks":  " ".join(weekly_dots),
                "W Score":   f"{weekly_green}/4",
                "🔶 Months": " ".join(monthly_dots),
                "M Score":   f"{monthly_green}/4",
                "Signal":    signal,
                "_order":    sig_order,
                "Strength":  weekly_green + monthly_green,
            })
        except Exception:
            continue

    if not recommendations:
        return pd.DataFrame()

    return (
        pd.DataFrame(recommendations)
        .sort_values(["_order", "Strength"], ascending=[True, False])
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_bounce_radar_scan"])
def fetch_bounce_radar_scan(threshold_pct: float = 5.0, top_n: int = 30) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for stocks within ±threshold_pct of their 200-day MA.
    Bounce score rewards: proximity to MA200 + oversold RSI + below-MA200 support.
    Returns top_n rows sorted by bounce score descending.
    """
    results = []

    for ticker in SPX_TICKERS:
        try:
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=320)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 201:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 201:
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

            company_name = yf.Ticker(ticker).info.get("longName", ticker)

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


@ttl_cache(CACHE_TTL["fetch_squeeze_scan"])
def fetch_squeeze_scan(
    rsi_min: float = 55.0,
    min_short_float: float = 0.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for potential short-squeeze setups:
      • RSI ≥ rsi_min              — stock extended (shorts under pressure)
      • Short % of Float ≥ min_short_float — meaningful short interest
    """
    results = []

    for ticker in SPX_TICKERS:
        try:
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=90)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 14:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 14:
                continue

            rsi = _rsi_last(df)
            if np.isnan(rsi) or rsi < rsi_min:
                continue

            info          = yf.Ticker(ticker).info
            raw_spf       = info.get("shortPercentOfFloat") or 0.0
            short_pct_flt = raw_spf * 100.0
            short_ratio   = float(info.get("shortRatio")            or 0.0)
            shares_short  = int(  info.get("sharesShort")           or 0)
            shares_prior  = int(  info.get("sharesShortPriorMonth") or 0)

            if short_pct_flt < min_short_float:
                continue

            price        = float(df["Close"].iloc[-1])
            company_name = info.get("longName", ticker)

            short_change_pct = (
                (shares_short - shares_prior) / shares_prior * 100
                if shares_prior > 0 else 0.0
            )

            rsi_score = max(0.0, (rsi - 50.0)) * 0.4

            if short_pct_flt >= 5:
                float_score = 40.0
            elif short_pct_flt >= 3:
                float_score = 25.0
            elif short_pct_flt >= 1.5:
                float_score = 15.0
            else:
                float_score = short_pct_flt * 8.0

            if short_ratio >= 10:
                ratio_score = 20.0
            elif short_ratio >= 5:
                ratio_score = 12.0
            elif short_ratio >= 2:
                ratio_score = 6.0
            else:
                ratio_score = short_ratio * 2.0

            build_score   = 5.0 if short_change_pct > 0 else 0.0
            squeeze_score = rsi_score + float_score + ratio_score + build_score

            if rsi >= 80:
                rsi_zone = "🔴 Extreme OB"
            elif rsi >= 70:
                rsi_zone = "🟠 Overbought"
            else:
                rsi_zone = "🟡 Elevated"

            results.append({
                "Ticker":          ticker,
                "Company":         company_name,
                "Price":           round(price, 2),
                "RSI":             round(rsi, 1),
                "RSI Zone":        rsi_zone,
                "Short % Float":   round(short_pct_flt, 1),
                "Days to Cover":   round(short_ratio, 1),
                "Short Chg % MoM": round(short_change_pct, 1),
                "Squeeze Score":   round(squeeze_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Squeeze Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def _quality_score(info: dict) -> tuple[float, list[str]]:
    """Score a stock's fundamental quality (Munger-style). Returns (score 0–85, breakdown)."""
    score     = 0.0
    breakdown: list[str] = []

    roe = info.get("returnOnEquity")
    if roe is not None:
        roe_pct = roe * 100
        pts = 25.0 if roe_pct >= 20 else 18.0 if roe_pct >= 15 else 10.0 if roe_pct >= 10 else 5.0 if roe_pct > 0 else 0.0
        score += pts
        breakdown.append(f"ROE {roe_pct:.1f}% → {pts:.0f}/25")

    pm = info.get("profitMargins")
    if pm is not None:
        pm_pct = pm * 100
        pts = 20.0 if pm_pct >= 20 else 14.0 if pm_pct >= 10 else 8.0 if pm_pct >= 5 else 3.0 if pm_pct > 0 else 0.0
        score += pts
        breakdown.append(f"Profit Margin {pm_pct:.1f}% → {pts:.0f}/20")

    rg = info.get("revenueGrowth")
    if rg is not None:
        rg_pct = rg * 100
        pts = 15.0 if rg_pct >= 15 else 10.0 if rg_pct >= 8 else 6.0 if rg_pct >= 3 else 2.0 if rg_pct >= 0 else 0.0
        score += pts
        breakdown.append(f"Revenue Growth {rg_pct:.1f}% → {pts:.0f}/15")

    de = info.get("debtToEquity")
    if de is not None:
        de_ratio = de / 100.0
        pts = 15.0 if de_ratio < 0.3 else 10.0 if de_ratio < 0.7 else 5.0 if de_ratio < 1.5 else 0.0
        score += pts
        breakdown.append(f"D/E {de_ratio:.2f}× → {pts:.0f}/15")

    eg = info.get("earningsGrowth")
    if eg is not None:
        eg_pct = eg * 100
        pts = 10.0 if eg_pct >= 15 else 7.0 if eg_pct >= 8 else 3.0 if eg_pct >= 0 else 0.0
        score += pts
        breakdown.append(f"EPS Growth {eg_pct:.1f}% → {pts:.0f}/10")

    return score, breakdown


def _proximity_score(dist_pct: float) -> int:
    """Points for proximity to 200-week MA. Closer = higher score (max 15)."""
    abs_d = abs(dist_pct)
    if abs_d <= 2:   return 15
    if abs_d <= 5:   return 12
    if abs_d <= 10:  return 8
    if abs_d <= 15:  return 4
    if abs_d <= 20:  return 2
    return 0


@ttl_cache(CACHE_TTL["fetch_munger_strategy_scan"])
def fetch_munger_strategy_scan(
    threshold_pct: float = 15.0,
    min_quality: float = 30.0,
    top_n: int = 30,
) -> pd.DataFrame:
    """
    Scan SPX_TICKERS for Charlie Munger-style setups.
    Munger Score = Quality Score (0–85) + Proximity Score (0–15). Max = 100.
    """
    results = []

    for ticker in SPX_TICKERS:
        try:
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=1600)
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < 200:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 200:
                continue

            weekly = df["Close"].resample("W").last().dropna()
            if len(weekly) < 200:
                continue
            ma200w = float(weekly.rolling(200).mean().iloc[-1])
            if np.isnan(ma200w):
                continue

            price    = float(df["Close"].iloc[-1])
            dist_pct = (price - ma200w) / ma200w * 100
            if abs(dist_pct) > threshold_pct:
                continue

            info           = yf.Ticker(ticker).info
            q_score, breakdown = _quality_score(info)
            if q_score < min_quality:
                continue

            prox_score   = _proximity_score(dist_pct)
            munger_score = q_score + prox_score
            rsi          = _rsi_last(df)

            results.append({
                "Ticker":        ticker,
                "Company":       info.get("longName", ticker),
                "Sector":        info.get("sector", "—"),
                "Price":         round(price, 2),
                "MA 200W":       round(ma200w, 2),
                "Distance %":    round(dist_pct, 2),
                "RSI":           round(rsi, 1),
                "Quality Score": round(q_score, 1),
                "Prox Score":    prox_score,
                "Munger Score":  round(munger_score, 1),
                "Breakdown":     " | ".join(breakdown),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("Munger Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_strong_buy_scan"])
def fetch_strong_buy_scan(
    min_upside: float = 5.0,
    min_analysts: int = 5,
    max_rating: float = 2.5,
    top_n: int = 20,
) -> pd.DataFrame:
    """Scan SPX_TICKERS for analyst strong-buy / buy consensus setups."""
    results = []

    for ticker in SPX_TICKERS:
        try:
            info = yf.Ticker(ticker).info

            rec_mean = info.get("recommendationMean")
            if rec_mean is None or float(rec_mean) > max_rating:
                continue

            num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
            if num_analysts < min_analysts:
                continue

            target_mean = float(info.get("targetMeanPrice") or 0)
            target_high = float(info.get("targetHighPrice")  or 0)
            target_low  = float(info.get("targetLowPrice")   or 0)
            price       = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)

            if price <= 0 or target_mean <= 0:
                continue

            upside_pct = (target_mean - price) / price * 100
            if upside_pct < min_upside:
                continue

            end_dt   = datetime.today()
            start_dt = end_dt - timedelta(days=60)
            df = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])

            rsi = float(compute_rsi(df).iloc[-1]) if len(df) >= 14 else np.nan

            rating_score  = max(0.0, (2.5 - float(rec_mean)) * 26.7)
            upside_score  = min(upside_pct, 50.0) * 0.5
            analyst_score = min(num_analysts, 20) * 1.5
            rsi_bonus     = 5.0 if (not np.isnan(rsi) and rsi < 60) else 0.0
            sb_score      = rating_score + upside_score + analyst_score + rsi_bonus

            if float(rec_mean) <= 1.5:
                consensus = "⭐ Strong Buy"
            elif float(rec_mean) <= 2.0:
                consensus = "🟢 Buy"
            else:
                consensus = "🟡 Moderate Buy"

            results.append({
                "Ticker":      ticker,
                "Company":     info.get("longName", ticker),
                "Sector":      info.get("sector", "—"),
                "Price":       round(price, 2),
                "Target":      round(target_mean, 2),
                "Target High": round(target_high, 2),
                "Target Low":  round(target_low, 2),
                "Upside %":    round(upside_pct, 1),
                "Rating":      round(float(rec_mean), 2),
                "Consensus":   consensus,
                "Analysts":    num_analysts,
                "RSI":         round(rsi, 1) if not np.isnan(rsi) else None,
                "SB Score":    round(sb_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SB Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


@ttl_cache(CACHE_TTL["fetch_strong_sell_scan"])
def fetch_strong_sell_scan(
    min_downside: float = 0.0,
    min_analysts: int = 1,
    min_rating: float = 2.5,
    top_n: int = 30,
) -> pd.DataFrame:
    """Scan SPX_TICKERS for analyst sell / strong-sell consensus setups."""
    results = []

    for ticker in SPX_TICKERS:
        try:
            info = yf.Ticker(ticker).info

            rec_mean = info.get("recommendationMean")
            if rec_mean is None or float(rec_mean) < min_rating:
                continue

            num_analysts = int(info.get("numberOfAnalystOpinions") or 0)
            if num_analysts < min_analysts:
                continue

            target_mean = float(info.get("targetMeanPrice") or 0)
            target_high = float(info.get("targetHighPrice")  or 0)
            target_low  = float(info.get("targetLowPrice")   or 0)
            price       = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)

            if price <= 0 or target_mean <= 0:
                continue

            downside_pct = (target_mean - price) / price * 100
            if downside_pct > -min_downside:
                continue

            end_dt   = datetime.today()
            start_dt = end_dt - timedelta(days=60)
            df = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])

            rsi = float(compute_rsi(df).iloc[-1]) if len(df) >= 14 else np.nan

            rating_score   = max(0.0, (float(rec_mean) - 3.5) * 26.7)
            downside_score = min(abs(downside_pct), 50.0) * 0.5
            analyst_score  = min(num_analysts, 20) * 1.5
            rsi_bonus      = 5.0 if (not np.isnan(rsi) and rsi > 60) else 0.0
            ss_score       = rating_score + downside_score + analyst_score + rsi_bonus

            if float(rec_mean) >= 4.5:
                consensus = "🔴 Strong Sell"
            elif float(rec_mean) >= 4.0:
                consensus = "🟠 Sell"
            elif float(rec_mean) >= 3.5:
                consensus = "🟡 Moderate Sell"
            elif float(rec_mean) >= 3.0:
                consensus = "⚪ Hold"
            else:
                consensus = "🔵 Cautious Hold"

            results.append({
                "Ticker":      ticker,
                "Company":     info.get("longName", ticker),
                "Sector":      info.get("sector", "—"),
                "Price":       round(price, 2),
                "Target":      round(target_mean, 2),
                "Target High": round(target_high, 2),
                "Target Low":  round(target_low, 2),
                "Downside %":  round(downside_pct, 1),
                "Rating":      round(float(rec_mean), 2),
                "Consensus":   consensus,
                "Analysts":    num_analysts,
                "RSI":         round(rsi, 1) if not np.isnan(rsi) else None,
                "SS Score":    round(ss_score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("SS Score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
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

    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    try:
        raw = yf.download(
            tickers,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return pd.DataFrame()

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
                    avg_vol = float(vols.iloc[-21:-1].mean())
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


@ttl_cache(CACHE_TTL["fetch_premarket_scan"])
def fetch_premarket_scan() -> pd.DataFrame:
    """Scans NASDAQ-100 for today's pre-market movers."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]

    try:
        daily = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if daily.empty:
        return pd.DataFrame()

    is_d = isinstance(daily.columns, pd.MultiIndex)
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
            is_i = isinstance(intra.columns, pd.MultiIndex)
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
        pm_close_df  = intra_close[pm_mask]
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

            ref = float(d_closes.iloc[max(0, len(d_closes) - 8)])
            chg_7d = round((prev_close - ref) / ref * 100, 2) if ref > 0 else None

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
    df["_abs_chg"] = df["PM Chg %"].abs().fillna(-1)
    df = (
        df.sort_values(["_has_pm", "_abs_chg"], ascending=[False, False])
          .drop(columns=["_has_pm", "_abs_chg"])
          .reset_index(drop=True)
    )
    df.insert(1, "Company", df["Ticker"].map(_NASDAQ_COMPANY_NAMES).fillna("—"))
    return df


@ttl_cache(CACHE_TTL["fetch_premarket_history"])
def fetch_premarket_history() -> pd.DataFrame:
    """Returns the last 7 trading days of daily close prices for all NASDAQ-100 stocks."""
    tickers = [t for t in NASDAQ_100_TICKERS if isinstance(t, str)]
    try:
        raw = yf.download(tickers, period="12d", auto_adjust=True, progress=False)
    except Exception:
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    is_multi  = isinstance(raw.columns, pd.MultiIndex)
    close_df  = raw["Close"] if is_multi else raw

    close_df = close_df.dropna(how="all").tail(7)
    close_df.index = pd.to_datetime(close_df.index).strftime("%b %d")

    result = close_df.T.round(2)
    result.index.name = "Ticker"
    return result



# ── ETF universe ───────────────────────────────────────────────────────────────
ETF_UNIVERSE: list[dict] = [
    {"ticker": "SPY",  "name": "S&P 500",              "category": "Retail Favorites"},
    {"ticker": "QQQ",  "name": "NASDAQ-100",            "category": "Retail Favorites"},
    {"ticker": "TQQQ", "name": "3× NASDAQ (Bull)",      "category": "Retail Favorites"},
    {"ticker": "SQQQ", "name": "3× NASDAQ (Bear)",      "category": "Retail Favorites"},
    {"ticker": "SPXL", "name": "3× S&P 500 (Bull)",     "category": "Retail Favorites"},
    {"ticker": "SOXL", "name": "3× Semiconductors",     "category": "Retail Favorites"},
    {"ticker": "ARKK", "name": "ARK Innovation",        "category": "Retail Favorites"},
    {"ticker": "ARKG", "name": "ARK Genomics",          "category": "Retail Favorites"},
    {"ticker": "VXX",  "name": "VIX Short-Term Futures","category": "Retail Favorites"},
    {"ticker": "UVXY", "name": "1.5× VIX Futures",      "category": "Retail Favorites"},
    {"ticker": "JETS", "name": "Airlines",              "category": "Retail Favorites"},
    {"ticker": "MSOS", "name": "Cannabis",              "category": "Retail Favorites"},
    {"ticker": "IWM",  "name": "Russell 2000",          "category": "Retail Favorites"},
    {"ticker": "SPY",  "name": "S&P 500",            "category": "Broad Market"},
    {"ticker": "QQQ",  "name": "NASDAQ-100",          "category": "Broad Market"},
    {"ticker": "IWM",  "name": "Russell 2000",        "category": "Broad Market"},
    {"ticker": "DIA",  "name": "Dow Jones",           "category": "Broad Market"},
    {"ticker": "VTI",  "name": "Total US Market",     "category": "Broad Market"},
    {"ticker": "VOO",  "name": "Vanguard S&P 500",    "category": "Broad Market"},
    {"ticker": "XLK",  "name": "Technology",          "category": "Sector"},
    {"ticker": "XLF",  "name": "Financials",          "category": "Sector"},
    {"ticker": "XLE",  "name": "Energy",              "category": "Sector"},
    {"ticker": "XLV",  "name": "Health Care",         "category": "Sector"},
    {"ticker": "XLC",  "name": "Communication Svcs",  "category": "Sector"},
    {"ticker": "XLY",  "name": "Consumer Discret.",   "category": "Sector"},
    {"ticker": "XLP",  "name": "Consumer Staples",    "category": "Sector"},
    {"ticker": "XLB",  "name": "Materials",           "category": "Sector"},
    {"ticker": "XLI",  "name": "Industrials",         "category": "Sector"},
    {"ticker": "XLU",  "name": "Utilities",           "category": "Sector"},
    {"ticker": "XLRE", "name": "Real Estate",         "category": "Sector"},
    {"ticker": "TLT",  "name": "20+ Yr Treasury",     "category": "Fixed Income"},
    {"ticker": "IEF",  "name": "7-10 Yr Treasury",    "category": "Fixed Income"},
    {"ticker": "SHY",  "name": "1-3 Yr Treasury",     "category": "Fixed Income"},
    {"ticker": "HYG",  "name": "High Yield Corp",     "category": "Fixed Income"},
    {"ticker": "LQD",  "name": "Investment Grade Corp","category": "Fixed Income"},
    {"ticker": "GLD",  "name": "Gold",                "category": "Commodity"},
    {"ticker": "SLV",  "name": "Silver",              "category": "Commodity"},
    {"ticker": "USO",  "name": "Oil",                 "category": "Commodity"},
    {"ticker": "UNG",  "name": "Natural Gas",         "category": "Commodity"},
    {"ticker": "DBA",  "name": "Agriculture",         "category": "Commodity"},
    {"ticker": "EFA",  "name": "Developed Markets",   "category": "International"},
    {"ticker": "EEM",  "name": "Emerging Markets",    "category": "International"},
    {"ticker": "FXI",  "name": "China Large-Cap",     "category": "International"},
    {"ticker": "EWJ",  "name": "Japan",               "category": "International"},
    {"ticker": "IEFA", "name": "Core MSCI EAFE",      "category": "International"},
    {"ticker": "SOXX", "name": "iShares Semiconductors",     "category": "Semiconductor"},
    {"ticker": "SMH",  "name": "VanEck Semiconductors",      "category": "Semiconductor"},
    {"ticker": "SOXQ", "name": "Invesco PHLX Semis",         "category": "Semiconductor"},
    {"ticker": "PSI",  "name": "Invesco Dynamic Semis",      "category": "Semiconductor"},
    {"ticker": "FTXL", "name": "First Trust Nasdaq Semis",   "category": "Semiconductor"},
    {"ticker": "IGV",  "name": "iShares Expanded Tech-SW",   "category": "Software"},
    {"ticker": "WCLD", "name": "WisdomTree Cloud Computing", "category": "Software"},
    {"ticker": "BUG",  "name": "Global X Cybersecurity",     "category": "Software"},
    {"ticker": "CIBR", "name": "First Trust Cybersecurity",  "category": "Software"},
    {"ticker": "CLOU", "name": "Global X Cloud Computing",   "category": "Software"},
]


@ttl_cache(CACHE_TTL["fetch_etf_scan"])
def fetch_etf_scan(categories: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Scan ETF_UNIVERSE for momentum, RSI, MA crossover, and volume signals."""
    etfs = ETF_UNIVERSE
    if categories:
        etfs = [e for e in etfs if e["category"] in categories]

    tickers = [e["ticker"] for e in etfs]
    meta    = {e["ticker"]: e for e in etfs}

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=320)

    raw = yf.download(
        tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )

    spy_ret_1m = 0.0
    try:
        if "SPY" in tickers:
            spy_close = raw["SPY"]["Close"].dropna()
        else:
            spy_raw   = yf.download("SPY", start=start_date.strftime("%Y-%m-%d"),
                                    end=end_date.strftime("%Y-%m-%d"),
                                    progress=False, auto_adjust=True)
            spy_close = spy_raw["Close"].dropna()
        if len(spy_close) >= 22:
            spy_ret_1m = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-22])) / float(spy_close.iloc[-22]) * 100
    except Exception:
        pass

    results = []
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].copy()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 22:
                continue

            price = float(df["Close"].iloc[-1])

            def _ret(n: int) -> float | None:
                if len(df) > n:
                    prev = float(df["Close"].iloc[-(n + 1)])
                    return (price - prev) / prev * 100
                return None

            ret_1d = _ret(1)
            ret_1w = _ret(5)
            ret_1m = _ret(21)
            ret_3m = _ret(63)
            vs_spy = round(ret_1m - spy_ret_1m, 1) if ret_1m is not None else None

            rsi = _rsi_last(df)

            ma20  = float(df["Close"].rolling(20).mean().iloc[-1])  if len(df) >= 20  else None
            ma50  = float(df["Close"].rolling(50).mean().iloc[-1])  if len(df) >= 50  else None
            ma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

            if ma20 is not None and ma50 is not None and not np.isnan(ma20) and not np.isnan(ma50):
                ma_cross = "🟢 Bullish" if ma20 > ma50 else "🔴 Bearish"
            else:
                ma_cross = "—"

            ma200_dist = round((price - ma200) / ma200 * 100, 1) if ma200 and not np.isnan(ma200) else None

            avg_vol_5  = float(df["Volume"].tail(5).mean())
            avg_vol_20 = float(df["Volume"].tail(20).mean())
            vol_ratio  = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0
            vol_surge  = "🔼" if vol_ratio > 1.2 else "🔽" if vol_ratio < 0.8 else "➡️"

            if rsi <= 30:
                rsi_zone = "🟢 Oversold"
            elif rsi >= 70:
                rsi_zone = "🔴 Overbought"
            elif rsi <= 45:
                rsi_zone = "🟡 Weak"
            elif rsi >= 55:
                rsi_zone = "🔵 Strong"
            else:
                rsi_zone = "⚪ Neutral"

            score = 50.0
            if ret_1m is not None:
                score += min(ret_1m * 1.5, 15)
            if vs_spy is not None:
                score += min(vs_spy * 1.0, 10)
            if rsi <= 40:
                score += 10
            elif rsi >= 70:
                score -= 10
            if ma_cross == "🟢 Bullish":
                score += 10
            elif ma_cross == "🔴 Bearish":
                score -= 10
            if vol_ratio > 1.2:
                score += 5

            results.append({
                "Ticker":      ticker,
                "Name":        meta[ticker]["name"],
                "Category":    meta[ticker]["category"],
                "Price":       round(price, 2),
                "1D %":        round(ret_1d, 2) if ret_1d is not None else None,
                "1W %":        round(ret_1w, 1) if ret_1w is not None else None,
                "1M %":        round(ret_1m, 1) if ret_1m is not None else None,
                "3M %":        round(ret_3m, 1) if ret_3m is not None else None,
                "vs SPY":      vs_spy,
                "RSI":         round(rsi, 1),
                "RSI Zone":    rsi_zone,
                "MA Signal":   ma_cross,
                "MA200 Dist%": ma200_dist,
                "Vol":         vol_surge,
                "ETF Score":   round(score, 1),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values("ETF Score", ascending=False)
        .reset_index(drop=True)
    )
