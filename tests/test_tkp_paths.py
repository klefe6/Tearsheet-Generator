"""Tests for TKP state and source-workbook path configuration.

Compatibility contract: with no ``HC_TKP_*`` variables set and the default
``local-production`` profile, both resolvers must return exactly the paths
``tkp_ts.py`` used before this lane.

These tests never touch the laptop workbook on disk. The default workbook lives
under a protected H&C Documents folder, so it is only ever compared as a string.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

import tearsheet_paths as tp


REPO_ROOT = Path(__file__).resolve().parents[1]

# Pre-lane literals captured from tkp_ts.py @ a757629. These are the golden
# values the default profile must keep reproducing.
LEGACY_STATE_FILENAME = "daily_returns_secret_state.json"
LEGACY_WORKBOOK = (
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"
    r"\3_Advisors Marketing (Tearsheets, PitchBooks, etc)"
    r"\1. Tearsheet Project\TKP\VADI\Copy of tkp_alex_old1.xlsx"
)


# ---------------------------------------------------------------------------
# Default-profile parity
# ---------------------------------------------------------------------------


def test_state_path_default_parity():
    expected = (REPO_ROOT / LEGACY_STATE_FILENAME).resolve()
    assert tp.resolve_tkp_state_path(env={}, deploy_root=REPO_ROOT) == expected


def test_state_path_default_matches_legacy_module_dir_expression():
    """Legacy behaviour was os.path.dirname(os.path.abspath(tkp_ts.__file__))."""
    legacy = Path(
        os.path.join(
            os.path.dirname(os.path.abspath(str(REPO_ROOT / "tkp_ts.py"))),
            LEGACY_STATE_FILENAME,
        )
    )
    assert tp.resolve_tkp_state_path(env={}) == legacy


def test_source_workbook_default_is_exact_legacy_literal():
    assert str(tp.resolve_tkp_source_workbook(env={}, deploy_root=REPO_ROOT)) == LEGACY_WORKBOOK


def test_source_workbook_default_is_not_normalised_away():
    """The protected-folder default must be handed back verbatim, never re-rooted."""
    assert tp.DEFAULT_TKP_SOURCE_WORKBOOK == Path(LEGACY_WORKBOOK)
    assert str(tp.resolve_tkp_source_workbook(env={})) == LEGACY_WORKBOOK


def test_local_dev_matches_local_production_for_tkp():
    prod = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "local-production"}, module_dir=REPO_ROOT
    )
    dev = tp.load_tearsheet_paths(env={tp.HC_APP_ENV_VAR: "local-dev"}, module_dir=REPO_ROOT)
    assert prod.tkp_state_path == dev.tkp_state_path
    assert prod.tkp_source_workbook == dev.tkp_source_workbook
    assert prod.tkp_data_root == dev.tkp_data_root


def test_bundle_defaults_match_individual_resolvers():
    paths = tp.load_tearsheet_paths(env={}, module_dir=REPO_ROOT)
    assert paths.tkp_state_path == (REPO_ROOT / LEGACY_STATE_FILENAME).resolve()
    assert str(paths.tkp_source_workbook) == LEGACY_WORKBOOK
    assert paths.tkp_data_root == REPO_ROOT.resolve()


# ---------------------------------------------------------------------------
# Per-path environment overrides
# ---------------------------------------------------------------------------


def test_state_path_env_override_absolute(tmp_path):
    custom = tmp_path / "tkp" / "state.json"
    resolved = tp.resolve_tkp_state_path(
        env={tp.HC_TKP_STATE_PATH_ENV: str(custom)}, deploy_root=REPO_ROOT
    )
    assert resolved == custom.resolve()


def test_state_path_env_override_relative_is_rooted_at_deploy_root(tmp_path):
    resolved = tp.resolve_tkp_state_path(
        env={tp.HC_TKP_STATE_PATH_ENV: "appdata_tkp/state.json"}, deploy_root=tmp_path
    )
    assert resolved == (tmp_path / "appdata_tkp" / "state.json").resolve()


def test_source_workbook_env_override_absolute(tmp_path):
    custom = tmp_path / "tkp_source_workbook.xlsx"
    resolved = tp.resolve_tkp_source_workbook(
        env={tp.HC_TKP_SOURCE_WORKBOOK_ENV: str(custom)}, deploy_root=REPO_ROOT
    )
    assert resolved == custom.resolve()


def test_source_workbook_env_override_relative_is_rooted_at_deploy_root(tmp_path):
    resolved = tp.resolve_tkp_source_workbook(
        env={tp.HC_TKP_SOURCE_WORKBOOK_ENV: "data/tkp.xlsx"}, deploy_root=tmp_path
    )
    assert resolved == (tmp_path / "data" / "tkp.xlsx").resolve()


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_state_override_falls_back_to_default(blank):
    assert tp.resolve_tkp_state_path(
        env={tp.HC_TKP_STATE_PATH_ENV: blank}, deploy_root=REPO_ROOT
    ) == (REPO_ROOT / LEGACY_STATE_FILENAME).resolve()


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_workbook_override_falls_back_to_default(blank):
    assert (
        str(
            tp.resolve_tkp_source_workbook(
                env={tp.HC_TKP_SOURCE_WORKBOOK_ENV: blank}, deploy_root=REPO_ROOT
            )
        )
        == LEGACY_WORKBOOK
    )


def test_overrides_are_independent(tmp_path):
    """Overriding the state file must not move the workbook, and vice versa."""
    custom = tmp_path / "state.json"
    env = {tp.HC_TKP_STATE_PATH_ENV: str(custom)}
    assert tp.resolve_tkp_state_path(env=env, deploy_root=REPO_ROOT) == custom.resolve()
    assert str(tp.resolve_tkp_source_workbook(env=env, deploy_root=REPO_ROOT)) == LEGACY_WORKBOOK


# ---------------------------------------------------------------------------
# TKP data root
# ---------------------------------------------------------------------------


def test_tkp_data_root_env_moves_both_files(tmp_path):
    env = {tp.HC_TKP_DATA_ROOT_ENV: str(tmp_path)}
    assert tp.resolve_tkp_state_path(env=env, deploy_root=REPO_ROOT) == (
        tmp_path / LEGACY_STATE_FILENAME
    ).resolve()
    assert tp.resolve_tkp_source_workbook(env=env, deploy_root=REPO_ROOT) == (
        tmp_path / tp.TKP_SOURCE_WORKBOOK_FILENAME
    ).resolve()


def test_per_path_env_beats_tkp_data_root(tmp_path):
    custom = tmp_path / "elsewhere" / "state.json"
    env = {
        tp.HC_TKP_DATA_ROOT_ENV: str(tmp_path / "root"),
        tp.HC_TKP_STATE_PATH_ENV: str(custom),
    }
    assert tp.resolve_tkp_state_path(env=env, deploy_root=REPO_ROOT) == custom.resolve()


# ---------------------------------------------------------------------------
# VPS profiles — defined but inactive by default
# ---------------------------------------------------------------------------


def test_vps_profiles_are_inactive_without_hc_app_env():
    paths = tp.load_tearsheet_paths(env={}, module_dir=REPO_ROOT)
    assert paths.app_env == "local-production"
    assert paths.tkp_state_path == (REPO_ROOT / LEGACY_STATE_FILENAME).resolve()
    assert str(paths.tkp_source_workbook) == LEGACY_WORKBOOK
    assert tp.VPS_DATA_ROOT not in paths.tkp_state_path.parents


@pytest.mark.parametrize("app_env", ["vps-sandbox", "vps-production"])
def test_vps_profile_tkp_defaults(app_env):
    paths = tp.load_tearsheet_paths(env={tp.HC_APP_ENV_VAR: app_env}, module_dir=REPO_ROOT)
    tkp_root = (tp.VPS_DATA_ROOT / "tkp").resolve()
    assert paths.tkp_data_root == tkp_root
    assert paths.tkp_state_path == (tkp_root / LEGACY_STATE_FILENAME).resolve()
    assert paths.tkp_source_workbook == (tkp_root / tp.TKP_SOURCE_WORKBOOK_FILENAME).resolve()


def test_vps_per_path_env_beats_profile(tmp_path):
    custom = tmp_path / "state.json"
    paths = tp.load_tearsheet_paths(
        env={
            tp.HC_APP_ENV_VAR: "vps-production",
            tp.HC_TKP_STATE_PATH_ENV: str(custom),
        },
        module_dir=REPO_ROOT,
    )
    assert paths.tkp_state_path == custom.resolve()
    assert paths.tkp_source_workbook == (
        tp.VPS_DATA_ROOT / "tkp" / tp.TKP_SOURCE_WORKBOOK_FILENAME
    ).resolve()


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


def test_tkp_resolution_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = list(tmp_path.iterdir())
    tp.resolve_tkp_state_path(env={tp.HC_TKP_DATA_ROOT_ENV: str(tmp_path / "tkp")})
    tp.resolve_tkp_source_workbook(env={tp.HC_TKP_DATA_ROOT_ENV: str(tmp_path / "tkp")})
    tp.load_tearsheet_paths(env={}, module_dir=tmp_path)
    assert list(tmp_path.iterdir()) == before


def test_identity_summary_exposes_tkp_paths_without_secret_keys():
    summary = tp.paths_identity_summary(tp.load_tearsheet_paths(env={}, module_dir=REPO_ROOT))
    assert summary["tkp_state_path"].endswith(LEGACY_STATE_FILENAME)
    assert summary["tkp_source_workbook"] == LEGACY_WORKBOOK
    assert "tkp_data_root" in summary
    assert "token" not in "".join(summary).lower()
    assert "secret" not in "".join(summary).lower()


# ---------------------------------------------------------------------------
# tkp_ts.py wiring
#
# tkp_ts is never imported here: importing it reads the protected-folder
# workbook and builds a Dash app at module scope. Source analysis is enough to
# prove the delegation.
# ---------------------------------------------------------------------------


def _tkp_ts_source() -> str:
    return (REPO_ROOT / "tkp_ts.py").read_text(encoding="utf-8")


def _module_assignment(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"module-level assignment to {name!r} not found in tkp_ts.py")


def _called_names(node: ast.AST) -> set[str]:
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
    return names


def test_tkp_ts_no_longer_hardcodes_protected_workbook_literal():
    assert LEGACY_WORKBOOK not in _tkp_ts_source()


def test_tkp_ts_workbook_comes_from_resolver():
    tree = ast.parse(_tkp_ts_source())
    assert "resolve_tkp_source_workbook" in _called_names(_module_assignment(tree, "xlsx_path"))


def test_tkp_ts_state_path_comes_from_resolver():
    tree = ast.parse(_tkp_ts_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_secret_editor_state_path":
            assert "resolve_tkp_state_path" in _called_names(node)
            return
    raise AssertionError("_secret_editor_state_path not found in tkp_ts.py")


def test_tkp_ts_keeps_xlsx_path_as_str_for_downstream_consumers():
    """Dozens of call sites pass xlsx_path to pandas/openpyxl and f-strings."""
    tree = ast.parse(_tkp_ts_source())
    value = _module_assignment(tree, "xlsx_path")
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name) and value.func.id == "str"


def test_protected_literal_lives_only_in_central_config():
    offenders = []
    for path in REPO_ROOT.glob("*.py"):
        if path.name == "tearsheet_paths.py":
            continue
        if LEGACY_WORKBOOK in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.name)
    assert offenders == []
