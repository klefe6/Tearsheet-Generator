"""Tests for tcp_config.py (no production imports)."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import tcp_config

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_default_config_values(monkeypatch):
    for name in (
        "TCP_V2_STATE_MODE",
        "TCP_V2_STATE_PATH",
        "TCP_V2_STATE_BACKUP_PATH",
        "TCP_V2_STATE_LOCK_PATH",
        "TCP_V2_WORKBOOK_PATH",
        "TCP_V2_ALLOW_WORKBOOK_FALLBACK",
    ):
        monkeypatch.delenv(name, raising=False)
    cfg = tcp_config.load_config()
    assert cfg.app_code == "tcp"
    assert cfg.app_name == "TCP"
    assert cfg.preview_label == "TCP v2 Preview — Read Only"
    assert cfg.workbook_filename == "tcp_alex.xlsx"
    assert cfg.sheet_name == "NAV"
    assert cfg.date_column == "Date"
    assert cfg.nav_column == "nav-x1"
    assert cfg.state_filename == "tcp_daily_returns_secret_state.json"
    assert cfg.state_backup_filename == "tcp_daily_returns_secret_state.backup.json"
    assert cfg.lock_filename == "tcp_daily_returns_secret_state.lock"
    assert cfg.export_filename == "tcp_daily_returns_export.xlsx"
    assert cfg.preview_port == 8312
    assert cfg.production_port == 8302
    assert cfg.debug is False
    assert cfg.state_mode == "workbook"
    assert cfg.read_only is True


def test_validate_default_config_passes():
    cfg = tcp_config.load_config()
    ok, msg = tcp_config.validate_config(cfg)
    assert ok, msg


@pytest.mark.parametrize(
    "mutator,expected_substring",
    [
        (lambda c: _replace(c, workbook_filename="tkp_alex.xlsx"), "tkp"),
        (lambda c: _replace(c, sheet_name="Sheet1"), "Sheet1"),
        (lambda c: _replace(c, state_filename="daily_returns_secret_state.json"), "collides"),
        (lambda c: _replace(c, preview_port=8302), "8302"),
        (lambda c: _replace(c, preview_port=8200), "outside"),
        (lambda c: _replace(c, debug=True), "debug"),
        (lambda c: _replace(c, state_mode="invalid"), "state_mode"),
    ],
)
def test_validate_rejects_invalid_config(mutator, expected_substring):
    cfg = mutator(tcp_config.load_config())
    ok, msg = tcp_config.validate_config(cfg)
    assert not ok
    assert expected_substring.lower() in msg.lower()


def _replace(cfg: tcp_config.TCPConfig, **kwargs) -> tcp_config.TCPConfig:
    data = cfg.__dict__.copy()
    data.update(kwargs)
    return tcp_config.TCPConfig(**data)


def test_import_tcp_config_has_no_side_effects():
    """Import/reload and validate must not create JSON or touch the workbook."""
    cfg = tcp_config.load_config()
    active = REPO_ROOT / cfg.state_filename
    backup = REPO_ROOT / cfg.state_backup_filename
    lock = REPO_ROOT / cfg.lock_filename
    before = {"active": active.exists(), "backup": backup.exists(), "lock": lock.exists()}
    importlib.reload(tcp_config)
    cfg = tcp_config.load_config()
    ok, msg = tcp_config.validate_config(cfg)
    assert ok, msg
    after = {"active": active.exists(), "backup": backup.exists(), "lock": lock.exists()}
    assert before == after


def test_workbook_path_env_override(monkeypatch):
    custom = r"C:\custom\tcp_alex.xlsx"
    monkeypatch.setenv("TCP_V2_WORKBOOK_PATH", custom)
    cfg = tcp_config.load_config()
    assert cfg.workbook_path == custom
