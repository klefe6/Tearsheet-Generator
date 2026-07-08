"""Derived AGM monthly Performance Summary (algominds_monthly_summary).

Proves the June 2026 fix: monthly rows come from the accepted daily
accounting/fee/benchmark models (not the stale hand-maintained workbook), only
COMPLETE months are emitted, and the derivation reproduces the workbook's own
mature rows to tolerance.
"""
from __future__ import annotations

import datetime as dt

import openpyxl
import pandas as pd
import pytest

import algominds_benchmark_daily as agm_bench
import algominds_daily_accounting as agm_acct
import algominds_daily_balances as agm_bal
import algominds_daily_fees as agm_fees
import algominds_monthly_summary as agm_monthly

INCEPTION = pd.Timestamp("2025-11-13")
WORKBOOK = "Momentum Pacer/Momentum Fee Calculation.xlsx"


@pytest.fixture(scope="module")
def pipeline():
    bal = agm_bal.load_daily_balances()
    assert not bal.empty, "daily balances CSV must load"
    start = bal["Date"].min() - pd.Timedelta(days=45)
    end = bal["Date"].max()
    spx = agm_bench.load_daily_benchmark(agm_bench.SPX_TICKER, start, end)
    ndx = agm_bench.load_daily_benchmark(agm_bench.NDX_TICKER, start, end)

    wb = openpyxl.load_workbook(WORKBOOK, data_only=True)
    ws = wb["Summary"]
    workbook_rows = [
        r for r in ws.iter_rows(values_only=True)
        if isinstance(r[0], dt.datetime) and r[5] is not None
    ]
    reference = pd.DataFrame(
        [{"date": r[0], "bot_end_after_fees": r[6], "bot_fees_pct": r[10]} for r in workbook_rows]
    )
    fee_accrual = agm_fees.compute_daily_fee_accrual(
        bal, spx, inception=INCEPTION, monthly_reference=reference
    )
    accounting = agm_acct.compute_agm_daily_accounting(
        bal, spx, fee_accrual=fee_accrual, inception=INCEPTION, monthly_reference=reference
    )
    summary = agm_monthly.compute_agm_monthly_summary(
        accounting.table, fee_accrual.crystallized, spx, ndx, inception=INCEPTION
    )
    return {
        "bal": bal,
        "spx": spx,
        "ndx": ndx,
        "accounting": accounting,
        "fee_accrual": fee_accrual,
        "summary": summary,
        "workbook_rows": workbook_rows,
    }


def test_june_2026_row_present_and_july_excluded(pipeline):
    dates = set(pipeline["summary"].table["date"])
    assert pd.Timestamp("2026-06-01") in dates
    assert pd.Timestamp("2026-05-01") in dates  # does not stop at May either way
    assert pd.Timestamp("2026-07-01") not in dates  # in-progress month never a row
    assert pipeline["summary"].table["date"].max() == pd.Timestamp("2026-06-01")


def test_derivation_reproduces_mature_workbook_rows(pipeline):
    """Nov 2025 – Apr 2026 derived rows must agree with the workbook's own
    hand-entered rows — proof the derivation is real, not hardcoded. (May is
    deliberately excluded: the workbook's May row froze mid-May and is stale.)"""
    derived = pipeline["summary"].table.set_index(
        pipeline["summary"].table["date"].dt.to_period("M")
    )
    checked = 0
    for r in pipeline["workbook_rows"]:
        period = pd.Timestamp(r[0]).to_period("M")
        if str(period) > "2026-04":
            continue
        d = derived.loc[period]
        assert abs(float(d["bot_start"]) - float(r[5])) <= 1.0
        assert abs(float(d["bot_end_after_fees"]) - float(r[6])) <= 1.0
        assert abs(float(d["spx_start"]) - float(r[1])) <= 0.5
        assert abs(float(d["spx_end"]) - float(r[2])) <= 0.5
        assert abs(float(d["ndx_start"]) - float(r[3])) <= 0.5
        assert abs(float(d["ndx_end"]) - float(r[4])) <= 0.5
        for col, idx in (("spx_ret", 7), ("ndx_ret", 8), ("bot_gross_ret", 9),
                         ("bot_fees_pct", 10), ("bot_net_ret", 11), ("cumulative_net", 12)):
            assert abs(float(d[col]) - float(r[idx])) <= 1e-3, (period, col)
        checked += 1
    assert checked == 6  # Nov, Dec, Jan, Feb, Mar, Apr


def test_june_values_come_from_daily_models(pipeline):
    """June row values trace back to the daily accounting table, the fee
    engine's crystallization, and the cached benchmark closes."""
    summary = pipeline["summary"].table
    acct = pipeline["accounting"].table
    june = summary[summary["date"] == pd.Timestamp("2026-06-01")].iloc[0]

    june_acct = acct[acct["Date"].dt.to_period("M") == pd.Period("2026-06")]
    assert float(june["bot_end_after_fees"]) == pytest.approx(
        float(june_acct["client_net_value"].iloc[-1])
    )
    may_acct = acct[acct["Date"].dt.to_period("M") == pd.Period("2026-05")]
    assert float(june["bot_start"]) == pytest.approx(
        float(may_acct["client_net_value"].iloc[-1])
    )
    fee_by_month = {c["month"]: c["fee"] for c in pipeline["fee_accrual"].crystallized}
    assert float(june["bot_fees_pct"]) == pytest.approx(
        fee_by_month["2026-06"] / agm_fees.NOMINAL_CAPITAL
    )
    spx = pipeline["spx"].set_index("Date")["Close"]
    june_spx = spx[(spx.index >= "2026-06-01") & (spx.index <= "2026-06-30")]
    assert float(june["spx_end"]) == pytest.approx(float(june_spx.iloc[-1]))
    # Chain: derived June net return is consistent with its own row values.
    assert float(june["bot_net_ret"]) == pytest.approx(
        (float(june["bot_end_after_fees"]) - float(june["bot_start"]))
        / agm_fees.NOMINAL_CAPITAL
    )


def test_totals_are_column_sums_including_june(pipeline):
    summary = pipeline["summary"]
    t = summary.table
    for pct_key, col in (
        ("spx_net_pct", "spx_ret"),
        ("ndx_net_pct", "ndx_ret"),
        ("bot_gross_pct", "bot_gross_ret"),
        ("bot_fees_pct", "bot_fees_pct"),
        ("bot_net_pct", "bot_net_ret"),
    ):
        assert summary.totals[pct_key] == pytest.approx(float(t[col].fillna(0).sum()))
    # Dollar rows are the pct rows on the fixed $30k nominal.
    assert summary.totals["bot_net_dollar"] == pytest.approx(
        summary.totals["bot_net_pct"] * agm_fees.NOMINAL_CAPITAL
    )
    # Totals move when June is dropped -> June is genuinely included.
    without_june = float(t[t["date"] < "2026-06-01"]["bot_net_ret"].sum())
    assert summary.totals["bot_net_pct"] != pytest.approx(without_june)


def test_partial_month_never_becomes_a_row(pipeline):
    """Truncating the daily data mid-month must drop that month's row instead
    of fabricating a partial one."""
    bal = pipeline["bal"]
    truncated = bal[bal["Date"] <= pd.Timestamp("2026-06-15")].reset_index(drop=True)
    fee_accrual = agm_fees.compute_daily_fee_accrual(
        truncated, pipeline["spx"], inception=INCEPTION
    )
    accounting = agm_acct.compute_agm_daily_accounting(
        truncated, pipeline["spx"], fee_accrual=fee_accrual, inception=INCEPTION
    )
    summary = agm_monthly.compute_agm_monthly_summary(
        accounting.table, fee_accrual.crystallized,
        pipeline["spx"], pipeline["ndx"], inception=INCEPTION,
    )
    assert summary.table["date"].max() == pd.Timestamp("2026-05-01")
    assert pd.Timestamp("2026-06-01") not in set(summary.table["date"])


def test_accounting_invariant_still_holds(pipeline):
    assert agm_acct.verify_accounting_invariant(pipeline["accounting"].table)
