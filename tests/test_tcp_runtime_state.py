"""Tests for TCP v2 runtime state orchestration and JSON mutations."""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from tcp_config import TCPConfig, load_config, resolve_state_paths
from tcp_ledger import load_ledger
from tcp_runtime_state import (
    bootstrap_state_from_workbook,
    load_runtime_snapshot,
    persist_add_row,
    persist_delete_last_row,
)
from tcp_state import StatePaths, save_state, serialize_state

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = REPO_ROOT / "tests" / "_tmp_state"


@pytest.fixture
def state_tmp(request):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    path = TMP_DIR / safe
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture
def state_paths(state_tmp):
    return StatePaths(
        active_path=state_tmp / "tcp_test_state.json",
        backup_path=state_tmp / "tcp_test_state.backup.json",
        lock_path=state_tmp / "tcp_test_state.lock",
    )


@pytest.fixture(scope="session")
def workbook_ledger():
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


def _json_cfg(state_tmp: Path, *, mode: str = "json_active", fallback: bool = True) -> TCPConfig:
    base = load_config()
    return replace(
        base,
        state_mode=mode,
        state_active_path=str(state_tmp / "tcp_test_state.json"),
        state_backup_path=str(state_tmp / "tcp_test_state.backup.json"),
        state_lock_path=str(state_tmp / "tcp_test_state.lock"),
        allow_workbook_fallback=fallback,
    )


def _seed(paths: StatePaths, ledger, cfg: TCPConfig) -> dict:
    state = bootstrap_state_from_workbook(cfg, ledger)
    save_state(state, paths)
    return state


def test_workbook_mode_disables_writes(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp, mode="workbook")
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "workbook"
    assert not snap.writable


def test_json_active_loads_valid_state(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "json"
    assert snap.writable
    assert snap.state_revision == 1
    assert len(snap.records) == 112


def test_json_single_source_for_public_and_admin(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.ledger.metadata.completed_row_count == len(snap.canonical_nav)


def test_reload_after_app_recreate(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    first = load_runtime_snapshot(cfg, paths)
    second = load_runtime_snapshot(cfg, paths)
    assert first.state_revision == second.state_revision
    assert len(first.records) == len(second.records)


def test_missing_json_fallback(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "workbook_fallback"
    assert not snap.writable
    assert snap.warning


def test_corrupt_active_valid_backup(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    shutil.copy2(paths.active_path, paths.backup_path)
    paths.active_path.write_text("{bad json", encoding="utf-8")
    snap = load_runtime_snapshot(cfg, paths)
    assert snap.data_source == "json_backup"
    assert snap.recovery_status == "recovered_backup"
    assert not snap.writable


def test_no_fallback_when_disabled(state_tmp):
    cfg = _json_cfg(state_tmp, fallback=False)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    with pytest.raises(Exception):
        load_runtime_snapshot(cfg, paths)


def test_read_does_not_create_state(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    load_runtime_snapshot(cfg, paths)
    assert not paths.active_path.exists()


def test_health_fields_safe_metadata(state_tmp, workbook_ledger):
    from tcp_runtime_state import health_fields_from_snapshot

    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    snap = load_runtime_snapshot(cfg, paths)
    fields = health_fields_from_snapshot(snap, auth_configured=True)
    assert "state_mode" in fields
    assert "Hughes" not in json.dumps(fields)


def test_unauthenticated_save_rejected(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=False,
    )
    assert not result.success


def test_workbook_mode_save_rejected(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp, mode="workbook")
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
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


def test_valid_authenticated_save(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
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
    assert result.success
    assert result.revision == 2
    assert len(result.snapshot.records) == 113
    assert result.saved_date == "2026-06-25"
    assert abs(result.saved_nav - 45867.734) < 0.01
    assert paths.backup_path.is_file()
    backup = json.loads(paths.backup_path.read_text(encoding="utf-8"))
    assert backup["revision"] == 1


def test_stale_revision_rejected(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=99,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    assert not result.success
    assert "stale" in (result.error_message or "").lower()


def test_negative_transfer_rejected_on_save(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    _seed(paths, workbook_ledger, cfg)
    prior = workbook_ledger.completed_records[-1].fields
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=-1,
        tranche_count=int(prior["#"]),
        authenticated=True,
    )
    assert not result.success


def test_concurrent_same_revision_writes(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
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
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    successes = [r for r in results if r.success]
    assert len(successes) == 1


def test_delete_final_row(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
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
    delete = persist_delete_last_row(
        cfg,
        paths,
        expected_revision=2,
        expected_final_date="2026-06-25",
        authenticated=True,
    )
    assert delete.success
    assert delete.revision == 3
    assert len(delete.snapshot.records) == 112
    assert delete.saved_date == "2026-06-24"


def test_minimum_row_guard(state_tmp, workbook_ledger):
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
    state = bootstrap_state_from_workbook(cfg, workbook_ledger)
    state["records"] = state["records"][:1]
    state["record_count"] = 1
    state["latest_completed_date"] = state["records"][0]["Date"]
    save_state(state, paths)
    result = persist_delete_last_row(
        cfg,
        paths,
        expected_revision=1,
        expected_final_date=state["records"][0]["Date"],
        authenticated=True,
    )
    assert not result.success


@pytest.mark.local_workbook
def test_workbook_unchanged_after_mutation(state_tmp, workbook_ledger):
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    before = hashlib.sha256(wb.read_bytes()).hexdigest()
    cfg = _json_cfg(state_tmp)
    paths = StatePaths(
        active_path=Path(cfg.state_active_path),
        backup_path=Path(cfg.state_backup_path),
        lock_path=Path(cfg.state_lock_path),
    )
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
    after = hashlib.sha256(wb.read_bytes()).hexdigest()
    assert before == after
