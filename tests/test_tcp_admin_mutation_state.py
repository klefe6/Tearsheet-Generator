"""TCP v2 admin mutation modal and revision hydration regressions."""
from __future__ import annotations

from layout_helpers import layout_text

import socket
from dataclasses import replace
from pathlib import Path

import pytest

from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_runtime_state import bootstrap_state_from_workbook, persist_delete_last_row
from tcp_state import StatePaths, save_state
from tcp_ts_v2 import (
    ADMIN_AUTH_REVISION_STORE_ID,
    authoritative_server_revision,
    explicit_button_click,
    next_admin_auth_revision,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = REPO_ROOT / "tests" / "_tmp_mutation_state"
TEST_TOKEN = "test-admin-mutation-token"
TEST_SECRET = "test-admin-mutation-secret"
PREVIEW_PORT = 8312


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def state_tmp(request):
    import shutil

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    path = TMP_DIR / safe
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(scope="session")
def workbook_ledger():
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    from tcp_ledger import load_ledger

    return load_ledger(str(wb))


def _json_cfg(state_tmp: Path) -> object:
    base = load_config()
    return replace(
        base,
        state_mode="json_active",
        state_active_path=str(state_tmp / "tcp_test_state.json"),
        state_backup_path=str(state_tmp / "tcp_test_state.backup.json"),
        state_lock_path=str(state_tmp / "tcp_test_state.lock"),
    )


@pytest.fixture(scope="module")
def app_bundle():
    import os

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = TEST_TOKEN
    os.environ["TCP_V2_SESSION_SECRET"] = TEST_SECRET
    settings = AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)
    from tcp_layout_support import tcp_layout_benchmark_patches
    from tcp_ts_v2 import create_app

    with tcp_layout_benchmark_patches():
        bundle = create_app(auth_settings=settings)
        yield bundle
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def client(app_bundle):
    app, *_ = app_bundle
    return app.server.test_client()


def _callback_outputs(app, needle: str):
    return [str(cb.get("output", "")) for cb in app.callback_map.values() if needle in str(cb.get("output", ""))]


def test_gate_login_does_not_increment_data_revision():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    gate_block = source.split("def _gate_admin_login", 1)[1].split("\n    @app.callback", 1)[0]
    assert "admin-state-revision-store" not in gate_block.split("return", 1)[0]
    assert "next_admin_auth_revision" in gate_block
    assert "(revision or 0) + 1" not in gate_block


def test_reset_admin_mutation_state_callback_registered(app_bundle):
    app, *_ = app_bundle
    assert any(
        "admin-delete-modal.is_open" in out
        and ADMIN_AUTH_REVISION_STORE_ID in str(cb.get("inputs", []))
        for cb in app.callback_map.values()
        for out in _callback_outputs(app, "admin-delete-modal.is_open")
    )


def test_admin_auth_revision_store_in_layout(app_bundle):
    app, *_ = app_bundle
    assert ADMIN_AUTH_REVISION_STORE_ID in layout_text(app)


def test_login_with_matching_revision_leaves_delete_modal_closed(app_bundle):
    from tcp_admin import build_delete_modal

    modal = build_delete_modal(persistence_enabled=True)
    assert modal.is_open is False
    app, *_ = app_bundle
    reset_outputs = [
        str(cb.get("output", ""))
        for cb in app.callback_map.values()
        if ADMIN_AUTH_REVISION_STORE_ID in str(cb.get("inputs", []))
        and "admin-delete-modal.is_open" in str(cb.get("output", ""))
    ]
    assert reset_outputs


def test_stale_client_revision_helpers():
    assert next_admin_auth_revision(1) == 2
    holder = {"snapshot": type("Snap", (), {"state_revision": 1})()}
    assert authoritative_server_revision(holder) == 1


def test_login_reset_callback_rehydrates_server_revision(app_bundle):
    app, cfg, state, *_ = app_bundle
    assert state.snapshot is not None
    reset_cb = None
    for cb in app.callback_map.values():
        outputs = str(cb.get("output", ""))
        if "admin-state-revision-store.data" in outputs and ADMIN_AUTH_REVISION_STORE_ID in str(cb.get("inputs", [])):
            reset_cb = cb
            break
    assert reset_cb is not None


def test_explicit_delete_trigger_requires_positive_clicks():
    assert not explicit_button_click("admin-open-delete-modal", "admin-open-delete-modal", 0)
    assert not explicit_button_click("admin-open-delete-modal", "admin-open-delete-modal", None)
    assert explicit_button_click("admin-open-delete-modal", "admin-open-delete-modal", 1)


def test_explicit_add_trigger_requires_positive_clicks():
    assert not explicit_button_click("admin-open-add-modal", "admin-open-add-modal", 0)
    assert explicit_button_click("admin-open-add-modal", "admin-open-add-modal", 2)


def test_delete_callback_uses_explicit_click_guard():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    delete_block = source.split("def _delete_row", 1)[1].split("\n    @app.callback", 1)[0]
    assert "explicit_button_click" in delete_block
    assert 'return no_update, no_update, no_update, no_update, no_update, no_update, no_update' in delete_block


def test_add_callback_uses_explicit_click_guard():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    add_block = source.split("def _toggle_add_modal", 1)[1].split("\n    @app.callback", 1)[0]
    assert "explicit_button_click" in add_block


def test_stale_explicit_delete_rejected_without_mutation(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    state = bootstrap_state_from_workbook(cfg, workbook_ledger)
    save_state(state, paths)
    latest_date = workbook_ledger.completed_records[-1].fields["Date"]
    if hasattr(latest_date, "isoformat"):
        latest_date = latest_date.isoformat()
    result = persist_delete_last_row(
        cfg,
        paths,
        expected_revision=2,
        expected_final_date=str(latest_date),
        authenticated=True,
    )
    assert not result.success
    assert "Stale revision" in (result.error_message or "")


def test_conflict_handling_refreshes_revision_on_delete_failure():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    delete_block = source.split("def _delete_row", 1)[1].split("\n    @app.callback", 1)[0]
    assert "snap.state_revision" in delete_block


def test_conflict_handling_refreshes_revision_on_add_failure():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    save_block = source.split("def _save_add_row", 1)[1].split("\n    @app.callback", 1)[0]
    assert "refreshed_revision = current_snapshot().state_revision" in save_block


def test_public_users_cannot_persist_delete_unauthenticated():
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT / "tests" / "_tmp_canary_layout")
    paths = StatePaths(active_path=active, backup_path=backup, lock_path=lock)
    result = persist_delete_last_row(
        cfg,
        paths,
        expected_revision=1,
        expected_final_date="2026-06-24",
        authenticated=False,
    )
    assert not result.success


def test_import_starts_no_server():
    assert not _port_listening(PREVIEW_PORT)
    import tcp_ts_v2  # noqa: F401

    assert not _port_listening(PREVIEW_PORT)
