"""Test fixtures.

Each client gets a fresh, isolated SQLite file under ``tests/_tmp/`` (avoids the
machine-specific ``%TEMP%`` pytest-tmp_path PermissionError noted for this box,
and keeps test data well away from any real/production database).
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Make the backend package importable when pytest is run from the backend dir.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

_TMP = Path(__file__).resolve().parent / "_tmp"


def _fresh_db_path() -> Path:
    _TMP.mkdir(exist_ok=True)
    return _TMP / f"test_{uuid4().hex}.db"


def _make_client(**overrides) -> TestClient:
    dbfile = _fresh_db_path()
    # _env_file=None -> ignore any real .env; explicit kwargs override os env.
    settings = Settings(
        _env_file=None,
        database_path=str(dbfile),
        **overrides,
    )
    client = TestClient(create_app(settings))
    client._uploader_db_path = dbfile  # type: ignore[attr-defined]
    return client


@pytest.fixture
def sandbox_client():
    """Sandbox client: relaxed auth, export disabled."""
    client = _make_client(app_env="sandbox", export_enabled=False)
    try:
        yield client
    finally:
        client.close()
        _cleanup(client)


@pytest.fixture
def prod_client():
    """Production client with a known admin token; export disabled."""
    client = _make_client(
        app_env="production",
        export_enabled=False,
        admin_api_token="test-secret-token",
    )
    try:
        yield client
    finally:
        client.close()
        _cleanup(client)


@pytest.fixture
def prod_export_enabled_client():
    """Production client with export ENABLED (still must not call externals)."""
    client = _make_client(
        app_env="production",
        export_enabled=True,
        admin_api_token="test-secret-token",
    )
    try:
        yield client
    finally:
        client.close()
        _cleanup(client)


def _cleanup(client: TestClient) -> None:
    path = getattr(client, "_uploader_db_path", None)
    if path is not None:
        try:
            Path(path).unlink()
        except OSError:
            pass


# Convenience: valid sample rows per program.
VALID_ROWS = {
    "TKP": {"date": "2026-07-01", "stonex_nlv": 105000, "plus500_nlv": 20000, "cash_transfer": 0},
    "TCP": {"date": "2026-07-01", "stonex_nlv": 98000, "cash_transfer": 500},
    "AGM": {"date": "2026-07-01", "tradestation_nlv": 30000, "cash_transfer": 0, "fee": 125.50},
    "YQ": {"date": "2026-07-01", "stonex_nlv": 60000, "cash_transfer": 0},
}
