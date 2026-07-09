"""Tests for shared tearsheet runtime mode and bind-port helpers."""
from __future__ import annotations

import importlib
import os

import pytest

import tearsheet_runtime_mode as runtime_mode
from tearsheet_gate_ui import GATE_NOTICE_E_ID
from tcp_config import load_config, resolve_bind_port


@pytest.fixture(autouse=True)
def _clear_runtime_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runtime_mode.TEARSHEET_MODE_ENV, raising=False)
    monkeypatch.delenv(runtime_mode.TKP_BIND_PORT_ENV, raising=False)
    monkeypatch.delenv(runtime_mode.AGM_BIND_PORT_ENV, raising=False)
    monkeypatch.delenv("TCP_V2_BIND_PORT", raising=False)


def test_unset_env_defaults_to_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runtime_mode.TEARSHEET_MODE_ENV, raising=False)
    assert runtime_mode.load_runtime_mode() == "legacy"
    assert runtime_mode.is_legacy()
    assert not runtime_mode.is_public()
    assert not runtime_mode.is_staff()
    assert not runtime_mode.is_portal()


@pytest.mark.parametrize(
    "raw",
    ["legacy", "public", "staff", "portal", "LEGACY", " Public ", "STAFF", "Portal"],
)
def test_valid_modes_parse_correctly(raw: str) -> None:
    assert runtime_mode.parse_tearsheet_mode(raw) == raw.strip().lower()


@pytest.mark.parametrize("raw", ["", "unknown", "prod", "preview"])
def test_invalid_mode_falls_back_to_legacy(raw: str) -> None:
    assert runtime_mode.parse_tearsheet_mode(raw) == "legacy"


def test_mode_predicate_helpers_accept_explicit_mode() -> None:
    assert runtime_mode.is_legacy("legacy")
    assert runtime_mode.is_public("public")
    assert runtime_mode.is_staff("staff")
    assert runtime_mode.is_portal("portal")
    assert not runtime_mode.is_legacy("portal")


def test_tkp_default_bind_port_is_8301() -> None:
    assert runtime_mode.resolve_tkp_bind_port() == 8301


def test_agm_default_bind_port_is_8304() -> None:
    assert runtime_mode.resolve_agm_bind_port() == 8304


def test_tkp_bind_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(runtime_mode.TKP_BIND_PORT_ENV, "8310")
    assert runtime_mode.resolve_tkp_bind_port() == 8310


def test_agm_bind_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(runtime_mode.AGM_BIND_PORT_ENV, "8314")
    assert runtime_mode.resolve_agm_bind_port() == 8314


def test_invalid_bind_port_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(runtime_mode.TKP_BIND_PORT_ENV, "not-a-port")
    assert runtime_mode.resolve_tkp_bind_port() == 8301


def test_tcp_existing_bind_port_config_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config()
    assert resolve_bind_port(cfg) == cfg.preview_port
    monkeypatch.setenv("TCP_V2_BIND_PORT", "8309")
    assert resolve_bind_port(cfg) == 8309
    assert runtime_mode.resolve_tcp_bind_port(cfg) == 8309


def test_legacy_session_cookie_name_unchanged() -> None:
    assert runtime_mode.resolve_session_cookie_name("tkp") is None
    assert runtime_mode.resolve_session_cookie_name("tcp") is None
    assert runtime_mode.resolve_session_cookie_name("agm") is None


def test_non_legacy_session_cookie_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(runtime_mode.TEARSHEET_MODE_ENV, "public")
    assert runtime_mode.resolve_session_cookie_name("tkp") == "tkp_session"
    assert runtime_mode.resolve_session_cookie_name("tcp") == "tcp_session"
    assert runtime_mode.resolve_session_cookie_name("agm") == "agm_session"


def test_planned_staff_and_portal_ports() -> None:
    assert runtime_mode.resolve_planned_bind_port("tkp", "staff") == 8321
    assert runtime_mode.resolve_planned_bind_port("tcp", "staff") == 8322
    assert runtime_mode.resolve_planned_bind_port("agm", "staff") == 8324
    assert runtime_mode.resolve_planned_bind_port("tkp", "portal") == 8331
    assert runtime_mode.resolve_planned_bind_port("tcp", "portal") == 8332
    assert runtime_mode.resolve_planned_bind_port("agm", "portal") == 8334


def test_apply_runtime_session_config_legacy_leaves_default_cookie_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tcp_config import load_admin_auth_settings

    class _Server:
        config: dict = {}

    server = _Server()
    runtime_mode.apply_runtime_session_config(
        server,
        load_admin_auth_settings(),
        "tcp",
    )
    assert "SESSION_COOKIE_NAME" not in server.config


def test_apply_runtime_session_config_public_sets_strategy_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tcp_config import load_admin_auth_settings

    monkeypatch.setenv(runtime_mode.TEARSHEET_MODE_ENV, "public")

    class _Server:
        config: dict = {}

    server = _Server()
    runtime_mode.apply_runtime_session_config(
        server,
        load_admin_auth_settings(),
        "tcp",
    )
    assert server.config["SESSION_COOKIE_NAME"] == "tcp_session"


@pytest.mark.parametrize(
    ("module_name", "layout_attr"),
    [
        ("tkp_ts", "disclaimer_screen"),
        ("tcp_ts_v2", "app"),
    ],
)
def test_legacy_layout_still_has_hidden_e(module_name: str, layout_attr: str) -> None:
    mod = importlib.import_module(module_name)
    target = getattr(mod, layout_attr)
    layout = str(target.layout if hasattr(target, "layout") else target)
    assert GATE_NOTICE_E_ID in layout


def test_legacy_agm_layout_still_has_hidden_e() -> None:
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert GATE_NOTICE_E_ID in layout


def test_monthly_route_returns_404_for_tkp_and_tcp() -> None:
    from tkp_ts import app as tkp_app
    from tcp_ts_v2 import app as tcp_app

    for client_factory in (tkp_app.server.test_client, tcp_app.server.test_client):
        client = client_factory()
        response = client.get("/monthly")
        assert response.status_code == 404


def test_register_monthly_backup_404_is_idempotent() -> None:
    from flask import Flask

    server = Flask(__name__)
    runtime_mode.register_monthly_backup_404(server)
    rules_before = [rule.rule for rule in server.url_map.iter_rules()]
    runtime_mode.register_monthly_backup_404(server)
    rules_after = [rule.rule for rule in server.url_map.iter_rules()]
    assert rules_before.count("/monthly") == 1
    assert rules_after.count("/monthly") == 1
