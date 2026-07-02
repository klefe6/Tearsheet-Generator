"""Step 10 resilience acceptance tests (disposable state only)."""
from __future__ import annotations

import json
import shutil
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from tcp_config import TCPConfig, load_config
from tcp_ledger import load_ledger
from tcp_runtime_state import (
    bootstrap_state_from_workbook,
    load_runtime_snapshot,
    persist_add_row,
    persist_delete_last_row,
)
from tcp_state import StateLockError, StatePaths, save_state, serialize_state

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP = REPO_ROOT / "tests" / "_acceptance_state"
TKP_STATE = REPO_ROOT / "daily_returns_secret_state.json"


@pytest.fixture
def disposable(request):
    TMP.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    root = TMP / safe
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    paths = StatePaths(
        active_path=root / "state.json",
        backup_path=root / "state.backup.json",
        lock_path=root / "state.lock",
    )
    yield root, paths
    if root.exists():
        shutil.rmtree(root)


@pytest.fixture(scope="session")
def workbook_ledger():
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("workbook unavailable")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


def _cfg(root: Path, paths: StatePaths, **kwargs) -> TCPConfig:
    base = load_config()
    return replace(
        base,
        state_mode=kwargs.get("state_mode", "json_active"),
        state_active_path=str(paths.active_path),
        state_backup_path=str(paths.backup_path),
        state_lock_path=str(paths.lock_path),
        allow_workbook_fallback=kwargs.get("allow_workbook_fallback", True),
    )


def _seed(paths: StatePaths, ledger, cfg: TCPConfig) -> None:
    save_state(bootstrap_state_from_workbook(cfg, ledger), paths)


def test_g1_normal_startup(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "json"
    assert snap.state_revision == 1
    assert len(snap.records) == 112


def test_g2_missing_active_fallback(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "workbook_fallback"
    assert not snap.writable


def test_g3_corrupt_active_valid_backup(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    shutil.copy2(paths.active_path, paths.backup_path)
    paths.active_path.write_text("{bad", encoding="utf-8")
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "json_backup"
    assert snap.recovery_status == "recovered_backup"
    assert not snap.writable


def test_g4_invalid_active_and_backup_fallback(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    paths.active_path.write_text("{bad", encoding="utf-8")
    paths.backup_path.write_text("{bad", encoding="utf-8")
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "workbook_fallback"
    assert not snap.writable


def test_g5_fallback_disabled(disposable):
    _, paths = disposable
    cfg = _cfg(Path("."), paths, allow_workbook_fallback=False)
    with pytest.raises(Exception):
        load_runtime_snapshot(cfg, paths)


def test_g6_interrupted_write_preserves_active(disposable, workbook_ledger, monkeypatch):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    before = paths.active_path.read_bytes()

    def fail_replace(*_args, **_kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("tcp_state.os.replace", fail_replace)
    prior = workbook_ledger.completed_records[-1].fields
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    assert not result.success
    assert paths.active_path.read_bytes() == before


def test_g7_concurrent_writers(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    results = []

    def worker():
        results.append(
            persist_add_row(
                cfg,
                paths,
                expected_revision=1,
                row_date="2026-06-25",
                cash_balance=45000,
                cash_transfers=0,
                tranche_count=int(prior["#"]),
                authenticated=True,
            )
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r.success) == 1


def test_g8_duplicate_submission(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    first = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    second = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    assert first.success
    assert not second.success


def test_g9_stale_delete_preview(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    add = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    assert add.success
    stale = persist_delete_last_row(
        cfg,
        paths,
        expected_revision=1,
        expected_final_date="2026-06-24",
        authenticated=True,
    )
    assert not stale.success


def test_g10_lock_timeout(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    lock = __import__("tcp_state").StateFileLock(paths.lock_path, timeout=0.01)
    try:
        with lock:
            prior = workbook_ledger.completed_records[-1].fields
            result = persist_add_row(
                cfg,
                paths,
                expected_revision=1,
                row_date="2026-06-25",
                cash_balance=45000,
                cash_transfers=0,
                tranche_count=int(prior["#"]),
                authenticated=True,
            )
            assert not result.success
    except StateLockError:
        pytest.fail("outer lock should have been acquired")


def test_g11_restart_persistence(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.state_revision == 2
    assert len(snap.records) == 113


def test_g12_missing_secrets_disable_writes(monkeypatch):
    from tcp_admin import AdminAuthManager
    from tcp_config import AdminAuthSettings

    monkeypatch.delenv("TCP_V2_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("TCP_V2_SESSION_SECRET", raising=False)
    mgr = AdminAuthManager(AdminAuthSettings(admin_token=None, session_secret=None))
    assert not mgr.is_configured


def test_g13_workbook_mode_rollback(disposable, workbook_ledger):
    _, paths = disposable
    cfg_json = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg_json)
    before = paths.active_path.read_bytes()
    cfg_wb = replace(cfg_json, state_mode="workbook")
    snap = load_runtime_snapshot(cfg_wb, paths)
    assert snap.data_source == "workbook"
    assert not snap.writable
    assert paths.active_path.read_bytes() == before
    snap2 = load_runtime_snapshot(cfg_json, paths)
    assert snap2.state_revision == 1


def test_g14_tkp_isolation(disposable, workbook_ledger):
    _, paths = disposable
    cfg = _cfg(Path("."), paths)
    _seed(paths, workbook_ledger, cfg)
    tkp_before = TKP_STATE.stat().st_size if TKP_STATE.is_file() else None
    prior = workbook_ledger.completed_records[-1].fields
    persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    if tkp_before is not None:
        assert TKP_STATE.stat().st_size == tkp_before
