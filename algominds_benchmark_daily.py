"""
Algominds / Momentum Pacer — daily benchmark loader + cache (AGM-only).

Provides DAILY S&P 500 / Nasdaq-100 index closes for the AGM tearsheet charts
and the daily fee-accrual engine.

Ticker choice (documented, verified against the fee workbook)
-------------------------------------------------------------
The AlgoMinds Disclosure Document defines the incentive-fee Benchmark as the
S&P 500 return using official month-end closes (WSJ). Every SPX level in
"Momentum Fee Calculation.xlsx" (Summary + per-month detail sheets) matches the
S&P 500 PRICE index close from Yahoo Finance's ``^GSPC`` exactly (e.g. Nov 2025
end 6849.09, Apr 2026 end 7209.01) — NOT the total-return index ``^SP500TR``.
So the daily benchmark here is:

    SPX_TICKER = "^GSPC"   (S&P 500 price index — same series the workbook uses)
    NDX_TICKER = "^NDX"    (Nasdaq-100 price index — client-chart benchmark)

The workbook's November 2025 "month start" level (6737.49) is the ^GSPC close
on 2025-11-13, the program's live-inception day: the first fee month is
anchored at inception, subsequent months at the prior month-end close.

Cache policy
------------
Daily closes are cached as small CSVs under ``Momentum Pacer/data/benchmarks``
(committed to the repo so tests and offline servers never need the network).
The loader only calls yfinance when the cache does not already cover the
requested date range; set env ``AGM_BENCHMARK_CACHE_ONLY=1`` to forbid network
access entirely (tests / air-gapped runtime).

Alignment / missing-data policy
-------------------------------
``align_to_dates`` reindexes benchmark closes onto the AGM CSV's trading days
and forward-fills ONLY across short calendar gaps (default 5 days: weekends,
holidays). Larger gaps are left as NaN — never silently forward-filled — so a
hole in benchmark data is visible instead of fabricated.

Safe to import: no server start; network is used only inside
``load_daily_benchmark`` when the cache is insufficient and fetching is allowed.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd

# S&P 500 price index — matches the fee workbook / Disclosure Document benchmark.
SPX_TICKER = "^GSPC"
# Nasdaq-100 price index — the client chart's second benchmark.
NDX_TICKER = "^NDX"

CACHE_DIR = Path(__file__).resolve().parent / "Momentum Pacer" / "data" / "benchmarks"

# Forward-fill benchmark closes over calendar gaps up to this many days
# (weekend + holiday clusters); anything longer stays NaN.
DEFAULT_MAX_FFILL_DAYS = 5

CACHE_ONLY_ENV = "AGM_BENCHMARK_CACHE_ONLY"


def cache_path(symbol: str) -> Path:
    """CSV cache file for *symbol* (``^GSPC`` -> ``GSPC_daily.csv``)."""
    safe = symbol.replace("^", "").replace("/", "_")
    return CACHE_DIR / f"{safe}_daily.csv"


def _read_cache(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=["Date", "Close"])
    df = pd.read_csv(path)
    if "Date" not in df.columns or "Close" not in df.columns:
        return pd.DataFrame(columns=["Date", "Close"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
    return df


def _write_cache(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df[["Date", "Close"]].copy()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def _yfinance_fetch(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Fetch daily closes from yfinance. yf's *end* is exclusive, so pad +1 day."""
    import yfinance as yf

    data = yf.download(
        symbol,
        start=start.strftime("%Y-%m-%d"),
        end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    if data is None or data.empty:
        return pd.DataFrame(columns=["Date", "Close"])
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    out = close.reset_index()
    out.columns = ["Date", "Close"]
    out["Date"] = pd.to_datetime(out["Date"]).dt.tz_localize(None).dt.normalize()
    return out


def load_daily_benchmark(
    symbol: str,
    start,
    end,
    cache_file: Optional[os.PathLike | str] = None,
    fetcher: Optional[Callable[[str, pd.Timestamp, pd.Timestamp], pd.DataFrame]] = None,
    allow_fetch: bool = True,
) -> pd.DataFrame:
    """
    Daily closes for *symbol* covering [start, end], cache-first.

    Returns a DataFrame with columns Date (datetime64) / Close (float), sorted
    ascending, restricted to the requested range. Only fetches when the cache
    does not already span the range; a fetch failure falls back to whatever the
    cache holds (possibly empty) with a warning — it never raises.
    """
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    path = Path(cache_file) if cache_file is not None else cache_path(symbol)

    cached = _read_cache(path)
    covered = (
        not cached.empty
        and cached["Date"].min() <= start
        and cached["Date"].max() >= end
    )

    if os.environ.get(CACHE_ONLY_ENV, "").strip() in ("1", "true", "yes"):
        allow_fetch = False

    if not covered and allow_fetch:
        fetch = fetcher if fetcher is not None else _yfinance_fetch
        try:
            fetched = fetch(symbol, start - pd.Timedelta(days=7), end)
        except Exception as exc:  # network / provider failure — fall back to cache
            warnings.warn(f"benchmark fetch failed for {symbol}: {exc}")
            fetched = pd.DataFrame(columns=["Date", "Close"])
        if not fetched.empty:
            frames = [f for f in (cached, fetched) if not f.empty]
            merged = (
                pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset=["Date"], keep="last")
                .sort_values("Date")
                .reset_index(drop=True)
            )
            _write_cache(path, merged)
            cached = merged

    mask = (cached["Date"] >= start) & (cached["Date"] <= end)
    return cached.loc[mask].reset_index(drop=True)


def align_to_dates(
    bench_df: pd.DataFrame,
    dates: Sequence,
    max_ffill_days: int = DEFAULT_MAX_FFILL_DAYS,
) -> pd.Series:
    """
    Benchmark Close for each date in *dates* (the AGM CSV trading days).

    A date missing from the benchmark series takes the most recent prior close,
    but only if that close is at most *max_ffill_days* calendar days old —
    holiday/weekend gaps get filled, long data holes stay NaN (never silently
    forward-filled). Dates before the first benchmark row are NaN.
    """
    idx = pd.DatetimeIndex([pd.Timestamp(d).normalize() for d in dates])
    if bench_df is None or bench_df.empty:
        return pd.Series([float("nan")] * len(idx), index=idx, name="Close")

    ser = bench_df.set_index("Date")["Close"].sort_index()
    aligned = ser.reindex(idx)
    if aligned.isna().any():
        # For each missing date, look up the last available close and its age.
        prev_pos = ser.index.searchsorted(idx, side="right") - 1
        for i, (dt, val) in enumerate(zip(idx, aligned.values)):
            if pd.notna(val):
                continue
            p = prev_pos[i]
            if p < 0:
                continue  # before benchmark history starts
            gap_days = (dt - ser.index[p]).days
            if gap_days <= max_ffill_days:
                aligned.iloc[i] = ser.iloc[p]
    aligned.name = "Close"
    return aligned


def rebase(closes: pd.Series, base_value: float) -> pd.Series:
    """
    Rebase a close series so its first non-NaN value equals *base_value*
    (e.g. SPX rebased to the $30,000 starting capital on the chart start date).
    """
    valid = closes.dropna()
    if valid.empty:
        return closes * float("nan")
    first = float(valid.iloc[0])
    if first == 0:
        return closes * float("nan")
    return closes / first * float(base_value)
