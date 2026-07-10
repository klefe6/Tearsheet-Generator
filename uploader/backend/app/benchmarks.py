"""Benchmark lookup facade — delegates to :mod:`benchmark_store`."""

from __future__ import annotations

from .benchmark_store import (
    BENCHMARK_ALIGN_POLICY,
    BENCHMARK_SOURCE_CACHED,
    BENCHMARK_SOURCE_FIXTURE,
    BENCHMARK_SOURCE_LIVE,
    BENCHMARK_SOURCE_UNAVAILABLE,
    BENCHMARK_SYMBOLS,
    BenchmarkStore,
    CloseResult,
    SYMBOL_TICKERS,
    aggregate_benchmark_source,
    configure_store,
    get_store,
)

__all__ = [
    "BENCHMARK_ALIGN_POLICY",
    "BENCHMARK_SOURCE_CACHED",
    "BENCHMARK_SOURCE_FIXTURE",
    "BENCHMARK_SOURCE_LIVE",
    "BENCHMARK_SOURCE_UNAVAILABLE",
    "BENCHMARK_SYMBOLS",
    "BenchmarkStore",
    "CloseResult",
    "SYMBOL_TICKERS",
    "aggregate_benchmark_source",
    "configure_store",
    "get_store",
]
