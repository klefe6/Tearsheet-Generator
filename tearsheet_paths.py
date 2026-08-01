"""
Central path configuration for Hughes & Company tearsheet applications.

Pure resolver module: no Dash, no workbook reads, no mkdir, no network on import.
Call ``load_tearsheet_paths()`` at runtime to obtain resolved ``Path`` values.

Precedence for each setting:
  1. Non-empty per-path environment variable
  2. ``HC_APP_ENV`` profile default (when applicable)
  3. Current laptop compatibility default
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Union

# ---------------------------------------------------------------------------
# Environment names
# ---------------------------------------------------------------------------

HC_APP_ENV_VAR = "HC_APP_ENV"
DEFAULT_HC_APP_ENV = "local-production"

VALID_HC_APP_ENVS: frozenset[str] = frozenset(
    {
        "local-dev",
        "local-production",
        "vps-sandbox",
        "vps-production",
    }
)

# Root / layout settings
HC_DEPLOY_ROOT_ENV = "HC_DEPLOY_ROOT"
HC_DATA_ROOT_ENV = "HC_DATA_ROOT"
HC_PRODUCTION_DATA_ROOT_ENV = "HC_PRODUCTION_DATA_ROOT"
HC_SANDBOX_DATA_ROOT_ENV = "HC_SANDBOX_DATA_ROOT"
HC_LOG_ROOT_ENV = "HC_LOG_ROOT"
HC_CACHE_ROOT_ENV = "HC_CACHE_ROOT"
HC_BACKUP_ROOT_ENV = "HC_BACKUP_ROOT"

# Application data roots
HC_AGM_DATA_ROOT_ENV = "HC_AGM_DATA_ROOT"
HC_YQ_DATA_ROOT_ENV = "HC_YQ_DATA_ROOT"

# File-specific settings (active consumers in this lane)
HC_AGM_PINNED_CSV_ENV = "HC_AGM_PINNED_CSV"
HC_AGM_BENCHMARK_CACHE_DIR_ENV = "HC_AGM_BENCHMARK_CACHE_DIR"
HC_TCP_INGEST_AUDIT_PATH_ENV = "HC_TCP_INGEST_AUDIT_PATH"
HC_AGM_INGEST_AUDIT_PATH_ENV = "HC_AGM_INGEST_AUDIT_PATH"

# Launcher guard: main repo checkout that must not host production launches
HC_DIRTY_ROOT_ENV = "HC_DIRTY_ROOT"

# Y&Q CSV (existing env; highest precedence for CSV resolution)
YQ_CSV_PATH_ENV = "YQ_CSV_PATH"

# ---------------------------------------------------------------------------
# Compatibility literals (laptop production defaults)
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(__file__).resolve().parent

# Main dirty checkout — authoritative Y&Q CSV location and launcher guard target.
DEFAULT_DIRTY_ROOT = Path(r"C:\Coding Projects\Tearsheet Generator")
DEFAULT_YQ_REPO_ROOT_CSV = DEFAULT_DIRTY_ROOT / "yq.csv"

AGM_DATA_SUBDIR = "Momentum Pacer"
AGM_MANUAL_ROWS_FILENAME = "momentum_pacer_manual_daily_rows.json"
AGM_FEE_WORKBOOK_FILENAME = "Momentum Fee Calculation.xlsx"
AGM_DAILY_BALANCES_FILENAME = "balances_210TGG51_20OCT2025_07JUL2026.csv"

INGEST_AUDIT_TCP_FILENAME = "glenn_uploader_ingest_tcp_audit.jsonl"
INGEST_AUDIT_AGM_FILENAME = "glenn_uploader_ingest_agm_audit.jsonl"
INGEST_AUDIT_TKP_FILENAME = "glenn_uploader_ingest_tkp_audit.jsonl"

# VPS layout (not active until HC_APP_ENV selects a vps-* profile)
VPS_DATA_ROOT = Path(r"E:\H&C\data")
VPS_LOG_ROOT = Path(r"E:\H&C\logs")
VPS_CACHE_ROOT = Path(r"E:\H&C\data")
VPS_BACKUP_ROOT = Path(r"E:\H&C\backups")


@dataclass(frozen=True)
class TearsheetPaths:
    """Resolved path bundle for tearsheet applications."""

    app_env: str
    deploy_root: Path
    data_root: Path
    production_data_root: Path
    sandbox_data_root: Path
    log_root: Path
    cache_root: Path
    backup_root: Path
    agm_data_root: Path
    yq_data_root: Path
    agm_pinned_csv: Path
    agm_benchmark_cache_dir: Path
    tcp_ingest_audit_path: Path
    agm_ingest_audit_path: Path
    dirty_root: Path
    yq_csv_path: Path


def resolve_hc_app_env(env: Optional[Mapping[str, str]] = None) -> str:
    """Return validated ``HC_APP_ENV``; unset defaults to ``local-production``."""
    environ = env if env is not None else os.environ
    if HC_APP_ENV_VAR not in environ:
        return DEFAULT_HC_APP_ENV
    raw = (environ.get(HC_APP_ENV_VAR) or "").strip()
    if not raw:
        raise ValueError(
            f"Invalid {HC_APP_ENV_VAR}={environ.get(HC_APP_ENV_VAR)!r}; "
            f"expected one of {sorted(VALID_HC_APP_ENVS)}"
        )
    if raw not in VALID_HC_APP_ENVS:
        raise ValueError(
            f"Invalid {HC_APP_ENV_VAR}={raw!r}; "
            f"expected one of {sorted(VALID_HC_APP_ENVS)}"
        )
    return raw


def _environ_dict(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _non_empty(env: Mapping[str, str], key: str) -> Optional[str]:
    raw = (env.get(key) or "").strip()
    return raw or None


def _resolve_path_value(
    raw: str,
    *,
    deploy_root: Path,
) -> Path:
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (deploy_root / expanded).resolve()


def _resolve_optional_env_path(
    env: Mapping[str, str],
    key: str,
    *,
    deploy_root: Path,
) -> Optional[Path]:
    raw = _non_empty(env, key)
    if raw is None:
        return None
    return _resolve_path_value(raw, deploy_root=deploy_root)


def _profile_roots(
    app_env: str,
    *,
    deploy_root: Path,
) -> dict[str, Path]:
    """Return profile-level root defaults before per-path overrides."""
    if app_env in {"local-dev", "local-production"}:
        return {
            "data_root": deploy_root,
            "production_data_root": deploy_root,
            "sandbox_data_root": deploy_root,
            "log_root": deploy_root,
            "cache_root": deploy_root,
            "backup_root": deploy_root,
            "agm_data_root": deploy_root / AGM_DATA_SUBDIR,
            "yq_data_root": DEFAULT_DIRTY_ROOT,
        }
    # vps-sandbox and vps-production share the same structural layout;
    # isolation is expected via separate VMs or explicit per-path overrides.
    return {
        "data_root": VPS_DATA_ROOT,
        "production_data_root": VPS_DATA_ROOT,
        "sandbox_data_root": VPS_DATA_ROOT / "sandbox",
        "log_root": VPS_LOG_ROOT,
        "cache_root": VPS_CACHE_ROOT,
        "backup_root": VPS_BACKUP_ROOT,
        "agm_data_root": VPS_DATA_ROOT / "agm",
        "yq_data_root": VPS_DATA_ROOT / "yq",
    }


def resolve_deploy_root(
    *,
    env: Optional[Mapping[str, str]] = None,
    module_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Canonical deployment checkout root (defaults to this module's parent)."""
    environ = _environ_dict(env)
    anchor = Path(module_dir).resolve() if module_dir is not None else _MODULE_DIR
    deploy_root = _resolve_optional_env_path(
        environ, HC_DEPLOY_ROOT_ENV, deploy_root=anchor
    )
    if deploy_root is not None:
        return deploy_root
    return anchor


def resolve_dirty_root(*, env: Optional[Mapping[str, str]] = None) -> Path:
    """Main repo checkout used by launcher guards and Y&Q CSV default."""
    environ = _environ_dict(env)
    override = _resolve_optional_env_path(
        environ, HC_DIRTY_ROOT_ENV, deploy_root=_MODULE_DIR
    )
    if override is not None:
        return override
    return DEFAULT_DIRTY_ROOT.resolve()


def resolve_yq_csv_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    module_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve authoritative Y&Q monthly CSV path.

    Precedence:
      1. ``YQ_CSV_PATH`` environment variable
      2. ``HC_YQ_DATA_ROOT`` / ``yq.csv`` when ``HC_YQ_DATA_ROOT`` is set
      3. ``yq.csv`` beside *module_dir* when that file exists
      4. ``HC_YQ_DATA_ROOT`` profile default + ``yq.csv`` for VPS profiles
      5. Repo-root ``yq.csv`` at ``DEFAULT_DIRTY_ROOT``
    """
    environ = _environ_dict(env)
    override = _non_empty(environ, YQ_CSV_PATH_ENV)
    if override:
        return _resolve_path_value(override, deploy_root=resolve_deploy_root(env=environ))

    yq_root_override = _resolve_optional_env_path(
        environ, HC_YQ_DATA_ROOT_ENV, deploy_root=resolve_deploy_root(env=environ)
    )
    if yq_root_override is not None:
        return (yq_root_override / "yq.csv").resolve()

    if module_dir is not None:
        sibling = Path(module_dir) / "yq.csv"
        if sibling.is_file():
            return sibling.resolve()

    app_env = resolve_hc_app_env(environ)
    if app_env.startswith("vps-"):
        return (_profile_roots(app_env, deploy_root=resolve_deploy_root(env=environ))[
            "yq_data_root"
        ] / "yq.csv").resolve()

    return DEFAULT_YQ_REPO_ROOT_CSV.resolve()


def resolve_agm_pinned_csv(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """Pinned TradeStation balances CSV (read-only authoritative history)."""
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(environ, HC_AGM_PINNED_CSV_ENV, deploy_root=root)
    if override is not None:
        return override
    app_env = resolve_hc_app_env(environ)
    agm_root = _resolve_optional_env_path(
        environ, HC_AGM_DATA_ROOT_ENV, deploy_root=root
    ) or _profile_roots(app_env, deploy_root=root)["agm_data_root"]
    return (
        agm_root / "data" / "daily_balances" / AGM_DAILY_BALANCES_FILENAME
    ).resolve()


def resolve_agm_benchmark_cache_dir(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """AGM benchmark CSV cache directory."""
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_AGM_BENCHMARK_CACHE_DIR_ENV, deploy_root=root
    )
    if override is not None:
        return override
    cache_root = _resolve_optional_env_path(
        environ, HC_CACHE_ROOT_ENV, deploy_root=root
    )
    if cache_root is not None:
        return (cache_root / "agm" / "benchmarks").resolve()
    app_env = resolve_hc_app_env(environ)
    agm_root = _resolve_optional_env_path(
        environ, HC_AGM_DATA_ROOT_ENV, deploy_root=root
    ) or _profile_roots(app_env, deploy_root=root)["agm_data_root"]
    return (agm_root / "data" / "benchmarks").resolve()


def resolve_tcp_ingest_audit_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """TCP Glenn uploader ingest audit JSONL path."""
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_TCP_INGEST_AUDIT_PATH_ENV, deploy_root=root
    )
    if override is not None:
        return override
    log_root = _resolve_optional_env_path(environ, HC_LOG_ROOT_ENV, deploy_root=root)
    if log_root is not None:
        return (log_root / "ingest" / INGEST_AUDIT_TCP_FILENAME).resolve()
    return (root / INGEST_AUDIT_TCP_FILENAME).resolve()


def resolve_agm_ingest_audit_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """AGM Glenn uploader ingest audit JSONL path."""
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_AGM_INGEST_AUDIT_PATH_ENV, deploy_root=root
    )
    if override is not None:
        return override
    log_root = _resolve_optional_env_path(environ, HC_LOG_ROOT_ENV, deploy_root=root)
    if log_root is not None:
        return (log_root / "ingest" / INGEST_AUDIT_AGM_FILENAME).resolve()
    app_env = resolve_hc_app_env(environ)
    agm_root = _resolve_optional_env_path(
        environ, HC_AGM_DATA_ROOT_ENV, deploy_root=root
    ) or _profile_roots(app_env, deploy_root=root)["agm_data_root"]
    return (agm_root / INGEST_AUDIT_AGM_FILENAME).resolve()


def load_tearsheet_paths(
    *,
    env: Optional[Mapping[str, str]] = None,
    module_dir: Optional[Union[str, Path]] = None,
) -> TearsheetPaths:
    """Load the full resolved path bundle without side effects."""
    environ = _environ_dict(env)
    app_env = resolve_hc_app_env(environ)
    deploy_root = resolve_deploy_root(env=environ, module_dir=module_dir)
    profiles = _profile_roots(app_env, deploy_root=deploy_root)

    data_root = (
        _resolve_optional_env_path(environ, HC_DATA_ROOT_ENV, deploy_root=deploy_root)
        or profiles["data_root"]
    ).resolve()
    production_data_root = (
        _resolve_optional_env_path(
            environ, HC_PRODUCTION_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["production_data_root"]
    ).resolve()
    sandbox_data_root = (
        _resolve_optional_env_path(
            environ, HC_SANDBOX_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["sandbox_data_root"]
    ).resolve()
    log_root = (
        _resolve_optional_env_path(environ, HC_LOG_ROOT_ENV, deploy_root=deploy_root)
        or profiles["log_root"]
    ).resolve()
    cache_root = (
        _resolve_optional_env_path(environ, HC_CACHE_ROOT_ENV, deploy_root=deploy_root)
        or profiles["cache_root"]
    ).resolve()
    backup_root = (
        _resolve_optional_env_path(environ, HC_BACKUP_ROOT_ENV, deploy_root=deploy_root)
        or profiles["backup_root"]
    ).resolve()
    agm_data_root = (
        _resolve_optional_env_path(
            environ, HC_AGM_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["agm_data_root"]
    ).resolve()
    yq_data_root = (
        _resolve_optional_env_path(
            environ, HC_YQ_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["yq_data_root"]
    ).resolve()

    return TearsheetPaths(
        app_env=app_env,
        deploy_root=deploy_root,
        data_root=data_root,
        production_data_root=production_data_root,
        sandbox_data_root=sandbox_data_root,
        log_root=log_root,
        cache_root=cache_root,
        backup_root=backup_root,
        agm_data_root=agm_data_root,
        yq_data_root=yq_data_root,
        agm_pinned_csv=resolve_agm_pinned_csv(env=environ, deploy_root=deploy_root),
        agm_benchmark_cache_dir=resolve_agm_benchmark_cache_dir(
            env=environ, deploy_root=deploy_root
        ),
        tcp_ingest_audit_path=resolve_tcp_ingest_audit_path(
            env=environ, deploy_root=deploy_root
        ),
        agm_ingest_audit_path=resolve_agm_ingest_audit_path(
            env=environ, deploy_root=deploy_root
        ),
        dirty_root=resolve_dirty_root(env=environ),
        yq_csv_path=resolve_yq_csv_path(env=environ, module_dir=module_dir),
    )


def paths_identity_summary(paths: TearsheetPaths) -> dict[str, str]:
    """Safe diagnostics for health endpoints — paths and env only, no secrets."""
    return {
        "app_env": paths.app_env,
        "deploy_root": str(paths.deploy_root),
        "data_root": str(paths.data_root),
        "production_data_root": str(paths.production_data_root),
        "sandbox_data_root": str(paths.sandbox_data_root),
        "log_root": str(paths.log_root),
        "cache_root": str(paths.cache_root),
        "backup_root": str(paths.backup_root),
        "agm_data_root": str(paths.agm_data_root),
        "yq_data_root": str(paths.yq_data_root),
        "agm_pinned_csv": str(paths.agm_pinned_csv),
        "agm_benchmark_cache_dir": str(paths.agm_benchmark_cache_dir),
        "tcp_ingest_audit_path": str(paths.tcp_ingest_audit_path),
        "agm_ingest_audit_path": str(paths.agm_ingest_audit_path),
        "dirty_root": str(paths.dirty_root),
        "yq_csv_path": str(paths.yq_csv_path),
    }


def ensure_non_authoritative_directories(
    *paths,
    parents: bool = True,
) -> None:
    """Explicitly create log/cache directories. Never call implicitly on import.

    Authoritative financial inputs must already exist; this helper is for
    non-authoritative append-only logs and regenerable caches only.
    """
    for path in paths:
        path.mkdir(parents=parents, exist_ok=True)
