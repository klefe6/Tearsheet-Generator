"""
TCP v2 configuration — isolated module with no Dash or workbook side effects on import.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

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
    read_only: bool = True


def load_config() -> TCPConfig:
    """Build config from defaults and optional environment overrides."""
    workbook_path = os.environ.get("TCP_V2_WORKBOOK_PATH", DEFAULT_WORKBOOK_PATH)
    return TCPConfig(workbook_path=workbook_path)


def resolve_state_paths(cfg: TCPConfig, base_dir: str | Path) -> Tuple[Path, Path, Path]:
    """Resolve active, backup, and lock paths under base_dir. Does not create directories."""
    base = Path(base_dir)
    return (
        base / cfg.state_filename,
        base / cfg.state_backup_filename,
        base / cfg.lock_filename,
    )


def validate_config(cfg: TCPConfig) -> Tuple[bool, str]:
    """
    Side-effect-free validation. Returns (ok, message).
    Does not read the workbook or create files.
    """
    if cfg.app_code != "tcp":
        return False, f"app_code must be 'tcp', got {cfg.app_code!r}"
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
    if not cfg.read_only:
        return False, "read_only must be True for this milestone"
    return True, "ok"
