"""GET /api/display-rows/{program}: bottom-table data source.

Display rows merge manual daily_rows with backfilled historical_rows so the
tables show the latest known values — WITHOUT ever becoming Export All
candidates. GET /api/rows stays manual-only; export reads daily_rows only.
"""

from __future__ import annotations

from tests.conftest import VALID_ROWS


def _seed_history(client, rows):
    resp = client.post("/api/backfill/import", json={"dry_run": False, "rows": rows})
    assert resp.status_code == 200, resp.text
    assert resp.json()["row_error_count"] == 0


def _tkp_history(n=10, start_day=1):
    rows = []
    for i in range(n):
        rows.append(
            {
                "program": "TKP",
                "date": f"2026-06-{start_day + i:02d}",
                "stonex_nlv": 150000.0 + i * 10,
                "plus500_nlv": 0.0,
                "cash_transfer": 0.0,
                "source": "tkp_state_json",
                "source_detail": "daily_returns_secret_state.json (StoneX performance, Plus500 informational)",
            }
        )
    return rows


def test_display_rows_show_tkp_plus500_when_backfilled(backfill_client):
    rows = [
        {
            "program": "TKP",
            "date": "2026-06-01",
            "stonex_nlv": 130200.0,
            "plus500_nlv": 20000.0,
            "cash_transfer": 0.0,
            "source": "tkp_state_json",
            "source_detail": "StoneX authoritative",
        }
    ]
    _seed_history(backfill_client, rows)
    top = backfill_client.get("/api/display-rows/TKP").json()["rows"][0]
    assert top["plus500_nlv"] == 20000.0
    assert top["stonex_nlv"] == 130200.0
    assert top["value"] == 130200.0  # StoneX-only performance balance


def test_display_rows_include_latest_history_newest_first(backfill_client):
    _seed_history(backfill_client, _tkp_history(10))
    body = backfill_client.get("/api/display-rows/TKP").json()
    assert body["count"] == 7  # default limit
    dates = [r["date"] for r in body["rows"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2026-06-10"  # newest of the 10 seeded
    assert all(r["source_label"] == "Backfilled" for r in body["rows"])
    assert all(r["row_source"] == "tkp_state_json" for r in body["rows"])
    assert "StoneX" in body["rows"][0]["source_detail"]
    assert body["rows"][0]["value"] == 150090.0  # stonex_nlv only
    assert "historical backfill" in body["display_note"]
    assert "manually entered" in body["export_note"]


def test_display_rows_limit_respected(backfill_client):
    _seed_history(backfill_client, _tkp_history(10))
    body = backfill_client.get("/api/display-rows/TKP?limit=3").json()
    assert [r["date"] for r in body["rows"]] == ["2026-06-10", "2026-06-09", "2026-06-08"]


def test_manual_row_wins_and_is_badged_manual(backfill_client):
    _seed_history(backfill_client, _tkp_history(3))
    manual = dict(VALID_ROWS["TKP"], date="2026-06-03")  # collides with history
    assert backfill_client.post("/api/rows/TKP", json=manual).status_code == 200
    body = backfill_client.get("/api/display-rows/TKP").json()
    top = body["rows"][0]
    assert top["date"] == "2026-06-03"
    assert top["source_label"] == "Manual"
    assert top["value"] == 105000.0  # manual StoneX only (105000 + 20000 stored, chart uses StoneX)
    assert [r["source_label"] for r in body["rows"]] == ["Manual", "Backfilled", "Backfilled"]


def test_rows_endpoint_stays_manual_only(backfill_client):
    _seed_history(backfill_client, _tkp_history(5))
    assert backfill_client.get("/api/rows/TKP?limit=365").json()["count"] == 0
    manual = dict(VALID_ROWS["TKP"], date="2026-07-01")
    backfill_client.post("/api/rows/TKP", json=manual)
    body = backfill_client.get("/api/rows/TKP?limit=365").json()
    assert body["count"] == 1
    assert body["rows"][0]["date"] == "2026-07-01"


def test_display_rows_never_reach_export(backfill_client):
    _seed_history(backfill_client, _tkp_history(7))
    export = backfill_client.post("/api/export/all").json()
    assert export["total_rows"] == 0
    assert export["dry_run"] is True
    assert export["external_calls_made"] == 0


def test_agm_fee_shown_only_for_manual_rows(backfill_client):
    _seed_history(
        backfill_client,
        [{
            "program": "AGM", "date": "2026-06-01", "tradestation_nlv": 45000.0,
            "cash_transfer": 0.0, "source": "agm_daily_balances_csv",
        }],
    )
    manual = dict(VALID_ROWS["AGM"], date="2026-06-02")  # fee 125.50
    backfill_client.post("/api/rows/AGM", json=manual)
    body = backfill_client.get("/api/display-rows/AGM").json()
    by_date = {r["date"]: r for r in body["rows"]}
    assert by_date["2026-06-02"]["fee"] == 125.50  # manual fee is real
    assert by_date["2026-06-01"]["fee"] is None  # historical fee never invented
    assert by_date["2026-06-01"]["value"] == 45000.0


def test_yq_empty_state_is_explicit(backfill_client):
    body = backfill_client.get("/api/display-rows/YQ").json()
    assert body["count"] == 0
    assert body["empty_reason"] == "No daily Y&Q source available."
    # ...but a manual Y&Q row, if Glenn ever adds one, IS shown (no fake data,
    # no suppression of real entries).
    backfill_client.post("/api/rows/YQ", json=dict(VALID_ROWS["YQ"], date="2026-07-01"))
    body = backfill_client.get("/api/display-rows/YQ").json()
    assert body["count"] == 1
    assert "empty_reason" not in body
    assert body["rows"][0]["source_label"] == "Manual"


def test_display_rows_readable_without_backfill_flag(sandbox_client):
    """The display endpoint is a UI read of the uploader's own DB — it must
    work with BACKFILL_ENABLED off (like the performance graph), while the
    backfill import/preview/status/clear endpoints stay gated."""
    resp = sandbox_client.get("/api/display-rows/TKP")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert sandbox_client.get("/api/backfill/status").status_code == 403


def test_unknown_program_is_404(backfill_client):
    assert backfill_client.get("/api/display-rows/NOPE").status_code == 404
