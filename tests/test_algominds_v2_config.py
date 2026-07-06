"""Tests for Algominds v2 config foundation."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import algominds_v2_config as config


def test_default_config() -> None:
    root = Path("/tmp/algominds-v2-repo")
    cfg = config.load_algominds_v2_config(env={}, repo_root=root)
    assert cfg.preview_port == config.DEFAULT_PREVIEW_PORT == 8311
    assert cfg.env_prefix == "ALGOMINDS_V2_"
    assert cfg.state_path == root / config.DEFAULT_STATE_FILENAME
    assert str(cfg.state_path).endswith("algominds_daily_returns_secret_state.json")


def test_custom_preview_port() -> None:
    cfg = config.load_algominds_v2_config(
        env={config.PREVIEW_PORT_ENV: "8312"},
        repo_root=Path("/tmp/algominds-v2-repo"),
    )
    assert cfg.preview_port == 8312


@pytest.mark.parametrize(
    "raw",
    ["abc", "0", "65536", "8301", "8302", "8304"],
)
def test_invalid_preview_port_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        config.load_algominds_v2_config(
            env={config.PREVIEW_PORT_ENV: raw},
            repo_root=Path("/tmp/algominds-v2-repo"),
        )


def test_custom_state_path_absolute(tmp_path: Path) -> None:
    custom = tmp_path / "custom" / "state.json"
    cfg = config.load_algominds_v2_config(
        env={config.STATE_PATH_ENV: str(custom)},
        repo_root=tmp_path,
    )
    assert cfg.state_path == custom


def test_custom_state_path_relative(tmp_path: Path) -> None:
    cfg = config.load_algominds_v2_config(
        env={config.STATE_PATH_ENV: "preview/state.json"},
        repo_root=tmp_path,
    )
    assert cfg.state_path == tmp_path / "preview" / "state.json"


def test_loading_config_does_not_create_files(tmp_path: Path) -> None:
    config.load_algominds_v2_config(env={}, repo_root=tmp_path)
    assert not (tmp_path / config.DEFAULT_STATE_FILENAME).exists()
    assert not (tmp_path / config.DEFAULT_ENV_FILENAME).exists()
    assert list(tmp_path.iterdir()) == []


def test_config_module_has_no_forbidden_imports() -> None:
    source_path = Path(config.__file__)
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
                assert root not in forbidden_roots, f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                assert root not in forbidden_roots, f"forbidden import from: {node.module}"


def test_validate_preview_port_accepts_safe_port() -> None:
    config.validate_preview_port(8311)
    config.validate_preview_port(9000)


def test_parse_preview_port_strips_whitespace() -> None:
    assert config.parse_preview_port(" 8312 ") == 8312


def test_constants_exported() -> None:
    assert config.ENV_PREFIX == "ALGOMINDS_V2_"
    assert config.DEFAULT_ENV_FILENAME == ".algominds_production.env"
    assert config.PROTECTED_PORTS == frozenset({8301, 8302, 8304})
