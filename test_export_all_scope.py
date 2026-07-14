"""Export All scope: unexported manual daily_rows only, globally across programs.

Historical/display rows live in downstream TKP/TCP/AGM apps — not in the
uploader SQLite schema — so they are excluded by construction (only daily_rows
is queried). Y&Q rows may appear in the uploader preview when unexported but
are always skipped by downstream export (see test_downstream_export.py).
"""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import VALID_ROWS, _make_client

# Base date for sequential manual rows (one program/card).
_BASE = date(2026, 7, 1)


def _tkp_row(day_offset: int, **overrides) -> dict:
    d = _BASE + timedelta(days=day_offset)
    row = {
        "date": d.isoformat(),
        "stonex_nlv": 100_000 + day_offset * 100,
        "plus500_nlv": 20_000,
        "cash_transfer": 0,
    }
    row.update(overrides)
    return row


def _agm_row(day_offset: int, **overrides) -> dict:
    d = _BASE + timedelta(days=day_offset)
    row = {
        "date": d.isoformat(),
        "tradestation_nlv": 30_000 + day_offset * 50,
        "cash_transfer": 0,
        "fee": 125.50,
    }
    row.update(overrides)
    return row


def _post_rows(client, program: str, rows: list[dict]) -> None:
    for row in rows:
        r = client.post(f"/api/rows/{program}", json=row)
        assert r.status_code == 200, r.text


def _mark_exported(client, program: str, row_date: str) -> None:
    client.app.state.db.mark_exported(program, row_date)


def _export_all(client) -> dict:
    r = client.post("/api/export/all")
    assert r.status_code == 200, r.text
    return r.json()


def _program_dates(body: dict, program: str) -> list[str]:
    return [row["date"] for row in body["programs"][program]["rows"]]


def test_get_unexported_rows_query_is_exported_false_only():
    """Confirm the storage-layer selection matches the contract."""
    client = _make_client(app_env="sandbox", export_enabled=False)
    try:
        db = client.app.state.db
        _post_rows(client, "TKP", [_tkp_row(0), _tkp_row(1)])
        _mark_exported(client, "TKP", _tkp_row(0)["date"])

        unexported = db.get_unexported_rows()
        dates = {r["date"] for r in unexported if r["program"] == "TKP"}
        assert dates == {_tkp_row(1)["date"]}
        assert all(r["exported"] == 0 for r in unexported)
    finally:
        client.close()


def test_export_all_five_tkp_rows_single_card_excludes_exported_and_other_programs():
    """5 unexported TKP rows in one program; no other pending manual rows.

  Setup also seeds already-exported manual rows (TKP/TCP/AGM) to prove they
  are excluded. Historical/display rows are not in uploader daily_rows.
    """
    client = _make_client(app_env="sandbox", export_enabled=False)
    try:
        db = client.app.state.db

        # Five unexported manual rows — all TKP (one program/card).
        tkp_pending = [_tkp_row(i) for i in range(5)]
        _post_rows(client, "TKP", tkp_pending)

        # Already-exported manual rows (must not re-export).
        _post_rows(client, "TKP", [_tkp_row(10)])
        _mark_exported(client, "TKP", _tkp_row(10)["date"])
        _post_rows(client, "TCP", [VALID_ROWS["TCP"]])
        _mark_exported(client, "TCP", VALID_ROWS["TCP"]["date"])
        _post_rows(client, "AGM", [VALID_ROWS["AGM"]])
        _mark_exported(client, "AGM", VALID_ROWS["AGM"]["date"])

        # Sanity: uploader DB holds manual rows only; no historical/display tables.
        with db.connect() as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "daily_rows" in tables
        assert "historical_rows" not in tables
        assert "display_rows" not in tables

        body = _export_all(client)

        assert body["dry_run"] is True
        assert body["external_calls_made"] == 0
        assert body["total_rows"] == 5

        assert body["programs"]["TKP"]["row_count"] == 5
        assert set(_program_dates(body, "TKP")) == {r["date"] for r in tkp_pending}

        assert body["programs"]["TCP"]["row_count"] == 0
        assert body["programs"]["AGM"]["row_count"] == 0
        assert body["programs"]["YQ"]["row_count"] == 0

        # Exported manual rows stay out of the batch.
        exported_tkp_date = _tkp_row(10)["date"]
        assert exported_tkp_date not in _program_dates(body, "TKP")

        # Rows remain unexported after dry-run preview.
        for row in client.get("/api/rows/TKP?limit=20").json()["rows"]:
            if row["date"] in {r["date"] for r in tkp_pending}:
                assert row["exported"] is False
            if row["date"] == exported_tkp_date:
                assert row["exported"] is True
    finally:
        client.close()


def test_export_all_spans_all_programs_with_unexported_rows():
    """5 TKP + 2 AGM unexported manual rows -> 7 total (global, not card-scoped)."""
    client = _make_client(app_env="sandbox", export_enabled=False)
    try:
        tkp_pending = [_tkp_row(i) for i in range(5)]
        agm_pending = [_agm_row(i) for i in range(2)]
        _post_rows(client, "TKP", tkp_pending)
        _post_rows(client, "AGM", agm_pending)

        body = _export_all(client)

        assert body["total_rows"] == 7
        assert body["programs"]["TKP"]["row_count"] == 5
        assert body["programs"]["AGM"]["row_count"] == 2
        assert body["programs"]["TCP"]["row_count"] == 0
        assert body["programs"]["YQ"]["row_count"] == 0
        assert set(_program_dates(body, "TKP")) == {r["date"] for r in tkp_pending}
        assert set(_program_dates(body, "AGM")) == {r["date"] for r in agm_pending}
    finally:
        client.close()


def test_export_all_yq_skipped_in_downstream_dry_run():
    """Y&Q unexported rows appear in preview but downstream always skips them."""
    client = _make_client(
        app_env="sandbox",
        export_enabled=False,
        export_downstream_enabled=True,
        export_dry_run=True,
    )
    try:
        _post_rows(client, "TKP", [_tkp_row(0)])
        _post_rows(client, "YQ", [VALID_ROWS["YQ"]])

        body = _export_all(client)

        # Preview includes all unexported daily_rows (TKP + YQ).
        assert body["total_rows"] == 2
        assert body["programs"]["YQ"]["row_count"] == 1

        downstream = body["downstream"]
        assert downstream["dry_run"] is True
        assert downstream["results"]["YQ"]["status"] == "skipped"
        assert (
            downstream["results"]["YQ"]["date_results"][0]["reason"]
            == "destination not configured"
        )
        # YQ never marked exported when skipped.
        yq_rows = client.get("/api/rows/YQ").json()["rows"]
        assert yq_rows[0]["exported"] is False
    finally:
        client.close()
