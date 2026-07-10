"""SQLite schema verification on startup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import Database, SchemaError


def test_verify_schema_passes_on_fresh_db(tmp_path):
    db_path = tmp_path / "fresh.db"
    db = Database(str(db_path))
    db.verify_schema()  # no raise


def test_verify_schema_fails_on_outdated_daily_rows(tmp_path):
    db_path = tmp_path / "stale.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE daily_rows (id INTEGER PRIMARY KEY, program TEXT, date TEXT)"
    )
    conn.commit()
    conn.close()

    db = Database(str(db_path))
    with pytest.raises(SchemaError, match="outdated schema"):
        db.verify_schema()


def test_startup_fails_on_outdated_schema(tmp_path):
    db_path = tmp_path / "stale.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE daily_rows (id INTEGER PRIMARY KEY, program TEXT, date TEXT)"
    )
    conn.commit()
    conn.close()

    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(_env_file=None, database_path=str(db_path))
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="reset_local_db"):
        with TestClient(app):
            pass
