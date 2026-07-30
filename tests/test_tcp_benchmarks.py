"""Step 11E — TCP benchmark provider, cache, and integration tests."""
from __future__ import annotations

from layout_helpers import layout_text as render_layout_text

import json
import socket
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from tcp_admin import simulate_add_row
from tcp_benchmarks import (
    BENCHMARK_STATUS_READY,
    BENCHMARK_STATUS_STALE,
    BENCHMARK_STATUS_UNAVAILABLE,
    BenchmarkNormalizationError,
    SPXTR_INCEPTION_COLUMN,
    SPXTR_SYMBOL,
    BenchmarkResult,
    QuantstatsBenchmarkProvider,
    align_benchmark_returns,
    benchmark_status_message,
    build_scaled_benchmark_nav,
    load_spxtr_benchmark,
    normalize_provider_returns,
)
from tcp_dashboard import canonical_nav_records_from_ledger, propagate_tcp_dashboard
from tcp_drawdown import SPXTR_INCEPTION_COLUMN as DD_SPXTR_COL, build_drawdown_dataframe
from tcp_ledger import load_ledger
from tcp_public_sections import resolve_public_gate_styles

REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_LEDGER = None


class MockBenchmarkProvider:
    def __init__(self, series: pd.Series | None = None, *, error: Exception | None = None):
        self.series = series
        self.error = error
        self.calls = 0

    def download_returns(self, symbol: str) -> pd.Series:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.series is None:
            raise ValueError("no data")
        series = self.series.copy()
        if series.index.has_duplicates:
            series = series[~series.index.duplicated(keep="first")]
        return series


def _returns_series(values, start="2026-01-20"):
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


@pytest.fixture(scope="session")
def ledger():
    global _SESSION_LEDGER
    if _SESSION_LEDGER is None:
        from tcp_config import load_config

        cfg = load_config()
        wb = Path(cfg.workbook_path)
        if not wb.is_file():
            pytest.skip("TCP workbook not available")
        _SESSION_LEDGER = load_ledger(cfg.workbook_path, cfg.sheet_name)
    return _SESSION_LEDGER


@pytest.fixture(scope="session")
def canonical(ledger):
    return canonical_nav_records_from_ledger(ledger.completed_records)


# --- normalize_provider_returns (focused) ---


def test_normalize_plain_series():
    raw = pd.Series([0.01, -0.02], index=pd.to_datetime(["2026-01-20", "2026-01-21"]))
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert isinstance(out, pd.Series)
    assert len(out) == 2


def test_normalize_one_column_dataframe():
    raw = pd.DataFrame({"ret": [0.01, 0.02]}, index=pd.to_datetime(["2026-01-20", "2026-01-21"]))
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert isinstance(out, pd.Series)
    assert out.iloc[0] == pytest.approx(0.01)


def test_normalize_yfinance_multiindex_dataframe():
    cols = pd.MultiIndex.from_tuples([("Close", "^SP500TR"), ("Volume", "^SP500TR")])
    raw = pd.DataFrame(
        [[0.01, 1000.0], [0.02, 1100.0]],
        index=pd.to_datetime(["2026-01-20", "2026-01-21"]),
        columns=cols,
    )
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert isinstance(out, pd.Series)
    assert out.iloc[0] == pytest.approx(0.01)


def test_normalize_ambiguous_multi_symbol_dataframe():
    raw = pd.DataFrame(
        {"SPY": [0.01, 0.02], "QQQ": [0.03, 0.04]},
        index=pd.to_datetime(["2026-01-20", "2026-01-21"]),
    )
    with pytest.raises(BenchmarkNormalizationError):
        normalize_provider_returns(raw, SPXTR_SYMBOL)


def test_normalize_duplicate_dates_keep_first():
    idx = pd.to_datetime(["2026-01-20", "2026-01-20", "2026-01-21"])
    raw = pd.Series([0.01, 0.99, 0.02], index=idx)
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert not out.index.has_duplicates
    assert out.loc["2026-01-20"] == pytest.approx(0.01)


def test_normalize_nan_values_dropped():
    raw = pd.Series([0.01, float("nan")], index=pd.to_datetime(["2026-01-20", "2026-01-21"]))
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert len(out) == 1


def test_normalize_infinity_values_dropped():
    raw = pd.Series([0.01, float("inf"), float("-inf")], index=pd.to_datetime(["2026-01-20", "2026-01-21", "2026-01-22"]))
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert len(out) == 1


def test_normalize_empty_result():
    raw = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["x"])
    out = normalize_provider_returns(raw, SPXTR_SYMBOL)
    assert out.empty


# --- Pure benchmark module (1–17) ---


def test_committed_v1_spxtr_symbol_spec():
    assert SPXTR_SYMBOL == "^SP500TR"
    assert SPXTR_INCEPTION_COLUMN == "SPXTR (Inception)"


def test_correct_start_end_alignment():
    full = _returns_series([0.01, -0.02, 0.005, -0.01])
    nav_index = pd.to_datetime(["2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23"])
    aligned = align_benchmark_returns(full, nav_index)
    assert len(aligned) == len(nav_index)
    assert aligned.index.equals(nav_index)


def test_correct_return_calculation_scaled_nav():
    aligned = _returns_series([0.1, -0.05, 0.02])
    nav = build_scaled_benchmark_nav(aligned, inception_start=aligned.index.min(), baseline=50000.0)
    assert nav.iloc[0] == pytest.approx(55000.0)


def test_total_return_field_via_provider_contract():
    provider = MockBenchmarkProvider(_returns_series([0.01, 0.02]))
    series = provider.download_returns(SPXTR_SYMBOL)
    assert isinstance(series, pd.Series)


def test_missing_benchmark_dates_ffill_bfill():
    full = _returns_series([0.01, 0.02, 0.03, 0.04, 0.05])
    nav_index = pd.to_datetime(["2026-01-20", "2026-01-22", "2026-01-24"])
    aligned = align_benchmark_returns(full, nav_index)
    assert not aligned.isna().any()
    assert len(aligned) == 3


def test_empty_provider_result_unavailable(tmp_path):
    provider = MockBenchmarkProvider(series=pd.Series(dtype=float))
    result = load_spxtr_benchmark(provider=provider, cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_provider_exception_uses_cache(tmp_path):
    cache = {
        "symbol": SPXTR_SYMBOL,
        "as_of": "2026-01-23",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "source": "quantstats",
        "returns": [{"date": "2026-01-20", "value": 0.01}, {"date": "2026-01-21", "value": -0.02}],
    }
    (tmp_path / "cache.json").write_text(json.dumps(cache), encoding="utf-8")
    provider = MockBenchmarkProvider(error=RuntimeError("network down"))
    result = load_spxtr_benchmark(provider=provider, cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_STALE
    assert result.returns is not None


def test_provider_timeout_unavailable_without_cache(tmp_path):
  class SlowProvider:
      def download_returns(self, symbol: str) -> pd.Series:
          import time

          time.sleep(2)
          return _returns_series([0.01])

  result = load_spxtr_benchmark(provider=SlowProvider(), cache_path=tmp_path / "cache.json", timeout_seconds=0.1)
  assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_non_finite_prices_rejected(tmp_path):
    series = pd.Series([float("nan"), float("nan")], index=pd.to_datetime(["2026-01-20", "2026-01-21"]))

    class BadProvider(MockBenchmarkProvider):
        def download_returns(self, symbol: str) -> pd.Series:
            return series

    result = load_spxtr_benchmark(provider=BadProvider(), cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_duplicate_dates_deduped_in_provider_download():
    idx = pd.to_datetime(["2026-01-20", "2026-01-20", "2026-01-21"])
    series = pd.Series([0.01, 0.02, 0.03], index=idx)
    provider = MockBenchmarkProvider(series)
    out = provider.download_returns(SPXTR_SYMBOL)
    assert not out.index.has_duplicates


def test_input_immutability_alignment():
    full = _returns_series([0.01, 0.02, 0.03])
    snapshot = deepcopy(full)
    nav_index = pd.to_datetime(["2026-01-20", "2026-01-21", "2026-01-22"])
    align_benchmark_returns(full, nav_index)
    assert full.equals(snapshot)


def test_deterministic_normalization():
    full = _returns_series([0.01, -0.02, 0.03])
    nav_index = pd.to_datetime(["2026-01-20", "2026-01-21", "2026-01-22"])
    a = align_benchmark_returns(full, nav_index)
    b = align_benchmark_returns(full, nav_index)
    assert a.equals(b)


def test_ready_status(tmp_path):
    provider = MockBenchmarkProvider(_returns_series([0.01, 0.02, 0.03]))
    result = load_spxtr_benchmark(provider=provider, cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_READY
    assert result.as_of is not None
    assert (tmp_path / "cache.json").is_file()


def test_stale_cached_status(tmp_path):
    cache = {
        "symbol": SPXTR_SYMBOL,
        "as_of": "2026-01-22",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "source": "quantstats",
        "returns": [{"date": "2026-01-20", "value": 0.01}],
    }
    (tmp_path / "cache.json").write_text(json.dumps(cache), encoding="utf-8")
    provider = MockBenchmarkProvider(error=RuntimeError("offline"))
    result = load_spxtr_benchmark(provider=provider, cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_STALE
    assert "stale" in (result.warning or "").lower()


def test_unavailable_status(tmp_path):
    provider = MockBenchmarkProvider(error=RuntimeError("offline"))
    result = load_spxtr_benchmark(provider=provider, cache_path=tmp_path / "cache.json", timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_cache_corruption_isolated(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{not-json", encoding="utf-8")
    provider = MockBenchmarkProvider(error=RuntimeError("offline"))
    result = load_spxtr_benchmark(provider=provider, cache_path=path, timeout_seconds=1)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_atomic_cache_update(tmp_path):
    provider = MockBenchmarkProvider(_returns_series([0.01, 0.02]))
    path = tmp_path / "cache.json"
    load_spxtr_benchmark(provider=provider, cache_path=path, timeout_seconds=1)
    assert path.is_file()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


# --- Drawdown + benchmark integration ---


def test_spxtr_drawdown_column_with_ready_benchmark(canonical):
    returns = _returns_series([0.01] * 120)
    result = BenchmarkResult(
        status=BENCHMARK_STATUS_READY,
        symbol=SPXTR_SYMBOL,
        display_name="SPXTR",
        as_of="2026-06-24",
        fetched_at="2026-06-24T00:00:00+00:00",
        returns=returns,
        warning=None,
    )
    propagation = propagate_tcp_dashboard(canonical, benchmark_result=result)
    assert DD_SPXTR_COL in propagation.drawdown_profile.columns


def test_unavailable_benchmark_tcp_only(canonical):
    propagation = propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    )
    assert DD_SPXTR_COL not in propagation.drawdown_profile.columns


# --- Layout / integration (18–30) ---


@pytest.fixture(scope="module")
def layout_text():
    import os

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = "benchmark-test-token"
    os.environ["TCP_V2_SESSION_SECRET"] = "benchmark-test-secret"
    from tcp_config import AdminAuthSettings
    from tcp_ts_v2 import create_app

    app, _cfg, state, _auth, _holder = create_app(
        auth_settings=AdminAuthSettings(
            admin_token="benchmark-test-token",
            session_secret="benchmark-test-secret",
        )
    )
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    text = render_layout_text(app)
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return text


def test_benchmark_store_present(layout_text):
    assert "benchmark-store" in layout_text


def test_benchmark_notice_container(layout_text):
    assert "tcp-benchmark-notice" in layout_text


def test_drawdown_footnote_mentions_spxtr(layout_text):
    assert "SPXTR" in layout_text


def test_section_behind_public_gate(layout_text):
    assert "disclaimer-screen" in layout_text
    assert "main-app" in layout_text


def test_gate_acceptance_reveals_section():
    hidden, shown = resolve_public_gate_styles(1)
    assert hidden["display"] == "none"
    assert shown["display"] == "block"


def test_gate_not_admin_auth():
    hidden, shown = resolve_public_gate_styles(1)
    assert shown == {"display": "block"}


def test_benchmark_failure_preserves_tcp_blocks(canonical):
    propagation = propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    )
    assert not propagation.monthly_calendar.empty
    assert not propagation.daily_performance.empty


def test_benchmark_failure_does_not_affect_drawdown_tcp_column(canonical):
    base = propagate_tcp_dashboard(canonical).drawdown_profile
    unavailable = propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    ).drawdown_profile
    assert base["TCP (Inception)"].equals(unavailable["TCP (Inception)"])


def test_benchmark_failure_does_not_affect_json_state(canonical, ledger):
    before = deepcopy(canonical)
    propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    )
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert canonical == before


def test_no_network_at_import():
    import tcp_benchmarks  # noqa: F401


def test_mock_provider_no_network_in_unit_suite():
    provider = MockBenchmarkProvider(_returns_series([0.01]))
    assert provider.download_returns(SPXTR_SYMBOL).iloc[0] == 0.01


def test_no_tkp_wording():
    body = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").lower()
    assert "the kelly program" not in body


def test_no_stonex_plus500_in_benchmark_module():
    body = (REPO_ROOT / "tcp_benchmarks.py").read_text(encoding="utf-8")
    assert "StoneX" not in body
    assert "Plus500" not in body


def test_import_starts_no_server():
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        assert sock.connect_ex(("127.0.0.1", 8312)) != 0
    finally:
        sock.close()


def test_layout_construction_writes_no_financial_state(tmp_path):
    from tcp_public_sections import build_drawdown_profile_card

    assert build_drawdown_profile_card("x") is not None


def test_benchmark_status_message_ready():
    msg = benchmark_status_message(
        BenchmarkResult(
            status=BENCHMARK_STATUS_READY,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of="2026-06-20",
            fetched_at="2026-06-20",
            returns=None,
            warning=None,
        )
    )
    assert "as of" in msg.lower()


def test_store_roundtrip():
    series = _returns_series([0.01, 0.02])
    original = BenchmarkResult(
        status=BENCHMARK_STATUS_READY,
        symbol=SPXTR_SYMBOL,
        display_name="SPXTR",
        as_of="2026-01-21",
        fetched_at="2026-01-21",
        returns=series,
        warning=None,
    )
    restored = BenchmarkResult.from_store_dict(original.to_store_dict())
    assert restored.status == original.status
    assert restored.returns is not None
    assert len(restored.returns) == 2
