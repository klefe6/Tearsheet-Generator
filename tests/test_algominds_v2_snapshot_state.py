"""Tests for Algominds v2 snapshot/state integration."""
from __future__ import annotations

import ast
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_snapshot_state as snapshot_state
import algominds_v2_state as state
from algominds_v2_account_registry import get_account_profile
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot, snapshot_to_dict

D = Decimal
TOLERANCE = D("0.01")


def _may_2026_snapshot() -> AlgomindsV2FeeSnapshot:
    return AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        notes="may preview",
    )


def _june_2026_snapshot() -> AlgomindsV2FeeSnapshot:
    return AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 6, 30),
        account_balance=D("48049.07"),
        fee_removal=D("0"),
        prior_high_water_mark=D("48794.960939"),
        spx_start=D("7580.06"),
        spx_end=D("7499.36"),
        benchmark_base=D("30000"),
    )


def test_missing_state_returns_no_latest_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    assert snapshot_state.load_latest_snapshot(path) is None
    assert snapshot_state.compute_latest_snapshot_result(path) is None


def test_save_load_snapshot_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    original = _may_2026_snapshot()
    snapshot_state.save_latest_snapshot(path, original)
    loaded = snapshot_state.load_latest_snapshot(path)
    assert loaded == original


def test_loaded_snapshot_can_be_computed(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    snapshot_state.save_latest_snapshot(path, _may_2026_snapshot())
    result = snapshot_state.compute_latest_snapshot_result(path)
    assert result is not None
    assert abs(result.current_estimated_fee - D("1330.249061")) < TOLERANCE


def test_may_2026_golden_like_fee(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    snapshot_state.save_latest_snapshot(path, _may_2026_snapshot())
    result = snapshot_state.compute_latest_snapshot_result(path)
    assert result is not None
    assert abs(result.current_estimated_fee - D("1330.249061")) < TOLERANCE
    assert abs(result.after_fee_nlv - D("48794.960939")) < TOLERANCE


def test_june_2026_zero_fee_hwm_hold(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    snapshot_state.save_latest_snapshot(path, _june_2026_snapshot())
    result = snapshot_state.compute_latest_snapshot_result(path)
    assert result is not None
    assert result.current_estimated_fee == D("0")
    assert result.next_high_water_mark == D("48794.960939")


def test_existing_preview_fields_preserved(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    preview = state.AlgomindsV2PreviewState(
        last_updated_utc="2026-07-06T12:00:00Z",
        account_balance=D("100"),
        fee_removal=D("5"),
        notes="legacy preview row",
    )
    state.write_preview_state(path, preview)
    snapshot_state.save_latest_snapshot(path, _may_2026_snapshot())
    loaded_preview = state.read_preview_state(path)
    assert loaded_preview.last_updated_utc == preview.last_updated_utc
    assert loaded_preview.account_balance == preview.account_balance
    assert loaded_preview.fee_removal == preview.fee_removal
    assert loaded_preview.notes == preview.notes
    assert snapshot_state.load_latest_snapshot(path) == _may_2026_snapshot()


def test_decimal_values_stored_as_strings(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    snapshot_state.save_latest_snapshot(path, _may_2026_snapshot())
    payload = json.loads(path.read_text(encoding="utf-8"))
    latest = payload["latest_snapshot"]
    assert isinstance(latest["account_balance"], str)
    assert isinstance(latest["fee_removal"], str)
    assert isinstance(latest["benchmark_base"], str)


def test_invalid_latest_snapshot_schema_raises(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "latest_snapshot": {"account_balance": 123.45},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(state.PreviewStateSchemaError, match="latest_snapshot"):
        snapshot_state.load_latest_snapshot(path)


def test_corrupted_json_behavior_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(state.PreviewStateCorruptedError, match="invalid JSON"):
        snapshot_state.load_latest_snapshot(path)


def test_no_files_created_outside_tmp_path(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "preview.json"
    snapshot_state.save_latest_snapshot(path, _may_2026_snapshot())
    assert list(tmp_path.iterdir()) == [tmp_path / "nested"]
    assert path.exists()


def test_backward_compatible_state_without_latest_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    state.write_preview_state(
        path,
        state.AlgomindsV2PreviewState(account_balance=D("100")),
    )
    loaded = state.read_preview_state(path)
    assert loaded.latest_snapshot is None
    assert snapshot_state.load_latest_snapshot(path) is None


def test_save_load_preserves_account_slug(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    original = AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        notes="may preview",
        account_slug="prop",
    )
    snapshot_state.save_latest_snapshot(path, original)
    loaded = snapshot_state.load_latest_snapshot(path)
    assert loaded == original
    assert loaded is not None
    assert loaded.account_slug == "prop"


def test_load_snapshot_without_account_slug_backward_compatible(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    legacy = _may_2026_snapshot()
    snapshot_state.save_latest_snapshot(path, legacy)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "account_slug" not in payload["latest_snapshot"]
    loaded = snapshot_state.load_latest_snapshot(path)
    assert loaded == legacy
    assert loaded is not None
    assert loaded.account_slug is None


def test_invalid_account_slug_in_persisted_latest_snapshot_raises(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    latest = snapshot_to_dict(_may_2026_snapshot())
    latest["account_slug"] = "Bad Slug"
    path.write_text(
        json.dumps({"schema_version": 1, "latest_snapshot": latest}),
        encoding="utf-8",
    )
    with pytest.raises(state.PreviewStateSchemaError, match="latest_snapshot"):
        snapshot_state.load_latest_snapshot(path)


def test_loaded_snapshot_matches_registry_route_slug(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    expected_route_slug = "vikram-suman"
    snapshot = AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("60868.19"),
        fee_removal=D("0"),
        prior_high_water_mark=D("60000"),
        spx_start=D("7408.5"),
        spx_end=D("7580.06"),
        benchmark_base=D("60000"),
        account_slug=expected_route_slug,
    )
    snapshot_state.save_latest_snapshot(path, snapshot)
    loaded = snapshot_state.load_latest_snapshot(path)
    assert loaded is not None
    assert loaded.account_slug == expected_route_slug
    assert loaded.account_slug == get_account_profile(expected_route_slug).account_slug


def test_forbidden_import_scan() -> None:
    source_path = Path(snapshot_state.__file__)
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
                root = alias.name.split(".")[0]
                assert root not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in forbidden_roots
