"""Export safety (dry-run by default) and auth behavior."""

from __future__ import annotations

from tests.conftest import VALID_ROWS


def test_export_all_is_dry_run_by_default(sandbox_client):
    sandbox_client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
    r = sandbox_client.post("/api/export/all")
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert body["export_enabled"] is False
    assert body["external_calls_made"] == 0
    assert body["transport_implemented"] is False
    # The unexported TKP row shows up in the preview.
    assert body["programs"]["TKP"]["row_count"] == 1
    assert body["total_rows"] == 1


def test_export_stays_safe_even_when_enabled(prod_export_enabled_client):
    c = prod_export_enabled_client
    hdr = {"X-API-Token": "test-secret-token"}
    c.post("/api/rows/AGM", json=VALID_ROWS["AGM"], headers=hdr)
    r = c.post("/api/export/all", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    # Enabled -> not a dry run, but STILL no external calls are made.
    assert body["dry_run"] is False
    assert body["export_enabled"] is True
    assert body["external_calls_made"] == 0
    assert body["transport_implemented"] is False


def test_sandbox_allows_mutations_without_token(sandbox_client):
    r = sandbox_client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
    assert r.status_code == 200


def test_production_requires_token_for_mutations(prod_client):
    # No token -> 401.
    r = prod_client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
    assert r.status_code == 401

    # Wrong token -> 401.
    r = prod_client.post(
        "/api/rows/TCP", json=VALID_ROWS["TCP"], headers={"X-API-Token": "nope"}
    )
    assert r.status_code == 401

    # Correct token -> 200.
    r = prod_client.post(
        "/api/rows/TCP",
        json=VALID_ROWS["TCP"],
        headers={"X-API-Token": "test-secret-token"},
    )
    assert r.status_code == 200


def test_production_bearer_header_also_works(prod_client):
    r = prod_client.post(
        "/api/rows/TCP",
        json=VALID_ROWS["TCP"],
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert r.status_code == 200


def test_reads_are_open_in_production(prod_client):
    # GETs do not require a token.
    assert prod_client.get("/health").status_code == 200
    assert prod_client.get("/api/programs").status_code == 200


def test_audit_trail_records_actions(sandbox_client):
    sandbox_client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
    sandbox_client.delete("/api/rows/YQ/last")
    sandbox_client.post("/api/export/all")
    events = sandbox_client.get("/api/audit").json()["events"]
    actions = {e["action"] for e in events}
    assert {"create", "delete", "export_dry_run"}.issubset(actions)
