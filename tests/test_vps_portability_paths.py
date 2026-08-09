"""Phase P3 — VPS portability path resolver + consumer-wiring tests.

Covers the path keys added to complete Windows VPS portability:
  * new layout roots (apps/config/secrets/website + per-program TCP data root)
  * AGM manual-state JSON and fee workbook
  * per-program log directory helper
  * VPS ingest-audit coherence under C:\\H&C\\logs
  * default (laptop) parity for every new key
  * consumer wiring (AST, no heavy Dash imports)

No test mutates the filesystem or touches production paths.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import tearsheet_paths as tp

REPO_ROOT = Path(__file__).resolve().parents[1]
VPS = {tp.HC_APP_ENV_VAR: "vps-production"}


# ---------------------------------------------------------------------------
# Canonical root + new layout roots
# ---------------------------------------------------------------------------
def test_canonical_vps_root_is_c_hc():
    assert str(tp.VPS_ROOT) == r"C:\H&C"


def test_new_roots_default_parity():
    paths = tp.load_tearsheet_paths(env={}, module_dir=REPO_ROOT)
    for field in ("apps_root", "config_root", "secrets_root", "website_root", "tcp_data_root"):
        assert getattr(paths, field) == REPO_ROOT.resolve(), field


def test_new_roots_vps_layout_under_c_hc():
    paths = tp.load_tearsheet_paths(env=VPS, module_dir=REPO_ROOT)
    assert paths.apps_root == tp.VPS_APPS_ROOT.resolve()
    assert paths.config_root == tp.VPS_CONFIG_ROOT.resolve()
    assert paths.secrets_root == tp.VPS_SECRETS_ROOT.resolve()
    assert paths.website_root == tp.VPS_WEBSITE_ROOT.resolve()
    assert paths.tcp_data_root == (tp.VPS_DATA_ROOT / "tcp").resolve()
    for field in (
        "apps_root", "data_root", "config_root", "secrets_root", "log_root",
        "backup_root", "website_root", "tcp_data_root", "agm_data_root",
        "yq_data_root", "tkp_data_root",
    ):
        assert str(getattr(paths, field)).startswith(r"C:\H&C"), field


@pytest.mark.parametrize("app_env", ["local-dev", "local-production"])
def test_new_roots_local_dev_matches_production(app_env):
    prod = tp.load_tearsheet_paths(env={tp.HC_APP_ENV_VAR: "local-production"}, module_dir=REPO_ROOT)
    other = tp.load_tearsheet_paths(env={tp.HC_APP_ENV_VAR: app_env}, module_dir=REPO_ROOT)
    for field in ("apps_root", "config_root", "secrets_root", "website_root", "tcp_data_root"):
        assert getattr(prod, field) == getattr(other, field)


# ---------------------------------------------------------------------------
# TCP data root
# ---------------------------------------------------------------------------
def test_tcp_data_root_default_parity():
    assert tp.resolve_tcp_data_root(env={}, deploy_root=REPO_ROOT) == REPO_ROOT.resolve()


def test_tcp_data_root_vps():
    assert tp.resolve_tcp_data_root(env=VPS, deploy_root=REPO_ROOT) == (tp.VPS_DATA_ROOT / "tcp").resolve()


def test_tcp_data_root_env_override(tmp_path):
    assert tp.resolve_tcp_data_root(
        env={tp.HC_TCP_DATA_ROOT_ENV: str(tmp_path)}, deploy_root=REPO_ROOT
    ) == tmp_path.resolve()


# ---------------------------------------------------------------------------
# AGM manual-state JSON
# ---------------------------------------------------------------------------
def test_agm_manual_state_default_parity():
    expected = (REPO_ROOT / "Momentum Pacer" / tp.AGM_MANUAL_ROWS_FILENAME).resolve()
    assert tp.resolve_agm_manual_state_path(env={}, deploy_root=REPO_ROOT) == expected


def test_agm_manual_state_vps():
    assert tp.resolve_agm_manual_state_path(env=VPS, deploy_root=REPO_ROOT) == (
        tp.VPS_DATA_ROOT / "agm" / tp.AGM_MANUAL_ROWS_FILENAME
    ).resolve()


def test_agm_manual_state_explicit_override(tmp_path):
    custom = tmp_path / "rows.json"
    assert tp.resolve_agm_manual_state_path(
        env={tp.HC_AGM_MANUAL_STATE_PATH_ENV: str(custom)}, deploy_root=REPO_ROOT
    ) == custom.resolve()


def test_agm_manual_state_data_root_override(tmp_path):
    assert tp.resolve_agm_manual_state_path(
        env={tp.HC_AGM_DATA_ROOT_ENV: str(tmp_path)}, deploy_root=REPO_ROOT
    ) == (tmp_path / tp.AGM_MANUAL_ROWS_FILENAME).resolve()


def test_agm_manual_state_empty_override_falls_back(tmp_path):
    assert tp.resolve_agm_manual_state_path(
        env={tp.HC_AGM_MANUAL_STATE_PATH_ENV: "   "}, deploy_root=REPO_ROOT
    ) == (REPO_ROOT / "Momentum Pacer" / tp.AGM_MANUAL_ROWS_FILENAME).resolve()


# ---------------------------------------------------------------------------
# AGM fee workbook
# ---------------------------------------------------------------------------
def test_agm_fee_workbook_default_parity():
    expected = (REPO_ROOT / "Momentum Pacer" / tp.AGM_FEE_WORKBOOK_FILENAME).resolve()
    assert tp.resolve_agm_fee_workbook(env={}, deploy_root=REPO_ROOT) == expected


def test_agm_fee_workbook_vps():
    assert tp.resolve_agm_fee_workbook(env=VPS, deploy_root=REPO_ROOT) == (
        tp.VPS_DATA_ROOT / "agm" / tp.AGM_FEE_WORKBOOK_FILENAME
    ).resolve()


def test_agm_fee_workbook_explicit_override(tmp_path):
    custom = tmp_path / "with space" / "fees.xlsx"
    assert tp.resolve_agm_fee_workbook(
        env={tp.HC_AGM_FEE_WORKBOOK_ENV: str(custom)}, deploy_root=REPO_ROOT
    ) == custom.resolve()


# ---------------------------------------------------------------------------
# Per-program log directory
# ---------------------------------------------------------------------------
def test_program_log_dir_laptop_parity_is_checkout_root():
    # Laptop logs currently live at the checkout root, not a per-program subdir.
    assert tp.resolve_program_log_dir("tcp", env={}, deploy_root=REPO_ROOT) == REPO_ROOT.resolve()


def test_program_log_dir_vps_under_logs():
    assert tp.resolve_program_log_dir("tkp", env=VPS, deploy_root=REPO_ROOT) == (
        tp.VPS_LOG_ROOT / "tkp"
    ).resolve()


def test_program_log_dir_explicit_log_root(tmp_path):
    assert tp.resolve_program_log_dir(
        "agm", env={tp.HC_LOG_ROOT_ENV: str(tmp_path)}, deploy_root=REPO_ROOT
    ) == (tmp_path / "agm").resolve()


# ---------------------------------------------------------------------------
# Ingest-audit VPS coherence (logs) + preserved laptop parity
# ---------------------------------------------------------------------------
def test_ingest_audit_vps_lands_under_logs_ingest():
    assert tp.resolve_tcp_ingest_audit_path(env=VPS, deploy_root=REPO_ROOT) == (
        tp.VPS_LOG_ROOT / "ingest" / tp.INGEST_AUDIT_TCP_FILENAME
    ).resolve()
    assert tp.resolve_agm_ingest_audit_path(env=VPS, deploy_root=REPO_ROOT) == (
        tp.VPS_LOG_ROOT / "ingest" / tp.INGEST_AUDIT_AGM_FILENAME
    ).resolve()


def test_ingest_audit_laptop_parity_unchanged():
    assert tp.resolve_tcp_ingest_audit_path(env={}, deploy_root=REPO_ROOT) == (
        REPO_ROOT / tp.INGEST_AUDIT_TCP_FILENAME
    ).resolve()
    assert tp.resolve_agm_ingest_audit_path(env={}, deploy_root=REPO_ROOT) == (
        REPO_ROOT / "Momentum Pacer" / tp.INGEST_AUDIT_AGM_FILENAME
    ).resolve()


# ---------------------------------------------------------------------------
# Safety: no filesystem mutation
# ---------------------------------------------------------------------------
def test_new_resolvers_never_create_directories(tmp_path):
    before = list(tmp_path.iterdir())
    tp.resolve_agm_manual_state_path(env=VPS, deploy_root=tmp_path)
    tp.resolve_agm_fee_workbook(env=VPS, deploy_root=tmp_path)
    tp.resolve_tcp_data_root(env=VPS, deploy_root=tmp_path)
    tp.resolve_program_log_dir("tcp", env=VPS, deploy_root=tmp_path)
    tp.load_tearsheet_paths(env=VPS, module_dir=tmp_path)
    assert list(tmp_path.iterdir()) == before


# ---------------------------------------------------------------------------
# Consumer wiring — AST only (avoids importing Dash apps / reading workbooks)
# ---------------------------------------------------------------------------
def _called_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_agm_consumer_wires_central_resolvers():
    names = _called_names(REPO_ROOT / "Momentum Pacer" / "mp_ts.py")
    assert "resolve_agm_manual_state_path" in names
    assert "resolve_agm_fee_workbook" in names


def test_tcp_consumer_wires_central_resolver():
    names = _called_names(REPO_ROOT / "tcp_ts_v2.py")
    assert "resolve_tcp_data_root" in names


def test_yq_data_current_delegates_to_central():
    src = (REPO_ROOT / "yq_data_current.py").read_text(encoding="utf-8")
    assert "from tearsheet_paths import" in src
    assert "DEFAULT_YQ_REPO_ROOT_CSV" in src
    # The duplicate hardcoded literal must be gone.
    assert r"C:\Coding Projects\Tearsheet Generator\yq.csv" not in src
