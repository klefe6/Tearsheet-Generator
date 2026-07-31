"""Deterministic TCP layout-test support without live benchmark downloads."""
from __future__ import annotations

import os
import socket
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

import pandas as pd

from tcp_benchmarks import (
    BENCHMARK_STATUS_READY,
    BTC_DISPLAY_NAME,
    BTC_SYMBOL,
    ETH_DISPLAY_NAME,
    ETH_SYMBOL,
    SPXTR_DISPLAY_NAME,
    SPXTR_SYMBOL,
    BenchmarkResult,
)

TCP_LAYOUT_TEST_MODULES = frozenset(
    {
        "test_tcp_public_content.py",
        "test_tcp_public_shell.py",
        "test_tcp_access_daily_values.py",
        "test_tcp_admin_mutation_state.py",
        "test_tcp_benchmarks.py",
        "test_tcp_drawdown.py",
        "test_tcp_mobile_responsive.py",
        "test_tcp_layout_overlap_fixes.py",
        "test_tcp_desktop_visual_parity.py",
        "test_tcp_daily_values_collapse.py",
        "test_tcp_production_labeling.py",
        "test_tcp_hotfix_table_benchmark_auth.py",
        "test_tcp_admin.py",
        "test_tearsheet_password_gate.py",
        "test_tcp_v2_shell.py",
        "test_tcp_tkp_visual_parity.py",
        "test_tcp_layout_no_network.py",
    }
)


def deterministic_benchmark_returns(*, start: str = "2026-01-20", periods: int = 40) -> pd.Series:
    idx = pd.bdate_range(start=start, periods=periods)
    return pd.Series([0.001] * len(idx), index=idx, dtype=float)


def deterministic_benchmark_result(
    *,
    symbol: str,
    display_name: str,
    start: str = "2026-01-20",
    periods: int = 40,
) -> BenchmarkResult:
    series = deterministic_benchmark_returns(start=start, periods=periods)
    return BenchmarkResult(
        status=BENCHMARK_STATUS_READY,
        symbol=symbol,
        display_name=display_name,
        as_of=series.index[-1].strftime("%Y-%m-%d"),
        fetched_at="2026-01-01T00:00:00+00:00",
        returns=series,
        warning=None,
    )


SPXTR_LAYOUT_FIXTURE = deterministic_benchmark_result(
    symbol=SPXTR_SYMBOL,
    display_name=SPXTR_DISPLAY_NAME,
)
BTC_LAYOUT_FIXTURE = deterministic_benchmark_result(
    symbol=BTC_SYMBOL,
    display_name=BTC_DISPLAY_NAME,
)
ETH_LAYOUT_FIXTURE = deterministic_benchmark_result(
    symbol=ETH_SYMBOL,
    display_name=ETH_DISPLAY_NAME,
)


def _benchmark_loader(result: BenchmarkResult):
    def _loader(*, cache_path=None, provider=None, timeout_seconds=None, now=None):
        return result

    return _loader


@contextmanager
def tcp_layout_benchmark_patches() -> Iterator[None]:
    """Patch TCP benchmark loaders to deterministic fixtures for layout tests."""
    loaders = {
        "load_spxtr_benchmark": SPXTR_LAYOUT_FIXTURE,
        "load_spxtr_benchmark_cache_only": SPXTR_LAYOUT_FIXTURE,
        "load_btc_benchmark": BTC_LAYOUT_FIXTURE,
        "load_btc_benchmark_cache_only": BTC_LAYOUT_FIXTURE,
        "load_eth_benchmark": ETH_LAYOUT_FIXTURE,
        "load_eth_benchmark_cache_only": ETH_LAYOUT_FIXTURE,
    }
    with patch.dict(os.environ, {"TCP_V2_SKIP_BENCHMARK_FETCH": "1"}, clear=False):
        with patch("tcp_benchmarks._fetch_returns_with_timeout", side_effect=_blocked_network_fetch):
            patches = [
                patch(f"tcp_ts_v2.{name}", side_effect=_benchmark_loader(result))
                for name, result in loaders.items()
            ]
            for item in patches:
                item.start()
            try:
                yield
            finally:
                for item in reversed(patches):
                    item.stop()


def _blocked_network_fetch(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("TCP layout tests must not perform live benchmark downloads")


@contextmanager
def block_outbound_tcp_connect() -> Iterator[None]:
    """Fail fast if a layout test opens an outbound TCP connection."""
    original_socket = socket.socket

    def guarded_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
        if family == socket.AF_INET and type == socket.SOCK_STREAM:
            raise AssertionError("TCP layout test attempted outbound TCP network access")
        return original_socket(family, type, proto, fileno)

    with patch("socket.socket", side_effect=guarded_socket):
        yield
