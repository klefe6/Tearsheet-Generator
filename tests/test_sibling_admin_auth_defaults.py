"""Shared sibling admin auth defaults for TKP, TCP, and AGM tearsheets."""
from __future__ import annotations

import pytest

from tearsheet_gate_auth import (
    AGM_SESSION_KEY,
    TKP_SESSION_KEY,
    load_agm_admin_auth_settings,
    load_tkp_admin_auth_settings,
)
from tcp_admin import AdminAuthManager, SESSION_KEY
from tcp_config import (
    DEFAULT_SIBLING_ADMIN_TOKEN,
    load_admin_auth_settings,
    resolve_sibling_admin_auth_settings,
)

DEFAULT_PASSWORD = DEFAULT_SIBLING_ADMIN_TOKEN
OVERRIDE_TOKEN = "override-admin-token"
OVERRIDE_SECRET = "override-session-secret"


def _clear_sibling_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TKP_ADMIN_TOKEN",
        "TKP_SESSION_SECRET",
        "TCP_V2_ADMIN_TOKEN",
        "TCP_V2_SESSION_SECRET",
        "AGM_ADMIN_TOKEN",
        "AGM_SESSION_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("loader", "session_key"),
    [
        (load_tkp_admin_auth_settings, TKP_SESSION_KEY),
        (load_admin_auth_settings, SESSION_KEY),
        (load_agm_admin_auth_settings, AGM_SESSION_KEY),
    ],
)
def test_default_gc11_when_env_vars_absent(monkeypatch, loader, session_key):
    _clear_sibling_auth_env(monkeypatch)
    auth = AdminAuthManager(loader(), session_key=session_key)
    assert auth.is_configured
    session: dict = {}
    ok, _msg = auth.login(session, DEFAULT_PASSWORD)
    assert ok
    assert auth.is_authenticated(session)


@pytest.mark.parametrize(
    ("loader", "session_key", "token_env", "secret_env"),
    [
        (load_tkp_admin_auth_settings, TKP_SESSION_KEY, "TKP_ADMIN_TOKEN", "TKP_SESSION_SECRET"),
        (load_admin_auth_settings, SESSION_KEY, "TCP_V2_ADMIN_TOKEN", "TCP_V2_SESSION_SECRET"),
        (load_agm_admin_auth_settings, AGM_SESSION_KEY, "AGM_ADMIN_TOKEN", "AGM_SESSION_SECRET"),
    ],
)
def test_env_override_replaces_default_password(
    monkeypatch, loader, session_key, token_env, secret_env
):
    _clear_sibling_auth_env(monkeypatch)
    monkeypatch.setenv(token_env, OVERRIDE_TOKEN)
    monkeypatch.setenv(secret_env, OVERRIDE_SECRET)
    auth = AdminAuthManager(loader(), session_key=session_key)
    session: dict = {}
    ok, _msg = auth.login(session, OVERRIDE_TOKEN)
    assert ok
    ok, _msg = auth.login({}, DEFAULT_PASSWORD)
    assert not ok


@pytest.mark.parametrize(
    ("loader", "session_key"),
    [
        (load_tkp_admin_auth_settings, TKP_SESSION_KEY),
        (load_admin_auth_settings, SESSION_KEY),
        (load_agm_admin_auth_settings, AGM_SESSION_KEY),
    ],
)
def test_bad_password_blocked_with_defaults(monkeypatch, loader, session_key):
    _clear_sibling_auth_env(monkeypatch)
    auth = AdminAuthManager(loader(), session_key=session_key)
    ok, msg = auth.login({}, "definitely-wrong-password")
    assert not ok
    assert msg == "Invalid password"


def test_resolve_helper_uses_shared_defaults_when_env_missing(monkeypatch):
    _clear_sibling_auth_env(monkeypatch)
    settings = resolve_sibling_admin_auth_settings(
        admin_token_env="AGM_ADMIN_TOKEN",
        session_secret_env="AGM_SESSION_SECRET",
    )
    assert settings.is_configured
    assert settings.admin_token == DEFAULT_PASSWORD
