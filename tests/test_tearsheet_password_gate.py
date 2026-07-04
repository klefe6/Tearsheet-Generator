"""Password-gated hidden admin entry tests for TCP v2 and TKP."""
from __future__ import annotations

import importlib
import os
import socket
from pathlib import Path

import pytest

from tcp_admin import AdminAuthManager, SESSION_KEY
from tcp_config import AdminAuthSettings, load_admin_auth_settings
from tcp_daily_values import (
    DAILY_VALUES_TABLE_ID,
    DAILY_VALUES_TOOLBAR_ID,
    GATE_NOTICE_E_ID,
    PUBLIC_GATE_ACCEPTED_STORE_ID,
    build_daily_values_datatable,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
)
from tcp_public_sections import build_public_accept_gate, normalized_gate_title_text
from tearsheet_gate_auth import (
    GATE_PASSWORD_INPUT_ID,
    GATE_PASSWORD_ROW_ID,
    GATE_PASSWORD_SUBMIT_ID,
    GATE_PASSWORD_VISIBLE_STORE_ID,
    INVALID_PASSWORD_MESSAGE,
    TKP_SESSION_KEY,
    build_gate_password_row,
    gate_password_row_style,
    load_tkp_admin_auth_settings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-runtime-admin-token"
TEST_SECRET = "test-runtime-session-secret"
PREVIEW_PORT_TCP = 8312


def _layout_text(app) -> str:
    return str(app.layout)


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("TCP_V2_ADMIN_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TCP_V2_SESSION_SECRET", TEST_SECRET)
    monkeypatch.setenv("TKP_ADMIN_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TKP_SESSION_SECRET", TEST_SECRET)


@pytest.fixture
def layout_text():
    from tcp_ts_v2 import create_app

    app, *_ = create_app()
    return _layout_text(app)


@pytest.fixture
def tcp_app():
    from tcp_ts_v2 import create_app

    return create_app()


@pytest.fixture
def ledger():
    from tcp_config import load_config
    from tcp_ledger import load_ledger

    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


def test_heading_normalizes_to_important_notice():
    assert normalized_gate_title_text() == "Important Notice"


def test_exactly_one_clickable_final_e(layout_text):
    assert layout_text.count(f"id='{GATE_NOTICE_E_ID}'") == 1


def test_clickable_e_inside_title_structure():
    gate = build_public_accept_gate()
    h2 = gate.children.children[0]
    assert h2.id == "tcp-public-gate-title"
    child_ids = [getattr(child, "id", None) for child in h2.children]
    assert child_ids.count(GATE_NOTICE_E_ID) == 1


def test_password_row_present_in_gate():
    gate = build_public_accept_gate()
    layout = str(gate)
    assert GATE_PASSWORD_ROW_ID in layout
    assert GATE_PASSWORD_INPUT_ID in layout
    assert GATE_PASSWORD_SUBMIT_ID in layout
    assert "password" in layout.lower()
    assert "Admin password" in layout


def test_password_row_initially_hidden():
    row = build_gate_password_row()
    assert row.style == gate_password_row_style(False)


def test_runtime_token_not_in_layout_or_health(tcp_app):
    app, cfg, state, auth_manager, _ = tcp_app
    layout = _layout_text(app)
    assert TEST_TOKEN not in layout
    assert "gc11" not in layout
    with app.server.test_client() as client:
        response = client.get("/healthz")
        payload = response.get_json()
    assert TEST_TOKEN not in str(payload)
    assert "gc11" not in str(payload)
    assert auth_manager.auth_status_label() in {"configured", "not_configured"}


def test_e_click_does_not_authenticate(tcp_app):
    app, *_ = tcp_app
    auth = AdminAuthManager(load_admin_auth_settings(), session_key=SESSION_KEY)
    with app.server.test_client() as client:
        client.get("/")
        assert not auth.is_authenticated({})


def test_e_reveals_password_row_callback_registered(tcp_app):
    app, *_ = tcp_app
    assert any(
        inp.get("id") == GATE_NOTICE_E_ID
        for cb in app.callback_map.values()
        for inp in cb.get("inputs", [])
    )
    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == GATE_NOTICE_E_ID for inp in cb.get("inputs", []))
        for cb in app.callback_map.values()
    )


def test_gate_submit_callback_registered(tcp_app):
    app, *_ = tcp_app
    assert any(
        inp.get("id") in (GATE_PASSWORD_SUBMIT_ID, GATE_PASSWORD_INPUT_ID)
        for cb in app.callback_map.values()
        for inp in cb.get("inputs", [])
    )


def test_wrong_password_message_constant():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    ok, msg = auth.login({}, "wrong-password-value")
    assert not ok
    assert msg == INVALID_PASSWORD_MESSAGE


def test_correct_runtime_token_authenticates():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    flask_session = {}
    ok, msg = auth.login(flask_session, TEST_TOKEN)
    assert ok
    assert msg == ""
    assert auth.is_authenticated(flask_session)


def test_accept_remains_public_only():
    resolve_access_visibility(accept_clicks=1, admin_authenticated=False, public_accepted=False)
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    assert not auth.is_authenticated({})


def test_public_daily_values_read_only(ledger):
    from tcp_admin import ledger_records_to_rows

    rows = ledger_records_to_rows(ledger.completed_records)
    table = build_daily_values_datatable(rows)
    assert table.editable is False


def test_admin_toolbar_hidden_without_session():
    assert resolve_daily_values_toolbar_style(admin_authenticated=False) == {"display": "none"}


def test_admin_toolbar_visible_when_authenticated():
    assert resolve_daily_values_toolbar_style(admin_authenticated=True) == {"display": "block"}


def test_client_store_cannot_grant_admin():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    fake = {PUBLIC_GATE_ACCEPTED_STORE_ID: True, "disclaimer-accepted": True}
    assert not auth.is_authenticated(fake)


def test_direct_unauthenticated_mutation_rejected():
    from tcp_config import load_config, resolve_state_paths
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
        tranche_count=112,
        authenticated=False,
    )
    assert not result.success


def test_logout_clears_admin_access():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    flask_session = {}
    auth.login(flask_session, TEST_TOKEN)
    auth.logout(flask_session)
    assert not auth.is_authenticated(flask_session)


def test_gate_password_row_construction_writes_no_state():
    from tcp_config import load_config, resolve_state_paths

    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    before = {p: p.exists() for p in (active, backup, lock)}
    assert build_gate_password_row() is not None
    after = {p: p.exists() for p in (active, backup, lock)}
    assert before == after


def test_missing_runtime_token_disables_auth():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=None, session_secret=None))
    flask_session = {}
    ok, msg = auth.login(flask_session, "anything")
    assert not ok
    assert "not configured" in msg.lower()


def test_tkp_auth_settings_from_env():
    settings = load_tkp_admin_auth_settings()
    assert settings.admin_token == TEST_TOKEN
    assert settings.session_secret == TEST_SECRET


def test_tkp_session_key_distinct():
    assert TKP_SESSION_KEY != SESSION_KEY


def test_tkp_layout_has_password_gate_contract():
    tkp_ts = importlib.import_module("tkp_ts")

    layout = str(tkp_ts.dynamic_layout())
    assert GATE_PASSWORD_ROW_ID in layout
    assert GATE_NOTICE_E_ID in layout
    assert TEST_TOKEN not in layout
    assert "gc11" not in layout


def test_tkp_secret_mode_not_granted_by_e_click():
    tkp_ts = importlib.import_module("tkp_ts")

    source = Path(tkp_ts.__file__).read_text(encoding="utf-8")
    show_main_block = source.split("def show_main", 1)[1].split("\ndef ", 1)[0]
    assert "secret-notice-e" not in show_main_block
    assert 'access_mode == "secret"' not in source.split("def toggle_secret_table", 1)[1].split("\ndef ", 1)[0]


def test_mobile_password_row_css_contract():
    css = (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    assert ".tearsheet-gate-password-row" in css
    assert "max-width: 340px" in css
    assert "overflow-x: hidden" in css


def test_import_starts_no_server():
    assert not _port_listening(PREVIEW_PORT_TCP)
    import tearsheet_gate_auth  # noqa: F401

    assert not _port_listening(PREVIEW_PORT_TCP)


def test_no_duplicate_daily_values_table(layout_text):
    assert layout_text.count(DAILY_VALUES_TABLE_ID) == 1
    assert layout_text.count(DAILY_VALUES_TOOLBAR_ID) == 1
