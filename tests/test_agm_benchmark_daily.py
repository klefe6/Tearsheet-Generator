"""Daily SPX/NDX benchmark loader tests (algominds_benchmark_daily).

All deterministic: fixture frames / local cache CSVs only — a stub fetcher
that raises proves no live yfinance call ever happens in tests. The benchmark
cache lives on the ops machine like the balances CSV (repo gitignores *.csv);
a fresh deployment populates it from yfinance once, then runs offline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import algominds_benchmark_daily as ab
import algominds_daily_balances as adb

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Momentum Pacer" / "data" / "daily_balances" / adb.DAILY_BALANCES_FILENAME


def _bench(dates_closes) -> pd.DataFrame:
    return pd.DataFrame(
        {"Date": pd.to_datetime([d for d, _ in dates_closes]),
         "Close": [c for _, c in dates_closes]}
    )


def _raising_fetcher(symbol, start, end):
    raise AssertionError("network fetch attempted during tests")


# ── Ticker / cache contract ──────────────────────────────────────────────────

def test_ticker_is_price_index_gspc():
    # The workbook / Disclosure Document benchmark is the S&P 500 PRICE index
    # (its SPX levels match ^GSPC closes exactly), not the total-return index.
    assert ab.SPX_TICKER == "^GSPC"
    assert ab.NDX_TICKER == "^NDX"


def test_local_cache_covers_agm_csv_range():
    bal = adb.load_daily_balances(CSV_PATH)
    for symbol in (ab.SPX_TICKER, ab.NDX_TICKER):
        path = ab.cache_path(symbol)
        assert path.is_file(), f"missing local benchmark cache {path}"
        cached = pd.read_csv(path, parse_dates=["Date"])
        assert cached["Date"].min() <= bal["Date"].min()
        assert cached["Date"].max() >= bal["Date"].max()


def test_cache_hit_never_fetches():
    bal = adb.load_daily_balances(CSV_PATH)
    out = ab.load_daily_benchmark(
        ab.SPX_TICKER, bal["Date"].min(), bal["Date"].max(),
        fetcher=_raising_fetcher,
    )
    assert not out.empty
    assert out["Date"].min() <= bal["Date"].min()
    assert out["Date"].max() >= bal["Date"].max()


def test_cache_only_env_blocks_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv(ab.CACHE_ONLY_ENV, "1")
    called = []

    def fetcher(symbol, start, end):
        called.append(symbol)
        return _bench([("2026-01-02", 100.0)])

    out = ab.load_daily_benchmark(
        "^TEST", "2026-01-01", "2026-01-31",
        cache_file=tmp_path / "TEST_daily.csv", fetcher=fetcher,
    )
    assert called == []
    assert out.empty


def test_fetch_populates_cache_and_slices_range(tmp_path, monkeypatch):
    monkeypatch.delenv(ab.CACHE_ONLY_ENV, raising=False)
    fixture = _bench([
        ("2025-12-31", 99.0),
        ("2026-01-02", 100.0),
        ("2026-01-05", 101.0),
        ("2026-02-02", 105.0),
    ])
    cache_file = tmp_path / "TEST_daily.csv"
    out = ab.load_daily_benchmark(
        "^TEST", "2026-01-01", "2026-01-31",
        cache_file=cache_file, fetcher=lambda s, a, b: fixture,
    )
    assert cache_file.is_file()
    assert list(out["Close"]) == [100.0, 101.0]  # sliced to requested range
    # Second call is served entirely from the cache written above.
    again = ab.load_daily_benchmark(
        "^TEST", "2026-01-01", "2026-01-31",
        cache_file=cache_file, fetcher=_raising_fetcher,
    )
    assert list(again["Close"]) == [100.0, 101.0]


def test_fetch_failure_falls_back_to_cache_not_exception(tmp_path, monkeypatch):
    monkeypatch.delenv(ab.CACHE_ONLY_ENV, raising=False)

    def broken(symbol, start, end):
        raise ConnectionError("offline")

    with pytest.warns(UserWarning):
        out = ab.load_daily_benchmark(
            "^TEST", "2026-01-01", "2026-01-31",
            cache_file=tmp_path / "TEST_daily.csv", fetcher=broken,
        )
    assert out.empty  # honest empty result, no crash, nothing fabricated


# ── Alignment policy ─────────────────────────────────────────────────────────

def test_align_fills_short_holiday_gaps_only():
    bench = _bench([
        ("2026-01-02", 100.0),
        ("2026-01-05", 101.0),
        # long hole: nothing until Feb 2
        ("2026-02-02", 105.0),
    ])
    dates = pd.to_datetime([
        "2026-01-02",
        "2026-01-06",  # 1 day after last close -> filled with 101
        "2026-01-20",  # 15 days after last close -> NOT filled (honest NaN)
        "2026-02-02",
    ])
    aligned = ab.align_to_dates(bench, dates, max_ffill_days=5)
    assert aligned.iloc[0] == 100.0
    assert aligned.iloc[1] == 101.0
    assert pd.isna(aligned.iloc[2])
    assert aligned.iloc[3] == 105.0


def test_align_before_history_start_is_nan():
    bench = _bench([("2026-01-05", 101.0)])
    aligned = ab.align_to_dates(bench, pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert pd.isna(aligned.iloc[0])
    assert aligned.iloc[1] == 101.0


def test_align_to_agm_csv_dates_is_complete():
    """The committed SPX cache aligns onto every AGM CSV trading day."""
    bal = adb.load_daily_balances(CSV_PATH)
    spx = ab.load_daily_benchmark(
        ab.SPX_TICKER, bal["Date"].min() - pd.Timedelta(days=10),
        bal["Date"].max(), fetcher=_raising_fetcher,
    )
    aligned = ab.align_to_dates(spx, bal["Date"])
    assert len(aligned) == len(bal)
    assert not aligned.isna().any()


def test_rebase_to_starting_capital():
    ser = pd.Series([50.0, 55.0, 60.5])
    rebased = ab.rebase(ser, 30_000.0)
    assert rebased.iloc[0] == pytest.approx(30_000.0)
    assert rebased.iloc[1] == pytest.approx(33_000.0)
    assert rebased.iloc[2] == pytest.approx(36_300.0)
