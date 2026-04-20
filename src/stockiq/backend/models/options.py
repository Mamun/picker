"""Options analytics: max pain and open interest by strike."""

from datetime import datetime

import numpy as np
import pandas as pd


def compute_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float:
    """
    Return the max-pain strike — the price at which total in-the-money dollar
    value across all open contracts is minimised (dealers gain most).

    Algorithm (vectorised):
      For each candidate strike S:
        call_pain = Σ (S − K) × call_OI  for every call strike K < S
        put_pain  = Σ (K − S) × put_OI   for every put  strike K > S
      max_pain = argmin(call_pain + put_pain)
    """
    call_oi = (
        calls[["strike", "openInterest"]]
        .rename(columns={"openInterest": "call_oi"})
        .groupby("strike", as_index=False)["call_oi"].sum()
    )
    put_oi = (
        puts[["strike", "openInterest"]]
        .rename(columns={"openInterest": "put_oi"})
        .groupby("strike", as_index=False)["put_oi"].sum()
    )
    merged = (
        pd.merge(call_oi, put_oi, on="strike", how="outer")
        .fillna(0)
        .sort_values("strike")
        .reset_index(drop=True)
    )

    strikes      = merged["strike"].values
    call_oi_vals = merged["call_oi"].values
    put_oi_vals  = merged["put_oi"].values

    # Vectorised pain matrix: rows = candidate strikes, cols = chain strikes
    s = strikes[:, np.newaxis]      # (n, 1)
    k = strikes[np.newaxis, :]      # (1, n)

    call_pain = np.sum(np.maximum(s - k, 0) * call_oi_vals, axis=1)
    put_pain  = np.sum(np.maximum(k - s, 0) * put_oi_vals,  axis=1)

    return float(strikes[np.argmin(call_pain + put_pain)])


def compute_oi_by_strike(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: float,
    n_strikes: int = 30,
) -> pd.DataFrame:
    """
    Return call OI and put OI aggregated per strike, filtered to the
    n_strikes nearest to current_price (split evenly above and below).

    Returns columns: strike, call_oi, put_oi
    """
    call_oi = (
        calls[["strike", "openInterest"]]
        .rename(columns={"openInterest": "call_oi"})
        .groupby("strike", as_index=False)["call_oi"].sum()
    )
    put_oi = (
        puts[["strike", "openInterest"]]
        .rename(columns={"openInterest": "put_oi"})
        .groupby("strike", as_index=False)["put_oi"].sum()
    )
    oi = (
        pd.merge(call_oi, put_oi, on="strike", how="outer")
        .fillna(0)
        .sort_values("strike")
        .reset_index(drop=True)
    )

    idx  = int(np.searchsorted(oi["strike"].values, current_price))
    half = n_strikes // 2
    lo   = max(0, idx - half)
    hi   = min(len(oi), lo + n_strikes)
    lo   = max(0, hi - n_strikes)          # re-align if we hit the top

    return oi.iloc[lo:hi].reset_index(drop=True)


def label_expirations(expirations: list[str], today: datetime | None = None) -> list[str]:
    """
    Convert ISO expiration strings to human-readable labels with days-to-expiry.
    e.g. "2026-04-25" → "Apr 25 (5d)"
    """
    ref = (today or datetime.today()).date()
    labels = []
    for e in expirations:
        try:
            exp_date = datetime.strptime(e, "%Y-%m-%d").date()
            dte      = (exp_date - ref).days
            labels.append(f"{exp_date.strftime('%b %d')} ({dte}d)")
        except Exception:
            labels.append(e)
    return labels
