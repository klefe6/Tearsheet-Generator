"""Cached real benchmark closes for SPX / NDX / BTC (yfinance + CSV cache).

Pattern mirrors ``algominds_benchmark_daily.py`` in the parent tearsheet repo:
cache-first CSV files, optional yfinance fetch, no synthetic values in the
default path.

Tickers (documented):
  SPX -> ^GSPC  (S&P 500 price index — same as AGM fee workbook)
  NDX -> ^NDX   (Nasdaq-100 price index)
  BTC -> BTC-USD (Yahoo spot USD)
"""

from __future__ import annotations

import csv
import os
import warnings
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

BENCHMARK_SYMBOLS = ["SPX", "NDX", "BTC"]

SYMBOL_TICKERS: dict[str, str] = {
    "SPX": "^GSPC",
    "NDX": "^NDX",
    "BTC": "BTC-USD",
}

# Provenance values surfaced on GET /api/performance.
BENCHMARK_SOURCE_LIVE = "market_cache_live_fetch"
BENCHMARK_SOURCE_CACHED = "market_cache_cached"
BENCHMARK_SOURCE_UNAVAILABLE = "unavailable"
BENCHMARK_SOURCE_FIXTURE = "deterministic_fixture"  # tests only (BENCHMARK_ALLOW_FIXTURE)

BENCHMARK_ALIGN_POLICY = "prior_close_within_5_calendar_days"
MAX_PRIOR_CLOSE_GAP_DAYS = 5
MAX_FORWARD_LOOKAHEAD_DAYS = 14

CACHE_ONLY_ENV = "BENCHMARK_CACHE_ONLY"


@dataclass
class CloseResult:
    """A benchmark close aligned to a target calendar date."""

    value: Optional[float]
    as_of: Optional[date]
    warning: Optional[str] = None


@dataclass
class BenchmarkStore:
    """CSV-backed daily close cache with optional yfinance refresh."""

    cache_dir: Path
    cache_only: bool = False
    allow_fixture: bool = False
    fetcher: Optional[Callable[[str, date, date], dict[date, float]]] = None
    _closes: dict[str, dict[date, float]] = field(default_factory=dict)
    _live_fetch_used: bool = False

    def reset_session(self) -> None:
        self._live_fetch_used = False

    def session_source(self) -> Optional[str]:
        if self._live_fetch_used:
            return BENCHMARK_SOURCE_LIVE
        if any(self._closes.values()):
            return BENCHMARK_SOURCE_CACHED
        return None

    def _cache_path(self, symbol: str) -> Path:
        ticker = SYMBOL_TICKERS[symbol]
        safe = ticker.replace("^", "").replace("/", "_")
        return self.cache_dir / f"{safe}_daily.csv"

    def _read_cache_file(self, symbol: str) -> dict[date, float]:
        path = self._cache_path(symbol)
        out: dict[date, float] = {}
        if not path.is_file():
            return out
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    d = date.fromisoformat(row["Date"][:10])
                    out[d] = float(row["Close"])
                except (KeyError, ValueError, TypeError):
                    continue
        return out

    def _write_cache_file(self, symbol: str, closes: dict[date, float]) -> None:
        path = self._cache_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["Date", "Close"])
            writer.writeheader()
            for d in sorted(closes):
                writer.writerow({"Date": d.isoformat(), "Close": closes[d]})

    def _merged_closes(self, symbol: str) -> dict[date, float]:
        if symbol not in self._closes:
            self._closes[symbol] = self._read_cache_file(symbol)
        return self._closes[symbol]

    def ensure_range(self, symbol: str, start: date, end: date) -> None:
        """Load cache and optionally fetch missing range from yfinance."""
        if symbol not in SYMBOL_TICKERS:
            return

        closes = self._merged_closes(symbol)
        pad_start = start - timedelta(days=7)
        covered = closes and min(closes) <= pad_start and max(closes) >= end

        allow_fetch = not self.cache_only
        if os.environ.get(CACHE_ONLY_ENV, "").strip().lower() in ("1", "true", "yes"):
            allow_fetch = False

        if not covered and allow_fetch and self.fetcher is not None:
            try:
                fetched = self.fetcher(SYMBOL_TICKERS[symbol], pad_start, end)
            except Exception as exc:
                warnings.warn(f"benchmark fetch failed for {symbol}: {exc}")
                fetched = {}
            if fetched:
                closes = {**closes, **fetched}
                self._closes[symbol] = closes
                self._write_cache_file(symbol, closes)
                self._live_fetch_used = True

    def close_on_or_before(
        self, symbol: str, target: date, max_gap_days: int = MAX_PRIOR_CLOSE_GAP_DAYS
    ) -> CloseResult:
        """Latest close on or before ``target`` within ``max_gap_days``."""
        self.ensure_range(symbol, target - timedelta(days=max_gap_days + 3), target)
        closes = self._merged_closes(symbol)
        if not closes:
            return CloseResult(None, None, None)

        if target in closes:
            return CloseResult(closes[target], target, None)

        prior_dates = [d for d in closes if d <= target]
        if not prior_dates:
            return CloseResult(None, None, None)
        as_of = max(prior_dates)
        gap = (target - as_of).days
        if gap > max_gap_days:
            return CloseResult(
                None,
                None,
                f"{symbol}: no close within {max_gap_days}d before {target.isoformat()}.",
            )
        warn = None
        if gap > 0:
            warn = (
                f"{symbol}: no close on {target.isoformat()}; used prior close "
                f"from {as_of.isoformat()} ({gap}d earlier)."
            )
        return CloseResult(closes[as_of], as_of, warn)

    def close_on_or_after(
        self, symbol: str, target: date, max_lookahead: int = MAX_FORWARD_LOOKAHEAD_DAYS
    ) -> CloseResult:
        """First close on or after ``target`` (for program-start rebasing)."""
        self.ensure_range(symbol, target, target + timedelta(days=max_lookahead))
        closes = self._merged_closes(symbol)
        if not closes:
            return CloseResult(None, None, None)

        if target in closes:
            return CloseResult(closes[target], target, None)

        for offset in range(1, max_lookahead + 1):
            d = target + timedelta(days=offset)
            if d in closes:
                return CloseResult(
                    closes[d],
                    d,
                    f"{symbol} has no close on {target.isoformat()}; rebased from "
                    f"{d.isoformat()} instead.",
                )
        return CloseResult(None, None, f"{symbol}: no close within {max_lookahead}d after {target}.")


_store: Optional[BenchmarkStore] = None


def configure_store(store: BenchmarkStore) -> None:
    global _store
    _store = store


def get_store() -> BenchmarkStore:
    global _store
    if _store is None:
        from .config import Settings

        settings = Settings()
        _store = BenchmarkStore(
            cache_dir=Path(settings.benchmark_cache_dir),
            cache_only=settings.benchmark_cache_only,
            allow_fixture=settings.benchmark_allow_fixture,
            fetcher=_default_yfinance_fetch if not settings.benchmark_cache_only else None,
        )
    return _store


def _default_yfinance_fetch(ticker: str, start: date, end: date) -> dict[date, float]:
    import pandas as pd
    import yfinance as yf

    data = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if data is None or data.empty:
        return {}
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    out: dict[date, float] = {}
    for ts, val in close.items():
        if pd.isna(val):
            continue
        d = pd.Timestamp(ts).date()
        out[d] = float(val)
    return out


def aggregate_benchmark_source(
    requested: bool, resolved_count: int, store: BenchmarkStore
) -> Optional[str]:
    if not requested:
        return None
    if resolved_count > 0:
        return store.session_source() or BENCHMARK_SOURCE_CACHED
    return BENCHMARK_SOURCE_UNAVAILABLE
