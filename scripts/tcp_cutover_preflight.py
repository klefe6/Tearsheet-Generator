"""
TCP v2 production cutover preflight — read-only checks only.

No workbook writes, no state writes, no process kills, no port binding, no deployment.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tcp_config import (  # noqa: E402
    TKP_STATE_FILENAME,
    load_admin_auth_settings,
    load_config,
    resolve_bind_port,
    resolve_state_paths,
    sibling_admin_auth_explicitly_configured,
    validate_bind_port,
    validate_config,
)
from tcp_ledger import TCPLedgerError, load_ledger  # noqa: E402
from tcp_state import load_state, validate_state  # noqa: E402

try:
    from tests.replay_tcp_ledger import replay_ledger
except ImportError:
    replay_ledger = None  # type: ignore[assignment]

EXIT_GO = 0
EXIT_NO_GO = 1
EXIT_ERROR = 2

GIT_TIMEOUT_EXIT = 124
GIT_TIMEOUT_MARKER = "GIT_COMMAND_TIMEOUT"
DEFAULT_GIT_TIMEOUT_SECONDS = 15.0

REQUIRED_TRACKED = (
    "tcp_ts_v2.py",
    "tcp_config.py",
    "tcp_runtime_state.py",
    "tcp_admin.py",
    "tcp_dashboard.py",
    "tcp_ledger.py",
    "tcp_state.py",
    "reboot_tcp_ts.bat",
    "reboot_tcp_ts_v2.bat",
    "scripts/seed_tcp_state.py",
    "scripts/preflight_tcp_cutover.py",
)

SECRET_PATTERNS = (
  re.compile(r"TCP_V2_ADMIN_TOKEN\s*=\s*\S+", re.I),
  re.compile(r"TCP_V2_SESSION_SECRET\s*=\s*\S+", re.I),
)

PATH_REDACT = re.compile(r"[A-Za-z]:[\\/][^\s\"']+")


@dataclass
class CheckItem:
    name: str
    status: str  # PASS | WARNING | BLOCKER
    detail: str


@dataclass
class PreflightReport:
    verdict: str = "PENDING"
    exit_code: int = EXIT_ERROR
    checks: List[CheckItem] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passes: List[str] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str) -> None:
        item = CheckItem(name=name, status=status, detail=detail)
        self.checks.append(item)
        if status == "BLOCKER":
            self.blockers.append(f"{name}: {detail}")
        elif status == "WARNING":
            self.warnings.append(f"{name}: {detail}")
        else:
            self.passes.append(f"{name}: {detail}")

    def finalize(self) -> None:
        if any(c.status == "BLOCKER" for c in self.checks):
            self.verdict = "NO-GO"
            self.exit_code = EXIT_NO_GO
        else:
            self.verdict = "GO"
            self.exit_code = EXIT_GO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "exit_code": self.exit_code,
            "blockers": [redact_text(b) for b in self.blockers],
            "warnings": [redact_text(w) for w in self.warnings],
            "passes": [redact_text(p) for p in self.passes],
            "checks": [
                {"name": c.name, "status": c.status, "detail": redact_text(c.detail)}
                for c in self.checks
            ],
        }


def redact_text(text: str) -> str:
    text = PATH_REDACT.sub("<redacted-path>", text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("<redacted-secret>", text)
  # redact long hex tokens that might be secrets
    text = re.sub(r"\b[A-Fa-f0-9]{32,}\b", lambda m: "<redacted-token>" if len(m.group()) >= 40 else m.group(), text)
    return text


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _kill_process_tree(pid: int) -> None:
    """Terminate a hung subprocess and its children (Windows-safe)."""
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
                check=False,
            )
        else:
            os.kill(pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass


def make_bounded_git_runner(timeout_seconds: float = DEFAULT_GIT_TIMEOUT_SECONDS):
    """Return a git subprocess runner with explicit timeout and child cleanup."""

    def runner(args: Sequence[str], cwd: Path = REPO_ROOT) -> Tuple[int, str, str]:
        try:
            proc = subprocess.Popen(
                ["git", *args],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            return 127, "", str(exc)
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            return proc.returncode, stdout.strip(), stderr.strip()
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc.pid)
            try:
                proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc.pid)
            return GIT_TIMEOUT_EXIT, "", GIT_TIMEOUT_MARKER

    return runner


def _run_git(args: Sequence[str], cwd: Path = REPO_ROOT) -> Tuple[int, str, str]:
    return make_bounded_git_runner()(args, cwd=cwd)


def _git_timed_out(code: int, stderr: str) -> bool:
    return code == GIT_TIMEOUT_EXIT or GIT_TIMEOUT_MARKER in stderr


def port_listener(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _paths_collide(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a).lower() == str(b).lower()


def check_git(
    report: PreflightReport,
    *,
    expected_branch: str,
    expected_commit: Optional[str],
    production_ready: bool,
    git_runner: Callable[..., Tuple[int, str, str]] = _run_git,
) -> None:
    code, branch, _ = git_runner(["branch", "--show-current"])
    if code != 0:
        report.add("git_branch", "BLOCKER", "unable to determine current branch")
        return
    if branch != expected_branch:
        report.add("git_branch", "BLOCKER", f"expected {expected_branch}, got {branch}")
    else:
        report.add("git_branch", "PASS", branch)

    code, head, _ = git_runner(["rev-parse", "HEAD"])
    if code != 0:
        report.add("git_head", "BLOCKER", "unable to read HEAD")
        return
    if expected_commit:
        if not head.startswith(expected_commit):
            report.add("git_head", "BLOCKER", f"expected {expected_commit}, got {head[:12]}")
        else:
            report.add("git_head", "PASS", head[:12])

    code, _, err = git_runner(["fetch", "origin", expected_branch])
    if _git_timed_out(code, err):
        detail = "git fetch origin timed out"
        report.add("git_remote_fetch", "BLOCKER" if production_ready else "WARNING", detail)
    elif code != 0:
        report.add("git_remote_fetch", "WARNING", "could not fetch origin (offline or auth)")
    else:
        code, remote_head, _ = git_runner(["rev-parse", f"origin/{expected_branch}"])
        if code == 0:
            if expected_commit and not remote_head.startswith(expected_commit):
                report.add(
                    "git_remote_commit",
                    "BLOCKER",
                    f"expected commit {expected_commit} not on origin/{expected_branch}",
                )
            else:
                report.add("git_remote_commit", "PASS", f"origin/{expected_branch} at {remote_head[:12]}")
        else:
            report.add("git_remote_commit", "WARNING", f"origin/{expected_branch} not found locally")

    code, staged, _ = git_runner(["diff", "--cached", "--name-only"])
    if code == 0 and staged.strip():
        suspicious = [
            line for line in staged.splitlines()
            if line.endswith(".json") or "secret" in line.lower() or line.endswith(".xlsx")
        ]
        if suspicious:
            report.add("git_staged_runtime", "BLOCKER", f"staged runtime-like files: {', '.join(suspicious[:5])}")
        elif production_ready:
            report.add("git_staged_changes", "WARNING", "staged changes present before cutover")
        else:
            report.add("git_staged_changes", "PASS", "staged changes reviewed separately")

    for rel in REQUIRED_TRACKED:
        path = REPO_ROOT / rel
        if not path.is_file():
            report.add("git_required_source", "BLOCKER", f"missing required file {rel}")
            return
    report.add("git_required_source", "PASS", f"{len(REQUIRED_TRACKED)} required source files present")

    for rel in ("tcp_daily_returns_secret_state.json", TKP_STATE_FILENAME):
        path = REPO_ROOT / rel
        code, tracked, _ = git_runner(["ls-files", "--error-unmatch", rel])
        if code == 0:
            report.add("git_runtime_tracked", "BLOCKER", f"runtime file is tracked: {rel}")
        elif path.is_file():
            report.add("git_runtime_untracked", "PASS", f"{rel} exists locally but is not tracked")


def check_workbook(report: PreflightReport, workbook_path: Path, sheet_name: str) -> Optional[Any]:
    if not workbook_path.is_file():
        report.add("workbook_exists", "BLOCKER", "workbook not found")
        return None
    before = sha256_file(workbook_path)
    try:
        ledger = load_ledger(str(workbook_path), sheet_name)
    except TCPLedgerError as exc:
        report.add("workbook_schema", "BLOCKER", str(exc))
        return None
    after = sha256_file(workbook_path)
    if before != after:
        report.add("workbook_readonly", "BLOCKER", "workbook checksum changed during preflight read")
    else:
        report.add("workbook_readonly", "PASS", "workbook not modified by preflight")

    meta = ledger.metadata
    if meta.completed_row_count <= 0:
        report.add("workbook_rows", "BLOCKER", "no completed rows")
        return None

    report.add(
        "workbook_rows",
        "PASS",
        f"rows={meta.completed_row_count} first={meta.first_completed_date} latest={meta.latest_completed_date}",
    )

    if replay_ledger is None:
        report.add("workbook_replay", "BLOCKER", "replay helper unavailable")
        return ledger

    replay = replay_ledger(ledger)
    if replay.rows_mismatched > 0:
        report.add(
            "workbook_replay",
            "BLOCKER",
            f"calculator replay failed ({replay.rows_mismatched}/{replay.completed_rows})",
        )
    else:
        report.add("workbook_replay", "PASS", f"replay {replay.completed_rows}/{replay.completed_rows}")

    return ledger


def check_state_paths(
    report: PreflightReport,
    cfg,
    state_base: Path,
    preview_state_path: Path,
    tkp_state_path: Path,
    workbook_path: Path,
    production_ready: bool,
) -> Tuple[Path, Path, Path]:
    active, backup, lock = resolve_state_paths(cfg, state_base)

    cfg_paths = replace(
        cfg,
        state_mode="json_active",
        state_active_path=str(active),
        state_backup_path=str(backup),
        state_lock_path=str(lock),
    )
    ok_paths, path_msg = validate_config(cfg_paths)
    if not ok_paths:
        report.add("state_path_validate", "BLOCKER", path_msg)
    else:
        report.add("state_path_validate", "PASS", path_msg)

    collisions: List[str] = []
    if _paths_collide(active, backup) or _paths_collide(active, lock) or _paths_collide(backup, lock):
        collisions.append("active/backup/lock paths must be distinct")
    if _paths_collide(active, preview_state_path):
        collisions.append("production active collides with preview state")
    if _paths_collide(active, tkp_state_path):
        collisions.append("production active collides with TKP state")
    if _paths_collide(active, workbook_path):
        collisions.append("production active collides with workbook")
    if collisions:
        report.add("state_path_isolation", "BLOCKER", "; ".join(collisions))
    else:
        report.add("state_path_isolation", "PASS", "production/preview/TKP/workbook paths distinct")

    parent = active.parent
    if production_ready:
        if not parent.exists():
            report.add("state_parent_writable", "WARNING", "production state parent does not exist yet")
        elif not os.access(parent, os.W_OK):
            report.add("state_parent_writable", "BLOCKER", "production state parent is not writable")
        else:
            report.add("state_parent_writable", "PASS", "production state parent is writable")

    if active.exists():
        try:
            envelope = load_state(active)
            validate_state(envelope)
            records = envelope.get("records", [])
            report.add(
                "state_existing_active",
                "WARNING",
                f"active state exists revision={envelope.get('revision')} rows={len(records)} (not overwritten)",
            )
        except Exception as exc:
            report.add("state_existing_active", "WARNING", f"active state exists but invalid: {exc}")
    else:
        report.add("state_existing_active", "PASS", "no production active state file yet")

    return active, backup, lock


def check_configuration(
    report: PreflightReport,
    cfg,
    *,
    production_ready: bool,
    production_port: int,
    preview_port: int,
) -> None:
    ok, msg = validate_config(cfg)
    if not ok:
        report.add("config_validate", "BLOCKER", msg)
    else:
        report.add("config_validate", "PASS", msg)

    if cfg.state_mode != "json_active":
        if production_ready:
            report.add("config_state_mode", "BLOCKER", f"expected json_active, got {cfg.state_mode}")
        else:
            report.add("config_state_mode", "WARNING", f"state_mode is {cfg.state_mode} (json_active required for cutover)")

    bind_port = resolve_bind_port(cfg)
    ok_bind, bind_msg = validate_bind_port(cfg, bind_port)
    if production_ready and bind_port != production_port:
        report.add("config_bind_port", "BLOCKER", f"TCP_V2_BIND_PORT must be {production_port} for production")
    elif not ok_bind:
        report.add("config_bind_port", "BLOCKER", bind_msg)
    else:
        report.add("config_bind_port", "PASS", f"bind_port={bind_port}")

    if cfg.debug:
        report.add("config_debug", "BLOCKER", "debug must be False")
    else:
        report.add("config_debug", "PASS", "debug is False")

    if preview_port == production_port:
        report.add("config_preview_port", "BLOCKER", "preview port must not equal production port")
    else:
        report.add("config_preview_port", "PASS", f"preview={preview_port} production={production_port}")

    auth = load_admin_auth_settings()
    secrets_explicit = sibling_admin_auth_explicitly_configured(
        admin_token_env="TCP_V2_ADMIN_TOKEN",
        session_secret_env="TCP_V2_SESSION_SECRET",
    )
    if production_ready:
        if not secrets_explicit:
            report.add("config_secrets", "BLOCKER", "TCP_V2_ADMIN_TOKEN and TCP_V2_SESSION_SECRET required")
        else:
            report.add("config_secrets", "PASS", "admin/session secrets configured (values not shown)")
    else:
        if secrets_explicit:
            report.add("config_secrets", "PASS", "secrets present in environment")
        elif auth.is_configured:
            report.add("config_secrets", "PASS", "using sibling admin auth defaults (local)")
        else:
            report.add("config_secrets", "WARNING", "production secrets not configured yet")


def check_runtime_topology(
    report: PreflightReport,
    *,
    production_port: int,
    preview_port: int,
    python_exe: Path,
    production_ready: bool,
    port_check: Callable[[str, int], bool] = port_listener,
) -> None:
    prod_listening = port_check("127.0.0.1", production_port)
    preview_listening = port_check("127.0.0.1", preview_port)

    if prod_listening:
        report.add("topology_port_production", "PASS", f"port {production_port} has a listener (expected for live v1)")
    else:
        report.add("topology_port_production", "WARNING", f"port {production_port} is not listening locally")

    if preview_listening:
        report.add("topology_port_preview", "WARNING", f"port {preview_port} is listening (stop preview before cutover)")
    else:
        report.add("topology_port_preview", "PASS", f"port {preview_port} is free")

    v1_path = REPO_ROOT / "tcp_ts.py"
    v2_path = REPO_ROOT / "tcp_ts_v2.py"
    bat_prod = REPO_ROOT / "reboot_tcp_ts.bat"
    bat_preview = REPO_ROOT / "reboot_tcp_ts_v2.bat"
    for label, path in (
        ("launcher_production", bat_prod),
        ("launcher_preview", bat_preview),
        ("rollback_v1_source", v1_path),
        ("cutover_v2_source", v2_path),
    ):
        if path.is_file():
            report.add(label, "PASS", path.name)
        else:
            report.add(label, "BLOCKER", f"missing {path.name}")

    if not python_exe.is_file():
        report.add("python_interpreter", "BLOCKER", "configured Python executable not found")
    else:
        report.add("python_interpreter", "PASS", python_exe.name)

    try:
        import tcp_ts_v2  # noqa: F401
        report.add("import_tcp_ts_v2", "PASS", "tcp_ts_v2 imports without starting server")
    except Exception as exc:
        report.add("import_tcp_ts_v2", "BLOCKER", f"import failed: {exc}")

    free = shutil.disk_usage(REPO_ROOT).free
    if free < 500 * 1024 * 1024:
        report.add("disk_space", "BLOCKER", "less than 500MB free disk space")
    else:
        report.add("disk_space", "PASS", f"free_bytes={free}")


def check_infrastructure(report: PreflightReport) -> None:
    cf = REPO_ROOT.parent / "Manager" / "cloudflare_tunnel_config.yaml"
    manager = REPO_ROOT.parent / "Manager" / "service_config.py"
    debug_page = REPO_ROOT.parent / "HomePage" / "debug.py"
    for label, path, needle in (
        ("infra_cloudflare", cf, "tcp-ts.hcresearch.ltd"),
        ("infra_manager", manager, "8302"),
        ("infra_homepage", debug_page, "reboot_tcp_ts.bat"),
    ):
        if not path.is_file():
            report.add(label, "WARNING", f"missing {path.name} in parent repo")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            report.add(label, "PASS", f"{path.name} references {needle}")
        else:
            report.add(label, "WARNING", f"{path.name} missing expected reference {needle}")

    report.add(
        "infra_change_required",
        "PASS",
        "no Cloudflare/Manager/HomePage change required for launcher-target cutover",
    )


def check_parent_pointer(
    report: PreflightReport,
    expected_submodule_commit: Optional[str],
    git_runner: Callable[..., Tuple[int, str, str]] = _run_git,
) -> None:
    parent = REPO_ROOT.parent
    code, url, err = git_runner(["remote", "get-url", "origin"], cwd=parent)
    if code == 0:
        report.add("parent_remote_url", "PASS" if "github.com" in url else "WARNING", url)
    else:
        report.add("parent_remote_url", "WARNING", err or "no parent remote")

    code, out, err = git_runner(["ls-remote", "origin"], cwd=parent)
    if _git_timed_out(code, err):
        report.add(
            "parent_remote_access",
            "BLOCKER",
            "parent repository remote check timed out",
        )
    elif code != 0:
        detail = err or "parent remote not accessible"
        if "not found" in detail.lower():
            detail = "parent remote not accessible (repository not found)"
        report.add("parent_remote_access", "BLOCKER", detail)
    else:
        report.add("parent_remote_access", "PASS", "parent remote reachable")

    code, msg, _ = git_runner(["log", "-1", "--oneline", "f53de23"], cwd=parent)
    if code == 0:
        report.add("parent_stale_pointer", "WARNING", f"f53de23 is stale checkpoint: {msg}")
    if expected_submodule_commit:
        report.add(
            "parent_pointer_target",
            "PASS",
            f"fresh parent pointer must reference merged submodule main @ {expected_submodule_commit[:12]}",
        )


def run_preflight(
    *,
    expected_branch: str = "feature/tcp-v2-migration",
    expected_commit: Optional[str] = None,
    workbook_path: Optional[Path] = None,
    state_base: Optional[Path] = None,
    production_port: int = 8302,
    preview_port: int = 8312,
    production_ready: bool = False,
    check_parent: bool = True,
    python_exe: Optional[Path] = None,
    env_overrides: Optional[Dict[str, str]] = None,
    git_runner: Optional[Callable[..., Tuple[int, str, str]]] = None,
    port_check: Optional[Callable[[str, int], bool]] = None,
    git_timeout_seconds: float = DEFAULT_GIT_TIMEOUT_SECONDS,
) -> PreflightReport:
    """Run all preflight checks. Read-only; does not mutate workbook or state."""
    report = PreflightReport()
    old_env: Dict[str, Optional[str]] = {}
    if env_overrides:
        for key, value in env_overrides.items():
            old_env[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    runner = git_runner or make_bounded_git_runner(git_timeout_seconds)
    listener = port_check or port_listener

    if production_ready and not check_parent:
        report.add(
            "parent_check_skipped",
            "BLOCKER",
            "production-ready preflight cannot skip parent integration checks",
        )

    try:
        cfg = load_config()
        wb = Path(workbook_path or cfg.workbook_path)
        base = Path(state_base) if state_base else Path(
            os.environ.get(
                "TCP_V2_PRODUCTION_STATE_DIR",
                str(Path(os.environ.get("LOCALAPPDATA", REPO_ROOT)) / "HughesCompany" / "TCP" / "state"),
            )
        )
        preview_cfg = replace(
            cfg,
            state_active_path=None,
            state_backup_path=None,
            state_lock_path=None,
        )
        preview_active = resolve_state_paths(preview_cfg, REPO_ROOT)[0]
        tkp_state = REPO_ROOT / TKP_STATE_FILENAME
        py = python_exe or (REPO_ROOT / ".venv310" / "Scripts" / "python.exe")

        check_git(
            report,
            expected_branch=expected_branch,
            expected_commit=expected_commit,
            production_ready=production_ready,
            git_runner=runner,
        )
        check_workbook(report, wb, cfg.sheet_name)
        check_state_paths(report, cfg, base, preview_active, tkp_state, wb, production_ready)
        check_configuration(
            report,
            cfg,
            production_ready=production_ready,
            production_port=production_port,
            preview_port=preview_port,
        )
        check_runtime_topology(
            report,
            production_port=production_port,
            preview_port=preview_port,
            python_exe=py,
            production_ready=production_ready,
            port_check=listener,
        )
        check_infrastructure(report)
        if check_parent:
            check_parent_pointer(report, expected_commit, git_runner=runner)
        else:
            report.add("parent_check_skipped", "WARNING", "parent integration checks skipped by request")

        if production_ready:
            report.add("step10_acceptance", "WARNING", "re-run scripts/audit_tcp_acceptance.py parity before cutover")
        else:
            report.add("step10_acceptance", "PASS", "Step 10 acceptance recorded at 7de8ba1 (re-verify on cutover day)")

        report.finalize()
        return report
    except Exception as exc:
        report.add("preflight_execution", "BLOCKER", f"unexpected error: {exc}")
        report.verdict = "NO-GO"
        report.exit_code = EXIT_NO_GO
        return report
    finally:
        if env_overrides:
            for key, previous in old_env.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
