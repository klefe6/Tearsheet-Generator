"""Tests for Algominds v2 preview state foundation."""
from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_config
import algominds_v2_state as state


def test_missing_state_file_reads_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    assert state.read_preview_state(path) == state.empty_preview_state()


def test_write_read_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "preview.json"
    original = state.AlgomindsV2PreviewState(
        last_updated_utc="2026-07-06T15:30:00Z",
        account_balance=Decimal("50125.21"),
        fee_removal=Decimal("1330.249061"),
        notes="preview seed",
    )
    state.write_preview_state(path, original)
    loaded = state.read_preview_state(path)
    assert loaded == original


def test_decimal_values_serialized_as_strings(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    preview = state.AlgomindsV2PreviewState(
        account_balance=Decimal("60868.19"),
        fee_removal=Decimal("0"),
    )
    state.write_preview_state(path, preview)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload["account_balance"], str)
    assert isinstance(payload["fee_removal"], str)
    assert payload["account_balance"] == "60868.19"
    assert payload["fee_removal"] == "0"


def test_write_creates_parent_directory_only_on_write(tmp_path: Path) -> None:
    nested = tmp_path / "preview" / "state.json"
    assert not nested.parent.exists()
    state.write_preview_state(
        nested,
        state.AlgomindsV2PreviewState(account_balance=Decimal("100")),
    )
    assert nested.exists()
    assert nested.parent.is_dir()


def test_import_does_not_create_files(repo_root: Path) -> None:
    default_path = repo_root / algominds_v2_config.DEFAULT_STATE_FILENAME
    state.resolve_preview_state_path(env={}, repo_root=repo_root)
    assert not default_path.exists()


def test_corrupted_json_raises_clear_exception(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(state.PreviewStateCorruptedError, match="invalid JSON"):
        state.read_preview_state(path)


def test_invalid_schema_raises_clear_exception(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text(
        json.dumps({"schema_version": 99, "account_balance": "1"}),
        encoding="utf-8",
    )
    with pytest.raises(state.PreviewStateSchemaError, match="schema_version"):
        state.read_preview_state(path)


def test_invalid_decimal_type_rejected(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text(
        json.dumps({"schema_version": 1, "account_balance": 123.45}),
        encoding="utf-8",
    )
    with pytest.raises(state.PreviewStateSchemaError, match="decimal string"):
        state.read_preview_state(path)


def test_custom_state_path_from_env(tmp_path: Path) -> None:
    custom = tmp_path / "custom" / "state.json"
    resolved = state.resolve_preview_state_path(
        env={algominds_v2_config.STATE_PATH_ENV: str(custom)},
        repo_root=tmp_path,
    )
    assert resolved == custom


def test_default_repo_root_state_not_created_during_tests(tmp_path: Path) -> None:
    default_path = tmp_path / algominds_v2_config.DEFAULT_STATE_FILENAME
    resolved = state.resolve_preview_state_path(env={}, repo_root=tmp_path)
    assert resolved == default_path
    state.read_preview_state(resolved)
    assert not default_path.exists()


def test_forbidden_import_scan() -> None:
    source_path = Path(state.__file__)
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


def test_empty_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    state.write_preview_state(path, state.empty_preview_state())
    loaded = state.read_preview_state(path)
    assert loaded == state.empty_preview_state()


def test_backward_compatible_without_latest_snapshot_field(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text(
        json.dumps({"schema_version": 1, "account_balance": "100"}),
        encoding="utf-8",
    )
    loaded = state.read_preview_state(path)
    assert loaded.latest_snapshot is None
    assert loaded.account_balance == Decimal("100")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path
