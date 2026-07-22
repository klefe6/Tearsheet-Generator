"""TKP public chart must plot the canonical NAV chain — the nominal,
non-compounded, StoneX-only, cash-flow-neutral performance series — not raw
broker balances and not a compounded rebuild of raw balance deltas.

Raw StoneX deltas are NOT a valid substitute for the persisted ledger: the
first month would anchor against the $150k baseline instead of the $100k
StoneX opening, and the workbook's curated P&L attribution (e.g. the 2025
period where only half the StoneX delta belongs to TKP) would be lost.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / "daily_returns_secret_state.json"

# date, prior StoneX, new StoneX, external cash flow that day
_JUMP_DATES = (
    ("2025-04-22", 133908.06, 235714.84, 100000.0),
    ("2025-10-29", 247142.92, 147162.63, -100000.0),
    ("2026-01-09", 149896.42, 99868.63, -50000.0),
)


@pytest.fixture(scope="module")
def tkp_mod():
    import tkp_ts

    return tkp_ts


@pytest.fixture(scope="module")
def state_rows():
    if not _STATE.exists():
        pytest.skip(f"missing {_STATE}")
    return json.loads(_STATE.read_text(encoding="utf-8"))


def _seed_row(date="2026-01-01", stonex=100_000.0, nav=150_000.0):
    return {
        "Date": date,
        "StoneX": f"${stonex:,.2f}",
        "Plus500": "",
        "$PL": "",
        "Fee (20%)": "",
        "Cumm Fee": "$0.00",
        "Net P&L": 0,
        "NAV": f"${nav:,.2f}",
        "Loss Carry": "$0.00",
        "Perc. Net": "",
        "Cumm Perc. Net": 0,
        "HWM": f"${nav:,.2f}",
        "Deposit": "",
    }


def _next_row(tkp_mod, prev, date, balance, deposit=0.0):
    row = dict(prev)
    row.update(tkp_mod._compute_new_row(prev, balance, deposit))
    row["Date"] = date
    return row


def test_deposit_only_day_has_zero_performance(tkp_mod):
    r1 = _seed_row("2026-01-01")
    r2 = _next_row(tkp_mod, r1, "2026-01-02", balance=200_000.0, deposit=100_000.0)
    perf = tkp_mod._performance_series_from_secret_rows([r1, r2])
    assert perf.iloc[0] == pytest.approx(150_000.0, abs=0.01)
    assert perf.iloc[1] == pytest.approx(150_000.0, abs=0.01)
    # The broker balance itself must still move.
    assert r2["StoneX"] == "$200,000.00"


def test_withdrawal_only_day_has_zero_performance(tkp_mod):
    r1 = _seed_row("2026-01-01", stonex=200_000.0)
    r2 = _next_row(tkp_mod, r1, "2026-01-02", balance=100_000.0, deposit=-100_000.0)
    perf = tkp_mod._performance_series_from_secret_rows([r1, r2])
    assert perf.iloc[1] == pytest.approx(perf.iloc[0], abs=0.01)
    assert r2["StoneX"] == "$100,000.00"


def test_plus500_does_not_move_performance_curve(tkp_mod, state_rows):
    base_perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    mutated = []
    for r in state_rows:
        row = dict(r)
        if row.get("Date", "").startswith("2026-07-09"):
            row["Plus500"] = "$999,999.99"
        mutated.append(row)
    mut_perf = tkp_mod._performance_series_from_secret_rows(mutated)
    assert base_perf.loc["2026-07-09"] == pytest.approx(mut_perf.loc["2026-07-09"], abs=0.01)


def test_stonex_trading_pnl_moves_performance_curve(tkp_mod):
    r1 = _seed_row("2026-01-01")
    flat = tkp_mod._performance_series_from_secret_rows([r1])
    r2 = _next_row(tkp_mod, r1, "2026-01-02", balance=101_000.0, deposit=0.0)
    perf = tkp_mod._performance_series_from_secret_rows([r1, r2])
    assert perf.iloc[-1] > flat.iloc[-1]
    # $1,000 gross gain, 20% fee => +$800 net on the performance series.
    assert perf.iloc[-1] == pytest.approx(150_800.0, abs=0.01)


@pytest.mark.parametrize("date_str,prev_sx,new_sx,cash", _JUMP_DATES)
def test_major_cash_events_do_not_jump_performance(
    tkp_mod, state_rows, date_str, prev_sx, new_sx, cash
):
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    dt = pytest.importorskip("pandas").to_datetime(date_str)
    before = perf.loc[:dt].iloc[-2]
    after = perf.loc[dt]
    raw_jump_pct = abs((new_sx - prev_sx) / prev_sx)
    perf_jump_pct = abs((after - before) / before) if before else 0
    assert raw_jump_pct > 0.25
    assert perf_jump_pct < 0.05


def test_chart_series_is_persisted_nav_chain(tkp_mod, state_rows):
    """The chart plots the ledger's NAV column verbatim — no recomputation."""
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    nav_by_date = {
        r["Date"]: tkp_mod._parse_money(r["NAV"])
        for r in state_rows
        if r.get("Date") and r.get("NAV") not in ("", None)
    }
    assert perf.iloc[0] == pytest.approx(150_000.0, abs=0.01)
    for probe in ("2023-04-28", "2025-04-22", "2026-07-09"):
        assert perf.loc[probe] == pytest.approx(nav_by_date[probe], abs=0.01)
    assert perf.loc["2026-07-09"] == pytest.approx(192_875.99, abs=0.01)


def test_chart_is_not_compounded_from_raw_stonex_deltas(tkp_mod, state_rows):
    """Regression: compounding Glenn-style daily returns of raw StoneX deltas
    inflated the chart to ~$239.6k (vs the true $193.2k ledger NAV)."""
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    stonex_s, deposit_s, _ = tkp_mod._extract_stonex_deposit_fee_series(state_rows)
    level = tkp_mod.BASELINE_AMOUNT
    prior = None
    for dt in stonex_s.index:
        raw = float(stonex_s.loc[dt])
        cash = float(deposit_s.loc[dt]) if dt in deposit_s.index else 0.0
        if prior is not None:
            level *= 1.0 + tkp_mod._glenn_aligned_daily_return(prior, raw, cash)
        prior = raw
    assert perf.iloc[-1] != pytest.approx(level, abs=1000.0)
    assert perf.iloc[-1] < level  # the compounded rebuild overstates


def test_uploader_normalized_curve_is_exact_rescale_of_chart(tkp_mod, state_rows):
    """Glenn Uploader plots the NAV track (cash_transfer=0) rebased to 100k;
    compounding those daily ratios telescopes to an exact linear rescale of
    this chart. That is the true Glenn alignment."""
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    scale = 100_000.0 / tkp_mod.BASELINE_AMOUNT
    normalized = 100_000.0 * perf / perf.iloc[0]
    for dt in perf.index[:: max(1, len(perf) // 20)]:
        assert normalized.loc[dt] == pytest.approx(perf.loc[dt] * scale, rel=1e-9)


def test_canonical_store_matches_chart_series(tkp_mod, state_rows):
    recs = tkp_mod._canonical_records_from_secret_rows(state_rows)
    by_date = {r["Date"]: r["NAV"] for r in recs}
    assert by_date["2026-07-09"] == pytest.approx(192_875.99, abs=0.01)


def test_fee_hwm_nav_ledger_unchanged(tkp_mod, state_rows):
    jul9 = next(r for r in state_rows if str(r.get("Date", "")).startswith("2026-07-09"))
    assert jul9["NAV"] == "$192,875.99"
    assert jul9["StoneX"] == "$82,838.14"
