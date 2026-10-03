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
HC_CONFIG_ROOT_ENV = "HC_CONFIG_ROOT"
HC_SECRETS_ROOT_ENV = "HC_SECRETS_ROOT"
HC_WEBSITE_ROOT_ENV = "HC_WEBSITE_ROOT"
HC_APPS_ROOT_ENV = "HC_APPS_ROOT"

# Application data roots
HC_AGM_DATA_ROOT_ENV = "HC_AGM_DATA_ROOT"
HC_YQ_DATA_ROOT_ENV = "HC_YQ_DATA_ROOT"
HC_TKP_DATA_ROOT_ENV = "HC_TKP_DATA_ROOT"
HC_TCP_DATA_ROOT_ENV = "HC_TCP_DATA_ROOT"

# File-specific settings (active consumers in this lane)
HC_AGM_PINNED_CSV_ENV = "HC_AGM_PINNED_CSV"
HC_AGM_BENCHMARK_CACHE_DIR_ENV = "HC_AGM_BENCHMARK_CACHE_DIR"
HC_AGM_MANUAL_STATE_PATH_ENV = "HC_AGM_MANUAL_STATE_PATH"
HC_AGM_FEE_WORKBOOK_ENV = "HC_AGM_FEE_WORKBOOK"
HC_TCP_INGEST_AUDIT_PATH_ENV = "HC_TCP_INGEST_AUDIT_PATH"
HC_AGM_INGEST_AUDIT_PATH_ENV = "HC_AGM_INGEST_AUDIT_PATH"
HC_TKP_STATE_PATH_ENV = "HC_TKP_STATE_PATH"
HC_TKP_SOURCE_WORKBOOK_ENV = "HC_TKP_SOURCE_WORKBOOK"

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

TKP_STATE_FILENAME = "daily_returns_secret_state.json"
TKP_SOURCE_WORKBOOK_FILENAME = "tkp_source_workbook.xlsx"

# Current laptop TKP workbook. Held verbatim: it lives under a protected
# OneDrive-synced Documents tree, and normalising it (``Path.resolve()``) could
# rewrite the path through a reparse point and change which file is opened.
DEFAULT_TKP_SOURCE_WORKBOOK = Path(
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"
    r"\3_Advisors Marketing (Tearsheets, PitchBooks, etc)"
    r"\1. Tearsheet Project\TKP\VADI\Copy of tkp_alex_old1.xlsx"
)

INGEST_AUDIT_TCP_FILENAME = "glenn_uploader_ingest_tcp_audit.jsonl"
INGEST_AUDIT_AGM_FILENAME = "glenn_uploader_ingest_agm_audit.jsonl"
INGEST_AUDIT_TKP_FILENAME = "glenn_uploader_ingest_tkp_audit.jsonl"

# VPS layout (not active until HC_APP_ENV selects a vps-* profile).
#
# Canonical provider-neutral root is ``C:\H&C`` — the system volume that every
# conventional Windows Server VPS exposes (AWS Lightsail, OVHcloud, Azure, etc.).
# A data disk is intentionally NOT assumed: operators who attach one can point
# ``HC_DATA_ROOT`` (and siblings) at it without editing source. This deliberately
# supersedes the earlier E:\H&C draft from the TKP path lane, which assumed a
# second volume that some providers do not provision by default.
VPS_ROOT = Path(r"C:\H&C")
VPS_APPS_ROOT = VPS_ROOT / "apps"
VPS_DATA_ROOT = VPS_ROOT / "data"
VPS_CONFIG_ROOT = VPS_ROOT / "config"
VPS_SECRETS_ROOT = VPS_ROOT / "secrets"
VPS_LOG_ROOT = VPS_ROOT / "logs"
VPS_BACKUP_ROOT = VPS_ROOT / "backups"
VPS_WEBSITE_ROOT = VPS_ROOT / "website"
VPS_DEPLOYMENT_ROOT = VPS_ROOT / "deployment"
# Benchmark/return caches are regenerable; they live under the data tree so a
# single backup contract covers them without a distinct cache volume.
VPS_CACHE_ROOT = VPS_DATA_ROOT


@dataclass(frozen=True)
class TearsheetPaths:
    """Resolved path bundle for tearsheet applications."""

    app_env: str
    deploy_root: Path
    apps_root: Path
    data_root: Path
    production_data_root: Path
    sandbox_data_root: Path
    config_root: Path
    secrets_root: Path
    log_root: Path
    cache_root: Path
    backup_root: Path
    website_root: Path
    agm_data_root: Path
    yq_data_root: Path
    tkp_data_root: Path
    tcp_data_root: Path
    agm_pinned_csv: Path
    agm_benchmark_cache_dir: Path
    agm_manual_state_path: Path
    agm_fee_workbook: Path
    tcp_ingest_audit_path: Path
    agm_ingest_audit_path: Path
    tkp_state_path: Path
    tkp_source_workbook: Path
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
            "apps_root": deploy_root,
            "data_root": deploy_root,
            "production_data_root": deploy_root,
            "sandbox_data_root": deploy_root,
            "config_root": deploy_root,
            "secrets_root": deploy_root,
            "log_root": deploy_root,
            "cache_root": deploy_root,
            "backup_root": deploy_root,
            "website_root": deploy_root,
            "agm_data_root": deploy_root / AGM_DATA_SUBDIR,
            "yq_data_root": DEFAULT_DIRTY_ROOT,
            # TKP and TCP state have always lived beside their modules in the checkout.
            "tkp_data_root": deploy_root,
            "tcp_data_root": deploy_root,
        }
    # vps-sandbox and vps-production share the same structural layout;
    # isolation is expected via separate VMs or explicit per-path overrides.
    return {
        "apps_root": VPS_APPS_ROOT,
        "data_root": VPS_DATA_ROOT,
        "production_data_root": VPS_DATA_ROOT,
        "sandbox_data_root": VPS_DATA_ROOT / "sandbox",
        "config_root": VPS_CONFIG_ROOT,
        "secrets_root": VPS_SECRETS_ROOT,
        "log_root": VPS_LOG_ROOT,
        "cache_root": VPS_CACHE_ROOT,
        "backup_root": VPS_BACKUP_ROOT,
        "website_root": VPS_WEBSITE_ROOT,
        "agm_data_root": VPS_DATA_ROOT / "agm",
        "yq_data_root": VPS_DATA_ROOT / "yq",
        "tkp_data_root": VPS_DATA_ROOT / "tkp",
        "tcp_data_root": VPS_DATA_ROOT / "tcp",
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


def _resolve_root(
    env_key: str,
    profile_key: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve a layout root: explicit ``env_key`` override, else profile default."""
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(environ, env_key, deploy_root=root)
    if override is not None:
        return override
    app_env = resolve_hc_app_env(environ)
    return _profile_roots(app_env, deploy_root=root)[profile_key].resolve()


def resolve_apps_root(
    *, env: Optional[Mapping[str, str]] = None, deploy_root: Optional[Union[str, Path]] = None
) -> Path:
    """Application-code root (``C:\\H&C\\apps`` on VPS; checkout on laptop)."""
    return _resolve_root(HC_APPS_ROOT_ENV, "apps_root", env=env, deploy_root=deploy_root)


def resolve_config_root(
    *, env: Optional[Mapping[str, str]] = None, deploy_root: Optional[Union[str, Path]] = None
) -> Path:
    """Non-secret configuration root (``C:\\H&C\\config`` on VPS)."""
    return _resolve_root(HC_CONFIG_ROOT_ENV, "config_root", env=env, deploy_root=deploy_root)


def resolve_secrets_root(
    *, env: Optional[Mapping[str, str]] = None, deploy_root: Optional[Union[str, Path]] = None
) -> Path:
    """Secret material root (``C:\\H&C\\secrets`` on VPS). Never committed to Git."""
    return _resolve_root(HC_SECRETS_ROOT_ENV, "secrets_root", env=env, deploy_root=deploy_root)


def resolve_website_root(
    *, env: Optional[Mapping[str, str]] = None, deploy_root: Optional[Union[str, Path]] = None
) -> Path:
    """Static website/publishing root (``C:\\H&C\\website`` on VPS)."""
    return _resolve_root(HC_WEBSITE_ROOT_ENV, "website_root", env=env, deploy_root=deploy_root)


def resolve_tcp_data_root(
    *, env: Optional[Mapping[str, str]] = None, deploy_root: Optional[Union[str, Path]] = None
) -> Path:
    """TCP persistent-state root.

    Precedence: ``HC_TCP_DATA_ROOT`` → profile ``tcp_data_root`` (checkout on
    laptop, ``C:\\H&C\\data\\tcp`` on VPS). The active/backup/lock filenames and
    any ``TCP_V2_STATE_*`` per-file overrides continue to resolve relative to
    this base inside ``tcp_config.resolve_state_paths``.
    """
    return _resolve_root(HC_TCP_DATA_ROOT_ENV, "tcp_data_root", env=env, deploy_root=deploy_root)


def resolve_program_log_dir(
    program: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """Per-program log directory under the resolved log root (``<log_root>/<program>``).

    On laptop this is the checkout root (current behaviour: logs sit beside the
    app); on VPS it becomes ``C:\\H&C\\logs\\<program>``. This helper never
    creates directories — call ``ensure_non_authoritative_directories`` for that.
    """
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    log_root = (
        _resolve_optional_env_path(environ, HC_LOG_ROOT_ENV, deploy_root=root)
        or _profile_roots(resolve_hc_app_env(environ), deploy_root=root)["log_root"]
    ).resolve()
    normalized = str(program).strip().lower()
    if log_root == root:
        # Laptop parity: logs currently live at the checkout root, not a subdir.
        return log_root
    return (log_root / normalized).resolve()


def _agm_data_root(
    env: Mapping[str, str],
    *,
    deploy_root: Path,
) -> Path:
    """AGM data root: ``HC_AGM_DATA_ROOT`` override else profile default."""
    override = _resolve_optional_env_path(env, HC_AGM_DATA_ROOT_ENV, deploy_root=deploy_root)
    if override is not None:
        return override
    return _profile_roots(resolve_hc_app_env(env), deploy_root=deploy_root)["agm_data_root"]


def resolve_agm_manual_state_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """AGM / Momentum Pacer manual daily-rows state JSON (authoritative, read/write).

    Precedence:
      1. ``HC_AGM_MANUAL_STATE_PATH``
      2. ``HC_AGM_DATA_ROOT`` / filename
      3. VPS profile AGM root + filename
      4. Laptop default: the filename beside ``mp_ts.py`` (``Momentum Pacer/``)
    """
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_AGM_MANUAL_STATE_PATH_ENV, deploy_root=root
    )
    if override is not None:
        return override
    return (_agm_data_root(environ, deploy_root=root) / AGM_MANUAL_ROWS_FILENAME).resolve()


def resolve_agm_fee_workbook(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """AGM Momentum fee-calculation workbook (authoritative input; must already exist).

    Precedence:
      1. ``HC_AGM_FEE_WORKBOOK``
      2. ``HC_AGM_DATA_ROOT`` / filename
      3. VPS profile AGM root + filename
      4. Laptop default: the workbook beside ``mp_ts.py`` (``Momentum Pacer/``)
    """
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_AGM_FEE_WORKBOOK_ENV, deploy_root=root
    )
    if override is not None:
        return override
    return (_agm_data_root(environ, deploy_root=root) / AGM_FEE_WORKBOOK_FILENAME).resolve()


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
    if log_root is None and resolve_hc_app_env(environ).startswith("vps-"):
        log_root = _profile_roots(resolve_hc_app_env(environ), deploy_root=root)["log_root"]
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
    app_env = resolve_hc_app_env(environ)
    if log_root is None and app_env.startswith("vps-"):
        log_root = _profile_roots(app_env, deploy_root=root)["log_root"]
    if log_root is not None:
        return (log_root / "ingest" / INGEST_AUDIT_AGM_FILENAME).resolve()
    agm_root = _resolve_optional_env_path(
        environ, HC_AGM_DATA_ROOT_ENV, deploy_root=root
    ) or _profile_roots(app_env, deploy_root=root)["agm_data_root"]
    return (agm_root / INGEST_AUDIT_AGM_FILENAME).resolve()


def _tkp_data_root(
    env: Mapping[str, str],
    *,
    deploy_root: Path,
) -> Optional[Path]:
    """Explicit TKP data root, or ``None`` when no override is configured."""
    override = _resolve_optional_env_path(
        env, HC_TKP_DATA_ROOT_ENV, deploy_root=deploy_root
    )
    if override is not None:
        return override
    app_env = resolve_hc_app_env(env)
    if app_env.startswith("vps-"):
        return _profile_roots(app_env, deploy_root=deploy_root)["tkp_data_root"]
    return None


def resolve_tkp_state_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """TKP persisted Daily Returns editor state JSON.

    Precedence:
      1. ``HC_TKP_STATE_PATH``
      2. ``HC_TKP_DATA_ROOT`` / ``daily_returns_secret_state.json``
      3. VPS profile TKP root + filename
      4. Laptop default: the filename beside the deployment checkout root
    """
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_TKP_STATE_PATH_ENV, deploy_root=root
    )
    if override is not None:
        return override
    tkp_root = _tkp_data_root(environ, deploy_root=root)
    if tkp_root is not None:
        return (tkp_root / TKP_STATE_FILENAME).resolve()
    return (root / TKP_STATE_FILENAME).resolve()


def resolve_tkp_source_workbook(
    *,
    env: Optional[Mapping[str, str]] = None,
    deploy_root: Optional[Union[str, Path]] = None,
) -> Path:
    """TKP source workbook (authoritative NAV input; must already exist).

    Precedence:
      1. ``HC_TKP_SOURCE_WORKBOOK``
      2. ``HC_TKP_DATA_ROOT`` / ``tkp_source_workbook.xlsx``
      3. VPS profile TKP root + filename
      4. Laptop default: the protected-folder workbook, returned verbatim
    """
    environ = _environ_dict(env)
    root = Path(deploy_root).resolve() if deploy_root is not None else resolve_deploy_root(env=environ)
    override = _resolve_optional_env_path(
        environ, HC_TKP_SOURCE_WORKBOOK_ENV, deploy_root=root
    )
    if override is not None:
        return override
    tkp_root = _tkp_data_root(environ, deploy_root=root)
    if tkp_root is not None:
        return (tkp_root / TKP_SOURCE_WORKBOOK_FILENAME).resolve()
    return DEFAULT_TKP_SOURCE_WORKBOOK


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
    tkp_data_root = (
        _resolve_optional_env_path(
            environ, HC_TKP_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["tkp_data_root"]
    ).resolve()
    tcp_data_root = (
        _resolve_optional_env_path(
            environ, HC_TCP_DATA_ROOT_ENV, deploy_root=deploy_root
        )
        or profiles["tcp_data_root"]
    ).resolve()
    apps_root = (
        _resolve_optional_env_path(environ, HC_APPS_ROOT_ENV, deploy_root=deploy_root)
        or profiles["apps_root"]
    ).resolve()
    config_root = (
        _resolve_optional_env_path(environ, HC_CONFIG_ROOT_ENV, deploy_root=deploy_root)
        or profiles["config_root"]
    ).resolve()
    secrets_root = (
        _resolve_optional_env_path(environ, HC_SECRETS_ROOT_ENV, deploy_root=deploy_root)
        or profiles["secrets_root"]
    ).resolve()
    website_root = (
        _resolve_optional_env_path(environ, HC_WEBSITE_ROOT_ENV, deploy_root=deploy_root)
        or profiles["website_root"]
    ).resolve()

    return TearsheetPaths(
        app_env=app_env,
        deploy_root=deploy_root,
        apps_root=apps_root,
        data_root=data_root,
        production_data_root=production_data_root,
        sandbox_data_root=sandbox_data_root,
        config_root=config_root,
        secrets_root=secrets_root,
        log_root=log_root,
        cache_root=cache_root,
        backup_root=backup_root,
        website_root=website_root,
        agm_data_root=agm_data_root,
        yq_data_root=yq_data_root,
        tkp_data_root=tkp_data_root,
        tcp_data_root=tcp_data_root,
        agm_pinned_csv=resolve_agm_pinned_csv(env=environ, deploy_root=deploy_root),
        agm_benchmark_cache_dir=resolve_agm_benchmark_cache_dir(
            env=environ, deploy_root=deploy_root
        ),
        agm_manual_state_path=resolve_agm_manual_state_path(
            env=environ, deploy_root=deploy_root
        ),
        agm_fee_workbook=resolve_agm_fee_workbook(
            env=environ, deploy_root=deploy_root
        ),
        tcp_ingest_audit_path=resolve_tcp_ingest_audit_path(
            env=environ, deploy_root=deploy_root
        ),
        agm_ingest_audit_path=resolve_agm_ingest_audit_path(
            env=environ, deploy_root=deploy_root
        ),
        tkp_state_path=resolve_tkp_state_path(env=environ, deploy_root=deploy_root),
        tkp_source_workbook=resolve_tkp_source_workbook(
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
        "apps_root": str(paths.apps_root),
        "data_root": str(paths.data_root),
        "production_data_root": str(paths.production_data_root),
        "sandbox_data_root": str(paths.sandbox_data_root),
        "config_root": str(paths.config_root),
        "secrets_root": str(paths.secrets_root),
        "log_root": str(paths.log_root),
        "cache_root": str(paths.cache_root),
        "backup_root": str(paths.backup_root),
        "website_root": str(paths.website_root),
        "agm_data_root": str(paths.agm_data_root),
        "yq_data_root": str(paths.yq_data_root),
        "tkp_data_root": str(paths.tkp_data_root),
        "tcp_data_root": str(paths.tcp_data_root),
        "agm_pinned_csv": str(paths.agm_pinned_csv),
        "agm_benchmark_cache_dir": str(paths.agm_benchmark_cache_dir),
        "agm_manual_state_path": str(paths.agm_manual_state_path),
        "agm_fee_workbook": str(paths.agm_fee_workbook),
        "tcp_ingest_audit_path": str(paths.tcp_ingest_audit_path),
        "agm_ingest_audit_path": str(paths.agm_ingest_audit_path),
        "tkp_state_path": str(paths.tkp_state_path),
        "tkp_source_workbook": str(paths.tkp_source_workbook),
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
