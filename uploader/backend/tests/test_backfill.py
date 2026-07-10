"""Historical backfill: idempotency, precedence, labeling, and safety rails.

Covers the guarantees documented in docs/historical_backfill.md:
  * import is idempotent (re-import => all "unchanged", nothing rewritten)
  * imported rows are labeled with their source and can never claim "manual"
  * Glenn's manual daily_rows always supersede historical rows on a date
  * backfill never touches daily_rows, the export path, or any tearsheet file
  * production refuses backfill entirely (403, no flag override)
  * dry-run classifies without writing
  * the extractor script only ever reads its inputs
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from tests.conftest import VALID_ROWS

_TMP = Path(__file__).resolve().parent / "_tmp"

# Mimics the REAL store shapes documented in docs/historical_backfill.md:
# TKP list-of-rows JSON with $-string money; TCP dict envelope with records
# (resolved via TCP_V2_STATE_PATH in .tcp_production.env, never the repo
# seed); AGM TradeStation balances CSV with metadata preamble.
_TKP_STATE = [
    {"_row_id": 0, "#Day": "1", "Date": "2023-04-10", "Plus500": "",
     "StoneX": "$100,000.00", "Deposit": "", "NAV": "$150,000.00"},
    {"_row_id": 1, "#Day": "2", "Date": "2023-04-11", "Plus500": "$20,000.00",
     "StoneX": "$100,250.00", "Deposit": "$20,000.00", "NAV": "$150,200.00"},
]

_TCP_STATE = {
    "schema_version": 1,
    "app": "tcp",
    "revision": 14,
    "source": "website_edit",
    "records": [
        {"#": 1.0, "Date": "2026-01-20", "NLV": 24996.76, "Cash Balance": 24996.76,
         "Cash Transfers": None, "Inc. Fee": 0.0},
        {"#": 2.0, "Date": "2026-01-21", "NLV": 25400.00, "Cash Balance": 25400.00,
         "Cash Transfers": 500.0, "Inc. Fee": 0.0},
    ],
}

_AGM_CSV_NEW = (
    "Account: 210TGG51\n"
    "Report: Historical Balances\n"
    "\n"
    "Date,Net Worth,Cash Balance,Unrealized P/L,Securities on Deposit,"
    "Initial Margin Req.,Maint Margin Req.,Buying Power/Margin Deficit\n"
    '10/20/2025,"$30,000.00 ","$30,000.00 ","$0.00 ","$0.00 ","$0.00 ","$0.00 ","$30,000.00 "\n'
    '10/21/2025,"$30,125.50 ","$30,125.50 ","$0.00 ","$0.00 ","$0.00 ","$0.00 ","$30,125.50 "\n'
)

# An older, superseded export — the resolver must pick the NEW file above.
_AGM_CSV_OLD = (
    "Account: 210TGG51\n"
    "\n"
    "Date,Net Worth,Cash Balance,Unrealized P/L,Securities on Deposit,"
    "Initial Margin Req.,Maint Margin Req.,Buying Power/Margin Deficit\n"
    '10/20/2025,"$30,000.00 ","$30,000.00 ","$0.00 ","$0.00 ","$0.00 ","$0.00 ","$30,000.00 "\n'
)


@pytest.fixture
def tmp_repo_root():
    """A throwaway fake tearsheet repo root holding realistic store files."""
    root = _TMP / f"repo_{uuid4().hex}"
    balances = root / "Momentum Pacer" / "data" / "daily_balances"
    balances.mkdir(parents=True)

    (root / "daily_returns_secret_state.json").write_text(
        json.dumps(_TKP_STATE), encoding="utf-8"
    )
    tcp_state = root / "appdata_tcp" / "tcp_daily_returns_secret_state.json"
    tcp_state.parent.mkdir(parents=True)
    tcp_state.write_text(json.dumps(_TCP_STATE), encoding="utf-8")
    # Real batch-file syntax, as used by the actual .tcp_production.env.
    (root / ".tcp_production.env").write_text(
        f'set "TCP_V2_STATE_MODE=json_active"\nset "TCP_V2_STATE_PATH={tcp_state}"\n',
        encoding="utf-8",
    )
    # Stale repo-root seed that must NEVER be read by default.
    (root / "tcp_daily_returns_secret_state.json").write_text(
        json.dumps({"revision": 1, "records": []}), encoding="utf-8"
    )
    (balances / "balances_210TGG51_20OCT2025_21OCT2025.csv").write_text(
        _AGM_CSV_NEW, encoding="utf-8"
    )
    (balances / "balances_210TGG51_20OCT2025_20OCT2025.csv").write_text(
        _AGM_CSV_OLD, encoding="utf-8"
    )
    # Evidenced AGM fee withdrawal (parsed textually by the extractor).
    (root / "algominds_fee_payment_evidence.py").write_text(
        'EVIDENCED_FEE_PAYMENTS = (\n'
        '    FeePaymentEvidence(\n'
        '        date=pd.Timestamp("2025-10-21"),\n'
        '        description="Test Incentive Fee",\n'
        '        amount=123.45,\n'
        '    ),\n'
        ')\n',
        encoding="utf-8",
    )

    files = sorted(p for p in root.rglob("*") if p.is_file())
    try:
        yield root, files
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _backfill_rows() -> list[dict]:
    return [
        {
            "program": "TKP",
            "date": "2026-06-29",
            "stonex_nlv": 80000.0,
            "plus500_nlv": 84000.0,
            "cash_transfer": 0.0,
            "source": "tkp_state_json",
            "source_detail": "daily_returns_secret_state.json",
        },
        {
            "program": "TKP",
            "date": "2026-06-30",
            "stonex_nlv": 80500.0,
            "plus500_nlv": 84100.0,
            "cash_transfer": 0.0,
            "source": "tkp_state_json",
            "source_detail": "daily_returns_secret_state.json",
        },
        {
            "program": "AGM",
            "date": "2026-06-30",
            "tradestation_nlv": 45000.0,
            "cash_transfer": 0.0,
            "source": "agm_daily_balances_csv",
            "source_detail": "balances_210TGG51_test.csv",
        },
    ]


def _import(client, rows, dry_run):
    resp = client.post("/api/backfill/import", json={"dry_run": dry_run, "rows": rows})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _table_count(client, table) -> int:
    with sqlite3.connect(client._uploader_db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# --- dry-run and import basics ------------------------------------------------

def test_dry_run_previews_without_writing(sandbox_client):
    body = _import(sandbox_client, _backfill_rows(), dry_run=True)
    assert body["dry_run"] is True
    assert body["programs"]["TKP"]["created"] == 2
    assert body["programs"]["AGM"]["created"] == 1
    assert body["programs"]["TKP"]["first_date"] == "2026-06-29"
    assert body["programs"]["TKP"]["last_date"] == "2026-06-30"
    assert _table_count(sandbox_client, "historical_rows") == 0
    assert _table_count(sandbox_client, "daily_rows") == 0


def test_dry_run_matches_real_import(sandbox_client):
    preview = _import(sandbox_client, _backfill_rows(), dry_run=True)
    real = _import(sandbox_client, _backfill_rows(), dry_run=False)
    for code in ("TKP", "AGM"):
        for key in ("received", "created", "updated", "unchanged"):
            assert preview["programs"][code][key] == real["programs"][code][key]
    assert _table_count(sandbox_client, "historical_rows") == 3


def test_import_is_idempotent(sandbox_client):
    first = _import(sandbox_client, _backfill_rows(), dry_run=False)
    assert first["programs"]["TKP"]["created"] == 2
    second = _import(sandbox_client, _backfill_rows(), dry_run=False)
    assert second["programs"]["TKP"]["created"] == 0
    assert second["programs"]["TKP"]["updated"] == 0
    assert second["programs"]["TKP"]["unchanged"] == 2
    assert second["programs"]["AGM"]["unchanged"] == 1
    assert _table_count(sandbox_client, "historical_rows") == 3


def test_reimport_with_changed_value_updates_in_place(sandbox_client):
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    rows = _backfill_rows()
    rows[0]["stonex_nlv"] = 81234.0
    body = _import(sandbox_client, rows, dry_run=False)
    assert body["programs"]["TKP"]["updated"] == 1
    assert body["programs"]["TKP"]["unchanged"] == 1
    assert _table_count(sandbox_client, "historical_rows") == 3  # upsert, no dupes


# --- labeling -------------------------------------------------------------------

def test_imported_rows_carry_source_labels(sandbox_client):
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    with sqlite3.connect(sandbox_client._uploader_db_path) as conn:
        conn.row_factory = sqlite3.Row
        stored = conn.execute(
            "SELECT source, source_detail FROM historical_rows WHERE program='TKP'"
        ).fetchall()
    assert {r["source"] for r in stored} == {"tkp_state_json"}
    assert all(r["source_detail"] == "daily_returns_secret_state.json" for r in stored)

    status = sandbox_client.get("/api/backfill/status").json()
    assert status["programs"]["TKP"]["sources"] == {"tkp_state_json": 2}
    assert status["programs"]["AGM"]["sources"] == {"agm_daily_balances_csv": 1}


def test_manual_source_label_is_rejected(sandbox_client):
    rows = _backfill_rows()[:1]
    rows[0]["source"] = "manual"
    body = _import(sandbox_client, rows, dry_run=False)
    assert body["total_rows_accepted"] == 0
    assert body["row_error_count"] == 1
    assert "reserved" in body["row_errors"][0]["errors"]["source"]


def test_missing_source_label_is_rejected(sandbox_client):
    rows = _backfill_rows()[:1]
    del rows[0]["source"]
    body = _import(sandbox_client, rows, dry_run=False)
    assert body["total_rows_accepted"] == 0
    assert body["row_error_count"] == 1


# --- precedence: manual entries supersede imported history ----------------------

def test_manual_row_supersedes_imported_row_in_performance(sandbox_client):
    # Manual entry and historical row on the SAME date with different values.
    manual = dict(VALID_ROWS["TKP"], date="2026-06-30")
    assert sandbox_client.post("/api/rows/TKP", json=manual).status_code == 200
    body = _import(sandbox_client, _backfill_rows(), dry_run=False)
    assert body["programs"]["TKP"]["overridden_by_manual"] == 1

    perf = sandbox_client.get("/api/performance?mode=program&program=TKP").json()
    points = perf["points"]["TKP"]
    # 2026-06-29 from backfill + 2026-06-30 from the manual entry (not both).
    assert [p["x"] for p in points] == ["2026-06-29", "2026-06-30"]
    series = perf["series"][0]
    assert series["point_count"] == 2
    assert series["backfilled_point_count"] == 1
    assert series["manual_point_count"] == 1
    # The 06-30 anchor must be the MANUAL value (125,000 = 105k+20k), which
    # differs from the imported 164,600 — verify via the normalized level:
    # base 100k at 06-29 (164k raw), manual 125k on 06-30 => big drop, not ~flat.
    assert points[1]["y"] < points[0]["y"]


def test_glenn_rows_endpoint_shows_manual_entries_only(sandbox_client):
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    rows = sandbox_client.get("/api/rows/TKP").json()
    assert rows["count"] == 0  # backfilled history never appears in the entry table


# --- performance provenance ------------------------------------------------------

def test_program_data_source_flips_only_with_backfill(sandbox_client):
    manual = dict(VALID_ROWS["TKP"], date="2026-07-01")
    sandbox_client.post("/api/rows/TKP", json=manual)
    perf = sandbox_client.get("/api/performance").json()
    assert perf["program_data_source"] == "uploader_daily_rows"

    _import(sandbox_client, _backfill_rows(), dry_run=False)
    perf = sandbox_client.get("/api/performance").json()
    assert perf["program_data_source"] == "uploader_daily_rows+tearsheet_backfill"

    # Clearing the backfill reverts the label (reversibility).
    resp = sandbox_client.delete("/api/backfill")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 3
    perf = sandbox_client.get("/api/performance").json()
    assert perf["program_data_source"] == "uploader_daily_rows"


def test_clear_backfill_never_touches_manual_rows(sandbox_client):
    manual = dict(VALID_ROWS["TKP"], date="2026-07-01")
    sandbox_client.post("/api/rows/TKP", json=manual)
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    sandbox_client.delete("/api/backfill")
    assert _table_count(sandbox_client, "historical_rows") == 0
    assert _table_count(sandbox_client, "daily_rows") == 1


# --- export isolation -------------------------------------------------------------

def test_backfilled_rows_are_never_exported(sandbox_client):
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    export = sandbox_client.post("/api/export/all").json()
    assert export["total_rows"] == 0  # historical rows are invisible to export
    assert export["external_calls_made"] == 0
    assert "downstream" not in export  # downstream flag untouched/off by default


def test_import_does_not_mark_or_reset_export_state(sandbox_client):
    manual = dict(VALID_ROWS["TKP"], date="2026-07-01")
    sandbox_client.post("/api/rows/TKP", json=manual)
    sandbox_client.post("/api/export/all")  # dry-run preview of the manual row
    before = sandbox_client.get("/api/rows/TKP").json()["rows"][0]["exported"]
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    after = sandbox_client.get("/api/rows/TKP").json()["rows"][0]["exported"]
    assert before == after  # backfill neither exports nor re-flags manual rows


# --- production refusal ------------------------------------------------------------

def test_production_refuses_backfill_import(prod_client):
    headers = {"Authorization": "Bearer test-secret-token"}
    resp = prod_client.post(
        "/api/backfill/import",
        json={"dry_run": True, "rows": _backfill_rows()},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "sandbox-only" in resp.json()["detail"]
    assert _table_count(prod_client, "historical_rows") == 0
    assert _table_count(prod_client, "backfill_batches") == 0


def test_production_refuses_backfill_clear(prod_client):
    headers = {"Authorization": "Bearer test-secret-token"}
    resp = prod_client.delete("/api/backfill", headers=headers)
    assert resp.status_code == 403


# --- validation ----------------------------------------------------------------------

def test_invalid_rows_are_reported_not_imported(sandbox_client):
    rows = _backfill_rows()
    rows.append({"program": "TKP", "date": "not-a-date", "stonex_nlv": 1,
                 "plus500_nlv": 1, "source": "tkp_state_json"})
    rows.append({"program": "NOPE", "date": "2026-06-30", "source": "x"})
    rows.append({"program": "TCP", "date": "2026-06-30", "stonex_nlv": 47000.0,
                 "fee": 12.0, "source": "tcp_state_json"})  # fee is AGM-only
    body = _import(sandbox_client, rows, dry_run=False)
    assert body["total_rows_accepted"] == 3
    assert body["row_error_count"] == 3
    assert _table_count(sandbox_client, "historical_rows") == 3


def test_rows_must_be_a_list(sandbox_client):
    resp = sandbox_client.post("/api/backfill/import", json={"rows": {"a": 1}})
    assert resp.status_code == 422


# --- audit trail -----------------------------------------------------------------------

def test_import_and_dry_run_are_audited_with_batches(sandbox_client):
    _import(sandbox_client, _backfill_rows(), dry_run=True)
    _import(sandbox_client, _backfill_rows(), dry_run=False)
    events = sandbox_client.get("/api/audit").json()["events"]
    actions = [e["action"] for e in events]
    assert "backfill_dry_run" in actions
    assert "backfill_import" in actions
    imported = next(e for e in events if e["action"] == "backfill_import")
    assert imported["detail"]["programs"]["TKP"]["created"] == 2
    assert _table_count(sandbox_client, "backfill_batches") == 2


# --- extractor: parsing + read-only guarantee ---------------------------------------

def _file_hashes(paths: list[Path]) -> dict:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_extractor_parses_fixture_stores_read_only(tmp_repo_root):
    from scripts.extract_tearsheet_history import build_payload, extract_all

    repo_root, files = tmp_repo_root
    before = _file_hashes(files)

    results = extract_all(repo_root, ["TKP", "TCP", "AGM", "YQ"])
    payload = build_payload(results, dry_run=True)

    by_program = {r.program: r for r in results}
    # TKP: $-string parsing, blank Plus500 -> 0.0, Deposit -> cash_transfer.
    tkp = by_program["TKP"].rows
    assert [r["date"] for r in tkp] == ["2023-04-10", "2023-04-11"]
    assert tkp[0]["stonex_nlv"] == 100000.0
    assert tkp[0]["plus500_nlv"] == 0.0  # blank at inception
    assert tkp[1]["plus500_nlv"] == 20000.0
    assert tkp[1]["cash_transfer"] == 20000.0  # Deposit column
    assert all(r["source"] == "tkp_state_json" for r in tkp)

    # TCP: live envelope records, null Cash Transfers -> 0.0.
    tcp = by_program["TCP"].rows
    assert [r["date"] for r in tcp] == ["2026-01-20", "2026-01-21"]
    assert tcp[0]["stonex_nlv"] == 24996.76
    assert tcp[0]["cash_transfer"] == 0.0
    assert tcp[1]["cash_transfer"] == 500.0
    assert "revision" in tcp[0]["source_detail"]

    # AGM: Net Worth -> tradestation_nlv, no fee key emitted, and the
    # evidenced fee withdrawal applied as a negative cash transfer.
    agm = by_program["AGM"].rows
    assert [r["date"] for r in agm] == ["2025-10-20", "2025-10-21"]
    assert agm[0]["tradestation_nlv"] == 30000.0
    assert agm[0]["cash_transfer"] == 0.0
    assert agm[1]["tradestation_nlv"] == 30125.5
    assert agm[1]["cash_transfer"] == -123.45
    assert "fee" not in agm[0]
    # The resolver picked the newest export, not the older overlapping one.
    assert "21OCT2025" in agm[0]["source_detail"]

    # YQ: always skipped with the documented reason.
    assert by_program["YQ"].skipped_reason
    assert not by_program["YQ"].rows

    assert len(payload["rows"]) == 6
    # READ-ONLY: every source file is byte-identical after extraction.
    assert _file_hashes(files) == before


def test_extractor_output_imports_cleanly(sandbox_client, tmp_repo_root):
    from scripts.extract_tearsheet_history import build_payload, extract_all

    repo_root, _files = tmp_repo_root
    payload = build_payload(extract_all(repo_root, ["TKP", "TCP", "AGM"]), dry_run=False)
    body = _import(sandbox_client, payload["rows"], dry_run=False)
    assert body["row_error_count"] == 0
    assert body["programs"]["TKP"]["created"] == 2
    assert body["programs"]["TCP"]["created"] == 2
    assert body["programs"]["AGM"]["created"] == 2
    # And it is idempotent end-to-end.
    again = _import(sandbox_client, payload["rows"], dry_run=False)
    assert again["programs"]["TKP"]["unchanged"] == 2


def test_extractor_synthesizes_unrecorded_plus500_funding(tmp_repo_root):
    """The real store's 2025-03-11 case: Plus500 funded but Deposit blank —
    the extractor must synthesize the cash transfer (and warn) so the funding
    day is not counted as +82% performance. When Deposit DID record the
    movement (the fixture's 2023-04-11 row), nothing is synthesized."""
    from scripts.extract_tearsheet_history import extract_tkp

    repo_root, _files = tmp_repo_root
    state = [
        {"Date": "2025-03-10", "StoneX": "$117,661.58", "Plus500": "", "Deposit": ""},
        {"Date": "2025-03-11", "StoneX": "$114,855.95", "Plus500": "$100,000.00",
         "Deposit": ""},
    ]
    path = repo_root / "tkp_unfunded_case.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    res = extract_tkp(path)
    assert res.rows[1]["cash_transfer"] == 100000.0
    assert any("synthesized cash_transfer" in w for w in res.warnings)

    # Counter-case from the shared fixture: recorded Deposit is left alone.
    recorded = extract_tkp(repo_root / "daily_returns_secret_state.json")
    assert recorded.rows[1]["cash_transfer"] == 20000.0
    assert not any("synthesized" in w for w in recorded.warnings)


def test_extractor_refuses_stale_tcp_repo_seed(tmp_repo_root):
    """Without TCP_V2_STATE_PATH the extractor must FAIL, not silently fall
    back to the stale repo-root seed file."""
    from scripts.extract_tearsheet_history import extract_all

    repo_root, _files = tmp_repo_root
    (repo_root / ".tcp_production.env").unlink()
    with pytest.raises(FileNotFoundError):
        extract_all(repo_root, ["TCP"])
