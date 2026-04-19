"""
GCS-backed fundamentals cache (Munger-style quality metrics).

Fields per ticker: returnOnEquity, profitMargins, revenueGrowth, debtToEquity, earningsGrowth
Updated quarterly (earnings cycle) via scripts/build_fundamentals_cache.py.

GCS object path: screener/fundamentals.json
Schema: {"AAPL": {"returnOnEquity": 1.47, "profitMargins": 0.26, ...}, ...}
"""

import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)

_GCS_OBJECT = "screener/fundamentals.json"
_cache: dict | None = None


class FundamentalsData(TypedDict):
    returnOnEquity: float | None
    profitMargins: float | None
    revenueGrowth: float | None
    debtToEquity: float | None
    earningsGrowth: float | None


def get_fundamentals() -> dict[str, FundamentalsData]:
    """Return fundamentals dict from GCS, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        logger.debug("GCS_BUCKET not set — fundamentals cache unavailable")
        _cache = {}
        return _cache

    try:
        from google.cloud import storage

        client = storage.Client()
        blob   = client.bucket(bucket_name).blob(_GCS_OBJECT)

        if not blob.exists():
            logger.warning("GCS fundamentals not found at gs://%s/%s", bucket_name, _GCS_OBJECT)
            _cache = {}
            return _cache

        _cache = json.loads(blob.download_as_text(encoding="utf-8"))
        logger.info("Loaded GCS fundamentals: %d tickers from gs://%s/%s",
                    len(_cache), bucket_name, _GCS_OBJECT)
    except Exception as exc:
        logger.warning("Failed to load GCS fundamentals (%s) — will call yfinance", exc)
        _cache = {}

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
