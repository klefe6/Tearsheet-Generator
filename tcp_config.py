"""
TCP v2 configuration — isolated module with no Dash or workbook side effects on import.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# Audited absolute path (Step 1 ledger contract). Override via TCP_V2_WORKBOOK_PATH.
DEFAULT_WORKBOOK_PATH = (
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"
    r"\3_Advisors Marketing (Tearsheets, PitchBooks, etc)\1. Tearsheet Project\TCP\tcp_alex.xlsx"
)

TKP_STATE_FILENAME = "daily_returns_secret_state.json"
TKP_SHEET_NAME = "Sheet1"

# Inclusive preview port range for tearsheet services (8301–8312 per port migration).
TCP_PREVIEW_PORT_MIN = 8301
TCP_PREVIEW_PORT_MAX = 8312

SUPPORTED_STATE_MODES = frozenset({"workbook", "json_active"})
DEFAULT_STATE_MODE = "workbook"


@dataclass(frozen=True)
class AdminAuthSettings:
    admin_token: Optional[str]
    session_secret: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.admin_token and self.session_secret)


@dataclass(frozen=True)
class TCPConfig:
    app_code: str = "tcp"
    app_name: str = "TCP"
    preview_label: str = "TCP v2 Preview — Read Only"
    workbook_path: str = DEFAULT_WORKBOOK_PATH
    workbook_filename: str = "tcp_alex.xlsx"
    sheet_name: str = "NAV"
    date_column: str = "Date"
    nav_column: str = "nav-x1"
    state_filename: str = "tcp_daily_returns_secret_state.json"
    state_backup_filename: str = "tcp_daily_returns_secret_state.backup.json"
    lock_filename: str = "tcp_daily_returns_secret_state.lock"
    export_filename: str = "tcp_daily_returns_export.xlsx"
    preview_port: int = 8312
    production_port: int = 8302
    debug: bool = False
    state_mode: str = DEFAULT_STATE_MODE
    state_active_path: Optional[str] = None
    state_backup_path: Optional[str] = None
    state_lock_path: Optional[str] = None
    allow_workbook_fallback: bool = True

    @property
    def read_only(self) -> bool:
        return self.state_mode != "json_active"

    @property
    def persistence_enabled(self) -> bool:
        return self.state_mode == "json_active"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_benchmark_cache_path(base_dir: str | Path) -> Path:
    """Resolve SPXTR benchmark cache path. Override with TCP_V2_BENCHMARK_CACHE_PATH."""
    override = os.environ.get("TCP_V2_BENCHMARK_CACHE_PATH")
    if override:
        return Path(override)
    return Path(base_dir) / "_runtime" / "tcp_benchmark_cache.json"


def load_config() -> TCPConfig:
    """Build config from defaults and optional environment overrides."""
    workbook_path = os.environ.get("TCP_V2_WORKBOOK_PATH", DEFAULT_WORKBOOK_PATH)
    state_mode = os.environ.get("TCP_V2_STATE_MODE", DEFAULT_STATE_MODE).strip().lower()
    if state_mode not in SUPPORTED_STATE_MODES:
        state_mode = DEFAULT_STATE_MODE
    return TCPConfig(
        workbook_path=workbook_path,
        state_mode=state_mode,
        state_active_path=os.environ.get("TCP_V2_STATE_PATH"),
        state_backup_path=os.environ.get("TCP_V2_STATE_BACKUP_PATH"),
        state_lock_path=os.environ.get("TCP_V2_STATE_LOCK_PATH"),
        allow_workbook_fallback=_env_bool("TCP_V2_ALLOW_WORKBOOK_FALLBACK", True),
    )


def resolve_bind_port(cfg: TCPConfig) -> int:
    """Port for tcp_ts_v2.py. Defaults to preview_port; override with TCP_V2_BIND_PORT."""
    raw = os.environ.get("TCP_V2_BIND_PORT")
    if raw is None or not raw.strip():
        return cfg.preview_port
    try:
        return int(raw.strip())
    except ValueError:
        return cfg.preview_port


def validate_bind_port(cfg: TCPConfig, bind_port: int) -> Tuple[bool, str]:
    if bind_port == cfg.production_port:
        if cfg.debug:
            return False, "debug must be False when binding production port 8302"
        if bind_port != 8302:
            return False, "production_port must be 8302"
        return True, "ok"
    if TCP_PREVIEW_PORT_MIN <= bind_port <= TCP_PREVIEW_PORT_MAX:
        if bind_port == cfg.production_port:
            return False, "preview bind must not use production port 8302"
        return True, "ok"
    return False, (
        f"bind port {bind_port} must be production port 8302 or preview range "
        f"{TCP_PREVIEW_PORT_MIN}-{TCP_PREVIEW_PORT_MAX}"
    )


def is_production_runtime(cfg: TCPConfig) -> bool:
    return resolve_bind_port(cfg) == cfg.production_port


def load_admin_auth_settings() -> AdminAuthSettings:
    """Load preview admin auth settings from environment variables only."""
    token = os.environ.get("TCP_V2_ADMIN_TOKEN")
    secret = os.environ.get("TCP_V2_SESSION_SECRET")
    return AdminAuthSettings(
        admin_token=token if token else None,
        session_secret=secret if secret else None,
    )


def _resolve_path(base: Path, override: Optional[str], default_name: str) -> Path:
    if override:
        candidate = Path(override)
        if not candidate.is_absolute():
            candidate = base / candidate
        return candidate
    return base / default_name


def resolve_state_paths(cfg: TCPConfig, base_dir: str | Path) -> Tuple[Path, Path, Path]:
    """Resolve active, backup, and lock paths. Does not create directories."""
    base = Path(base_dir)
    return (
        _resolve_path(base, cfg.state_active_path, cfg.state_filename),
        _resolve_path(base, cfg.state_backup_path, cfg.state_backup_filename),
        _resolve_path(base, cfg.state_lock_path, cfg.lock_filename),
    )


def _path_is_safe_state_target(path: Path, cfg: TCPConfig) -> Tuple[bool, str]:
    normalized = str(path).replace("\\", "/").lower()
    if normalized.endswith(".xlsx") or normalized.endswith(".xls"):
        return False, "state path must not point at a workbook"
    if "_runtime" in normalized and "tests" not in normalized:
        return False, "state path must not point into _runtime"
    if path.name == TKP_STATE_FILENAME:
        return False, "state path collides with TKP JSON state"
    if "tkp" in path.name.lower() and "tcp" not in path.name.lower():
        return False, "state path must not reference TKP"
    workbook_name = Path(cfg.workbook_path).name.lower()
    if path.name.lower() == workbook_name:
        return False, "state path must not point at the workbook"
    return True, "ok"


def validate_config(cfg: TCPConfig) -> Tuple[bool, str]:
    """
    Side-effect-free validation. Returns (ok, message).
    Does not read the workbook or create files.
    """
    if cfg.app_code != "tcp":
        return False, f"app_code must be 'tcp', got {cfg.app_code!r}"
    if cfg.state_mode not in SUPPORTED_STATE_MODES:
        return False, f"state_mode must be one of {sorted(SUPPORTED_STATE_MODES)}, got {cfg.state_mode!r}"
    if "tkp" in cfg.workbook_filename.lower():
        return False, "workbook_filename must not reference TKP"
    if cfg.workbook_filename != "tcp_alex.xlsx":
        return False, f"workbook_filename must be tcp_alex.xlsx, got {cfg.workbook_filename!r}"
    if cfg.sheet_name == TKP_SHEET_NAME:
        return False, "sheet_name must not be TKP Sheet1"
    if cfg.sheet_name != "NAV":
        return False, f"sheet_name must be NAV, got {cfg.sheet_name!r}"
    if cfg.state_filename == TKP_STATE_FILENAME:
        return False, "state_filename collides with TKP JSON state"
    if "tkp" in cfg.state_filename.lower():
        return False, "state_filename must not reference TKP"
    if cfg.state_backup_filename == TKP_STATE_FILENAME:
        return False, "state_backup_filename collides with TKP JSON state"
    if cfg.state_filename == cfg.state_backup_filename:
        return False, "state_filename and state_backup_filename must differ"
    if cfg.lock_filename == cfg.state_filename:
        return False, "lock_filename must differ from state_filename"
    if cfg.lock_filename == cfg.state_backup_filename:
        return False, "lock_filename must differ from state_backup_filename"
    if cfg.lock_filename == TKP_STATE_FILENAME:
        return False, "lock_filename collides with TKP JSON state"
    if "tkp" in cfg.lock_filename.lower():
        return False, "lock_filename must not reference TKP"
    if cfg.state_filename.lower().endswith(".xlsx"):
        return False, "state_filename must not point at a workbook"
    if "_runtime" in cfg.state_filename.replace("\\", "/").lower():
        return False, "state_filename must not point into _runtime"
    if "_runtime" in cfg.state_backup_filename.replace("\\", "/").lower():
        return False, "state_backup_filename must not point into _runtime"
    if cfg.preview_port == cfg.production_port:
        return False, "preview_port must differ from production_port (8302)"
    if cfg.preview_port == 8302:
        return False, "preview_port must not be production port 8302"
    if not (TCP_PREVIEW_PORT_MIN <= cfg.preview_port <= TCP_PREVIEW_PORT_MAX):
        return False, (
            f"preview_port {cfg.preview_port} outside tearsheet range "
            f"{TCP_PREVIEW_PORT_MIN}-{TCP_PREVIEW_PORT_MAX}"
        )
    if cfg.debug:
        return False, "debug must be False for this milestone"
    for label, override, default_name in (
        ("active", cfg.state_active_path, cfg.state_filename),
        ("backup", cfg.state_backup_path, cfg.state_backup_filename),
        ("lock", cfg.state_lock_path, cfg.lock_filename),
    ):
        path = _resolve_path(Path("."), override, default_name)
        ok, msg = _path_is_safe_state_target(path, cfg)
        if not ok:
            return False, f"{label} state path: {msg}"
    active, backup, lock = resolve_state_paths(cfg, Path("."))
    if active == backup or active == lock or backup == lock:
        return False, "active, backup, and lock paths must be distinct"
    return True, "ok"
