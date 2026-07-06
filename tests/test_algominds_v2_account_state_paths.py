"""Tests for Algominds v2 per-account preview state paths."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_account_state_paths as account_state_paths
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot

D = Decimal


def _may_2026_snapshot(**kwargs) -> AlgomindsV2FeeSnapshot:
    base = {
        "as_of_date": date(2026, 5, 31),
        "account_balance": D("50125.21"),
        "fee_removal": D("0"),
        "prior_high_water_mark": D("44483.423270"),
        "spx_start": D("7209.01"),
        "spx_end": D("7580.06"),
        "benchmark_base": D("30000"),
    }
    base.update(kwargs)
    return AlgomindsV2FeeSnapshot(**base)


def test_prop_resolves_to_prop_json(tmp_path: Path) -> None:
    path = account_state_paths.resolve_preview_state_path("prop", state_root=tmp_path)
    assert path == (tmp_path / "prop.json").resolve()


def test_acct_60k_resolves_to_acct_60k_json(tmp_path: Path) -> None:
    path = account_state_paths.resolve_preview_state_path("acct-60k", state_root=tmp_path)
    assert path == (tmp_path / "acct-60k.json").resolve()


@pytest.mark.parametrize(
    "slug",
    ["", "PROP", "prop/acct", "prop acct", "../prop", ".."],
)
def test_invalid_slug_rejected(slug: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        account_state_paths.resolve_preview_state_path(slug, state_root=tmp_path)


def test_resolver_does_not_create_files_or_directories(tmp_path: Path) -> None:
    root = tmp_path / "nested" / "state"
    assert not root.exists()
    path = account_state_paths.resolve_preview_state_path("prop", state_root=root)
    assert path.name == "prop.json"
    assert not root.exists()
    assert not path.exists()


def test_resolved_path_stays_under_state_root(tmp_path: Path) -> None:
    root = tmp_path / "accounts"
    path = account_state_paths.resolve_preview_state_path("acct-60k", state_root=root)
    assert path.resolve().relative_to(root.resolve())


def test_resolver_is_deterministic(tmp_path: Path) -> None:
    first = account_state_paths.resolve_preview_state_path("prop", state_root=tmp_path)
    second = account_state_paths.resolve_preview_state_path("prop", state_root=tmp_path)
    assert first == second


def test_matching_snapshot_account_slug_passes() -> None:
    account_state_paths.validate_snapshot_account_slug(
        _may_2026_snapshot(account_slug="prop"),
        "prop",
    )


def test_mismatched_snapshot_account_slug_raises() -> None:
    with pytest.raises(ValueError, match="does not match expected 'prop'"):
        account_state_paths.validate_snapshot_account_slug(
            _may_2026_snapshot(account_slug="acct-60k"),
            "prop",
        )


def test_legacy_snapshot_without_account_slug_passes() -> None:
    account_state_paths.validate_snapshot_account_slug(_may_2026_snapshot(), "prop")


def test_invalid_expected_account_slug_raises() -> None:
    with pytest.raises(ValueError):
        account_state_paths.validate_snapshot_account_slug(
            _may_2026_snapshot(account_slug="prop"),
            "Bad Slug",
        )


def test_save_and_load_for_prop_use_prop_json(tmp_path: Path) -> None:
    snapshot = _may_2026_snapshot(account_slug="prop")
    account_state_paths.save_latest_snapshot_for_account("prop", snapshot, state_root=tmp_path)
    loaded = account_state_paths.load_latest_snapshot_for_account("prop", state_root=tmp_path)
    assert loaded == snapshot
    assert (tmp_path / "prop.json").is_file()


def test_save_and_load_for_acct_60k_use_acct_60k_json(tmp_path: Path) -> None:
    snapshot = _may_2026_snapshot(
        account_slug="acct-60k",
        benchmark_base=D("60000"),
        account_balance=D("60868.19"),
        prior_high_water_mark=D("60000"),
        spx_start=D("7408.5"),
    )
    account_state_paths.save_latest_snapshot_for_account(
        "acct-60k",
        snapshot,
        state_root=tmp_path,
    )
    loaded = account_state_paths.load_latest_snapshot_for_account(
        "acct-60k",
        state_root=tmp_path,
    )
    assert loaded == snapshot
    assert (tmp_path / "acct-60k.json").is_file()


def test_save_acct_60k_snapshot_into_prop_wrapper_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match expected 'prop'"):
        account_state_paths.save_latest_snapshot_for_account(
            "prop",
            _may_2026_snapshot(account_slug="acct-60k"),
            state_root=tmp_path,
        )


def test_legacy_snapshot_loads_through_account_wrapper(tmp_path: Path) -> None:
    legacy = _may_2026_snapshot()
    account_state_paths.save_latest_snapshot_for_account("prop", legacy, state_root=tmp_path)
    loaded = account_state_paths.load_latest_snapshot_for_account("prop", state_root=tmp_path)
    assert loaded == legacy
    assert loaded is not None
    assert loaded.account_slug is None


def test_account_state_root_env_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom-root"
    path = account_state_paths.resolve_preview_state_path(
        "prop",
        state_root=None,
        env={account_state_paths.ACCOUNT_STATE_ROOT_ENV: str(custom)},
        repo_root=tmp_path,
    )
    assert path == (custom / "prop.json").resolve()


def test_forbidden_import_scan() -> None:
    source_path = Path(account_state_paths.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "dash",
        "flask",
        "openpyxl",
        "pandas",
        "tkp_ts",
        "tcp_ts",
        "mp_ts",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots
