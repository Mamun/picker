"""
Frontend visual configuration loaded from config/app.yml.

Backend data parameters (MA_PERIODS, FIB_LEVELS, ticker universes, CACHE_TTL)
live in stockiq.backend.config.
"""
from pathlib import Path

import yaml

_cfg_path = Path(__file__).parent.parent.parent / "config" / "app.yml"
with open(_cfg_path) as _f:
    _cfg: dict = yaml.safe_load(_f)

# ── Moving averages ────────────────────────────────────────────────────────────
_ma = _cfg["moving_averages"]
MA_COLORS:    dict[int, str] = {int(k): v for k, v in _ma["colors"].items()}
MA200W_COLOR: str             = _ma["weekly_ma200_color"]

# ── Fibonacci ──────────────────────────────────────────────────────────────────
FIB_COLORS: list[str] = _cfg["fibonacci"]["colors"]

# ── Reversal patterns ──────────────────────────────────────────────────────────
REVERSAL_PATTERNS: list[tuple] = [
    (p["col"], p["label"], p["bullish"], p["symbol"], p["color"])
    for p in _cfg["reversal_patterns"]
]

# ── Chart period options ───────────────────────────────────────────────────────
PERIOD_OPTIONS: dict[str, int] = _cfg["period_options"]
