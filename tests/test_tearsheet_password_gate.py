"""TCP Important Notice gate auth behavior tests (presentation + admin entry)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tcp_admin import AdminAuthManager, SESSION_KEY
from tcp_config import AdminAuthSettings, load_admin_auth_settings
from tcp_daily_values import (
    GATE_NOTICE_E_ID,
    PUBLIC_GATE_ACCEPTED_STORE_ID,
    TCP_GATE_STORAGE_PURGE_STORE_ID,
    TCP_UI_MODE_STORE_ID,
    UI_MODE_ADMIN,
    UI_MODE_PUBLIC,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
    resolve_gate_bootstrap_state,
    resolve_public_accept_ui_mode,
    resolve_public_access_ui_mode,
)
from tcp_public_sections import build_public_accept_gate, resolve_public_gate_styles
from tearsheet_gate_auth import (
    ADMIN_DAILY_ENTRY_PATH,
    ADMIN_PORTAL_PATH,
    GATE_PASSWORD_INPUT_ID,
    GATE_PASSWORD_PORTAL_ID,
    GATE_PASSWORD_ROW_ID,
    GATE_PASSWORD_SUBMIT_ID,
    GATE_PASSWORD_TEARSHEET_LABEL,
    GATE_PASSWORD_PORTAL_LABEL,
    GATE_PASSWORD_VISIBLE_STORE_ID,
    INVALID_PASSWORD_MESSAGE,
    build_gate_password_row,
    gate_password_row_style,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-runtime-admin-token"
TEST_SECRET = "test-runtime-session-secret"


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setenv("TCP_V2_ADMIN_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("TCP_V2_SESSION_SECRET", TEST_SECRET)


@pytest.fixture
def tcp_app():
    from tcp_ts_v2 import create_app

    return create_app()


def _layout_text(app) -> str:
    return str(app.layout)


def test_tcp_page_load_starts_at_gate():
    gate_style, main_style = resolve_public_gate_styles(None)
    assert gate_style == {"padding": "4rem", "textAlign": "center"}
    assert main_style == {"display": "none"}


def test_tcp_initial_layout_hides_main_app(tcp_app):
    app, *_ = tcp_app
    main = _find_by_id(app.layout, "main-app")
    assert main is not None
    assert main.style == {"display": "none"}


def test_tcp_gate_storage_purge_store_is_memory_only(tcp_app):
    app, *_ = tcp_app
    store = _find_by_id(app.layout, TCP_GATE_STORAGE_PURGE_STORE_ID)
    assert store is not None
    assert store.storage_type == "memory"


def test_tcp_ui_mode_store_is_memory_only(tcp_app):
    app, *_ = tcp_app
    store = _find_by_id(app.layout, TCP_UI_MODE_STORE_ID)
    assert store is not None
    assert store.storage_type == "memory"


def test_tcp_gate_renders_accept_button_and_copy():
    gate = build_public_accept_gate()
    layout = str(gate)
    assert "Accept & Continue" in layout
    assert "informational" in layout.lower()
    assert GATE_PASSWORD_ROW_ID in layout
    assert GATE_PASSWORD_TEARSHEET_LABEL in layout
    assert GATE_PASSWORD_PORTAL_LABEL in layout


def test_password_row_renders_tearsheet_and_portal_buttons():
    row = build_gate_password_row()
    layout = str(row)
    assert GATE_PASSWORD_SUBMIT_ID in layout
    assert GATE_PASSWORD_PORTAL_ID in layout
    assert GATE_PASSWORD_TEARSHEET_LABEL in layout
    assert GATE_PASSWORD_PORTAL_LABEL in layout


def test_password_row_initially_hidden():
    row = build_gate_password_row()
    assert row.style == gate_password_row_style(False)


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_by_id(child, target_id)
        if found is not None:
            return found
    return None


def test_portal_button_disabled_placeholder_mode():
    """portal_enabled=False renders a disabled/greyed Portal button (TKP/TCP)."""
    row = build_gate_password_row(portal_enabled=False)
    button = _find_by_id(row, GATE_PASSWORD_PORTAL_ID)
    assert button is not None
    assert button.disabled is True
    assert button.color == "secondary"


def test_portal_button_enabled_by_default():
    """Default (AGM) keeps the Portal button active."""
    row = build_gate_password_row()
    button = _find_by_id(row, GATE_PASSWORD_PORTAL_ID)
    assert button is not None
    assert getattr(button, "disabled", False) is not True
    assert button.color == "primary"


def test_tcp_public_gate_portal_button_disabled():
    """TCP's public gate uses the disabled Portal placeholder."""
    gate = build_public_accept_gate()
    button = _find_by_id(gate, GATE_PASSWORD_PORTAL_ID)
    assert button is not None
    assert button.disabled is True


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
    assert any(
        inp.get("id") == GATE_PASSWORD_PORTAL_ID
        for cb in app.callback_map.values()
        for inp in cb.get("inputs", [])
    )


def test_admin_route_constants():
    assert ADMIN_DAILY_ENTRY_PATH == "/"
    assert ADMIN_PORTAL_PATH == "/admin"


def test_admin_portal_requires_auth(tcp_app):
    app, *_ = tcp_app
    with app.server.test_client() as client:
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")


def test_admin_portal_returns_200_when_authenticated(tcp_app):
    app, *_ = tcp_app
    with app.server.test_client() as client:
        login = client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
        assert login.status_code == 302
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"portal-account-registry" in response.data
        assert b"Daily entry" in response.data


def test_admin_portal_matches_account_registry_columns_and_is_pending(tcp_app):
    from tearsheet_portal import PORTAL_COLUMNS

    app, *_ = tcp_app
    with app.server.test_client() as client:
        client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
        response = client.get("/admin")
        for column in PORTAL_COLUMNS:
            assert column.encode("utf-8") in response.data
        # TCP has no participating-account registry yet -> Pending empty state.
        assert b"Pending" in response.data


def test_accept_does_not_auto_admin():
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=None)
    assert gate_style["textAlign"] == "center"
    assert main_style == {"display": "none"}
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    assert not auth.is_authenticated({})


def test_refresh_does_not_restore_admin_from_stale_session():
    ui_mode, clear_session = resolve_gate_bootstrap_state(ui_mode=None)
    assert ui_mode is None
    assert clear_session is True
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=ui_mode)
    assert main_style == {"display": "none"}
    assert gate_style["textAlign"] == "center"


def test_refresh_with_stale_browser_ui_mode_admin_still_starts_at_gate():
    ui_mode, clear_session = resolve_gate_bootstrap_state(ui_mode=UI_MODE_ADMIN)
    assert ui_mode is None
    assert clear_session is True
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=ui_mode)
    assert main_style == {"display": "none"}


def test_refresh_with_stale_browser_ui_mode_public_still_starts_at_gate():
    ui_mode, clear_session = resolve_gate_bootstrap_state(ui_mode=UI_MODE_PUBLIC)
    assert ui_mode is None
    assert clear_session is True
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=ui_mode)
    assert main_style == {"display": "none"}


def test_refresh_clears_stale_admin_session_cookie(tcp_app):
    app, _, _, auth_manager, _ = tcp_app
    with app.server.test_client() as client:
        client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
        with client.session_transaction() as sess:
            assert auth_manager.is_authenticated(sess)
        with app.server.test_request_context("/"):
            from flask import session

            ui_mode, clear_session = resolve_gate_bootstrap_state(ui_mode=UI_MODE_ADMIN)
            assert clear_session is True
            if clear_session:
                auth_manager.logout(session)
            assert not auth_manager.is_authenticated(session)
            assert ui_mode is None


def test_public_accept_still_works_after_gate():
    ui_mode, clear_session = resolve_public_accept_ui_mode(accept_clicks=1)
    assert ui_mode == UI_MODE_PUBLIC
    assert clear_session is True
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=ui_mode)
    assert gate_style == {"display": "none"}
    assert main_style == {"display": "block"}


def test_accept_without_click_does_not_open_public():
    ui_mode, clear_session = resolve_public_accept_ui_mode(accept_clicks=0)
    assert ui_mode is None
    assert clear_session is True
    gate_style, main_style, _daily = resolve_access_visibility(ui_mode=ui_mode)
    assert main_style == {"display": "none"}


def test_combined_resolver_ignores_stale_store_on_non_accept_trigger():
    ui_mode, clear_session = resolve_public_access_ui_mode(
        triggered_id="url",
        accept_clicks=0,
        ui_mode=UI_MODE_PUBLIC,
    )
    assert ui_mode is None
    assert clear_session is True


def test_gate_bootstrap_and_accept_callbacks_registered(tcp_app):
    app, *_ = tcp_app
    bootstrap = [
        cb
        for cb in app.callback_map.values()
        if "disclaimer-screen" in str(cb.get("output", ""))
        and "main-app" in str(cb.get("output", ""))
        and any(inp.get("id") == "url" for inp in cb.get("inputs", []))
        and not any(inp.get("id") == "accept-button" for inp in cb.get("inputs", []))
    ]
    accept = [
        cb
        for cb in app.callback_map.values()
        if "disclaimer-screen" in str(cb.get("output", ""))
        and any(inp.get("id") == "accept-button" for inp in cb.get("inputs", []))
        and not any(inp.get("id") == "url" for inp in cb.get("inputs", []))
    ]
    assert bootstrap, "page-load gate bootstrap callback not registered"
    assert accept, "Accept-only gate callback not registered"


def test_clientside_gate_storage_purge_registered(tcp_app):
    app, *_ = tcp_app
    store = _find_by_id(app.layout, TCP_GATE_STORAGE_PURGE_STORE_ID)
    assert store is not None
    purge = app.callback_map.get(f"{TCP_GATE_STORAGE_PURGE_STORE_ID}.data")
    assert purge is not None, "gate storage purge callback not registered"
    assert any(inp.get("id") == "url" for inp in purge.get("inputs", []))


def test_client_store_cannot_grant_admin():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    fake = {PUBLIC_GATE_ACCEPTED_STORE_ID: True, "disclaimer-accepted": True}
    assert not auth.is_authenticated(fake)


def test_wrong_password_message_constant():
    auth = AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))
    ok, msg = auth.login({}, "wrong-password-value")
    assert not ok
    assert msg == INVALID_PASSWORD_MESSAGE


def test_runtime_token_not_in_layout(tcp_app):
    app, *_ = tcp_app
    layout = _layout_text(app)
    assert TEST_TOKEN not in layout


def test_admin_toolbar_hidden_without_admin_mode():
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=False) == {
        "display": "none"
    }


def test_admin_toolbar_visible_in_admin_mode_when_authenticated():
    assert resolve_daily_values_toolbar_style(
        ui_mode=UI_MODE_ADMIN, admin_authenticated=True
    ) == {"display": "block"}


def test_healthz_is_real_json(tcp_app):
    app, *_ = tcp_app
    with app.server.test_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload is not None
        assert payload["app"] == "tcp-v2"
