"""TKP performance reconciliation invariants.

Chart, monthly Performance Summary, year totals, drawdown, and daily stats
must all derive from ONE canonical series — the persisted NAV chain
($150,000 baseline + cumulative StoneX-only net trading P&L) — and must
reconcile with each other exactly:

- A pure deposit or withdrawal changes the broker balance but produces $0
  performance.
- The first month never generates an artificial return from account
  initialization (regression: April 2023 displayed -32.8266% because the
  monthly formula anchored the first month at the $150k baseline while the
  StoneX account opened at $100k).
- Month cells sum to year totals, and all months sum to the chart's
  cumulative performance.
- Recalculating twice produces exactly the same result and never rewrites
  the persisted ledger.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / "daily_returns_secret_state.json"

BL = 150_000.0


@pytest.fixture(scope="module")
def tkp_mod():
    import tkp_ts

    return tkp_ts


@pytest.fixture(scope="module")
def state_rows():
    if not _STATE.exists():
        pytest.skip(f"missing {_STATE}")
    return json.loads(_STATE.read_text(encoding="utf-8"))


def _seed_row(date="2025-12-30", stonex=100_000.0, nav=BL):
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


def _append(tkp_mod, rows, date, balance, deposit=0.0):
    prev = rows[-1]
    row = dict(prev)
    row.update(tkp_mod._compute_new_row(prev, balance, deposit))
    row["Date"] = date
    return rows + [row]


def _monthly_cells(tkp_mod, rows):
    recs = tkp_mod._recompute_monthly_records(pd.Series(dtype=float), BL, secret_rows=rows)
    cells = {}
    for r in recs:
        year = r["Year"]
        for i, m in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1):
            if r.get(m):
                cells[f"{year}-{i:02d}"] = float(r[m].rstrip("%"))
        cells[f"{year}-total"] = float(r["Year Total"].rstrip("%"))
    return cells


# ── cash-movement invariants (via the app's own row math) ──────────────────

def test_initial_funding_produces_no_performance(tkp_mod):
    rows = [_seed_row("2023-04-10")]
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[0] == pytest.approx(BL, abs=0.01)
    cells = _monthly_cells(tkp_mod, rows)
    assert cells["2023-04"] == pytest.approx(0.0, abs=1e-6)


def test_pure_deposit_zero_performance(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=150_000.0, deposit=50_000.0)
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL, abs=0.01)
    assert rows[-1]["StoneX"] == "$150,000.00"  # broker balance moved
    assert rows[-1]["$PL"] == "$0.00"


def test_pure_withdrawal_zero_performance(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=60_000.0, deposit=-40_000.0)
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL, abs=0.01)
    assert rows[-1]["StoneX"] == "$60,000.00"


def test_deposit_during_profitable_day(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=110_500.0, deposit=10_000.0)
    # $500 trading gain, 20% fee -> +$400 net
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL + 400.0, abs=0.01)


def test_deposit_during_losing_day(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=109_500.0, deposit=10_000.0)
    # -$500 trading loss, no fee
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL - 500.0, abs=0.01)


def test_withdrawal_during_profitable_day(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=91_000.0, deposit=-10_000.0)
    # +$1,000 trading gain despite withdrawal, 20% fee -> +$800 net
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL + 800.0, abs=0.01)


def test_withdrawal_during_losing_day(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=89_000.0, deposit=-10_000.0)
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL - 1_000.0, abs=0.01)


def test_multiple_same_day_cash_movements_net_out(tkp_mod):
    # +$20k deposit and -$5k withdrawal on the same day are entered as the
    # net $15k in the single Deposit cell; trading P&L is still isolated.
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=115_250.0, deposit=15_000.0)
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(BL + 250.0 * 0.8, abs=0.01)


def test_transfer_with_zero_trading_pnl(tkp_mod):
    rows = [_seed_row()]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=125_000.0, deposit=25_000.0)
    assert rows[-1]["$PL"] == "$0.00"
    assert rows[-1]["Fee (20%)"] == "$0.00"
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[-1] == pytest.approx(perf.iloc[0], abs=0.01)


# ── month / year boundaries ────────────────────────────────────────────────

def test_first_partial_month_and_month_boundary(tkp_mod):
    rows = [_seed_row("2023-04-10")]
    rows = _append(tkp_mod, rows, "2023-04-20", balance=101_000.0)          # +800 net
    rows = _append(tkp_mod, rows, "2023-04-28", balance=101_500.0)          # +400 net
    rows = _append(tkp_mod, rows, "2023-05-05", balance=102_500.0)          # +800 net
    cells = _monthly_cells(tkp_mod, rows)
    assert cells["2023-04"] == pytest.approx(1200.0 / BL * 100, abs=1e-4)
    assert cells["2023-05"] == pytest.approx(800.0 / BL * 100, abs=1e-4)
    # No -33% artifact from the $100k opening balance vs the $150k baseline.
    assert cells["2023-04"] > -1.0


def test_year_boundary_totals(tkp_mod):
    rows = [_seed_row("2025-12-30")]
    rows = _append(tkp_mod, rows, "2025-12-31", balance=101_000.0)          # 2025: +800 net
    rows = _append(tkp_mod, rows, "2026-01-02", balance=102_000.0)          # 2026: +800 net
    cells = _monthly_cells(tkp_mod, rows)
    assert cells["2025-total"] == pytest.approx(cells["2025-12"], abs=1e-6)
    assert cells["2026-total"] == pytest.approx(cells["2026-01"], abs=1e-6)
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    total = cells["2025-total"] + cells["2026-total"]
    assert total == pytest.approx((perf.iloc[-1] - BL) / BL * 100, abs=1e-4)


# ── historical vs newly ingested rows ──────────────────────────────────────

def test_new_ingested_row_extends_series_without_rewriting_history(tkp_mod, state_rows):
    base_perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    extended = _append(
        tkp_mod, sorted(state_rows, key=lambda r: str(r.get("Date", ""))),
        "2026-07-22",
        balance=tkp_mod._parse_money(state_rows[-1]["StoneX"]) + 100.0,
    )
    new_perf = tkp_mod._performance_series_from_secret_rows(extended)
    # history byte-identical
    assert len(new_perf) == len(base_perf) + 1
    for probe in ("2023-04-28", "2025-04-22", "2026-07-09"):
        assert new_perf.loc[probe] == pytest.approx(base_perf.loc[probe], abs=1e-9)
    # +$100 gross, -20% fee => +$80 net on the series
    assert new_perf.iloc[-1] == pytest.approx(base_perf.iloc[-1] + 80.0, abs=0.01)


# ── full-ledger reconciliation (real production state) ─────────────────────

def test_april_2023_monthly_return_is_correct(tkp_mod, state_rows):
    cells = _monthly_cells(tkp_mod, state_rows)
    # (150,608.12 month-end NAV - 150,000 baseline) / 150,000
    assert cells["2023-04"] == pytest.approx(0.4054, abs=0.0001)
    # Regression guard: the -32.8266% first-month artifact must never return.
    assert all(v > -30.0 for k, v in cells.items() if not k.endswith("total"))


def test_chart_table_year_totals_reconcile(tkp_mod, state_rows):
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    cells = _monthly_cells(tkp_mod, state_rows)
    month_sum = sum(v for k, v in cells.items() if not k.endswith("total"))
    year_sum = sum(v for k, v in cells.items() if k.endswith("total"))
    chart_cum = (perf.iloc[-1] - BL) / BL * 100
    assert month_sum == pytest.approx(chart_cum, abs=0.01)
    assert year_sum == pytest.approx(chart_cum, abs=0.01)
    # Chart ends at the ledger NAV, not a compounded raw-balance rebuild.
    ledger_last_nav = tkp_mod._parse_money(
        sorted(state_rows, key=lambda r: str(r.get("Date", "")))[-1]["NAV"]
    )
    assert perf.iloc[-1] == pytest.approx(ledger_last_nav, abs=0.01)


def test_authoritative_ending_nav_is_persisted_chain_not_column_aggregates(
    tkp_mod, state_rows,
):
    """Cent-level reconciliation: the NAV column chain is authoritative.

    Summing rounded $PL / Fee columns or display percentages can disagree
    with the persisted NAV by tens of cents; the public chart must track NAV.
    """
    auth = sorted(
        [r for r in state_rows if r.get("StoneX") and r.get("NAV")],
        key=lambda r: str(r.get("Date", "")),
    )
    last_nav = tkp_mod._parse_money(auth[-1]["NAV"])
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    assert perf.iloc[-1] == pytest.approx(last_nav, abs=1e-6)

    sum_gross = sum(tkp_mod._parse_money(r.get("$PL")) for r in auth)
    sum_fee = sum(tkp_mod._parse_money(r.get("Fee (20%)")) for r in auth)
    sum_net = sum(tkp_mod._parse_money(r.get("Net P&L")) for r in auth)
    bl = float(BL)
    aggregate_gross_minus_fee = bl + sum_gross - sum_fee
    aggregate_net = bl + sum_net
    chart_cum_pct_4dp = round((last_nav - bl) / bl * 100, 4)
    display_pct_implied = bl + bl * chart_cum_pct_4dp / 100

    # These alternate totals are expected to drift from the ledger; guard regressions.
    assert aggregate_gross_minus_fee == pytest.approx(last_nav + 0.72, abs=0.02)
    assert aggregate_net == pytest.approx(last_nav + 0.29, abs=0.02)
    assert display_pct_implied == pytest.approx(last_nav + 0.06, abs=0.02)


def test_daily_stats_reconcile_with_ledger(tkp_mod, state_rows):
    d = tkp_mod._daily_returns_from_secret_rows(state_rows, BL)
    total_net = sum(
        tkp_mod._parse_money(r.get("Net P&L"))
        for r in state_rows
        if r.get("Net P&L") not in ("", None)
    )
    assert d.sum() * BL == pytest.approx(total_net, abs=1.0)
    # Net cumulative return matches the NAV chain within cent-rounding drift.
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    assert d.sum() * 100 == pytest.approx((perf.iloc[-1] - BL) / BL * 100, abs=0.01)


def test_drawdown_uses_canonical_series(tkp_mod, state_rows):
    perf = tkp_mod._performance_series_from_secret_rows(state_rows)
    dd_df = tkp_mod._build_max_dd_df(perf)
    strategy_col = f"{tkp_mod.STRATEGY_NAME} (Inception)"
    depth = float(str(dd_df.set_index("Metric").loc["Depth", strategy_col]).rstrip("%"))
    # Real worst baseline-relative NAV drawdown is -11.56% (2025-02→2025-03).
    assert depth == pytest.approx(-11.6, abs=0.2)


# ── idempotency ────────────────────────────────────────────────────────────

def test_recalculation_is_idempotent_and_never_rewrites_ledger(tkp_mod, state_rows, monkeypatch, tmp_path):
    state_path = tmp_path / "daily_returns_secret_state.json"
    state_path.write_text(json.dumps(state_rows), encoding="utf-8")
    monkeypatch.setattr(tkp_mod, "_secret_editor_state_path", lambda: str(state_path))
    before_bytes = state_path.read_bytes()

    s1 = tkp_mod.apply_tkp_recalculation()
    s2 = tkp_mod.apply_tkp_recalculation()
    assert s1["latest_display_date"] == s2["latest_display_date"]

    perf_a = tkp_mod._performance_series_from_secret_rows(s1["rows"])
    perf_b = tkp_mod._performance_series_from_secret_rows(s2["rows"])
    assert perf_a.equals(perf_b)
    cells_a = _monthly_cells(tkp_mod, s1["rows"])
    cells_b = _monthly_cells(tkp_mod, s2["rows"])
    assert cells_a == cells_b
    # Recalculation is read-only over the persisted ledger.
    assert state_path.read_bytes() == before_bytes
