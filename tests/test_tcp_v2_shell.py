"""Tests for tcp_ts_v2 read-only preview shell."""
from __future__ import annotations

import ast
import importlib
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


def test_import_does_not_start_preview_server():
    assert not _port_listening(8312), "Port 8312 already in use before import"
    import tcp_ts_v2  # noqa: F401

    assert not _port_listening(8312), "Importing tcp_ts_v2 must not start the server"


def test_preview_banner_in_layout_or_error():
    import tcp_ts_v2

    layout_str = str(tcp_ts_v2.app.layout)
    assert "TCP v2 Preview" in layout_str
    assert "Read Only" in layout_str


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


def test_health_route_registered():
    import tcp_ts_v2

    with tcp_ts_v2.app.server.test_client() as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["app"] == "tcp-v2"
    assert payload["mode"] == "read-only"
    assert payload["port"] == 8312
    assert payload["debug"] is False
    assert payload["workbook"] == "tcp_alex.xlsx"
    assert payload["sheet"] == "NAV"
    assert "Hughes" not in str(payload.get("workbook_path", ""))


def test_load_nav_preview_data_read_only(golden_fixture, monkeypatch):
    from tcp_config import load_config
    from tcp_ts_v2 import load_nav_preview_data

    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")

    before = wb_path.stat()
    cfg = load_config()
    monkeypatch.setenv("TCP_V2_WORKBOOK_PATH", str(wb_path))
    cfg = load_config()
    data = load_nav_preview_data(cfg)
    after = wb_path.stat()

    assert data.last_completed_date.strftime("%Y-%m-%d") == "2026-06-24"
    assert len(data.dates) >= 100
    assert before.st_size == after.st_size
    assert int(before.st_mtime) == int(after.st_mtime)


def test_latest_date_matches_golden_fixture(golden_fixture):
    import tcp_ts_v2
    from tcp_config import load_config

    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")

    cfg = load_config()
    if cfg.workbook_path != str(wb_path):
        pytest.skip("Workbook path differs from golden fixture metadata")

    data = tcp_ts_v2.load_nav_preview_data(cfg)
    latest_row = next(
        r for r in golden_fixture["rows"] if r["excel_row_number"] == 114
    )
    assert data.last_completed_date.strftime("%Y-%m-%d") == latest_row["date"]


def test_import_does_not_create_state_files():
    from tcp_config import load_config

    cfg = load_config()
    tcp_state = REPO_ROOT / cfg.state_filename
    assert not tcp_state.exists(), "TCP v2 import must not create JSON state"
