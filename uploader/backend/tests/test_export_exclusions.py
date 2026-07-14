"""Export exclusion: keep historical interior-date rows visible but never Export All."""

from __future__ import annotations

from app.db import EXCLUSION_REASON_INTERIOR_DATE, Database


TOKEN = "test-admin-token"
REASON = EXCLUSION_REASON_INTERIOR_DATE


def _admin_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def _client_with_admin(tmp_path, monkeypatch=None):
    from tests.conftest import _make_client

    return _make_client(
        app_env="sandbox",
        export_enabled=False,
        export_downstream_enabled=False,
        admin_api_token=TOKEN,
    )


def _insert_tcp(client, date: str, nlv: float):
    r = client.post(
        "/api/rows/TCP",
        json={"date": date, "stonex_nlv": nlv, "cash_transfer": 0.0},
    )
    assert r.status_code == 200, r.text
    return r.json()["row"]


def _insert_agm(client, date: str, nlv: float):
    r = client.post(
        "/api/rows/AGM",
        json={
            "date": date,
            "tradestation_nlv": nlv,
            "cash_transfer": 0.0,
            "fee": 0.0,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["row"]


def test_excluded_rows_not_selected_by_export_all(sandbox_client):
    # Reconfigure with admin token for exclusion endpoint.
    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    from tests.conftest import _fresh_db_path, _TMP
    from pathlib import Path
    from uuid import uuid4
    from app.benchmark_store import BenchmarkStore
    from app.benchmarks import configure_store
    from tests.benchmark_fixtures import seed_standard_benchmark_window
    from datetime import date

    dbfile = _fresh_db_path()
    cache_dir = _TMP / f"bench_{uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    seed_standard_benchmark_window(cache_dir, date(2026, 7, 6))
    settings = Settings(
        _env_file=None,
        database_path=str(dbfile),
        benchmark_cache_dir=str(cache_dir),
        benchmark_cache_only=True,
        app_env="sandbox",
        export_enabled=False,
        export_downstream_enabled=False,
        admin_api_token=TOKEN,
    )
    app = create_app(settings)
    configure_store(
        BenchmarkStore(
            cache_dir=cache_dir,
            cache_only=True,
            allow_fixture=True,
            fetcher=None,
        )
    )
    client = TestClient(app)

    tcp_old = _insert_tcp(client, "2026-07-08", 46073.2)
    tcp_tip = _insert_tcp(client, "2026-07-14", 47000.05)
    agm_old = _insert_agm(client, "2026-07-07", 45372.2)
    agm_tip = _insert_agm(client, "2026-07-13", 44709.5)

    # Mark tips exported without going through downstream.
    db = Database(str(dbfile))
    db.mark_exported("TCP", "2026-07-14", batch_id=1)
    db.mark_exported("AGM", "2026-07-13", batch_id=1)

    excl = client.post(
        "/api/export/exclusions",
        headers=_admin_headers(),
        json={
            "program": "TCP",
            "source_row_id": tcp_old["id"],
            "reason": REASON,
        },
    )
    assert excl.status_code == 200, excl.text
    excl2 = client.post(
        "/api/export/exclusions",
        headers=_admin_headers(),
        json={
            "program": "AGM",
            "source_row_id": agm_old["id"],
            "reason": REASON,
        },
    )
    assert excl2.status_code == 200, excl2.text

    # Excluded rows remain stored, exported=false, state=excluded.
    tcp_rows = client.get("/api/rows/TCP?limit=20").json()["rows"]
    by_date = {r["date"]: r for r in tcp_rows}
    assert by_date["2026-07-08"]["exported"] is False
    assert by_date["2026-07-08"]["export_state"] == "excluded"
    assert by_date["2026-07-08"]["excluded_reason"] == REASON
    assert by_date["2026-07-14"]["exported"] is True
    assert by_date["2026-07-14"]["export_state"] == "exported"

    agm_rows = client.get("/api/rows/AGM?limit=20").json()["rows"]
    agm_by = {r["date"]: r for r in agm_rows}
    assert agm_by["2026-07-07"]["export_state"] == "excluded"
    assert agm_by["2026-07-13"]["export_state"] == "exported"

    # New tip dates after the successful tips remain eligible.
    new_tcp = _insert_tcp(client, "2026-07-15", 48000.0)
    new_agm = _insert_agm(client, "2026-07-14", 45000.0)
    assert new_tcp["export_state"] == "eligible"
    assert new_agm["export_state"] == "eligible"

    counts = client.get("/api/export/eligibility").json()
    assert counts["excluded"] == 2
    assert counts["exported"] == 2
    assert counts["eligible"] == 2  # 07-15 TCP + 07-14 AGM

    preview = client.post("/api/export/all")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_rows"] == 2
    assert body["eligible_count"] == 2
    assert body["excluded_count"] == 2
    assert body["exported_count"] == 2
    tcp_payload_dates = [r["date"] for r in body["programs"]["TCP"]["rows"]]
    agm_payload_dates = [r["date"] for r in body["programs"]["AGM"]["rows"]]
    assert tcp_payload_dates == ["2026-07-15"]
    assert agm_payload_dates == ["2026-07-14"]
    assert "2026-07-08" not in tcp_payload_dates
    assert "2026-07-07" not in agm_payload_dates
    # No excluded row sneaks into the export payload.
    for prog in ("TKP", "TCP", "AGM", "YQ"):
        for row in body["programs"][prog]["rows"]:
            assert row.get("export_state") != "excluded"
            assert row.get("excluded") is not True

    # Removing exclusion restores eligibility.
    restored = client.delete(
        f"/api/export/exclusions/TCP/{tcp_old['id']}",
        headers=_admin_headers(),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["row"]["export_state"] == "eligible"

    after = client.post("/api/export/all").json()
    tcp_dates = [r["date"] for r in after["programs"]["TCP"]["rows"]]
    assert "2026-07-08" in tcp_dates
    assert after["excluded_count"] == 1

    client.close()


def test_exclusion_requires_admin_token(sandbox_client):
    row = sandbox_client.post(
        "/api/rows/TCP",
        json={"date": "2026-07-08", "stonex_nlv": 1.0, "cash_transfer": 0.0},
    ).json()["row"]
    # sandbox_client has no admin token configured for require_admin_actor.
    r = sandbox_client.post(
        "/api/export/exclusions",
        json={
            "program": "TCP",
            "source_row_id": row["id"],
            "reason": REASON,
        },
    )
    # Without ADMIN_API_TOKEN on this fixture → 503 fail-closed, or 401 if set.
    assert r.status_code in (401, 503)
