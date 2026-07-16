"""Authoritative export-mode status — health, export preview, and UI banners."""

from __future__ import annotations

from app.config import Settings
from app.export_status import (
    build_export_status,
    export_batch_message,
    export_mode_banner_message,
)


def _settings(**overrides) -> Settings:
    return Settings(
        database_path=":memory:",
        app_env="sandbox",
        **overrides,
    )


def test_live_production_writes_enabled_despite_sandbox_app_env():
    status = build_export_status(
        _settings(
            export_downstream_enabled=True,
            export_dry_run=False,
            export_target_env="production",
            export_enabled=False,
        )
    )
    assert status["export_mode"] == "live"
    assert status["real_writes_enabled"] is True
    assert status["transport_implemented"] is True
    assert status["dry_run"] is False
    assert status["app_env"] == "sandbox"
    banner = export_mode_banner_message(status)
    assert "Live export enabled" in banner
    assert "DRY RUN" not in banner.upper()


def test_downstream_dry_run_mode():
    status = build_export_status(
        _settings(
            export_downstream_enabled=True,
            export_dry_run=True,
            export_target_env="production",
        )
    )
    assert status["export_mode"] == "dry_run"
    assert status["real_writes_enabled"] is False
    assert "Dry run" in export_mode_banner_message(status)


def test_downstream_disabled_mode():
    status = build_export_status(_settings(export_downstream_enabled=False))
    assert status["export_mode"] == "disabled"
    assert status["real_writes_enabled"] is False
    assert "disabled" in export_mode_banner_message(status).lower()


def test_health_and_export_status_share_fields(sandbox_client):
    health = sandbox_client.get("/health").json()
    endpoint = sandbox_client.get("/api/export/status").json()
    for key in (
        "downstream_export_enabled",
        "dry_run",
        "target_environment",
        "real_writes_enabled",
        "transport_implemented",
        "export_mode",
    ):
        assert health["export"][key] == endpoint[key]
    assert health["export_enabled"] == health["export"]["real_writes_enabled"]
    assert endpoint["banner_message"] == health["export_mode_banner"]


def test_export_batch_live_message_not_dry_run():
    status = build_export_status(
        _settings(
            export_downstream_enabled=True,
            export_dry_run=False,
            export_target_env="production",
        )
    )
    msg = export_batch_message(status, total_rows=1, downstream_attempted=True)
    assert "Live export" in msg
    assert "DRY RUN" not in msg.upper()


def test_legacy_export_enabled_does_not_force_live_mode():
    status = build_export_status(
        _settings(export_enabled=True, export_downstream_enabled=False)
    )
    assert status["export_mode"] == "disabled"
    assert status["real_writes_enabled"] is False


def test_export_all_live_fields_match_config():
    from tests.conftest import VALID_ROWS
    from tests.test_downstream_export import _downstream_client

    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        tkp_ingest_url="http://127.0.0.1:1/ingest",
        downstream_ingest_token="x" * 32,
    )
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        body = client.post("/api/export/all").json()
        assert body["export_mode"] == "live"
        assert body["real_writes_enabled"] is True
        assert body["export_enabled"] is True
        assert body["dry_run"] is False
        assert "DRY RUN" not in body["message"].upper()
        assert body["export_dry_run"] is False
        assert body["target_environment"] == "production"
    finally:
        client.close()
