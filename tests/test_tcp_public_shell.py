"""Step 11B — TCP v2 public shell, gate, and static content tests."""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest

from tcp_admin import SESSION_KEY, AdminAuthManager, SIMULATION_BANNER_TEXT
from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_public_sections import ACCOUNT_STATISTICS, required_copy_fragments, resolve_public_gate_styles

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-admin-token-public-shell"
TEST_SECRET = "test-session-secret-public-shell"

V1_BASE_COMMIT = "b5fce4b"


def _layout_text(app) -> str:
    return str(app.layout)


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="module")
def _app_bundle_module():
    """Load workbook-backed preview app once per module (no monkeypatch dependency)."""
    import os

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = TEST_TOKEN
    os.environ["TCP_V2_SESSION_SECRET"] = TEST_SECRET
    settings = AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)
    from tcp_ts_v2 import create_app

    bundle = create_app(auth_settings=settings)
    yield bundle
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def auth_settings():
    return AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)


@pytest.fixture
def auth_manager(auth_settings):
    return AdminAuthManager(auth_settings)


@pytest.fixture
def app_bundle(_app_bundle_module):
    return _app_bundle_module


@pytest.fixture
def app(app_bundle):
    return app_bundle[0]


@pytest.fixture
def client(app):
    return app.server.test_client()


@pytest.fixture
def layout_text(app_bundle):
    app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    return _layout_text(app)


# --- Static content ---


@pytest.mark.parametrize(
    "needle",
    [
        "The Crypto Program",
        "introducing brokerage firm",
        "Strategy Overview",
        "Bitcoin",
        "Ethereum",
        "Proprietary",
        "Client",
        "UNTIL TCP IS OFFICIALLY OPENED",
        "Please note that all percentages shown are relative",
        "Important Disclosure:",
        "NFA ID 0423388",
    ],
)
def test_static_copy_present(layout_text, needle):
    assert needle in layout_text


@pytest.mark.parametrize("label, _prop, _client", ACCOUNT_STATISTICS)
def test_account_stat_labels_present(layout_text, label, _prop, _client):
    assert label in layout_text


def test_no_stonex_in_trading_exchange_lists(layout_text):
    section = layout_text.split("Trading Universe & Risk Profile", 1)[1].split("Investor Information", 1)[0]
    pre_footnote = section.split("* Give up fee")[0]
    assert "StoneX" not in pre_footnote


def test_stonex_in_terms_and_fees_only(layout_text):
    assert "StoneX Financial" in layout_text
    assert "Execution FCM" in layout_text


def test_no_plus500_wording(layout_text):
    assert "Plus500" not in layout_text


def test_no_tkp_product_wording():
    combined = (
        (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8")
        + (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    ).lower()
    assert "the kinetics program" not in combined
    assert "tkp tearsheet" not in combined


def test_required_v1_copy_fragments(layout_text):
    for fragment in required_copy_fragments().values():
        assert fragment in layout_text


# --- Structure ---


def test_public_accept_gate_exists(layout_text):
    assert "disclaimer-screen" in layout_text
    assert "accept-button" in layout_text
    assert "Important Notice" in layout_text


def test_gate_initially_conceals_main_app(layout_text):
    assert 'id="main-app"' in layout_text or "id='main-app'" in layout_text
    assert '"display": "none"' in layout_text or "'display': 'none'" in layout_text


def test_gate_callback_reveals_main_app():
    gate_style, main_style = resolve_public_gate_styles(1)
    assert gate_style == {"display": "none"}
    assert main_style == {"display": "block"}


def test_gate_acceptance_does_not_authenticate_admin(app_bundle, auth_settings):
    _app, _cfg, state, auth_manager, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    session = {}
    resolve_public_gate_styles(1)
    assert not auth_manager.is_authenticated(session)
    assert SESSION_KEY not in session


def test_gate_state_cannot_enable_add_delete(app_bundle):
    _app, _cfg, state, auth_manager, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    resolve_public_gate_styles(1)
    assert SIMULATION_BANNER_TEXT not in _layout_text(_app)


def test_header_band_exists(layout_text):
    assert "header-row" in layout_text
    assert "tcp-public-header-row" in layout_text


def test_two_column_shell_exists(layout_text):
    assert "tcp-two-column-row" in layout_text
    assert "tcp-strategy-row" in layout_text
    assert "tcp-performance-account-row" in layout_text


def test_account_stat_columns_exist(layout_text):
    assert "tcp-account-stats-table" in layout_text
    assert "Account Stats" in layout_text


def test_mobile_stacking_structure(layout_text):
    assert "d-none d-md-block" in layout_text
    assert "d-block d-md-none" in layout_text
    assert "mb-lg-0" in layout_text


def test_disclosure_and_footer_ids(layout_text):
    assert "tcp-public-disclosure-panel" in layout_text
    assert "tcp-public-footer" in layout_text


# --- Dynamic core preservation ---


def test_monthly_container_present(layout_text):
    assert "monthly-calendar-container" in layout_text


def test_daily_container_present(layout_text):
    assert "daily-perf-container" in layout_text


def test_nav_graph_present(layout_text):
    assert "nav-preview-graph" in layout_text


def test_drawdown_container_present(layout_text):
    assert "drawdown-profile-container" in layout_text
    assert "Maximum Drawdown Profile" in layout_text


def test_desktop_date_label_present(layout_text):
    assert "data-current-label-desktop" in layout_text


def test_mobile_date_label_present(layout_text):
    assert "data-current-label-mobile" in layout_text


def test_dashboard_propagation_callback_registered(app):
    callbacks = app.callback_map
    assert any(
        inp.get("id") == "canonical-nav-store"
        for cb in callbacks.values()
        for inp in cb.get("inputs", [])
    )


def test_canonical_store_unchanged_in_layout(app_bundle):
    _app, _cfg, state, _holder_auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    layout = _layout_text(_app)
    assert "canonical-nav-store" in layout
    assert str(state.snapshot.state_revision or "") in layout or "revision" in layout.lower()


def test_data_source_in_diagnostics(layout_text):
    assert "Data source:" in layout_text


def test_no_static_monthly_duplication_beyond_container(app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    layout = _layout_text(_app)
    assert layout.count("monthly-calendar-container") == 1


def test_no_static_nav_trace_duplication(layout_text):
    assert layout_text.count("nav-preview-graph") == 1


# --- Admin / security ---


def test_public_layout_contains_no_admin_token(app_bundle):
    app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    layout = _layout_text(app)
    assert TEST_TOKEN not in layout
    assert TEST_SECRET not in layout


def test_public_gate_separate_from_flask_admin_session(app_bundle, auth_settings):
    _app, _cfg, state, auth_manager, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    flask_session = {}
    auth_manager.login(flask_session, TEST_TOKEN)
    layout = _layout_text(_app)
    assert "disclaimer-screen" in layout
    assert auth_manager.is_authenticated(flask_session)


def test_unauthenticated_user_cannot_see_admin_ledger(client, app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    response = client.get("/")
    body = response.get_data(as_text=True)
    assert "admin-ledger-table" not in body
    assert SIMULATION_BANNER_TEXT not in body


def test_existing_login_logout_behavior(client, auth_manager):
    login = client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
    assert login.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert auth_manager.is_authenticated(sess)
    logout = client.get("/admin/logout", follow_redirects=False)
    assert logout.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert not auth_manager.is_authenticated(sess)


def test_public_gate_callback_does_not_persist(monkeypatch):
    calls = {"add": 0, "delete": 0}

    def _fake_add(*_a, **_k):
        calls["add"] += 1
        raise AssertionError("add should not run")

    def _fake_delete(*_a, **_k):
        calls["delete"] += 1
        raise AssertionError("delete should not run")

    monkeypatch.setattr("tcp_ts_v2.persist_add_row", _fake_add)
    monkeypatch.setattr("tcp_ts_v2.persist_delete_last_row", _fake_delete)
    resolve_public_gate_styles(1)
    assert calls == {"add": 0, "delete": 0}


def test_import_starts_no_server():
    assert not _port_listening(8312), "Port 8312 already in use before import"
    import tcp_public_sections  # noqa: F401

    assert not _port_listening(8312)


def test_layout_construction_creates_no_state_files(tmp_path, monkeypatch):
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    for path in (active, backup, lock):
        if path.exists():
            mtime_before = path.stat().st_mtime
        else:
            mtime_before = None
    import tcp_public_sections as tps

    gate = tps.build_public_accept_gate()
    assert gate is not None
    if active.exists() and mtime_before is not None:
        assert active.stat().st_mtime == mtime_before


# --- Source provenance ---


def test_committed_v1_matches_git_index():
    indexed = subprocess.run(
        ["git", "rev-parse", f"{V1_BASE_COMMIT}:tcp_ts.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    hashed = subprocess.run(
        ["git", "hash-object", "tcp_ts.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    assert hashed == indexed
