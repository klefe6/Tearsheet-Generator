"""TKP StoneX-only performance and authoritative historical backfill mapping."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.performance import _normalized_values
from app.programs import program_nlv
from scripts.extract_tearsheet_history import extract_tkp, parse_money

_REPO_STATE = (
    Path(__file__).resolve().parents[3] / "daily_returns_secret_state.json"
)
_HISTORICAL_END = "2026-07-09"

_EXAMPLES = {
    "2026-07-09": (82838.14, 85213.12),
    "2026-07-08": (82768.43, 85143.41),
    "2026-07-07": (82746.22, 85121.20),
}


def _next_weekday(start: date, target_weekday: int) -> date:
    offset = (target_weekday - start.weekday()) % 7
    return start + timedelta(days=offset)


_A_MONDAY = _next_weekday(date(2026, 7, 1), 0)


def _post(client, program, date_str, **fields):
    payload = {"date": date_str, **fields}
    r = client.post(f"/api/rows/{program}", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _stonex_from_state(raw: dict) -> float:
    val = parse_money(raw.get("StoneX"))
    assert val is not None
    return val


def _plus500_from_state(raw: dict) -> float:
    val = parse_money(raw.get("Plus500"))
    return 0.0 if val is None else val


@pytest.fixture
def tkp_state_rows():
    if not _REPO_STATE.exists():
        pytest.skip(f"missing {_REPO_STATE}")
    return json.loads(_REPO_STATE.read_text(encoding="utf-8"))


@pytest.fixture
def extracted_tkp_rows(tkp_state_rows):
    res = extract_tkp(_REPO_STATE)
    return res.rows


def test_extractor_maps_authoritative_examples(extracted_tkp_rows):
    by_date = {r["date"]: r for r in extracted_tkp_rows}
    for d, (stonex, plus500) in _EXAMPLES.items():
        row = by_date[d]
        assert row["stonex_nlv"] == stonex
        assert row["plus500_nlv"] == plus500


def test_program_nlv_tkp_is_stonex_only():
    row = {"stonex_nlv": 82838.14, "plus500_nlv": 85213.12}
    assert program_nlv("TKP", row) == 82838.14
    assert program_nlv("TKP", row) not in (168051.26, 192875.99, 107662.87)


def test_program_nlv_tcp_agm_yq_unchanged():
    assert program_nlv("TCP", {"stonex_nlv": 50000.0}) == 50000.0
    assert program_nlv("AGM", {"tradestation_nlv": 30000.0}) == 30000.0
    assert program_nlv("YQ", {"stonex_nlv": 60000.0}) == 60000.0


def test_plus500_alone_does_not_change_normalized_series():
    rows = [
        {"_nlv": 100000.0, "cash_transfer": 0.0, "plus500_nlv": 0.0},
        {"_nlv": 100000.0, "cash_transfer": 0.0, "plus500_nlv": 999999.0},
    ]
    assert _normalized_values(rows) == [100000.0, 100000.0]


def test_stonex_change_moves_normalized_series():
    rows = [
        {"_nlv": 100000.0, "cash_transfer": 0.0},
        {"_nlv": 101000.0, "cash_transfer": 0.0},
    ]
    assert _normalized_values(rows) == [100000.0, 101000.0]


def test_tkp_cash_transfer_neutralized_on_stonex_only(sandbox_client):
    d0, d1 = _A_MONDAY.isoformat(), (_A_MONDAY + timedelta(days=1)).isoformat()
    _post(sandbox_client, "TKP", d0, stonex_nlv=100000, plus500_nlv=50000)
    _post(sandbox_client, "TKP", d1, stonex_nlv=106000, plus500_nlv=50000, cash_transfer=6000)

    body = sandbox_client.get("/api/performance?mode=program&program=TKP").json()
    assert body["points"]["TKP"][0]["y"] == 100000
    assert body["points"]["TKP"][1]["y"] == 100000  # deposit neutralized on StoneX


def test_manual_and_historical_tkp_use_stonex_only(backfill_client, extracted_tkp_rows):
    sample = dict(next(r for r in extracted_tkp_rows if r["date"] == "2026-07-09"))
    from tests.test_backfill import _import

    body = _import(backfill_client, [sample], dry_run=False)
    assert body["programs"]["TKP"]["created"] == 1

    display = backfill_client.get("/api/display-rows/TKP").json()["rows"][0]
    assert display["stonex_nlv"] == 82838.14
    assert display["plus500_nlv"] == 85213.12
    assert display["value"] == 82838.14

    perf = backfill_client.get("/api/performance?mode=program&program=TKP").json()
    assert perf["points"]["TKP"][0]["y"] == 100000


def test_manual_row_overrides_historical_on_same_date(backfill_client, extracted_tkp_rows):
    sample = dict(next(r for r in extracted_tkp_rows if r["date"] == "2026-07-09"))
    from tests.test_backfill import _import

    _import(backfill_client, [sample], dry_run=False)
    _post(
        backfill_client,
        "TKP",
        "2026-07-09",
        stonex_nlv=82842.85,
        plus500_nlv=85217.83,
    )

    display = backfill_client.get("/api/display-rows/TKP").json()["rows"]
    manual = next(r for r in display if r["date"] == "2026-07-09")
    assert manual["source_label"] == "Manual"
    assert manual["stonex_nlv"] == 82842.85
    assert manual["value"] == 82842.85


def test_all_historical_window_rows_match_authoritative_stonex(
    extracted_tkp_rows, tkp_state_rows
):
    by_state = {
        (r["Date"][:10] if "T" in r["Date"] else r["Date"]): r for r in tkp_state_rows
    }
    window = [r for r in extracted_tkp_rows if r["date"] <= _HISTORICAL_END]
    assert len(window) == 837
    for row in window:
        raw = by_state[row["date"]]
        assert row["stonex_nlv"] == _stonex_from_state(raw)
        assert row["plus500_nlv"] == _plus500_from_state(raw)


def test_plus500_correct_but_no_chart_impact(backfill_client, extracted_tkp_rows):
    """Changing only plus500_nlv in stored historical data must not move the chart."""
    row_a = dict(next(r for r in extracted_tkp_rows if r["date"] == "2026-07-08"))
    row_b = dict(row_a)
    row_b["plus500_nlv"] = row_a["plus500_nlv"] + 99999.0
    from tests.test_backfill import _import

    _import(backfill_client, [row_a], dry_run=False)
    y_a = backfill_client.get("/api/performance?mode=program&program=TKP").json()
    backfill_client.delete("/api/backfill?program=TKP")
    _import(backfill_client, [row_b], dry_run=False)
    y_b = backfill_client.get("/api/performance?mode=program&program=TKP").json()
    assert y_a["points"]["TKP"] == y_b["points"]["TKP"]
