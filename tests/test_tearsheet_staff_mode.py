"""Staff/admin-port mode: guard predicates, port defaults, and safety.

Staff mode (TEARSHEET_MODE=staff) serves the admin tearsheet password-free on
a dedicated loopback port; public exposure is Cloudflare Access's job. These
tests pin the fail-closed guard matrix so client hostnames/ports can never
pick up password-free admin by accident.
"""
from __future__ import annotations

import pytest
from flask import Flask

import tearsheet_local_admin as local_admin
import tearsheet_runtime_mode as runtime_mode
from tcp_config import (
    STAFF_PAGE_TITLE,
    is_staff_runtime,
    load_config,
    resolve_bind_port,
    resolve_page_title,
    show_preview_branding,
    validate_bind_port,
)

_flask_app = Flask(__name__)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runtime_mode.TEARSHEET_MODE_ENV, raising=False)
    monkeypatch.delenv(local_admin.LOCAL_DIRECT_ADMIN_ENV, raising=False)
    monkeypatch.delenv(local_admin.STAFF_ALLOWED_HOSTS_ENV, raising=False)
    monkeypatch.delenv(runtime_mode.TKP_BIND_PORT_ENV, raising=False)
    monkeypatch.delenv(runtime_mode.AGM_BIND_PORT_ENV, raising=False)
    monkeypatch.delenv("TCP_V2_BIND_PORT", raising=False)


def _staff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(runtime_mode.TEARSHEET_MODE_ENV, "staff")


def _request_ctx(host: str, remote_addr: str = "127.0.0.1", path: str = "/"):
    return _flask_app.test_request_context(
        path,
        headers={"Host": host},
        environ_base={"REMOTE_ADDR": remote_addr},
    )


# ── staff predicate: allow matrix ───────────────────────────────────────────

def test_staff_loopback_request_is_direct_admin(monkeypatch):
    _staff(monkeypatch)
    with _request_ctx("127.0.0.1:8321"):
        assert local_admin.is_staff_direct_admin_request()
        # staff serves admin on EVERY route, not just /admin/tearsheet
        assert local_admin.is_direct_admin_request("/")
        assert local_admin.is_direct_admin_request("/admin/tearsheet")
        assert local_admin.is_direct_admin_request("/anything")


def test_staff_allowlisted_admin_host_is_direct_admin(monkeypatch):
    _staff(monkeypatch)
    monkeypatch.setenv(
        local_admin.STAFF_ALLOWED_HOSTS_ENV,
        "tkp-admin.hcresearch.ltd, tcp-admin.hcresearch.ltd",
    )
    # tunnel: cloudflared connects from loopback with the public admin Host
    with _request_ctx("tkp-admin.hcresearch.ltd"):
        assert local_admin.is_staff_direct_admin_request()
    with _request_ctx("tcp-admin.hcresearch.ltd"):
        assert local_admin.is_direct_admin_request("/")


# ── staff predicate: deny matrix (fail-closed) ──────────────────────────────

def test_staff_denies_client_hostname(monkeypatch):
    """A client hostname pointed at a staff port must fall through to the gate."""
    _staff(monkeypatch)
    monkeypatch.setenv(local_admin.STAFF_ALLOWED_HOSTS_ENV, "tkp-admin.hcresearch.ltd")
    with _request_ctx("tkp-ts.hcresearch.ltd"):
        assert not local_admin.is_staff_direct_admin_request()
        assert not local_admin.is_direct_admin_request("/")


def test_staff_denies_unlisted_public_host_without_allowlist(monkeypatch):
    _staff(monkeypatch)
    with _request_ctx("tkp-admin.hcresearch.ltd"):
        assert not local_admin.is_staff_direct_admin_request()


def test_staff_denies_non_loopback_peer(monkeypatch):
    _staff(monkeypatch)
    monkeypatch.setenv(local_admin.STAFF_ALLOWED_HOSTS_ENV, "tkp-admin.hcresearch.ltd")
    with _request_ctx("tkp-admin.hcresearch.ltd", remote_addr="192.168.1.50"):
        assert not local_admin.is_staff_direct_admin_request()


def test_legacy_mode_never_staff_direct_admin(monkeypatch):
    monkeypatch.setenv(local_admin.STAFF_ALLOWED_HOSTS_ENV, "tkp-admin.hcresearch.ltd")
    with _request_ctx("127.0.0.1:8301"):
        assert not local_admin.is_staff_direct_admin_request()


def test_staff_requires_request_context(monkeypatch):
    _staff(monkeypatch)
    assert not local_admin.is_staff_direct_admin_request()


# ── combinator keeps the local-dev bypass semantics on client ports ─────────

def test_local_bypass_still_requires_loopback_host(monkeypatch):
    monkeypatch.setenv(local_admin.LOCAL_DIRECT_ADMIN_ENV, "1")
    with _request_ctx("127.0.0.1:8304", path="/admin/tearsheet"):
        assert local_admin.is_direct_admin_request("/admin/tearsheet")
        assert not local_admin.is_direct_admin_request("/")  # path-scoped
    # tunnel Host header (client hostname) must never trigger the local bypass
    with _request_ctx("agm-ts.hcresearch.ltd", path="/admin/tearsheet"):
        assert not local_admin.is_direct_admin_request("/admin/tearsheet")


def test_no_flags_no_direct_admin(monkeypatch):
    with _request_ctx("127.0.0.1:8304", path="/admin/tearsheet"):
        assert not local_admin.is_direct_admin_request("/admin/tearsheet")


# ── staff-aware bind ports ──────────────────────────────────────────────────

def test_staff_default_ports(monkeypatch):
    _staff(monkeypatch)
    assert runtime_mode.resolve_tkp_bind_port() == 8321
    assert runtime_mode.resolve_agm_bind_port() == 8324
    assert resolve_bind_port(load_config()) == 8322


def test_staff_port_env_override_still_wins(monkeypatch):
    _staff(monkeypatch)
    monkeypatch.setenv(runtime_mode.TKP_BIND_PORT_ENV, "8391")
    monkeypatch.setenv(runtime_mode.AGM_BIND_PORT_ENV, "8394")
    monkeypatch.setenv("TCP_V2_BIND_PORT", "8392")
    assert runtime_mode.resolve_tkp_bind_port() == 8391
    assert runtime_mode.resolve_agm_bind_port() == 8394
    assert resolve_bind_port(load_config()) == 8392


def test_legacy_default_ports_unchanged():
    assert runtime_mode.resolve_tkp_bind_port() == 8301
    assert runtime_mode.resolve_agm_bind_port() == 8304
    cfg = load_config()
    assert resolve_bind_port(cfg) == cfg.preview_port


# ── TCP staff validation + branding ─────────────────────────────────────────

def test_tcp_staff_port_passes_validation_only_in_staff_mode(monkeypatch):
    cfg = load_config()
    ok, msg = validate_bind_port(cfg, 8322)
    assert not ok  # legacy: 8322 outside preview range, not production
    _staff(monkeypatch)
    ok, msg = validate_bind_port(cfg, 8322)
    assert ok, msg


def test_tcp_production_validation_unchanged_in_staff_mode(monkeypatch):
    cfg = load_config()
    assert validate_bind_port(cfg, 8302)[0]
    assert validate_bind_port(cfg, 8312)[0]
    _staff(monkeypatch)
    assert validate_bind_port(cfg, 8302)[0]
    assert validate_bind_port(cfg, 8312)[0]


def test_tcp_staff_branding(monkeypatch):
    cfg = load_config()
    assert show_preview_branding(cfg)  # legacy preview default
    _staff(monkeypatch)
    assert is_staff_runtime()
    assert not show_preview_branding(cfg)
    assert resolve_page_title(cfg) == STAFF_PAGE_TITLE


def test_tcp_production_branding_unaffected(monkeypatch):
    monkeypatch.setenv("TCP_V2_BIND_PORT", "8302")
    cfg = load_config()
    assert not show_preview_branding(cfg)
    assert resolve_page_title(cfg) == "H&C – TCP"
