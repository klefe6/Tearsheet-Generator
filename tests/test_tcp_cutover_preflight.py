"""Step 11 production cutover preflight tests (synthetic fixtures, read-only)."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.tcp_cutover_preflight import (
    EXIT_ERROR,
    EXIT_GO,
    EXIT_NO_GO,
    redact_text,
    run_preflight,
    sha256_file,
)
from tcp_config import TKP_STATE_FILENAME, load_config, resolve_state_paths
from tcp_ledger import load_ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP = REPO_ROOT / "tests" / "_preflight_state"


@pytest.fixture(scope="session")
def cached_ledger(workbook_path):
    cfg = load_config()
    return load_ledger(str(workbook_path), cfg.sheet_name)


@pytest.fixture(autouse=True)
def accelerate_workbook_checks(monkeypatch, cached_ledger, request):
    node = request.node.name
    if "workbook_missing" in node or "replay_mismatch" in node:
        return

    def _fast_load(path, sheet):
        return cached_ledger

    class _FastReplay:
        rows_mismatched = 0
        completed_rows = cached_ledger.metadata.completed_row_count

    monkeypatch.setattr("scripts.tcp_cutover_preflight.load_ledger", _fast_load)
    monkeypatch.setattr("scripts.tcp_cutover_preflight.replay_ledger", lambda _ledger: _FastReplay())


@pytest.fixture(scope="session")
def workbook_path():
    cfg = load_config()
    path = Path(cfg.workbook_path)
    if not path.is_file():
        pytest.skip("workbook unavailable")
    return path


@pytest.fixture
def state_dir(request):
    TMP.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    root = TMP / safe
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    yield root
    if root.exists():
        shutil.rmtree(root)


def _git_ok(*, branch="feature/tcp-v2-migration", head="7de8ba1abc", remote_head=None):
    remote_head = remote_head or head

    def runner(args, cwd=REPO_ROOT):
        cmd = list(args)
        if cmd[:2] == ["branch", "--show-current"]:
            return 0, branch, ""
        if cmd[:1] == ["rev-parse"]:
            if "origin/" in cmd[1]:
                return 0, remote_head, ""
            return 0, head, ""
        if cmd[:2] == ["fetch", "origin"]:
            return 0, "", ""
        if cmd[:3] == ["diff", "--cached", "--name-only"]:
            return 0, "", ""
        if cmd[:2] == ["ls-files", "--error-unmatch"]:
            return 1, "", ""
        if cmd[:3] == ["remote", "get-url"]:
            return 0, "https://github.com/example/parent.git", ""
        if cmd[:1] == ["ls-remote"]:
            return 0, head, ""
        if cmd[:3] == ["log", "-1", "--oneline"]:
            return 0, "f53de23 stale", ""
        return 0, "", ""

    return runner


def _ports_free(_host, port):
    return False


def _env_production(state_dir: Path) -> dict[str, str]:
    active = state_dir / "tcp_daily_returns_secret_state.json"
    backup = state_dir / "tcp_daily_returns_secret_state.backup.json"
    lock = state_dir / "tcp_daily_returns_secret_state.lock"
    return {
        "TCP_V2_STATE_MODE": "json_active",
        "TCP_V2_STATE_PATH": str(active),
        "TCP_V2_STATE_BACKUP_PATH": str(backup),
        "TCP_V2_STATE_LOCK_PATH": str(lock),
        "TCP_V2_BIND_PORT": "8302",
        "TCP_V2_ADMIN_TOKEN": "test-admin-token",
        "TCP_V2_SESSION_SECRET": "test-session-secret",
    }


def test_valid_configuration_returns_go(workbook_path, state_dir):
    parent = REPO_ROOT.parent

    def runner(args, cwd=REPO_ROOT):
        if Path(cwd).resolve() == parent.resolve() and list(args)[:1] == ["ls-remote"]:
            return 0, "abc123\trefs/heads/main", ""
        return _git_ok()(args, cwd=cwd)

    before_wb = sha256_file(workbook_path)
    report = run_preflight(
        expected_branch="feature/tcp-v2-migration",
        expected_commit="7de8ba1",
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=True,
        git_runner=runner,
        port_check=_ports_free,
        env_overrides=_env_production(state_dir),
    )
    after_wb = sha256_file(workbook_path)
    assert before_wb == after_wb
    assert report.exit_code == EXIT_GO, report.blockers
    assert report.verdict == "GO"
    assert not any("secret" in p.lower() and "test-admin" in p for p in report.passes)


def test_wrong_branch_returns_no_go(workbook_path, state_dir):
    report = run_preflight(
        expected_branch="main",
        expected_commit="7de8ba1",
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(branch="feature/tcp-v2-migration"),
        port_check=_ports_free,
        env_overrides={"TCP_V2_STATE_MODE": "json_active"},
    )
    assert report.exit_code == EXIT_NO_GO


def test_wrong_commit_returns_no_go(workbook_path, state_dir):
    report = run_preflight(
        expected_commit="deadbeef",
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(head="7de8ba1abc"),
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO


def test_commit_absent_from_remote_returns_no_go(workbook_path, state_dir):
    report = run_preflight(
        expected_commit="7de8ba1",
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(head="7de8ba1abc", remote_head="aaaaaaaaaaa"),
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO


def test_workbook_missing_returns_no_go(state_dir):
    report = run_preflight(
        workbook_path=state_dir / "missing.xlsx",
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO


def test_state_path_collides_with_tkp_returns_no_go(workbook_path, state_dir):
    tkp = REPO_ROOT / TKP_STATE_FILENAME
    if not tkp.is_file():
        pytest.skip("TKP state file not present for collision test")
    env = _env_production(state_dir)
    env["TCP_V2_STATE_PATH"] = str(tkp)
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_state_path_collides_with_preview_returns_no_go(workbook_path, state_dir):
    preview_active, _, _ = resolve_state_paths(load_config(), REPO_ROOT)
    env = _env_production(state_dir)
    env["TCP_V2_STATE_PATH"] = str(preview_active)
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_state_path_equals_workbook_returns_no_go(workbook_path, state_dir):
    env = _env_production(state_dir)
    env["TCP_V2_STATE_PATH"] = str(workbook_path)
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_active_backup_lock_collision_returns_no_go(workbook_path, state_dir):
    same = state_dir / "same.json"
    env = {
        "TCP_V2_STATE_MODE": "json_active",
        "TCP_V2_STATE_PATH": str(same),
        "TCP_V2_STATE_BACKUP_PATH": str(same),
        "TCP_V2_STATE_LOCK_PATH": str(state_dir / "tcp_daily_returns_secret_state.lock"),
    }
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_missing_admin_token_returns_no_go_for_production_ready(workbook_path, state_dir):
    env = _env_production(state_dir)
    env.pop("TCP_V2_ADMIN_TOKEN")
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_missing_session_secret_returns_no_go(workbook_path, state_dir):
    env = _env_production(state_dir)
    env.pop("TCP_V2_SESSION_SECRET")
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_debug_true_returns_no_go(workbook_path, state_dir, monkeypatch):
    import scripts.tcp_cutover_preflight as preflight_mod

    cfg = load_config()
    monkeypatch.setattr(preflight_mod, "load_config", lambda: replace(cfg, debug=True))
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO


def test_wrong_production_bind_port_returns_no_go(workbook_path, state_dir):
    env = _env_production(state_dir)
    env["TCP_V2_BIND_PORT"] = "8312"
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=env,
    )
    assert report.exit_code == EXIT_NO_GO


def test_preview_port_listener_warning(workbook_path, state_dir):
    def listener(_host, port):
        return port == 8312

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=listener,
    )
    assert any("8312" in w for w in report.warnings)


def test_parent_remote_inaccessible_is_blocker(workbook_path, state_dir):
    parent = REPO_ROOT.parent

    def runner(args, cwd=REPO_ROOT):
        if Path(cwd).resolve() == parent.resolve() and list(args)[:1] == ["ls-remote"]:
            return 128, "", "Repository not found"
        return _git_ok()(args, cwd=cwd)

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=True,
        git_runner=runner,
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO
    assert any("parent_remote" in b.lower() or "parent remote" in b.lower() for b in report.blockers), report.blockers


def test_staged_runtime_file_is_blocker(workbook_path, state_dir):
    def runner(args, cwd=REPO_ROOT):
        if cmd := args:
            if list(cmd)[:3] == ["diff", "--cached", "--name-only"]:
                return 0, "tcp_daily_returns_secret_state.json\n", ""
        return _git_ok()(args, cwd=cwd)

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=False,
        git_runner=runner,
        port_check=_ports_free,
        env_overrides=_env_production(state_dir),
    )
    assert report.exit_code == EXIT_NO_GO


def test_preflight_writes_no_state(workbook_path, state_dir):
    active = state_dir / "tcp_daily_returns_secret_state.json"
    before = {p: p.exists() for p in state_dir.glob("*")}
    run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=_env_production(state_dir),
    )
    after = {p: p.exists() for p in state_dir.glob("*")}
    assert before == after
    assert not active.exists()


def test_preflight_writes_no_workbook(workbook_path, state_dir):
    before = sha256_file(workbook_path)
    run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
    )
    assert sha256_file(workbook_path) == before


def test_output_redacts_paths():
    text = redact_text(r"state at C:\Users\secret\state.json")
    assert "C:\\Users" not in text
    assert "<redacted-path>" in text


def test_output_redacts_secrets():
    text = redact_text("TCP_V2_ADMIN_TOKEN=super-secret-value")
    assert "super-secret" not in text


def test_exit_codes_follow_contract():
    assert EXIT_GO == 0
    assert EXIT_NO_GO == 1
    assert EXIT_ERROR == 2


def test_json_output_is_deterministic_apart_from_dynamic_fields(workbook_path, state_dir):
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=_env_production(state_dir),
    )
    a = json.dumps(report.to_dict(), sort_keys=True)
    b = json.dumps(report.to_dict(), sort_keys=True)
    assert a == b


def test_replay_mismatch_returns_no_go(workbook_path, state_dir, monkeypatch):
    class FakeReport:
        rows_mismatched = 1
        completed_rows = 112

    monkeypatch.setattr("scripts.tcp_cutover_preflight.replay_ledger", lambda _ledger: FakeReport())
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO


def test_parent_remote_success(workbook_path, state_dir):
    parent = REPO_ROOT.parent

    def runner(args, cwd=REPO_ROOT):
        if Path(cwd).resolve() == parent.resolve() and list(args)[:1] == ["ls-remote"]:
            return 0, "abc123\trefs/heads/main", ""
        return _git_ok()(args, cwd=cwd)

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=True,
        git_runner=runner,
        port_check=_ports_free,
    )
    assert any("parent remote reachable" in p for p in report.passes)


def test_parent_remote_timeout_is_blocker(workbook_path, state_dir):
    from scripts.tcp_cutover_preflight import GIT_TIMEOUT_EXIT, GIT_TIMEOUT_MARKER

    parent = REPO_ROOT.parent

    def runner(args, cwd=REPO_ROOT):
        if Path(cwd).resolve() == parent.resolve() and list(args)[:1] == ["ls-remote"]:
            return GIT_TIMEOUT_EXIT, "", GIT_TIMEOUT_MARKER
        return _git_ok()(args, cwd=cwd)

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=True,
        git_runner=runner,
        port_check=_ports_free,
    )
    assert report.exit_code == EXIT_NO_GO
    assert any("timed out" in b.lower() for b in report.blockers)


def test_parent_timeout_returns_promptly(workbook_path, state_dir):
    import time
    from scripts.tcp_cutover_preflight import GIT_TIMEOUT_EXIT, GIT_TIMEOUT_MARKER

    parent = REPO_ROOT.parent

    def runner(args, cwd=REPO_ROOT):
        if Path(cwd).resolve() == parent.resolve() and list(args)[:1] == ["ls-remote"]:
            return GIT_TIMEOUT_EXIT, "", GIT_TIMEOUT_MARKER
        return _git_ok()(args, cwd=cwd)

    start = time.monotonic()
    run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=True,
        git_runner=runner,
        port_check=_ports_free,
    )
    assert time.monotonic() - start < 5.0


def test_skip_parent_skips_parent_commands(workbook_path, state_dir):
    parent = REPO_ROOT.parent
    calls: list[tuple] = []

    def runner(args, cwd=REPO_ROOT):
        calls.append((list(args), Path(cwd).resolve()))
        return _git_ok()(args, cwd=cwd)

    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        check_parent=False,
        git_runner=runner,
        port_check=_ports_free,
    )
    assert not any(args[:1] == ["ls-remote"] and p == parent.resolve() for args, p in calls)
    assert any("skipped" in w.lower() for w in report.warnings)


def test_production_ready_with_skip_parent_is_no_go(workbook_path, state_dir):
    report = run_preflight(
        workbook_path=workbook_path,
        state_base=state_dir,
        production_ready=True,
        check_parent=False,
        git_runner=_git_ok(),
        port_check=_ports_free,
        env_overrides=_env_production(state_dir),
    )
    assert report.exit_code == EXIT_NO_GO
    assert any("parent_check_skipped" in b for b in report.blockers)


def test_bounded_git_runner_timeout_classification(tmp_path):
    import subprocess

    import scripts.tcp_cutover_preflight as mod

    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.pid = 424242

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="git", timeout=timeout or 0)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(mod, "_kill_process_tree", lambda _pid: None)
    try:
        code, _out, err = mod.make_bounded_git_runner(timeout_seconds=0.1)(["ls-remote"], cwd=tmp_path)
    finally:
        monkeypatch.undo()
    assert code == mod.GIT_TIMEOUT_EXIT
    assert mod.GIT_TIMEOUT_MARKER in err
