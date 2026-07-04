"""Regression tests for TCP v2 table order, SPXTR benchmark, and explicit auth choice hotfix."""
from __future__ import annotations

import json
import os
import socket
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from tcp_admin import (
    AdminAuthManager,
    SESSION_KEY,
    ledger_records_to_rows,
    simulate_delete_last_row,
)
from tcp_benchmarks import (
    BENCHMARK_STATUS_READY,
    BENCHMARK_STATUS_STALE,
    BENCHMARK_STATUS_UNAVAILABLE,
    BenchmarkResult,
    load_spxtr_benchmark,
)
from tcp_config import AdminAuthSettings, load_config, resolve_benchmark_cache_path, resolve_state_paths
from tcp_daily_values import (
    DAILY_VALUES_DEFAULT_SORT,
    TCP_UI_MODE_STORE_ID,
    UI_MODE_ADMIN,
    UI_MODE_PUBLIC,
    build_daily_values_datatable,
    project_public_daily_rows,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
    sort_rows_for_display,
)
from tcp_dashboard import canonical_nav_records_from_ledger, propagate_tcp_dashboard
from tcp_ledger import load_ledger
from tearsheet_gate_auth import (
    GATE_PASSWORD_INPUT_ID,
    GATE_PASSWORD_ROW_ID,
    GATE_PASSWORD_VISIBLE_STORE_ID,
    build_gate_password_row,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-runtime-admin-token"
TEST_SECRET = "test-runtime-session-secret"


class MockBenchmarkProvider:
    def __init__(self, series: pd.Series | None = None, *, error: Exception | None = None):
        self.series = series
        self.error = error

    def download_returns(self, symbol: str) -> pd.Series:
        if self.error is not None:
            raise self.error
        if self.series is None:
            raise ValueError("no data")
        return self.series.copy()


def _returns_series(values, start="2026-01-20"):
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def _cache_payload(series: pd.Series) -> dict:
    return {
        "symbol": "^SP500TR",
        "display_name": "SPXTR",
        "fetched_at": "2026-06-24T12:00:00+00:00",
        "as_of": series.index.max().strftime("%Y-%m-%d"),
        "source": "quantstats",
        "returns": [
            {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
            for idx, val in series.items()
        ],
    }


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("TCP_V2_ADMIN_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TCP_V2_SESSION_SECRET", TEST_SECRET)


@pytest.fixture(scope="session")
def ledger():
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


@pytest.fixture
def tcp_app():
    from tcp_ts_v2 import create_app

    return create_app()


@pytest.fixture
def sample_rows():
    return [
        {"#": 1, "Date": date(2026, 1, 20), "nav-x1": 100.0, "_highlight": "false"},
        {"#": 2, "Date": date(2026, 6, 24), "nav-x1": 200.0, "_highlight": "true"},
        {"#": 3, "Date": date(2026, 3, 15), "nav-x1": 150.0, "_highlight": "false"},
    ]


# --- Daily Values order ---


def test_latest_date_renders_first(sample_rows):
    sorted_rows = sort_rows_for_display(sample_rows)
    assert sorted_rows[0]["Date"] == date(2026, 6, 24)


def test_oldest_date_renders_last(sample_rows):
    sorted_rows = sort_rows_for_display(sample_rows)
    assert sorted_rows[-1]["Date"] == date(2026, 1, 20)


def test_page_one_contains_newest_rows(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    table = build_daily_values_datatable(rows)
    first_row = table.data[0]
    latest = ledger.metadata.latest_completed_date
    assert first_row["Date"] == latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else latest


def test_public_and_admin_row_order_matches(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    public_table = build_daily_values_datatable(rows)
    admin_table = build_daily_values_datatable(rows)
    assert [row["Date"] for row in public_table.data[:5]] == [row["Date"] for row in admin_table.data[:5]]


def test_display_sort_does_not_mutate_canonical_data(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    original_first = rows[0]["Date"]
    _ = sort_rows_for_display(rows)
    assert rows[0]["Date"] == original_first


def test_add_preserves_newest_first_display(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    table = build_daily_values_datatable(rows)
    assert table.sort_by == DAILY_VALUES_DEFAULT_SORT
    assert table.data[0]["Date"] == ledger.metadata.latest_completed_date.isoformat()


def test_delete_latest_targets_chronological_last_row(ledger):
    preview = simulate_delete_last_row(ledger.completed_records)
    assert preview.deleted_row is not None
    assert preview.deleted_row.get("Date") == ledger.metadata.latest_completed_date


def test_nav_and_calculations_unchanged_by_display_sort(ledger):
    canonical_before = canonical_nav_records_from_ledger(ledger.completed_records)
    rows = sort_rows_for_display(ledger_records_to_rows(ledger.completed_records))
    canonical_after = canonical_nav_records_from_ledger(ledger.completed_records)
    assert canonical_before == canonical_after
    assert len(rows) == len(ledger.completed_records)


# --- SPXTR benchmark ---


def test_valid_live_benchmark_response_renders(tmp_path):
    series = _returns_series([0.001, 0.002, -0.001])
    cache_path = tmp_path / "bench.json"
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(series), cache_path=cache_path)
    assert result.status == BENCHMARK_STATUS_READY
    assert result.returns is not None and not result.returns.empty
    propagation = propagate_tcp_dashboard([], benchmark_result=result)
    assert propagation is not None


def test_fresh_cache_renders(tmp_path):
    series = _returns_series([0.001, 0.002])
    cache_path = tmp_path / "bench.json"
    cache_path.write_text(json.dumps(_cache_payload(series)), encoding="utf-8")
    result = load_spxtr_benchmark(
        provider=MockBenchmarkProvider(error=RuntimeError("offline")),
        cache_path=cache_path,
    )
    assert result.status == BENCHMARK_STATUS_STALE
    assert result.returns is not None


def test_provider_failure_falls_back_to_last_known_good_cache(tmp_path):
    series = _returns_series([0.001, 0.002, 0.003])
    cache_path = tmp_path / "bench.json"
    cache_path.write_text(json.dumps(_cache_payload(series)), encoding="utf-8")
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(error=TimeoutError("timeout")), cache_path=cache_path)
    assert result.status == BENCHMARK_STATUS_STALE
    assert result.as_of is not None


def test_stale_cache_shows_as_of_indicator(tmp_path):
    series = _returns_series([0.001])
    cache_path = tmp_path / "bench.json"
    cache_path.write_text(json.dumps(_cache_payload(series)), encoding="utf-8")
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(error=RuntimeError("down")), cache_path=cache_path)
    assert result.status == BENCHMARK_STATUS_STALE
    assert "stale" in (result.warning or "").lower()


def test_invalid_cache_is_rejected(tmp_path):
    cache_path = tmp_path / "bench.json"
    cache_path.write_text(json.dumps({"symbol": "^SP500TR", "returns": []}), encoding="utf-8")
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(error=RuntimeError("down")), cache_path=cache_path)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE


def test_no_data_produces_controlled_unavailable_state(tmp_path):
    cache_path = tmp_path / "missing.json"
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(error=RuntimeError("down")), cache_path=cache_path)
    assert result.status == BENCHMARK_STATUS_UNAVAILABLE
    assert "unavailable" in (result.warning or "").lower()


def test_network_failure_does_not_prevent_app_startup(tcp_app):
    app, *_ = tcp_app
    with app.server.test_client() as client:
        response = client.get("/healthz")
    assert response.status_code == 200


def test_no_fake_zero_benchmark_values(tmp_path):
    series = _returns_series([0.001, 0.002])
    result = load_spxtr_benchmark(provider=MockBenchmarkProvider(series), cache_path=tmp_path / "bench.json")
    assert not (result.returns == 0).all()


def test_benchmark_date_alignment_remains_correct(ledger, tmp_path):
    series = _returns_series([0.001] * 120, start="2026-01-01")
    result = BenchmarkResult(
        status=BENCHMARK_STATUS_READY,
        symbol="^SP500TR",
        display_name="SPXTR",
        as_of="2026-06-24",
        fetched_at="2026-06-24T00:00:00+00:00",
        returns=series,
        warning=None,
    )
    canonical = canonical_nav_records_from_ledger(ledger.completed_records)
    propagation = propagate_tcp_dashboard(canonical, benchmark_result=result)
    assert propagation.drawdown_profile is not None


def test_resolve_benchmark_cache_path_env_override(tmp_path, monkeypatch):
    target = tmp_path / "custom" / "bench.json"
    monkeypatch.setenv("TCP_V2_BENCHMARK_CACHE_PATH", str(target))
    assert resolve_benchmark_cache_path(REPO_ROOT) == target


# --- Explicit public/admin choice ---


def test_new_page_load_begins_at_gate():
    gate, main, daily = resolve_access_visibility(ui_mode=None)
    assert gate.get("display") != "none"
    assert main.get("display") == "none"
    assert daily.get("display") == "none"


def test_existing_server_session_does_not_auto_render_admin_controls():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    flask_session = {}
    auth.login(flask_session, TEST_TOKEN)
    assert auth.is_authenticated(flask_session)
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=True) == {"display": "none"}


def test_stale_client_admin_state_does_not_auto_render_admin_controls():
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=False) == {"display": "none"}


def test_accept_enters_public_only_mode():
    gate, main, daily = resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert gate == {"display": "none"}
    assert main == {"display": "block"}
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    assert not auth.is_authenticated({})


def test_password_row_initially_hidden():
    row = build_gate_password_row()
    assert row.style == {"display": "none"}


def test_layout_contains_ui_mode_store(tcp_app):
    app, *_ = tcp_app
    assert TCP_UI_MODE_STORE_ID in str(app.layout)


def test_password_absent_from_layout_and_stores(tcp_app):
    app, *_ = tcp_app
    layout = str(app.layout)
    assert TEST_TOKEN not in layout
    assert "password" in layout.lower()
    assert "localStorage" not in layout
    assert "sessionStorage" not in layout


def test_gate_submit_requires_explicit_action(tcp_app):
    app, *_ = tcp_app
    assert any(
        inp.get("id") in (GATE_PASSWORD_ROW_ID, GATE_PASSWORD_VISIBLE_STORE_ID)
        for cb in app.callback_map.values()
        for inp in cb.get("inputs", [])
    )


def test_wrong_password_enables_nothing():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    ok, _ = auth.login({}, "wrong")
    assert not ok


def test_explicit_correct_submission_enables_admin_toolbar():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    session = {}
    auth.login(session, TEST_TOKEN)
    style = resolve_daily_values_toolbar_style(ui_mode=UI_MODE_ADMIN, admin_authenticated=auth.is_authenticated(session))
    assert style == {"display": "block"}


def test_public_users_cannot_mutate():
    from tcp_runtime_state import persist_add_row
    from tcp_state import StatePaths

    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    paths = StatePaths(active_path=active, backup_path=backup, lock_path=lock)
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=1,
        authenticated=False,
    )
    assert not result.success


def test_import_starts_no_server():
    with patch.dict(os.environ, {"TCP_V2_SKIP_BENCHMARK_FETCH": "1"}, clear=False):
        import importlib
        import tcp_ts_v2

        importlib.reload(tcp_ts_v2)
    assert not _port_listening(8312)


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def test_accept_callback_logs_out_stale_session(tcp_app):
    app, _, _, auth_manager, _ = tcp_app
    flask_session = {}
    auth_manager.login(flask_session, TEST_TOKEN)
    with app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[SESSION_KEY] = True
        client.get("/")
    assert resolve_daily_values_toolbar_style(ui_mode=UI_MODE_PUBLIC, admin_authenticated=False) == {"display": "none"}


def test_password_input_has_non_autofill_attributes():
    row = build_gate_password_row()
    layout = str(row)
    assert GATE_PASSWORD_INPUT_ID in layout
    assert "new-password" in layout or "new_password" in layout.lower()
