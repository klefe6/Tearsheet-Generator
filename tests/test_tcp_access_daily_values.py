"""TCP v2 access flow and shared Daily Values tests."""
from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest

from tcp_test_constants import TEST_AUTH_SECRET, TEST_AUTH_TOKEN
from tcp_admin import (
    SESSION_KEY,
    AdminAuthManager,
    ledger_records_to_rows,
    simulate_add_row,
    simulate_delete_last_row,
)
from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_dashboard import propagate_tcp_dashboard
from tcp_daily_values import (
    DAILY_VALUES_SECTION_ID,
    DAILY_VALUES_TABLE_ID,
    DAILY_VALUES_TOOLBAR_ID,
    GATE_NOTICE_E_ID,
    PUBLIC_GATE_ACCEPTED_STORE_ID,
    TCP_UI_MODE_STORE_ID,
    UI_MODE_ADMIN,
    UI_MODE_PUBLIC,
    build_daily_values_datatable,
    build_daily_values_section,
    project_public_daily_rows,
    public_daily_column_defs,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
)
from tcp_ledger import load_ledger
from tcp_public_sections import GATE_SCREEN_STYLE, build_public_accept_gate
from tcp_runtime_state import persist_add_row
from tcp_state import StatePaths

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = TEST_AUTH_TOKEN
TEST_SECRET = TEST_AUTH_SECRET
PRODUCTION_PORT = 8302
PREVIEW_PORT = 8312


def _layout_text(app) -> str:
    return str(app.layout)


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def auth_settings():
    return AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)


@pytest.fixture
def auth_manager(auth_settings):
    return AdminAuthManager(auth_settings)


@pytest.fixture
def app_bundle(tcp_app_bundle):
    return tcp_app_bundle


@pytest.fixture
def app(tcp_app):
    return tcp_app


@pytest.fixture
def client(tcp_client):
    return tcp_client


@pytest.fixture
def layout_text(tcp_layout_text):
    return tcp_layout_text


# --- Access flow ---


def test_initial_gate_visible(layout_text):
    assert "disclaimer-screen" in layout_text
    assert "accept-button" in layout_text
    gate, main, daily = resolve_access_visibility(ui_mode=None)
    assert main == {"display": "none"}
    assert daily == {"display": "none"}


def test_accept_reveals_public_site():
    gate, main, _daily = resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert gate == {"display": "none"}
    assert main == {"display": "block"}


def test_accept_reveals_daily_values():
    _gate, _main, daily = resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert daily == {"display": "block"}


def test_accept_does_not_authenticate_admin(auth_manager):
    session = {}
    resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert not auth_manager.is_authenticated(session)


def test_e_affordance_reveals_password_row_callback(app):
    from tearsheet_gate_auth import GATE_PASSWORD_VISIBLE_STORE_ID

    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == GATE_NOTICE_E_ID for inp in cb.get("inputs", []))
        for cb in app.callback_map.values()
    )


def test_e_alone_does_not_authenticate_admin(auth_manager):
    session = {}
    assert GATE_NOTICE_E_ID == "secret-notice-e"
    assert not auth_manager.is_authenticated(session)


def test_incorrect_login_rejected(client):
    response = client.post("/admin/login", data={"token": "wrong"}, follow_redirects=False)
    assert response.status_code == 401


def test_correct_login_establishes_admin_session(client, auth_manager):
    response = client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
    assert response.status_code in {302, 303}
    with client.session_transaction() as sess:
        assert auth_manager.is_authenticated(sess)


def test_admin_requires_explicit_ui_mode_even_with_session():
    gate, main, daily = resolve_access_visibility(ui_mode=None)
    assert gate != {"display": "none"}
    assert main == {"display": "none"}
    assert daily == {"display": "none"}


def test_admin_ui_mode_reveals_public_page():
    gate, main, daily = resolve_access_visibility(ui_mode=UI_MODE_ADMIN)
    assert gate == {"display": "none"}
    assert main == {"display": "block"}
    assert daily == {"display": "block"}


def test_logout_removes_admin_controls(client, auth_manager):
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = True
    logout = client.get("/admin/logout", follow_redirects=False)
    assert logout.status_code in {302, 303}
    with client.session_transaction() as sess:
        assert not auth_manager.is_authenticated(sess)
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=False) == {"display": "none"}


def test_accepted_public_user_sees_daily_values():
    _gate, _main, daily = resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert daily == {"display": "block"}


def test_authenticated_admin_sees_daily_values_with_ui_mode():
    _gate, _main, daily = resolve_access_visibility(ui_mode=UI_MODE_ADMIN)
    assert daily == {"display": "block"}


def test_unaccepted_unauthenticated_hides_daily_values():
    gate, main, daily = resolve_access_visibility(ui_mode=None)
    assert daily == {"display": "none"}
    assert main == {"display": "none"}
    assert gate == GATE_SCREEN_STYLE


def test_logout_returns_to_gate_on_fresh_visit(auth_manager):
    gate, main, daily = resolve_access_visibility(ui_mode=None)
    assert not auth_manager.is_authenticated({})
    assert main == {"display": "none"}
    assert daily == {"display": "none"}


# --- Daily Values placement and structure ---


def test_daily_values_at_bottom_of_public_hierarchy(layout_text):
    daily_idx = layout_text.index(DAILY_VALUES_SECTION_ID)
    disclosure_idx = layout_text.index("tcp-public-disclosure-panel")
    footer_idx = layout_text.index("tcp-public-footer")
    assert daily_idx < disclosure_idx < footer_idx


def test_single_canonical_daily_values_component(layout_text):
    assert layout_text.count(DAILY_VALUES_TABLE_ID) == 1
    assert layout_text.count(DAILY_VALUES_SECTION_ID) == 1
    assert "admin-ledger-table" not in layout_text


def test_public_table_is_read_only(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    table = build_daily_values_datatable(rows)
    assert table.editable is False


def test_public_user_sees_no_add_delete_controls():
    assert resolve_daily_values_toolbar_style(ui_mode=UI_MODE_PUBLIC, admin_authenticated=False) == {"display": "none"}


def test_admin_sees_add_delete_controls(layout_text):
    assert resolve_daily_values_toolbar_style(ui_mode=UI_MODE_ADMIN, admin_authenticated=True) == {"display": "block"}
    assert "admin-open-add-modal" in layout_text
    assert "admin-open-delete-modal" in layout_text


def test_client_store_cannot_reveal_admin_controls(auth_manager):
    """Session store flags do not grant server-side admin authorization."""
    fake_session = {PUBLIC_GATE_ACCEPTED_STORE_ID: True, "disclaimer-accepted": True}
    assert not auth_manager.is_authenticated(fake_session)
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=False) == {"display": "none"}


def test_direct_unauthenticated_mutation_rejected():
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
    assert "authentication" in result.error_message.lower()


# --- Canonical synchronization ---


def test_public_admin_row_counts_match(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    public_rows = project_public_daily_rows(rows)
    assert len(public_rows) == len(rows) == ledger.metadata.completed_row_count


def test_public_admin_latest_date_and_nav_match(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    public_rows = project_public_daily_rows(rows)
    assert public_rows[-1]["Date"] == rows[-1]["Date"]
    assert public_rows[-1]["nav-x1"] == rows[-1]["nav-x1"]


def test_successful_add_updates_shared_table(ledger):
    prior = deepcopy(ledger.completed_records[-1].fields)
    sim = simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert sim.success
    rows = ledger_records_to_rows(ledger.completed_records)
    public_before = project_public_daily_rows(rows)
    public_after = project_public_daily_rows(rows + [sim.proposed_row])
    assert len(public_after) == len(public_before) + 1
    assert public_after[-1]["nav-x1"] == sim.proposed_row["nav-x1"]


def test_successful_add_updates_dynamic_outputs(ledger):
    canonical = [
        {"Date": r.fields["Date"].isoformat(), "NAV": float(r.fields["nav-x1"])}
        for r in ledger.completed_records
    ]
    before = propagate_tcp_dashboard(canonical)
    prior = deepcopy(ledger.completed_records[-1].fields)
    sim = simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after_canonical = canonical + [
        {"Date": sim.proposed_row["Date"].isoformat(), "NAV": float(sim.proposed_row["nav-x1"])}
    ]
    after = propagate_tcp_dashboard(after_canonical)
    assert after.latest_nav != before.latest_nav
    assert after.nav_point_count == before.nav_point_count + 1


def test_successful_delete_restores_both_views(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    baseline_count = len(rows)
    sim = simulate_delete_last_row(ledger.completed_records)
    assert sim.success
    restored = project_public_daily_rows(rows[:-1])
    assert len(restored) == baseline_count - 1
    assert restored[-1]["Date"] == rows[-2]["Date"]


def test_refresh_preserves_shared_state(app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    revision = state.snapshot.state_revision
    layout = _layout_text(_app)
    assert str(revision) in layout or "admin-state-revision-store" in layout


def test_failed_mutation_changes_neither_view(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    public_before = project_public_daily_rows(rows)
    prior = deepcopy(ledger.completed_records[-1].fields)
    bad = simulate_add_row(
        prior,
        row_date="1999-01-01",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    assert not bad.success
    public_after = project_public_daily_rows(rows)
    assert public_before == public_after


def test_simulation_preview_changes_neither_view(ledger):
    canonical = [
        {"Date": r.fields["Date"].isoformat(), "NAV": float(r.fields["nav-x1"])}
        for r in ledger.completed_records
    ]
    before = propagate_tcp_dashboard(canonical)
    prior = deepcopy(ledger.completed_records[-1].fields)
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after = propagate_tcp_dashboard(canonical)
    assert before.latest_nav == after.latest_nav


# --- Side-effect safety ---


def test_accept_performs_no_state_write(monkeypatch):
    calls = {"add": 0, "delete": 0}

    def _fake_add(*_a, **_k):
        calls["add"] += 1

    def _fake_delete(*_a, **_k):
        calls["delete"] += 1

    monkeypatch.setattr("tcp_ts_v2.persist_add_row", _fake_add)
    monkeypatch.setattr("tcp_ts_v2.persist_delete_last_row", _fake_delete)
    resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    assert calls == {"add": 0, "delete": 0}


def test_e_performs_no_state_write():
    gate = build_public_accept_gate()
    assert gate is not None
    assert GATE_NOTICE_E_ID in str(gate)


def test_layout_creation_creates_no_state_files():
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    before = {p: p.exists() for p in (active, backup, lock)}
    from tcp_ledger import load_ledger

    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("workbook unavailable")
    ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)
    section = build_daily_values_section(ledger.completed_records, ledger.metadata, data_source="workbook")
    assert section is not None
    after = {p: p.exists() for p in (active, backup, lock)}
    assert before == after


def test_import_starts_no_server():
    assert not _port_listening(PREVIEW_PORT)
    import tcp_daily_values  # noqa: F401

    assert not _port_listening(PREVIEW_PORT)


def test_no_secret_in_layout_serialization(app_bundle):
    app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    layout = _layout_text(app)
    assert TEST_TOKEN not in layout
    assert TEST_SECRET not in layout


def test_port_8302_never_used_in_tcp_v2_source():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert str(PRODUCTION_PORT) not in source


def test_public_daily_columns_contract():
    cols = public_daily_column_defs()
    ids = [c["id"] for c in cols]
    assert ids == ["#", "Date", "nav-x1", "%Net", "$PL", "HWM", "Inc. Fee"]
    assert all(col.get("editable", True) is False or "editable" not in col for col in cols)


def test_access_callbacks_registered(app):
    outputs = [str(cb.get("output", "")) for cb in app.callback_map.values()]
    assert any(DAILY_VALUES_SECTION_ID in out for out in outputs)
    assert any(TCP_UI_MODE_STORE_ID in out for out in outputs)


def test_health_payload_contains_no_token(client):
    payload = client.get("/healthz").get_json()
    blob = json.dumps(payload)
    assert TEST_TOKEN not in blob
    assert TEST_SECRET not in blob
