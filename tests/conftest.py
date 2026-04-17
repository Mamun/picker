"""Shared pytest fixtures for StockIQ test suite."""

import numpy as np
import pandas as pd
import pytest


def _make_ohlcv(n: int = 300, base_price: float = 150.0, seed: int = 42) -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2024-12-31", periods=n)
    close = base_price + np.cumsum(rng.normal(0, 1.5, n))
    close = np.clip(close, 10, None)
    noise = rng.uniform(0.005, 0.02, n)
    high = close * (1 + noise)
    low = close * (1 - noise)
    open_ = close * (1 + rng.uniform(-0.01, 0.01, n))
    volume = rng.integers(1_000_000, 10_000_000, n).astype(float)

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    return df


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """300-bar synthetic OHLCV — enough warmup for MA200."""
    return _make_ohlcv(300)


@pytest.fixture
def long_ohlcv() -> pd.DataFrame:
    """500-bar synthetic OHLCV — enough warmup for MA200W resampling."""
    return _make_ohlcv(500)


@pytest.fixture
def short_ohlcv() -> pd.DataFrame:
    """30-bar OHLCV — tests edge cases with insufficient history."""
    return _make_ohlcv(30)


@pytest.fixture
def trending_up_ohlcv() -> pd.DataFrame:
    """Strong uptrend — price well above all MAs."""
    rng = np.random.default_rng(7)
    n = 300
    dates = pd.bdate_range(end="2024-12-31", periods=n)
    close = 100.0 + np.linspace(0, 100, n) + rng.normal(0, 0.5, n)
    high = close + rng.uniform(0.5, 2, n)
    low = close - rng.uniform(0.5, 2, n)
    open_ = close - rng.uniform(-1, 1, n)
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def trending_down_ohlcv() -> pd.DataFrame:
    """Strong downtrend — price well below all MAs."""
    rng = np.random.default_rng(13)
    n = 300
    dates = pd.bdate_range(end="2024-12-31", periods=n)
    close = 200.0 - np.linspace(0, 100, n) + rng.normal(0, 0.5, n)
    close = np.clip(close, 10, None)
    high = close + rng.uniform(0.5, 2, n)
    low = close - rng.uniform(0.5, 2, n)
    open_ = close - rng.uniform(-1, 1, n)
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def gap_ohlcv() -> pd.DataFrame:
    """OHLCV with deliberate gap days (open != prev close)."""
    rng = np.random.default_rng(99)
    n = 60
    dates = pd.bdate_range(end="2024-12-31", periods=n)
    close = np.full(n, 150.0)
    open_ = close.copy()
    high = close + 2
    low = close - 2

    # Introduce an upward gap on day 10: open 5 above prev close
    open_[10] = close[9] + 5
    high[10] = open_[10] + 2
    low[10] = open_[10] - 1
    close[10] = open_[10] + 1

    # Introduce a downward gap on day 30: open 5 below prev close
    open_[30] = close[29] - 5
    high[30] = open_[30] + 1
    low[30] = open_[30] - 2
    close[30] = open_[30] - 1

    volume = rng.integers(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def mock_quote() -> dict:
    """Fake live quote dict as returned by yfinance fast_info."""
    return {
        "regularMarketPrice": 152.0,
        "regularMarketDayHigh": 155.0,
        "regularMarketDayLow": 148.0,
        "regularMarketPreviousClose": 149.0,
    }
