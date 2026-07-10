"""Unit tests for benchmark_store — cache, alignment, provenance."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.benchmark_store import (
    BENCHMARK_SOURCE_CACHED,
    BENCHMARK_SOURCE_UNAVAILABLE,
    BenchmarkStore,
    aggregate_benchmark_source,
)
from tests.benchmark_fixtures import seed_standard_benchmark_window, write_daily_closes


def _tmp_cache() -> Path:
    root = Path(__file__).resolve().parent / "_tmp"
    root.mkdir(exist_ok=True)
    d = root / f"bench_unit_{uuid4().hex}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_close_on_or_before_uses_prior_weekday_close():
    cache = _tmp_cache()
    monday = date(2026, 7, 6)
    wednesday = monday + timedelta(days=2)
    write_daily_closes(cache, "SPX", [(monday, 5000.0)])
    store = BenchmarkStore(cache_dir=cache, cache_only=True)
    result = store.close_on_or_before("SPX", wednesday)
    assert result.value == 5000.0
    assert result.as_of == monday
    assert result.warning is not None


def test_close_on_or_after_rolls_forward_from_weekend():
    cache = _tmp_cache()
    saturday = date(2026, 7, 11)
    monday = date(2026, 7, 13)
    write_daily_closes(cache, "SPX", [(monday, 5100.0)])
    store = BenchmarkStore(cache_dir=cache, cache_only=True)
    result = store.close_on_or_after("SPX", saturday)
    assert result.value == 5100.0
    assert result.as_of == monday
    assert result.warning is not None


def test_no_cache_and_cache_only_returns_unavailable_aggregate():
    cache = _tmp_cache()
    store = BenchmarkStore(cache_dir=cache, cache_only=True)
    store.reset_session()
    assert aggregate_benchmark_source(True, 0, store) == BENCHMARK_SOURCE_UNAVAILABLE


def test_cached_data_reports_cached_provenance():
    cache = _tmp_cache()
    seed_standard_benchmark_window(cache, date(2026, 7, 6))
    store = BenchmarkStore(cache_dir=cache, cache_only=True)
    store.reset_session()
    result = store.close_on_or_before("SPX", date(2026, 7, 6))
    assert result.value is not None
    assert aggregate_benchmark_source(True, 1, store) == BENCHMARK_SOURCE_CACHED


def test_injected_fetcher_never_uses_synthetic_values():
    cache = _tmp_cache()

    def fake_fetch(ticker: str, start: date, end: date) -> dict[date, float]:
        out: dict[date, float] = {}
        d = start
        while d <= end:
            out[d] = 1234.56
            d += timedelta(days=1)
        return out

    store = BenchmarkStore(cache_dir=cache, fetcher=fake_fetch)
    store.ensure_range("SPX", date(2026, 7, 1), date(2026, 7, 10))
    val = store.close_on_or_before("SPX", date(2026, 7, 1)).value
    assert val == 1234.56
