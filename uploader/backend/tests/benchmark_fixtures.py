"""Helpers to seed benchmark CSV caches in tests."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from app.benchmark_store import SYMBOL_TICKERS


def cache_file_for_symbol(cache_dir: Path, symbol: str) -> Path:
    ticker = SYMBOL_TICKERS[symbol]
    safe = ticker.replace("^", "").replace("/", "_")
    return cache_dir / f"{safe}_daily.csv"


def write_daily_closes(cache_dir: Path, symbol: str, rows: list[tuple[date, float]]) -> None:
    path = cache_file_for_symbol(cache_dir, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Date", "Close"])
        writer.writeheader()
        for d, close in sorted(rows, key=lambda r: r[0]):
            writer.writerow({"Date": d.isoformat(), "Close": close})


def seed_standard_benchmark_window(cache_dir: Path, anchor_monday: date) -> None:
    """Weekday closes for ~6 weeks around ``anchor_monday`` (deterministic values)."""
    rows_spx: list[tuple[date, float]] = []
    rows_ndx: list[tuple[date, float]] = []
    rows_btc: list[tuple[date, float]] = []
    start = anchor_monday - timedelta(days=14)
    for i in range(60):
        d = start + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        offset = (d - anchor_monday).days
        rows_spx.append((d, 5000.0 + offset * 10))
        rows_ndx.append((d, 18000.0 + offset * 25))
        rows_btc.append((d, 60000.0 + offset * 100))
    write_daily_closes(cache_dir, "SPX", rows_spx)
    write_daily_closes(cache_dir, "NDX", rows_ndx)
    write_daily_closes(cache_dir, "BTC", rows_btc)
