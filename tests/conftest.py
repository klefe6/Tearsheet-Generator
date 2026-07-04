"""Shared pytest fixtures for TCP v2 test scaffold (no production imports)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Generator, Tuple

import pytest

# Prevent benchmark network I/O during pytest collection and test runs.
os.environ.setdefault("TCP_V2_SKIP_BENCHMARK_FETCH", "1")

# Isolate tests from developer shell overrides (e.g. production json_active mode).
os.environ["TCP_V2_STATE_MODE"] = "workbook"
for _state_env in (
    "TCP_V2_STATE_PATH",
    "TCP_V2_STATE_BACKUP_PATH",
    "TCP_V2_STATE_LOCK_PATH",
):
    os.environ.pop(_state_env, None)

from tcp_test_constants import CONTRACT_PATH, GOLDEN_FIXTURE_PATH, TEST_AUTH_SECRET, TEST_AUTH_TOKEN

_INTEGRATION_FILES = frozenset(
    {
        "test_tcp_seed_state.py",
        "test_tcp_parity_acceptance.py",
        "test_tcp_resilience_acceptance.py",
        "test_tcp_runtime_state.py",
        "test_tcp_state.py",
        "test_tcp_ledger.py",
        "test_tcp_v2_shell.py",
        "test_tcp_public_ui_parity.py",
    }
)

_WORKBOOK_FILES = frozenset(
    {
        "test_tcp_seed_state.py",
        "test_tcp_parity_acceptance.py",
        "test_tcp_calculations.py",
        "test_tcp_dashboard.py",
        "test_tcp_drawdown.py",
        "test_tcp_benchmarks.py",
        "test_tcp_admin.py",
        "test_tcp_access_daily_values.py",
        "test_tcp_hotfix_table_benchmark_auth.py",
        "test_tcp_layout_overlap_fixes.py",
        "test_tcp_resilience_acceptance.py",
        "test_tcp_ledger.py",
        "test_tcp_mobile_responsive.py",
        "test_tcp_desktop_visual_parity.py",
        "test_tcp_public_content.py",
        "test_tcp_public_shell.py",
        "test_tearsheet_password_gate.py",
        "test_tcp_v2_shell.py",
    }
)

_NETWORK_FILES = frozenset({"test_tcp_benchmarks.py"})

_BROWSER_FILES = frozenset(
    {
        "test_tcp_mobile_responsive.py",
        "test_tcp_desktop_visual_parity.py",
    }
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "local_workbook: requires local tcp_alex.xlsx at configured absolute path",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        fname = item.path.name
        if fname in _INTEGRATION_FILES:
            item.add_marker(pytest.mark.integration)
        if fname in _WORKBOOK_FILES:
            item.add_marker(pytest.mark.workbook)
        if fname in _NETWORK_FILES:
            item.add_marker(pytest.mark.network)
        if fname in _BROWSER_FILES:
            item.add_marker(pytest.mark.browser)
        if "integration" not in item.keywords and "slow" not in item.keywords:
            item.add_marker(pytest.mark.fast)


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


@pytest.fixture(scope="session")
def tcp_config():
    from tcp_config import load_config

    return load_config()


@pytest.fixture(scope="session")
def tcp_workbook_path(tcp_config) -> Path:
    wb = Path(tcp_config.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    return wb


@pytest.fixture(scope="session")
def tcp_ledger(tcp_workbook_path, tcp_config):
    from tcp_ledger import load_ledger

    return load_ledger(str(tcp_workbook_path), tcp_config.sheet_name)


@pytest.fixture(scope="session")
def ledger(tcp_ledger):
    """Backward-compatible alias used across TCP test modules."""
    return tcp_ledger


@pytest.fixture(scope="session")
def tcp_canonical_nav(tcp_ledger):
    from tcp_dashboard import canonical_nav_records_from_ledger

    return canonical_nav_records_from_ledger(tcp_ledger.completed_records)


@pytest.fixture(scope="session")
def canonical(tcp_canonical_nav):
    """Backward-compatible alias used by dashboard/drawdown/benchmark tests."""
    return tcp_canonical_nav


@pytest.fixture(scope="session")
def tcp_app_bundle() -> Generator[Tuple[Any, ...], None, None]:
    from tcp_config import AdminAuthSettings
    from tcp_ts_v2 import create_app

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
        "TCP_V2_STATE_MODE": os.environ.get("TCP_V2_STATE_MODE"),
        "TCP_V2_STATE_PATH": os.environ.get("TCP_V2_STATE_PATH"),
        "TCP_V2_STATE_BACKUP_PATH": os.environ.get("TCP_V2_STATE_BACKUP_PATH"),
        "TCP_V2_STATE_LOCK_PATH": os.environ.get("TCP_V2_STATE_LOCK_PATH"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = TEST_AUTH_TOKEN
    os.environ["TCP_V2_SESSION_SECRET"] = TEST_AUTH_SECRET
    os.environ["TCP_V2_STATE_MODE"] = "workbook"
    for key in ("TCP_V2_STATE_PATH", "TCP_V2_STATE_BACKUP_PATH", "TCP_V2_STATE_LOCK_PATH"):
        os.environ.pop(key, None)
    settings = AdminAuthSettings(admin_token=TEST_AUTH_TOKEN, session_secret=TEST_AUTH_SECRET)
    bundle = create_app(auth_settings=settings)
    yield bundle
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="session")
def tcp_app(tcp_app_bundle):
    return tcp_app_bundle[0]


@pytest.fixture(scope="session")
def tcp_client(tcp_app):
    return tcp_app.server.test_client()


@pytest.fixture(scope="session")
def tcp_layout_text(tcp_app_bundle) -> str:
    app, _cfg, state, _auth, _holder = tcp_app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    return str(app.layout)


@pytest.fixture(scope="session")
def tcp_ts_v2_module():
    """Single imported tcp_ts_v2 module for shell/import-isolation tests."""
    import tcp_ts_v2

    return tcp_ts_v2
