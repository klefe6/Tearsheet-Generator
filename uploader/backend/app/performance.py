"""Normalized $100,000 performance series.

For now this is **deterministic mock data** whose only job is to unblock the
frontend. Each series starts at exactly the normalization base (100,000) and
walks a smooth, reproducible path (no randomness, so tests are stable). It can
later be swapped for a series derived from the stored daily rows without
changing the response shape.

Series returned: TKP, TCP, AGM, YQ (the four programs) plus SPX, NDX, BTC
(benchmarks). YQ == "Y&Q".
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

SERIES_KEYS = ["TKP", "TCP", "AGM", "YQ", "SPX", "NDX", "BTC"]

# (daily drift, oscillation amplitude, period in days, phase offset)
# Chosen to give each line a distinct, plausible-looking but fully deterministic
# shape. Nothing here is real market data.
_PARAMS: dict[str, tuple[float, float, float, float]] = {
    "TKP": (0.00045, 0.010, 21.0, 0.0),
    "TCP": (0.00035, 0.008, 25.0, 0.6),
    "AGM": (0.00060, 0.014, 18.0, 1.2),
    "YQ": (0.00030, 0.009, 30.0, 2.0),
    "SPX": (0.00025, 0.011, 22.0, 0.3),
    "NDX": (0.00040, 0.016, 20.0, 1.5),
    "BTC": (0.00080, 0.045, 14.0, 2.5),
}


def build_performance(
    base: float = 100_000.0,
    points: int = 90,
    as_of: Optional[date] = None,
) -> dict:
    """Build the normalized performance payload.

    Args:
        base: starting (normalized) value for every series.
        points: number of daily points per series.
        as_of: last date in the series (defaults to today).
    """
    end = as_of or date.today()
    dates = [(end - timedelta(days=(points - 1 - i))).isoformat() for i in range(points)]

    series: dict[str, list[dict]] = {}
    for key, (drift, amp, period, phase) in _PARAMS.items():
        values: list[float] = []
        v = base
        for i in range(points):
            if i > 0:
                daily_return = drift + amp * math.sin(2 * math.pi * i / period + phase)
                v = v * (1.0 + daily_return)
            values.append(round(v, 2))
        series[key] = [{"date": d, "value": val} for d, val in zip(dates, values)]

    return {
        "as_of": end.isoformat(),
        "normalization_base": base,
        "points": points,
        "series_keys": SERIES_KEYS,
        "series": series,
        "note": "Mock/deterministic data — unblock-the-frontend placeholder.",
    }
