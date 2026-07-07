"""
Algominds / Momentum Pacer — DAILY incentive-fee accrual engine (AGM-only).

Converts the approved monthly fee formula from "Momentum Fee Calculation.xlsx"
into a daily cumulative accrual computed from:
  - daily AGM account Net Worth (TradeStation balances CSV), and
  - daily S&P 500 closes (^GSPC — see algominds_benchmark_daily for the ticker
    rationale; the workbook's SPX levels match ^GSPC closes exactly).

The approved monthly formula (reproduced from the workbook's per-month detail
sheets and verified to the cent for Nov 2025 / Jan / Feb / Apr 2026):

    B  (Benchmark $)     = SPX return for the period x NOMINAL_CAPITAL ($30,000
                           initial capital — the workbook multiplies every slab
                           by the fixed nominal, not the compounded balance).
    P  (net new profits) = max(0, pre-fee closing balance - High-Water Mark).
    If B > 0 : graduated slabs on slices of P —
                 10% of P in [0,B), 20% in [B,2B), 30% in [2B,3B),
                 40% in [3B,4B), 50% above 4B.
    If B <= 0: fee = 50% x P    (per the Disclosure Document).
    HWM      = highest after-fee month-end balance so far (starts at initial
               capital). The first fee month is anchored at live inception
               (SPX close on 2025-11-13); later months anchor at the prior
               month-end SPX close.

Daily conversion: within each month, the same formula is evaluated every
trading day with P_d measured from the day's Net Worth (net of fees still
owed) against the HWM, and B_d from the SPX close vs the month's anchor.
At month-end the accrued fee CRYSTALLIZES (fees are charged monthly per the
Disclosure Document) and starts accruing for the next month; crystallized fees
stay in an "outstanding" ledger until a payment/removal is actually EVIDENCED:

  - exact-daily-match: a day's Net-Worth change equals an outstanding fee
    amount (or the whole outstanding total) to the cent, or
  - workbook-reconciliation: a month-end Net Worth agrees (±$1) with the
    workbook's fee-deducted track, proving earlier fees have left the account.

No payment events are fabricated: fees with no such evidence remain in the
outstanding ledger and are reported in ``DailyFeeAccrual.outstanding``.

Deterministic and network-free: callers supply both dataframes. Safe to import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

import algominds_benchmark_daily as agm_bench

# Fixed nominal trading level used by every workbook fee calculation.
NOMINAL_CAPITAL = 30_000.0

# Graduated incentive slabs (rate applied to the slice of P in [i*B, (i+1)*B)).
SLAB_RATES = (0.10, 0.20, 0.30, 0.40)
# Rate above 4x the benchmark dollar return, and the flat rate when B <= 0.
TOP_SLAB_RATE = 0.50
NEGATIVE_BENCHMARK_RATE = 0.50

# Live inception (matches mp_ts.PROGRAM_INCEPTION and the workbook's Nov anchor).
DEFAULT_INCEPTION = pd.Timestamp("2025-11-13")

# Evidence tolerances (dollars).
EXACT_MATCH_TOL = 0.02
RECONCILE_TOL = 1.00


def slab_fee(profit: float, benchmark_dollars: float) -> float:
    """
    Incentive fee on *profit* (net new profits above HWM, $) given the
    benchmark dollar return *benchmark_dollars*. Never negative.
    """
    p = max(0.0, float(profit))
    if p == 0.0:
        return 0.0
    b = float(benchmark_dollars)
    if b <= 0.0:
        return NEGATIVE_BENCHMARK_RATE * p
    fee = 0.0
    for i, rate in enumerate(SLAB_RATES):
        slice_amount = min(max(p - i * b, 0.0), b)
        fee += rate * slice_amount
    fee += TOP_SLAB_RATE * max(p - len(SLAB_RATES) * b, 0.0)
    return fee


@dataclass
class DailyFeeAccrual:
    """Result of compute_daily_fee_accrual()."""

    # Per trading day: Date, net_worth, spx_close, spx_anchor, benchmark_dollars,
    # hwm, month_accrual, outstanding_total, accrued_total (the chart series).
    daily: pd.DataFrame
    # Month-end crystallizations: {"month", "date", "fee"}.
    crystallized: List[dict] = field(default_factory=list)
    # Evidenced payments/removals: {"date", "amount", "months", "method"}.
    payments: List[dict] = field(default_factory=list)
    # Crystallized fees with no payment evidence yet: {"month", "fee"}.
    outstanding: List[dict] = field(default_factory=list)
    # Balance dates skipped because no usable SPX close existed (accrual carried).
    skipped_dates: List[pd.Timestamp] = field(default_factory=list)


def _prior_close(bench: pd.Series, before: pd.Timestamp) -> Optional[float]:
    """Last benchmark close strictly before *before* (or None)."""
    earlier = bench[bench.index < before]
    if earlier.empty:
        return None
    return float(earlier.iloc[-1])


def compute_daily_fee_accrual(
    balances_df: pd.DataFrame,
    spx_df: pd.DataFrame,
    inception: pd.Timestamp = DEFAULT_INCEPTION,
    nominal: float = NOMINAL_CAPITAL,
    monthly_reference: Optional[pd.DataFrame] = None,
) -> DailyFeeAccrual:
    """
    Walk the daily balances chronologically and accrue incentive fees daily.

    balances_df : algominds_daily_balances.load_daily_balances() output
                  (needs Date + Net Worth, sorted ascending).
    spx_df      : algominds_benchmark_daily.load_daily_benchmark() output
                  (Date/Close), covering the balance range plus the prior
                  month-end before *inception*.
    monthly_reference : optional workbook Summary frame (internal reference
                  only) with columns date / bot_end_after_fees / bot_fees_pct,
                  used solely as payment-reconciliation EVIDENCE.

    Returns DailyFeeAccrual. Never fabricates SPX values or payment events.
    """
    empty = pd.DataFrame(
        columns=["Date", "net_worth", "spx_close", "spx_anchor", "benchmark_dollars",
                 "hwm", "month_accrual", "outstanding_total", "accrued_total"]
    )
    if balances_df is None or balances_df.empty:
        return DailyFeeAccrual(daily=empty)

    inception = pd.Timestamp(inception).normalize()
    bal = balances_df[balances_df["Date"] >= inception].reset_index(drop=True)
    if bal.empty:
        return DailyFeeAccrual(daily=empty)

    if spx_df is None or spx_df.empty:
        # No benchmark at all: report every date skipped, accrual honestly absent.
        return DailyFeeAccrual(daily=empty, skipped_dates=list(bal["Date"]))

    bench = spx_df.set_index("Date")["Close"].sort_index()
    aligned = agm_bench.align_to_dates(spx_df, bal["Date"])

    # Workbook reference: month period -> expected PRE-fee month-end close
    # (after-fee close + that month's fee), used only as payment evidence.
    reference: dict = {}
    if monthly_reference is not None and not monthly_reference.empty:
        for _, r in monthly_reference.iterrows():
            try:
                period = pd.Timestamp(r["date"]).to_period("M")
                after_fee = float(r["bot_end_after_fees"])
                fee = float(r["bot_fees_pct"]) * nominal
            except (KeyError, TypeError, ValueError):
                continue
            reference[period] = after_fee + fee

    months = bal["Date"].dt.to_period("M")
    inception_month = inception.to_period("M")

    # HWM starts at the account's value at inception (= initial capital).
    hwm = float(bal["Net Worth"].iloc[0])
    outstanding: List[dict] = []  # [{"month": Period, "fee": float}]
    crystallized: List[dict] = []
    payments: List[dict] = []
    skipped: List[pd.Timestamp] = []

    rows = []
    prev_nw: Optional[float] = None
    cur_month = None
    anchor: Optional[float] = None
    accrual = 0.0
    last_b = float("nan")

    for i in range(len(bal)):
        date = pd.Timestamp(bal["Date"].iloc[i])
        nw = float(bal["Net Worth"].iloc[i])
        month = months.iloc[i]
        spx_close = aligned.iloc[i]

        # ── new month: set the SPX anchor ────────────────────────────────
        if month != cur_month:
            cur_month = month
            accrual = 0.0
            if month == inception_month:
                # Inception month anchors at the inception-day close (workbook rule).
                anchor = float(spx_close) if pd.notna(spx_close) else None
            else:
                anchor = _prior_close(bench, month.to_timestamp())

        # ── payment evidence 1: exact daily Net-Worth match ─────────────
        if prev_nw is not None and outstanding:
            change = nw - prev_nw
            if change < 0:
                drop = -change
                total_out = sum(f["fee"] for f in outstanding)
                if abs(drop - total_out) <= EXACT_MATCH_TOL:
                    payments.append({
                        "date": date, "amount": total_out,
                        "months": [str(f["month"]) for f in outstanding],
                        "method": "exact-daily-match",
                    })
                    outstanding = []
                else:
                    for f in list(outstanding):
                        if abs(drop - f["fee"]) <= EXACT_MATCH_TOL:
                            payments.append({
                                "date": date, "amount": f["fee"],
                                "months": [str(f["month"])],
                                "method": "exact-daily-match",
                            })
                            outstanding.remove(f)
                            break

        # A month is complete when a later balance row exists in a newer month;
        # the file's final month is in-progress and never crystallizes.
        month_complete = i + 1 < len(bal) and months.iloc[i + 1] != month

        # ── payment evidence 2: workbook reconciliation at month-end ────
        if month_complete and outstanding and month in reference:
            if abs(nw - reference[month]) <= RECONCILE_TOL:
                older = [f for f in outstanding if f["month"] < month]
                if older:
                    payments.append({
                        "date": date,
                        "amount": sum(f["fee"] for f in older),
                        "months": [str(f["month"]) for f in older],
                        "method": "workbook-reconciliation",
                    })
                    outstanding = [f for f in outstanding if f["month"] >= month]

        # ── daily accrual ────────────────────────────────────────────────
        outstanding_total = sum(f["fee"] for f in outstanding)
        if anchor is None or pd.isna(spx_close):
            # No honest benchmark for this day: carry the accrual, record it.
            skipped.append(date)
            b = last_b
        else:
            b = (float(spx_close) / anchor - 1.0) * nominal
            last_b = b
            equity = nw - outstanding_total  # net of fees still owed
            accrual = slab_fee(equity - hwm, b)

        # ── month-end crystallization (fees are charged monthly) ────────
        if month_complete:
            fee_m = accrual
            crystallized.append({"month": str(month), "date": date, "fee": fee_m})
            if fee_m > 0:
                outstanding.append({"month": month, "fee": fee_m})
                outstanding_total += fee_m
            hwm = max(hwm, nw - outstanding_total)
            accrual_for_row = 0.0  # crystallized amount now counted in outstanding
        else:
            accrual_for_row = accrual

        rows.append({
            "Date": date,
            "net_worth": nw,
            "spx_close": float(spx_close) if pd.notna(spx_close) else float("nan"),
            "spx_anchor": anchor if anchor is not None else float("nan"),
            "benchmark_dollars": b,
            "hwm": hwm,
            "month_accrual": accrual_for_row,
            "outstanding_total": outstanding_total,
            "accrued_total": accrual_for_row + outstanding_total,
        })
        prev_nw = nw

    daily = pd.DataFrame(rows)
    return DailyFeeAccrual(
        daily=daily,
        crystallized=crystallized,
        payments=payments,
        outstanding=[{"month": str(f["month"]), "fee": f["fee"]} for f in outstanding],
        skipped_dates=skipped,
    )
