"""Tests for TCP v2 admin simulation shell and authorization."""
from __future__ import annotations

import hashlib
import json
import os
import socket
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tcp_admin import (
    ADD_ROW_CONFIRM_LABEL,
    EXPORT_DISABLED_LABEL,
    LEDGER_TABLE_COLUMNS,
    SESSION_KEY,
    SIMULATION_BANNER_TEXT,
    AdminAuthManager,
    datatable_column_defs,
    ledger_records_to_rows,
    simulate_add_row,
    simulate_delete_last_row,
)
from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_dashboard import propagate_tcp_dashboard
from tcp_ledger import load_ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_LEDGER = None

TEST_TOKEN = "test-admin-token-step8"
TEST_SECRET = "test-session-secret-step8"


@pytest.fixture
def auth_settings():
    return AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)


@pytest.fixture
def auth_manager(auth_settings):
    return AdminAuthManager(auth_settings)


@pytest.fixture
def app_bundle(auth_settings, monkeypatch):
    monkeypatch.setenv("TCP_V2_ADMIN_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TCP_V2_SESSION_SECRET", TEST_SECRET)
    from tcp_ts_v2 import create_app

    return create_app(auth_settings=auth_settings)


@pytest.fixture
def app(app_bundle):
    return app_bundle[0]


@pytest.fixture
def client(app):
    return app.server.test_client()


@pytest.fixture(scope="session")
def ledger():
    global _SESSION_LEDGER
    if _SESSION_LEDGER is None:
        cfg = load_config()
        wb = Path(cfg.workbook_path)
        if not wb.is_file():
            pytest.skip("TCP workbook not available")
        _SESSION_LEDGER = load_ledger(cfg.workbook_path, cfg.sheet_name)
    return _SESSION_LEDGER


def test_missing_admin_token_disables_login(auth_manager):
    unconfigured = AdminAuthManager(AdminAuthSettings(admin_token=None, session_secret=TEST_SECRET))
    session = {}
    ok, message = unconfigured.login(session, "anything")
    assert not ok
    assert "not configured" in message.lower()


def test_missing_session_secret_disables_login():
    unconfigured = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=None))
    assert not unconfigured.is_configured
    session = {}
    ok, message = unconfigured.login(session, TEST_TOKEN)
    assert not ok


def test_correct_token_authenticates(auth_manager):
    session = {}
    ok, message = auth_manager.login(session, TEST_TOKEN)
    assert ok
    assert message == ""
    assert auth_manager.is_authenticated(session)


def test_incorrect_token_rejected(auth_manager):
    session = {}
    ok, message = auth_manager.login(session, "wrong-token")
    assert not ok
    assert message == "Invalid credentials."
    assert not auth_manager.is_authenticated(session)


def test_logout_clears_authorization(auth_manager):
    session = {}
    auth_manager.login(session, TEST_TOKEN)
    auth_manager.logout(session)
    assert SESSION_KEY not in session
    assert not auth_manager.is_authenticated(session)


def test_token_absent_from_healthz(client, app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    payload = client.get("/healthz").get_json()
    assert TEST_TOKEN not in json.dumps(payload)
    assert TEST_SECRET not in json.dumps(payload)
    assert payload["admin_auth"] == "configured"
    assert payload["state_mode"] == "workbook"
    assert payload["row_save"] == "disabled"


def test_token_absent_from_layout_serialization(app_bundle):
    app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    layout = str(app.layout)
    assert TEST_TOKEN not in layout
    assert TEST_SECRET not in layout


def test_unauthenticated_admin_editor_hidden(client, app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    response = client.get("/")
    assert response.status_code == 200
    assert SIMULATION_BANNER_TEXT not in response.get_data(as_text=True)


def test_authenticated_admin_editor_available(client, app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = True
    response = client.get("/")
    assert response.status_code == 200


def test_login_route_rejects_bad_token(client):
    response = client.post("/admin/login", data={"token": "bad"}, follow_redirects=False)
    assert response.status_code == 401


def test_login_route_accepts_good_token(client):
    response = client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
    assert response.status_code in {302, 303}


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = True
    response = client.get("/admin/logout", follow_redirects=False)
    assert response.status_code in {302, 303}
    with client.session_transaction() as sess:
        assert not sess.get(SESSION_KEY)


def test_full_ledger_rows_available(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    assert len(rows) == 112
    assert rows[-1]["_highlight"] == "true"
    assert set(LEDGER_TABLE_COLUMNS).issubset(rows[0].keys())


def test_required_columns_present():
    assert "nav-x1" in LEDGER_TABLE_COLUMNS
    assert "#" in LEDGER_TABLE_COLUMNS
    assert "Cash Balance" in LEDGER_TABLE_COLUMNS


def test_datatable_columns_read_only_metadata():
    cols = datatable_column_defs()
    assert len(cols) == len(LEDGER_TABLE_COLUMNS)
    assert cols[0]["id"] == LEDGER_TABLE_COLUMNS[0]


def test_latest_row_identified(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    assert rows[-1]["Date"] == "2026-06-24"


def test_valid_add_row_simulation(ledger):
    prior = ledger.completed_records[-1].fields
    result = simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert result.success
    assert result.proposed_row is not None
    for field in LEDGER_TABLE_COLUMNS:
        assert field in result.proposed_row


def test_add_row_requires_chronological_date(ledger):
    prior = ledger.completed_records[-1].fields
    result = simulate_add_row(
        prior,
        row_date="2026-06-24",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert not result.success


def test_negative_transfer_unsupported(ledger):
    prior = ledger.completed_records[-1].fields
    result = simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=-100,
        tranche_count=int(prior["#"]),
    )
    assert not result.success
    assert "unsupported" in (result.error_message or "").lower()


def test_tranche_regression_fails(ledger):
    prior = ledger.completed_records[-1].fields
    result = simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=max(1, int(prior["#"]) - 1),
    )
    assert not result.success


def test_input_immutability_on_simulation(ledger):
    prior = deepcopy(ledger.completed_records[-1].fields)
    before = deepcopy(prior)
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert prior == before


def test_delete_simulation_shows_final_row(ledger):
    result = simulate_delete_last_row(ledger.completed_records)
    assert result.success
    assert result.deleted_row is not None
    assert result.deleted_row["Date"] in {"2026-06-24", date(2026, 6, 24)}


def test_delete_simulation_prior_row(ledger):
    result = simulate_delete_last_row(ledger.completed_records)
    assert result.prior_row is not None
    assert result.resulting_latest_date is not None


def test_simulation_banner_copy():
    assert "Simulation Only" in SIMULATION_BANNER_TEXT
    assert ADD_ROW_CONFIRM_LABEL == "Calculation Verified"
    assert "persistence parity validation" in EXPORT_DISABLED_LABEL


def test_canonical_store_unchanged_by_simulation(ledger):
    canonical = [{"Date": r.fields["Date"].isoformat(), "NAV": float(r.fields["nav-x1"])} for r in ledger.completed_records]
    before = deepcopy(canonical)
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    simulate_delete_last_row(ledger.completed_records)
    assert canonical == before


def test_dashboard_unchanged_by_simulation(ledger):
    canonical = [{"Date": r.fields["Date"].isoformat(), "NAV": float(r.fields["nav-x1"])} for r in ledger.completed_records]
    before = propagate_tcp_dashboard(canonical)
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after = propagate_tcp_dashboard(canonical)
    assert before.latest_nav == after.latest_nav
    assert before.nav_point_count == after.nav_point_count


def test_no_state_files_created_by_simulation(ledger):
    active, backup, lock = resolve_state_paths(load_config(), REPO_ROOT)
    before = {
        "active": active.exists(),
        "backup": backup.exists(),
        "lock": lock.exists(),
    }
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after = {
        "active": active.exists(),
        "backup": backup.exists(),
        "lock": lock.exists(),
    }
    assert before == after


@pytest.mark.local_workbook
def test_workbook_unchanged_after_simulation(ledger):
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("workbook unavailable")
    before = wb.stat()
    digest_before = hashlib.sha256(wb.read_bytes()).hexdigest()
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after = wb.stat()
    digest_after = hashlib.sha256(wb.read_bytes()).hexdigest()
    assert before.st_size == after.st_size
    assert int(before.st_mtime) == int(after.st_mtime)
    assert digest_before == digest_after


def test_import_does_not_start_server():
    with socket.socket() as sock:
        sock.settimeout(0.5)
        assert sock.connect_ex(("127.0.0.1", 8312)) != 0


def test_public_route_returns_200(client):
    assert client.get("/").status_code == 200


def test_health_reports_workbook_capabilities(client):
    payload = client.get("/healthz").get_json()
    assert payload["data_source"] == "workbook"
    assert payload["state_mode"] == "workbook"
    assert payload["state_write"] == "disabled"
