"""Downstream export (TKP/TCP/AGM sandbox destinations). See
docs/downstream_export_contract.md for the contract these tests verify."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from tests.conftest import VALID_ROWS, _make_client

_TMP = Path(__file__).resolve().parent / "_tmp"


def _sandbox_dir() -> Path:
    _TMP.mkdir(exist_ok=True)
    return _TMP / f"downstream_{uuid4().hex}"


def _downstream_client(**overrides):
    """Sandbox client with downstream export enabled (not dry-run), writing
    to an isolated temp sandbox dir — never the real data/downstream_sandbox/."""
    d = _sandbox_dir()
    kwargs = {
        "app_env": "sandbox",
        "export_enabled": False,
        "export_downstream_enabled": True,
        "export_dry_run": False,
        "export_target_env": "sandbox",
        "downstream_sandbox_dir": str(d),
    }
    kwargs.update(overrides)
    client = _make_client(**kwargs)
    client._downstream_dir = d  # type: ignore[attr-defined]
    return client


def test_downstream_export_disabled_by_default_leaves_response_unchanged(sandbox_client):
    """The master switch defaults false -> response has no "downstream" key
    at all, i.e. behavior is byte-for-byte what it was before this feature."""
    sandbox_client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
    r = sandbox_client.post("/api/export/all")
    body = r.json()
    assert "downstream" not in body


def test_downstream_export_dry_run_writes_nothing():
    client = _downstream_client(export_dry_run=True)
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        r = client.post("/api/export/all")
        body = r.json()["downstream"]
        assert body["dry_run"] is True
        assert body["results"]["TKP"]["status"] == "dry_run"
        assert not client._downstream_dir.exists()  # nothing written at all
        # Row must NOT be marked exported on a dry run.
        rows = client.get("/api/rows/TKP").json()["rows"]
        assert rows[0]["exported"] is False
    finally:
        client.close()


def test_downstream_export_sandbox_writes_file_and_marks_exported():
    client = _downstream_client()
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        r = client.post("/api/export/all")
        body = r.json()
        downstream = body["downstream"]
        assert downstream["dry_run"] is False
        assert downstream["target_env"] == "sandbox"
        assert downstream["results"]["TKP"]["status"] == "success"

        sandbox_file = client._downstream_dir / "tkp_rows.json"
        assert sandbox_file.exists()
        doc = json.loads(sandbox_file.read_text())
        assert doc["program"] == "TKP"
        row = doc["rows"]["2026-07-01"]
        assert row["stonex_nlv"] == 105000
        assert row["plus500_nlv"] == 20000

        # Row is now marked exported in the uploader's own DB.
        rows = client.get("/api/rows/TKP").json()["rows"]
        assert rows[0]["exported"] is True
    finally:
        client.close()


def test_downstream_export_yq_always_skipped():
    client = _downstream_client()
    try:
        client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
        r = client.post("/api/export/all")
        downstream = r.json()["downstream"]
        assert downstream["results"]["YQ"]["status"] == "skipped"
        date_result = downstream["results"]["YQ"]["date_results"][0]
        assert date_result["reason"] == "destination not configured"
        # Never written to any sandbox file.
        assert not (client._downstream_dir / "yq_rows.json").exists()
        # Never marked exported (stays retry-able forever, matches "not failed").
        rows = client.get("/api/rows/YQ").json()["rows"]
        assert rows[0]["exported"] is False
    finally:
        client.close()


def test_downstream_export_yq_skipped_even_with_include_flag_true():
    """EXPORT_INCLUDE_YQ is forward-compatible only — no destination exists
    yet, so YQ is skipped regardless of this flag (documented in the contract)."""
    client = _downstream_client(export_include_yq=True)
    try:
        client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
        r = client.post("/api/export/all")
        assert r.json()["downstream"]["results"]["YQ"]["status"] == "skipped"
    finally:
        client.close()


def test_downstream_export_is_idempotent_on_reexport():
    """Exporting the same program/date twice upserts in place — never a
    second entry, never a duplicate row in the sandbox file."""
    client = _downstream_client()
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        client.post("/api/export/all")

        # Change the value and re-enter the SAME date -> upsert in uploader DB
        # (exported resets to 0 on any write), then re-export.
        updated = {**VALID_ROWS["TKP"], "stonex_nlv": 999999}
        client.post("/api/rows/TKP", json=updated)
        r2 = client.post("/api/export/all")
        assert r2.json()["downstream"]["results"]["TKP"]["date_results"][0]["date"] == "2026-07-01"

        sandbox_file = client._downstream_dir / "tkp_rows.json"
        doc = json.loads(sandbox_file.read_text())
        assert list(doc["rows"].keys()) == ["2026-07-01"]  # exactly one entry, not two
        assert doc["rows"]["2026-07-01"]["stonex_nlv"] == 999999  # updated in place
    finally:
        client.close()


def test_downstream_export_production_always_fails_by_construction():
    """Selecting target_env=production can never silently succeed — the
    transport simply isn't implemented, regardless of any other flag."""
    client = _downstream_client(export_target_env="production")
    try:
        client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])
        r = client.post("/api/export/all")
        result = r.json()["downstream"]["results"]["AGM"]
        assert result["status"] == "failure"
        assert result["date_results"][0]["downstream_response"]["error_code"] == "transport_not_implemented"
        # A failed row must NOT be marked exported -> stays retry-able.
        rows = client.get("/api/rows/AGM").json()["rows"]
        assert rows[0]["exported"] is False
    finally:
        client.close()


def test_downstream_export_partial_failure_does_not_mark_failed_row_exported():
    """Mixed success/failure within one program batch: only the succeeding
    date is marked exported; the rest stay retry-able. We simulate this by
    exporting once successfully (sandbox), then flipping to production
    (always-fails) for a second date on the same program."""
    client = _downstream_client()
    try:
        client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])  # 2026-07-01
        r1 = client.post("/api/export/all")
        assert r1.json()["downstream"]["results"]["AGM"]["status"] == "success"

        second_row = {**VALID_ROWS["AGM"], "date": "2026-07-02"}
        client.post("/api/rows/AGM", json=second_row)

        # Flip this same client's settings object to production for the next call.
        client.app.state.settings.export_target_env = "production"
        r2 = client.post("/api/export/all")
        result = r2.json()["downstream"]["results"]["AGM"]
        assert result["status"] == "failure"

        rows = {r["date"]: r for r in client.get("/api/rows/AGM").json()["rows"]}
        assert rows["2026-07-01"]["exported"] is True  # untouched by the later failure
        assert rows["2026-07-02"]["exported"] is False  # never marked exported
    finally:
        client.close()


def test_downstream_export_audit_trail_records_every_attempt():
    client = _downstream_client()
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
        client.post("/api/export/all")
        events = client.get("/api/audit").json()["events"]
        actions = {e["action"] for e in events}
        assert "downstream_export_success" in actions
        assert "downstream_export_skipped" in actions
    finally:
        client.close()


def test_downstream_export_agm_fee_field_maps_correctly():
    client = _downstream_client()
    try:
        client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])
        client.post("/api/export/all")
        doc = json.loads((client._downstream_dir / "agm_rows.json").read_text())
        row = doc["rows"]["2026-07-01"]
        assert row["fee"] == 125.50
        assert row["tradestation_nlv"] == 30000
        assert row["cash_transfer"] == 0
    finally:
        client.close()


def test_production_export_disabled_by_default():
    """A plain sandbox_client (downstream feature not even enabled) must
    never touch target_env=production regardless of what's requested —
    there is no request surface for it; the flag is server-side config only."""
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.export_downstream_enabled is False
    assert s.export_dry_run is True
    assert s.export_target_env == "sandbox"
    assert s.export_include_yq is False
