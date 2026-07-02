"""Tests for tcp_ts_v2 read-only preview shell."""
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


def test_tcp_ts_v2_uses_tcp_ledger_adapter():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "from tcp_ledger import" in source or "import tcp_ledger" in source
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


def test_layout_shows_adapter_metadata_when_healthy():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.ledger is None:
        pytest.skip("Adapter not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "Adapter diagnostics" in layout_str
    assert "Completed ledger rows" in layout_str
    assert "First completed date" in layout_str


def test_preview_layout_reports_state_layer_not_initialized():
    import tcp_ts_v2

    if tcp_ts_v2._PREVIEW_STATE.ledger is None:
        pytest.skip("Adapter not healthy in this environment")
    layout_str = str(tcp_ts_v2.app.layout)
    assert "State layer" in layout_str
    assert "not_initialized" in layout_str
    assert "workbook adapter" in layout_str


def test_no_admin_or_mutation_hooks_in_source():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "secret-data-store",
        "secret-add-btn",
        "delete_last_row",
        "_save_secret_editor_state",
        "add_row",
        "to_excel",
        "json.dump",
    ]
    for token in forbidden:
        assert token not in source, f"Unexpected mutation hook: {token}"


def test_no_dash_callbacks_registered():
    import tcp_ts_v2

    assert tcp_ts_v2.app.callback_map == {}


def test_health_route_reports_adapter_diagnostics():
    import tcp_ts_v2

    with tcp_ts_v2.app.server.test_client() as client:
        resp = client.get("/healthz")
    payload = resp.get_json()
    assert payload["app"] == "tcp-v2"
    assert payload["mode"] == "read-only"
    assert payload["port"] == 8312
    assert payload["debug"] is False
    assert payload["workbook"] == "tcp_alex.xlsx"
    assert payload["sheet"] == "NAV"
    assert payload["data_source"] == "workbook"
    assert payload.get("state_layer") == "available"
    assert payload.get("active_state") == "not_initialized"
    assert "adapter_status" in payload
    assert "state_path" not in payload
    assert "Hughes" not in str(payload.get("workbook_path", ""))
    if payload["adapter_status"] == "ok":
        assert resp.status_code == 200
        assert payload["completed_rows"] == 112
        assert payload["latest_completed_date"] == "2026-06-24"
        assert "first_completed_date" in payload
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

    if tcp_ts_v2._PREVIEW_STATE.ledger is None:
        pytest.skip("Adapter not healthy in this environment")

    latest_row = next(
        r for r in golden_fixture["rows"] if r["excel_row_number"] == 114
    )
    meta = tcp_ts_v2._PREVIEW_STATE.ledger.metadata
    assert meta.latest_completed_date.isoformat() == latest_row["date"]
    assert meta.latest_completed_excel_row == 114


def test_import_does_not_create_state_files():
    from tcp_config import load_config

    cfg = load_config()
    tcp_state = REPO_ROOT / cfg.state_filename
    tcp_backup = REPO_ROOT / cfg.state_backup_filename
    tcp_lock = REPO_ROOT / cfg.lock_filename
    assert not tcp_state.exists(), "TCP v2 import must not create JSON state"
    assert not tcp_backup.exists(), "TCP v2 import must not create backup state"
    assert not tcp_lock.exists(), "TCP v2 import must not create lock file"
