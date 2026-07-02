"""Tests for tcp_ts_v2 preview shell."""
from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def test_tcp_ts_v2_source_does_not_import_production_modules():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert "tcp_ts" not in names
    assert "tkp_ts" not in names


def test_tcp_ts_v2_uses_runtime_state_layer():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "from tcp_runtime_state import" in source
    assert "read_excel" not in source
    assert "openpyxl" not in source


def test_import_does_not_start_preview_server():
    assert not _port_listening(8312), "Port 8312 already in use before import"
    import tcp_ts_v2  # noqa: F401

    assert not _port_listening(8312), "Importing tcp_ts_v2 must not start the server"


def test_preview_banner_in_layout_or_error():
    import tcp_ts_v2

    layout_str = str(tcp_ts_v2.app.layout)
    assert "TCP v2 Preview" in layout_str
    assert "Read Only" in layout_str


def test_layout_shows_runtime_metadata_when_healthy():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "Runtime diagnostics" in layout_str
    assert "Completed ledger rows" in layout_str
    assert "State mode" in layout_str


def test_preview_layout_reports_workbook_mode_by_default():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "workbook" in layout_str


def test_no_direct_save_state_in_preview_source():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "secret-data-store",
        "_save_secret_editor_state",
        "to_excel",
        "json.dump",
        "workbook.save",
    ]
    for token in forbidden:
        assert token not in source, f"Unexpected mutation hook: {token}"
    assert "save_state" not in source


def test_save_row_delegated_to_runtime_module():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "persist_add_row" in source
    assert "admin-add-save-btn" in source or "Save Row" in (REPO_ROOT / "tcp_admin.py").read_text(encoding="utf-8")


def test_dashboard_propagation_callback_registered():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    callbacks = tcp_ts_v2.app.callback_map
    assert any(
        inp.get("id") == "canonical-nav-store"
        for cb in callbacks.values()
        for inp in cb.get("inputs", [])
    )


def test_preview_uses_tcp_dashboard_module():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "from tcp_dashboard import" in source
    assert "propagate_tcp_dashboard" in source


def test_canonical_store_is_memory_only():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "canonical-nav-store" in layout_str
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").lower()
    assert "localstorage" not in source
    assert "sessionstorage" not in source


def test_layout_renders_dynamic_sections():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "Performance Summary" in layout_str
    assert "Performance Metrics" in layout_str
    assert "monthly-calendar-container" in layout_str
    assert "daily-perf-container" in layout_str
    assert "nav-preview-graph" in layout_str


def test_no_calculator_in_preview_source():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "compute_tcp_row" not in source
    assert "tcp_calculations" not in source


def test_health_route_reports_runtime_diagnostics():
    import tcp_ts_v2

    with tcp_ts_v2.app.server.test_client() as client:
        resp = client.get("/healthz")
    payload = resp.get_json()
    assert payload["app"] == "tcp-v2"
    assert payload["port"] == 8312
    assert payload["debug"] is False
    assert payload["workbook"] == "tcp_alex.xlsx"
    assert payload["sheet"] == "NAV"
    assert payload["data_source"] == "workbook"
    assert payload["state_mode"] == "workbook"
    assert payload.get("dashboard_propagation") == "ready"
    assert payload.get("row_save") == "disabled"
    assert payload.get("state_write") == "disabled"
    assert payload.get("monthly_performance") == "dynamic"
    assert "state_path" not in payload
    assert "Hughes" not in str(payload.get("workbook_path", ""))
    if payload.get("adapter_status") == "ok":
        assert resp.status_code == 200
        assert payload["completed_rows"] == 112
        assert payload["latest_completed_date"] == "2026-06-24"
    else:
        assert resp.status_code == 503


@pytest.mark.local_workbook
def test_adapter_read_only_workbook_unchanged(golden_fixture):
    from tcp_ledger import load_ledger

    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")

    before = wb_path.stat()
    load_ledger(str(wb_path))
    after = wb_path.stat()
    assert before.st_size == after.st_size
    assert int(before.st_mtime) == int(after.st_mtime)


@pytest.mark.local_workbook
def test_latest_date_matches_golden_fixture(golden_fixture):
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")

    latest_row = next(
        r for r in golden_fixture["rows"] if r["excel_row_number"] == 114
    )
    meta = tcp_ts_v2._PREVIEW_STATE.snapshot.ledger.metadata
    assert meta.latest_completed_date.isoformat() == latest_row["date"]
    assert meta.latest_completed_excel_row == 114


def test_import_does_not_create_state_files():
    from tcp_config import load_config

    cfg = load_config()
    tcp_state = REPO_ROOT / cfg.state_filename
    tcp_backup = REPO_ROOT / cfg.state_backup_filename
    tcp_lock = REPO_ROOT / cfg.lock_filename
    before = {
        "active": tcp_state.exists(),
        "backup": tcp_backup.exists(),
        "lock": tcp_lock.exists(),
    }
    import importlib
    import tcp_ts_v2

    importlib.reload(tcp_ts_v2)
    after = {
        "active": tcp_state.exists(),
        "backup": tcp_backup.exists(),
        "lock": tcp_lock.exists(),
    }
    assert before == after, "Importing tcp_ts_v2 must not create JSON state files"
