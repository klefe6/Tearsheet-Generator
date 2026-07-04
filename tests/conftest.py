"""Shared pytest fixtures for TCP v2 test scaffold (no production imports)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Prevent benchmark network I/O during pytest collection and test runs.
os.environ.setdefault("TCP_V2_SKIP_BENCHMARK_FETCH", "1")

_TESTS_DIR = Path(__file__).resolve().parent
_CANARY_STATE = _TESTS_DIR / "_tmp_canary_layout" / "tcp_daily_returns_secret_state.json"
if _CANARY_STATE.is_file():
    os.environ.setdefault("TCP_V2_STATE_PATH", str(_CANARY_STATE))

from tcp_test_constants import CONTRACT_PATH, GOLDEN_FIXTURE_PATH


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "local_workbook: requires local tcp_alex.xlsx at configured absolute path",
    )


@pytest.fixture(scope="session")
def golden_fixture_path() -> Path:
    return GOLDEN_FIXTURE_PATH


@pytest.fixture(scope="session")
def golden_fixture(golden_fixture_path: Path) -> dict:
    with golden_fixture_path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def contract_path() -> Path:
    return CONTRACT_PATH
