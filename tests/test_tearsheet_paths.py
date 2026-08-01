"""Tests for central tearsheet path configuration."""
from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path

import pytest

import tearsheet_paths as tp


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_unset_hc_app_env_defaults_to_local_production():
    assert tp.resolve_hc_app_env({}) == "local-production"


@pytest.mark.parametrize("bad", ["", "production", "vps", "LOCAL-PRODUCTION"])
def test_invalid_hc_app_env_raises(bad):
    with pytest.raises(ValueError, match="Invalid HC_APP_ENV"):
        tp.resolve_hc_app_env({tp.HC_APP_ENV_VAR: bad})


def test_deploy_root_defaults_to_module_parent():
    assert tp.resolve_deploy_root(env={}) == REPO_ROOT.resolve()


def test_deploy_root_env_override_absolute(tmp_path):
    custom = tmp_path / "deploy"
    custom.mkdir()
    assert tp.resolve_deploy_root(env={tp.HC_DEPLOY_ROOT_ENV: str(custom)}) == custom.resolve()


def test_deploy_root_env_override_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = tp.resolve_deploy_root(
        env={tp.HC_DEPLOY_ROOT_ENV: "nested/deploy"},
        module_dir=tmp_path,
    )
    assert resolved == (tmp_path / "nested" / "deploy").resolve()


def test_dirty_root_default_literal():
    assert tp.resolve_dirty_root(env={}) == tp.DEFAULT_DIRTY_ROOT.resolve()


def test_dirty_root_env_override(tmp_path):
    custom = tmp_path / "dirty"
    custom.mkdir()
    assert tp.resolve_dirty_root(env={tp.HC_DIRTY_ROOT_ENV: str(custom)}) == custom.resolve()


def test_tcp_ingest_audit_default_parity():
    expected = (REPO_ROOT / "glenn_uploader_ingest_tcp_audit.jsonl").resolve()
    assert tp.resolve_tcp_ingest_audit_path(env={}, deploy_root=REPO_ROOT) == expected


def test_agm_ingest_audit_default_parity():
    expected = (
        REPO_ROOT / "Momentum Pacer" / "glenn_uploader_ingest_agm_audit.jsonl"
    ).resolve()
    assert tp.resolve_agm_ingest_audit_path(env={}, deploy_root=REPO_ROOT) == expected


def test_agm_pinned_csv_default_parity():
    expected = (
        REPO_ROOT
        / "Momentum Pacer"
        / "data"
        / "daily_balances"
        / tp.AGM_DAILY_BALANCES_FILENAME
    ).resolve()
    assert tp.resolve_agm_pinned_csv(env={}, deploy_root=REPO_ROOT) == expected


def test_agm_benchmark_cache_default_parity():
    expected = (REPO_ROOT / "Momentum Pacer" / "data" / "benchmarks").resolve()
    assert tp.resolve_agm_benchmark_cache_dir(env={}, deploy_root=REPO_ROOT) == expected


def test_yq_csv_repo_root_fallback_parity():
    assert tp.resolve_yq_csv_path(env={}, module_dir=REPO_ROOT / "empty") == (
        tp.DEFAULT_YQ_REPO_ROOT_CSV.resolve()
    )


def test_yq_csv_env_override(tmp_path):
    csv = tmp_path / "custom.csv"
    csv.write_text("x", encoding="utf-8")
    resolved = tp.resolve_yq_csv_path(
        env={tp.YQ_CSV_PATH_ENV: str(csv)},
        module_dir=tmp_path,
    )
    assert resolved == csv.resolve()


def test_yq_csv_sibling_precedence(tmp_path):
    sibling = tmp_path / "yq.csv"
    sibling.write_text("x", encoding="utf-8")
    assert tp.resolve_yq_csv_path(env={}, module_dir=tmp_path) == sibling.resolve()


def test_tcp_ingest_audit_log_root_override(tmp_path):
    log_root = tmp_path / "logs"
    resolved = tp.resolve_tcp_ingest_audit_path(
        env={tp.HC_LOG_ROOT_ENV: str(log_root)},
        deploy_root=REPO_ROOT,
    )
    assert resolved == (log_root / "ingest" / tp.INGEST_AUDIT_TCP_FILENAME).resolve()


def test_agm_pinned_csv_override_isolated(tmp_path):
    custom = tmp_path / "custom.csv"
    custom.write_text("x", encoding="utf-8")
    resolved = tp.resolve_agm_pinned_csv(
        env={tp.HC_AGM_PINNED_CSV_ENV: str(custom)},
        deploy_root=REPO_ROOT,
    )
    assert resolved == custom.resolve()
    assert tp.resolve_agm_benchmark_cache_dir(env={}, deploy_root=REPO_ROOT) == (
        REPO_ROOT / "Momentum Pacer" / "data" / "benchmarks"
    ).resolve()


def test_vps_production_profile_roots():
    paths = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "vps-production"},
        module_dir=REPO_ROOT,
    )
    assert paths.app_env == "vps-production"
    assert paths.data_root == tp.VPS_DATA_ROOT.resolve()
    assert paths.agm_data_root == (tp.VPS_DATA_ROOT / "agm").resolve()
    assert paths.yq_csv_path == (tp.VPS_DATA_ROOT / "yq" / "yq.csv").resolve()


def test_vps_sandbox_has_separate_sandbox_data_root():
    paths = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "vps-sandbox"},
        module_dir=REPO_ROOT,
    )
    assert paths.sandbox_data_root == (tp.VPS_DATA_ROOT / "sandbox").resolve()
    assert paths.production_data_root == tp.VPS_DATA_ROOT.resolve()


def test_vps_per_path_env_beats_profile(tmp_path):
    custom_state = tmp_path / "tkp" / "state.json"
    paths = tp.load_tearsheet_paths(
        env={
            tp.HC_APP_ENV_VAR: "vps-production",
            tp.HC_TCP_INGEST_AUDIT_PATH_ENV: str(custom_state),
        },
        module_dir=REPO_ROOT,
    )
    assert paths.tcp_ingest_audit_path == custom_state.resolve()
    assert paths.agm_pinned_csv == (
        tp.VPS_DATA_ROOT / "agm" / "data" / "daily_balances" / tp.AGM_DAILY_BALANCES_FILENAME
    ).resolve()


def test_local_dev_matches_local_production_defaults():
    prod = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "local-production"},
        module_dir=REPO_ROOT,
    )
    dev = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "local-dev"},
        module_dir=REPO_ROOT,
    )
    prod_fields = {f.name: getattr(prod, f.name) for f in prod.__dataclass_fields__.values() if f.name != "app_env"}
    dev_fields = {f.name: getattr(dev, f.name) for f in dev.__dataclass_fields__.values() if f.name != "app_env"}
    assert prod_fields == dev_fields


def test_load_does_not_create_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.iterdir())
    tp.load_tearsheet_paths(env={}, module_dir=tmp_path)
    assert list(tmp_path.iterdir()) == before


def test_import_and_reload_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.iterdir())
    importlib.reload(tp)
    assert list(tmp_path.iterdir()) == before


def test_forbidden_imports():
    source = (REPO_ROOT / "tearsheet_paths.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"dash", "flask", "pandas", "tkp_ts", "mp_ts", "yfinance"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in forbidden


def test_paths_identity_summary_no_secrets():
    paths = tp.load_tearsheet_paths(env={}, module_dir=REPO_ROOT)
    summary = tp.paths_identity_summary(paths)
    assert summary["app_env"] == "local-production"
    assert "deploy_root" in summary
    assert "token" not in "".join(summary).lower()
    assert "secret" not in "".join(summary).lower()


def test_empty_env_override_falls_back_to_default():
    assert tp.resolve_tcp_ingest_audit_path(
        env={tp.HC_TCP_INGEST_AUDIT_PATH_ENV: "   "},
        deploy_root=REPO_ROOT,
    ) == (REPO_ROOT / "glenn_uploader_ingest_tcp_audit.jsonl").resolve()


def test_ensure_non_authoritative_directories_explicit_only(tmp_path):
    target = tmp_path / "logs" / "ingest"
    assert not target.exists()
    tp.ensure_non_authoritative_directories(target)
    assert target.is_dir()
