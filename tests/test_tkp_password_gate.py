"""TKP Important Notice gate auth behavior tests (parity with TCP's password gate)."""
from __future__ import annotations

import pytest

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
    TKP_SESSION_KEY,
    gate_password_row_style,
    load_tkp_admin_auth_settings,
)
from tcp_admin import AdminAuthManager

TEST_TOKEN = "test-runtime-admin-token"  # matches tests/conftest.py TKP_ADMIN_TOKEN


@pytest.fixture
def tkp_app():
    import tkp_ts

    return tkp_ts.app


def _layout_text(app) -> str:
    layout = app.layout() if callable(app.layout) else app.layout
    return str(layout)


def test_admin_route_constants():
    assert ADMIN_DAILY_ENTRY_PATH == "/"
    assert ADMIN_PORTAL_PATH == "/admin"


def test_gate_renders_tearsheet_and_portal_buttons(tkp_app):
    import tkp_ts

    layout = str(tkp_ts.disclaimer_screen)
    assert GATE_PASSWORD_ROW_ID in layout
    assert GATE_PASSWORD_SUBMIT_ID in layout
    assert GATE_PASSWORD_PORTAL_ID in layout
    assert GATE_PASSWORD_TEARSHEET_LABEL in layout
    assert GATE_PASSWORD_PORTAL_LABEL in layout


def test_password_row_initially_hidden(tkp_app):
    import tkp_ts

    layout = str(tkp_ts.disclaimer_screen)
    hidden_style = str(gate_password_row_style(False))
    assert GATE_PASSWORD_ROW_ID in layout
    # The row is rendered with the hidden style by default (visible-store starts False).
    assert "'display': 'none'" in hidden_style or '"display": "none"' in hidden_style


def test_e_click_reveals_row_without_authenticating(tkp_app):
    auth = AdminAuthManager(load_tkp_admin_auth_settings(), session_key=TKP_SESSION_KEY)
    assert not auth.is_authenticated({})
    # secret-notice-e only drives the visibility store, never the auth manager directly.
    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == "secret-notice-e" for inp in cb.get("inputs", []))
        for cb in tkp_app.callback_map.values()
    )


def test_enter_key_wired_to_tearsheet_not_portal(tkp_app):
    tearsheet_callbacks = [
        cb
        for cb in tkp_app.callback_map.values()
        if any(inp.get("id") == GATE_PASSWORD_SUBMIT_ID for inp in cb.get("inputs", []))
    ]
    portal_callbacks = [
        cb
        for cb in tkp_app.callback_map.values()
        if any(inp.get("id") == GATE_PASSWORD_PORTAL_ID for inp in cb.get("inputs", []))
    ]
    assert tearsheet_callbacks, "TearSheet submit callback not registered"
    assert portal_callbacks, "Portal callback not registered"
    assert any(
        inp.get("id") == GATE_PASSWORD_INPUT_ID and inp.get("property") == "n_submit"
        for cb in tearsheet_callbacks
        for inp in cb.get("inputs", [])
    ), "Enter key (n_submit) must trigger the TearSheet callback"
    assert not any(
        inp.get("id") == GATE_PASSWORD_INPUT_ID and inp.get("property") == "n_submit"
        for cb in portal_callbacks
        for inp in cb.get("inputs", [])
    ), "Enter key must not trigger the Portal callback"


def test_wrong_password_message_constant():
    auth = AdminAuthManager(load_tkp_admin_auth_settings(), session_key=TKP_SESSION_KEY)
    ok, msg = auth.login({}, "definitely-wrong-password")
    assert not ok
    assert msg == INVALID_PASSWORD_MESSAGE


def test_empty_password_blocked():
    auth = AdminAuthManager(load_tkp_admin_auth_settings(), session_key=TKP_SESSION_KEY)
    ok, _msg = auth.login({}, "")
    assert not ok


def test_correct_password_authenticates():
    auth = AdminAuthManager(load_tkp_admin_auth_settings(), session_key=TKP_SESSION_KEY)
    session: dict = {}
    ok, _msg = auth.login(session, TEST_TOKEN)
    assert ok
    assert auth.is_authenticated(session)


def test_admin_portal_requires_auth(tkp_app):
    with tkp_app.server.test_client() as client:
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")


def test_admin_portal_returns_200_when_authenticated(tkp_app):
    with tkp_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[TKP_SESSION_KEY] = True
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"portal-account-registry" in response.data
        assert b"TKP" in response.data
        assert b"Daily entry" in response.data


def test_admin_portal_matches_account_registry_columns_and_is_pending(tkp_app):
    from tearsheet_portal import PORTAL_COLUMNS

    with tkp_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[TKP_SESSION_KEY] = True
        response = client.get("/admin")
        for column in PORTAL_COLUMNS:
            assert column.encode("utf-8") in response.data
        # TKP has no participating-account registry yet -> Pending empty state.
        assert b"Pending" in response.data


def test_healthz_is_real_json(tkp_app):
    with tkp_app.server.test_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload is not None
        assert payload["app"] == "tkp"


def test_admin_logout_clears_session(tkp_app):
    with tkp_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[TKP_SESSION_KEY] = True
        client.get("/admin/logout")
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 302


def test_runtime_token_not_in_layout(tkp_app):
    import tkp_ts

    layout = _layout_text(tkp_ts.app)
    assert TEST_TOKEN not in layout
