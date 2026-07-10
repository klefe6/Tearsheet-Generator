"""Deterministic local benchmark fixtures for SPX, NDX, BTC.

No external API calls — every value is computed by a fixed formula keyed off
the date itself, so the same date always yields the same value regardless of
wall-clock time or network access. This is a placeholder: swap `_raw_value`
for a real cached ingestion lookup later (e.g. yfinance behind a cache, like
the tearsheet apps already do elsewhere in this repo) without touching any
caller — `benchmark_value` / `first_available_on_or_after` keep their
signatures.

Trading-day model: weekends have NO data (no holiday calendar modeled). This
mirrors real markets closely enough for a fixture, and gives callers a real
"missing data" case to exercise the roll-forward-and-warn fallback with.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

BENCHMARK_SYMBOLS = ["SPX", "NDX", "BTC"]

# Fixed reference point for the formula below — NOT "today". Keeps the fixture
# stable forever regardless of when it's evaluated.
_ANCHOR = date(2020, 1, 1)

# (linear drift per day, oscillation amplitude, period in days, phase offset).
# Chosen to give each symbol a distinct, smooth, deterministic shape. Not real
# market data.
_PARAMS: dict[str, tuple[float, float, float, float]] = {
    "SPX": (0.00025, 0.11, 22.0, 0.3),
    "NDX": (0.00040, 0.16, 20.0, 1.5),
    "BTC": (0.00080, 0.45, 14.0, 2.5),
}


def is_trading_day(on_date: date) -> bool:
    """Mon-Fri only — a simple open/closed proxy (no holiday calendar)."""
    return on_date.weekday() < 5


def _raw_value(symbol: str, on_date: date) -> float:
    drift, amp, period, phase = _PARAMS[symbol]
    n = (on_date - _ANCHOR).days
    return 100.0 * (1.0 + drift * n + amp * math.sin(2 * math.pi * n / period + phase))


def benchmark_value(symbol: str, on_date: date) -> Optional[float]:
    """Deterministic value for `symbol` on `on_date`, or None if the market is
    modeled as closed that day (weekend) or `symbol` is unknown."""
    if symbol not in _PARAMS or not is_trading_day(on_date):
        return None
    return _raw_value(symbol, on_date)


def first_available_on_or_after(
    symbol: str, start: date, max_lookahead_days: int = 14
) -> tuple[Optional[date], Optional[float]]:
    """Roll forward from `start` to the first date with data for `symbol`.

    Returns (date, value), or (None, None) if nothing is found within the
    lookahead window (defensive cap — a real trading calendar never has a gap
    this long).
    """
    for offset in range(max_lookahead_days + 1):
        d = start + timedelta(days=offset)
        v = benchmark_value(symbol, d)
        if v is not None:
            return d, v
    return None, None
