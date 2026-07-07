"""Shared pytest fixtures for TCP v2 test scaffold (no production imports)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tcp_test_constants import CONTRACT_PATH, GOLDEN_FIXTURE_PATH

# TKP (tkp_ts.py) builds its AdminAuthManager once at module-import time (unlike TCP's
# create_app() factory), so its admin token/session secret must be set before *any* test
# module imports tkp_ts -- including a bare `import tkp_ts` inside another file's test
# body. conftest.py loads before collection, so setting real env vars here (not via
# monkeypatch, which only applies during a running test) is deterministic regardless of
# test execution order.
os.environ.setdefault("TKP_ADMIN_TOKEN", "test-runtime-admin-token")
os.environ.setdefault("TKP_SESSION_SECRET", "test-runtime-session-secret")

# Same reasoning for AGM (Momentum Pacer / mp_ts.py) -- it also builds its
# AdminAuthManager at module-import time.
os.environ.setdefault("AGM_ADMIN_TOKEN", "test-runtime-admin-token")
os.environ.setdefault("AGM_SESSION_SECRET", "test-runtime-session-secret")

# mp_ts.py lives in "Momentum Pacer/" (a directory with a space) which isn't on
# sys.path by default; add it once here so any test can `import mp_ts`.
_MOMENTUM_PACER_DIR = str(Path(__file__).resolve().parent.parent / "Momentum Pacer")
if _MOMENTUM_PACER_DIR not in sys.path:
    sys.path.insert(0, _MOMENTUM_PACER_DIR)


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
