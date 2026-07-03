"""Shared pytest fixtures for TCP v2 test scaffold (no production imports)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Prevent benchmark network I/O during pytest collection and test runs.
os.environ.setdefault("TCP_V2_SKIP_BENCHMARK_FETCH", "1")

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
