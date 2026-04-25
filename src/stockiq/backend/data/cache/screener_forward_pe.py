"""
Local forward P/E and earnings growth cache.

Fields per ticker: forwardPE, forwardEps, trailingPE, earningsGrowth, revenueGrowth, pegRatio

Populated by: cache/scripts/build_forward_pe_cache.py (run weekly)
Cache file:   cache/screener/forward_pe.json
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent.parent.parent / "cache" / "screener" / "forward_pe.json"
_cache: dict | None = None


class ForwardPEData(TypedDict):
    forwardPE: float | None
    forwardEps: float | None
    trailingPE: float | None
    earningsGrowth: float | None
    revenueGrowth: float | None
    pegRatio: float | None


def get_forward_pe() -> dict[str, ForwardPEData]:
    """Return forward P/E dict from local cache, or empty dict if unavailable."""
    global _cache
    if _cache is not None:
        return _cache

    if not _CACHE_FILE.exists():
        logger.debug(
            "Forward P/E cache not found at %s — run cache/scripts/build_forward_pe_cache.py",
            _CACHE_FILE,
        )
        return {}

    try:
        _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        logger.info("Loaded forward P/E cache: %d tickers from %s", len(_cache), _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to load forward P/E cache (%s)", exc)
        return {}

    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
