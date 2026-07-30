"""TCP v2 production vs preview labeling and page title contracts."""
from __future__ import annotations

from layout_helpers import layout_text

import socket

import pytest

from tcp_config import PREVIEW_PAGE_TITLE, PRODUCTION_PAGE_TITLE, load_config, resolve_page_title
from tcp_public_sections import PREVIEW_BANNER_CLASS, RUNTIME_DIAGNOSTICS_CARD_ID


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _create_app(monkeypatch, *, bind_port: str | None):
    if bind_port is None:
        monkeypatch.delenv("TCP_V2_BIND_PORT", raising=False)
    else:
        monkeypatch.setenv("TCP_V2_BIND_PORT", bind_port)
    from tcp_ts_v2 import create_app

    return create_app()


def test_resolve_page_title_preview_mode():
    cfg = load_config()
    assert resolve_page_title(cfg) == PREVIEW_PAGE_TITLE
    assert "TCP v2 Preview" in resolve_page_title(cfg)


def test_resolve_page_title_production_mode(monkeypatch):
    monkeypatch.setenv("TCP_V2_BIND_PORT", "8302")
    cfg = load_config()
    assert resolve_page_title(cfg) == PRODUCTION_PAGE_TITLE
    assert "Preview" not in resolve_page_title(cfg)


def test_preview_mode_title_contains_tcp_v2_preview(monkeypatch):
    app, _cfg, state, *_ = _create_app(monkeypatch, bind_port=None)
    if state.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    assert "TCP v2 Preview" in app.title
    assert app.title == PREVIEW_PAGE_TITLE


def test_production_mode_title_excludes_preview(monkeypatch):
    app, _cfg, state, *_ = _create_app(monkeypatch, bind_port="8302")
    if state.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    assert "Preview" not in app.title
    assert app.title == PRODUCTION_PAGE_TITLE


def test_production_public_layout_hides_preview_diagnostics(monkeypatch):
    app, _cfg, state, *_ = _create_app(monkeypatch, bind_port="8302")
    if state.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout = layout_text(app)
    assert RUNTIME_DIAGNOSTICS_CARD_ID not in layout
    assert "Runtime diagnostics (preview only)" not in layout
    assert PREVIEW_BANNER_CLASS not in layout
    assert "TCP v2 Preview" not in layout
    assert "Read Only" not in layout


def test_preview_mode_retains_diagnostics(monkeypatch):
    app, _cfg, state, *_ = _create_app(monkeypatch, bind_port=None)
    if state.snapshot is None:
        pytest.skip("Runtime not healthy in this environment")
    layout = layout_text(app)
    assert RUNTIME_DIAGNOSTICS_CARD_ID in layout
    assert "Runtime diagnostics (preview only)" in layout
    assert "TCP v2 Preview" in layout


def test_import_starts_no_server():
    assert not _port_listening(8312), "Port 8312 already in use before import"
    import tcp_ts_v2  # noqa: F401

    assert not _port_listening(8312), "Importing tcp_ts_v2 must not start the server"
