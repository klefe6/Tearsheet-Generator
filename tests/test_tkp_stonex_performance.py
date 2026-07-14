"""TKP tearsheet performance must use StoneX only (Plus500 is display-only)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / "daily_returns_secret_state.json"

_EXAMPLES = {
    "2026-07-07": (82746.22, 85121.20),
    "2026-07-08": (82768.43, 85143.41),
    "2026-07-09": (82838.14, 85213.12),
    "2026-07-10": (82842.85, 85217.83),
    "2026-07-13": (82887.56, 85262.54),
}

_INCORRECT = (168051.26, 192875.99, 107662.87)


@pytest.fixture(scope="module")
def tkp_mod():
    import tkp_ts

    return tkp_ts


@pytest.fixture(scope="module")
def state_rows():
    if not _STATE.exists():
        pytest.skip(f"missing {_STATE}")
    return json.loads(_STATE.read_text(encoding="utf-8"))


def test_canonical_performance_uses_stonex_only(tkp_mod, state_rows):
    recs = tkp_mod._canonical_records_from_secret_rows(state_rows)
    by_date = {r["Date"]: r["NAV"] for r in recs}
    stonex, plus500 = _EXAMPLES["2026-07-09"]
    assert by_date["2026-07-09"] == pytest.approx(stonex, abs=0.01)
    assert by_date["2026-07-09"] == pytest.approx(stonex, abs=0.01)
    for bad in _INCORRECT:
        assert by_date["2026-07-09"] != pytest.approx(bad, abs=0.01)
    assert by_date["2026-07-09"] != pytest.approx(stonex + plus500, abs=0.01)


@pytest.mark.parametrize("date_str", list(_EXAMPLES))
def test_sample_dates_match_stonex_balance(tkp_mod, state_rows, date_str):
    recs = tkp_mod._canonical_records_from_secret_rows(state_rows)
    by_date = {r["Date"]: r["NAV"] for r in recs}
    stonex, _ = _EXAMPLES[date_str]
    assert by_date[date_str] == pytest.approx(stonex, abs=0.01)


def test_plus500_change_does_not_move_performance_series(tkp_mod, state_rows):
    base = tkp_mod._canonical_records_from_secret_rows(state_rows)
    series_a = tkp_mod._rebuild_nav_series(base)

    mutated = []
    for r in state_rows:
        row = dict(r)
        if row.get("Date") == "2026-07-09":
            row["Plus500"] = "$999,999.99"
        mutated.append(row)
    series_b = tkp_mod._rebuild_nav_series(
        tkp_mod._canonical_records_from_secret_rows(mutated)
    )

    assert series_a.loc["2026-07-09"] == pytest.approx(series_b.loc["2026-07-09"], abs=0.01)
    d_ret_a = tkp_mod._daily_returns_from_secret_rows(state_rows, tkp_mod.BASELINE_AMOUNT)
    d_ret_b = tkp_mod._daily_returns_from_secret_rows(mutated, tkp_mod.BASELINE_AMOUNT)
    assert d_ret_a.loc["2026-07-09"] == pytest.approx(d_ret_b.loc["2026-07-09"], abs=1e-9)


def test_stonex_change_moves_performance_series(tkp_mod, state_rows):
    base = tkp_mod._canonical_records_from_secret_rows(state_rows)
    series_a = tkp_mod._rebuild_nav_series(base)

    mutated = []
    for r in state_rows:
        row = dict(r)
        if row.get("Date") == "2026-07-09":
            row["StoneX"] = "$83,000.00"
            row["$PL"] = "$1,000.00"
        mutated.append(row)
    series_b = tkp_mod._rebuild_nav_series(
        tkp_mod._canonical_records_from_secret_rows(mutated)
    )

    assert series_a.loc["2026-07-09"] != pytest.approx(series_b.loc["2026-07-09"], abs=0.01)


def test_client_admin_canonical_same_source(tkp_mod, state_rows):
    """canonical-nav-store path uses the same StoneX extraction for all views."""
    recs = tkp_mod._canonical_records_from_secret_rows(state_rows)
    assert recs
    nav_s = tkp_mod._rebuild_nav_series(recs)
    assert nav_s.loc["2026-07-09"] == pytest.approx(82838.14, abs=0.01)


def test_broker_columns_still_include_plus500(state_rows):
    jul9 = next(r for r in state_rows if r.get("Date") == "2026-07-09")
    assert "Plus500" in jul9
    assert "StoneX" in jul9
    assert jul9["Plus500"] == "$85,213.12"
    assert jul9["StoneX"] == "$82,838.14"


def test_cash_transfer_neutralization_unchanged(tkp_mod):
    prev = {
        "StoneX": "$100,000.00",
        "NAV": "$150,000.00",
        "HWM": "$150,000.00",
        "Loss Carry": "$0.00",
        "Cumm Fee": "$0.00",
        "Cumm Perc. Net": 0,
    }
    computed = tkp_mod._compute_new_row(prev, new_balance=105_000.0, deposit=5_000.0)
    assert computed["$PL"] == "$0.00"


def test_fee_hwm_still_use_synthetic_nav_not_stonex(tkp_mod, state_rows):
    """Fee/HWM row fields remain on synthetic NAV accounting (unchanged in this fix)."""
    jul9 = next(r for r in state_rows if r.get("Date") == "2026-07-09")
    assert jul9["NAV"] == "$192,875.99"
    assert jul9["HWM"] == "$192,875.99 *"
    perf = {r["Date"]: r["NAV"] for r in tkp_mod._canonical_records_from_secret_rows(state_rows)}
    assert perf["2026-07-09"] == pytest.approx(82838.14, abs=0.01)
    assert perf["2026-07-09"] != pytest.approx(192875.99, abs=0.01)
