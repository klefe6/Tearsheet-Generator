"""Single-host frontend static serving."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.main import create_app


def _make_singlehost_client(tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text(
        "<!doctype html><html><body>Uploader UI</body></html>",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        database_path=str(tmp_path / "test.db"),
        serve_frontend=True,
        frontend_static_dir=str(static),
        benchmark_cache_dir=str(tmp_path / "bench"),
    )
    from fastapi.testclient import TestClient

    return TestClient(create_app(settings))


def test_spa_index_served(tmp_path):
    client = _make_singlehost_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "Uploader UI" in r.text


def test_api_still_available_when_serving_frontend(tmp_path):
    client = _make_singlehost_client(tmp_path)
    assert client.get("/health").status_code == 200
    assert client.get("/api/programs").status_code == 200


def test_spa_does_not_shadow_api(tmp_path):
    client = _make_singlehost_client(tmp_path)
    assert client.get("/api/performance?mode=combined").status_code == 200
