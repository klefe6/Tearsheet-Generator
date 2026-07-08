"""
Algominds / Momentum Pacer — DERIVED monthly Performance Summary (AGM-only).

Builds the tearsheet's monthly Performance Summary rows (and the Net% / Net$
footer totals) directly from the accepted daily models instead of the manually
maintained workbook Summary sheet, which goes stale between updates (its last
hand-entered row froze mid-May 2026, which is why June never appeared):

  - month-end client value  : ``client_net_value`` from
    algominds_daily_accounting (TradeStation NLV minus accrued unpaid fees)
  - monthly incentive fees  : month-end crystallizations from
    algominds_daily_fees (the accepted workbook slab/HWM formula — reused,
    never recomputed here)
  - SPX / NDX start & end   : cached daily benchmark closes from
    algominds_benchmark_daily

Workbook conventions are preserved exactly (verified against the workbook's
own Nov 2025 – Apr 2026 rows):

  - every BOT percentage is measured against the FIXED $30,000 nominal
    (non-compounded), matching the workbook and the fee engine's slab base;
  - BOT Start chains from the prior month's BOT End After Fees
    (inception month starts at the account value on live inception);
  - SPX/NDX Start chain the prior month-end close (inception month anchors
    at the live-inception-day close, e.g. ^GSPC 6737.49 on 2025-11-13);
  - Net% footer = sum of the monthly percentage columns; Net$ = Net% x $30k.

Only COMPLETE months are emitted: a month qualifies when a later balance date
exists in a newer month (same completeness rule as the fee engine). The
in-progress month (e.g. July 2026 with data through Jul 6) is never shown as
a monthly row.

Deterministic and network-free: callers supply every dataframe. Safe to import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from algominds_daily_fees import NOMINAL_CAPITAL

# Output schema — identical to mp_ts.load_summary()'s workbook frame so every
# downstream consumer (table builder, metrics, stats cards) works unchanged.
SUMMARY_COLUMNS: List[str] = [
    "date",
    "spx_start", "spx_end",
    "ndx_start", "ndx_end",
    "bot_start", "bot_end_after_fees",
    "spx_ret", "ndx_ret",
    "bot_gross_ret", "bot_fees_pct", "bot_net_ret",
    "cumulative_net",
]


@dataclass
class AgmMonthlySummary:
    """Result of compute_agm_monthly_summary()."""

    # One row per COMPLETE month, oldest→newest (workbook Summary schema).
    table: pd.DataFrame
    # Net% / Net$ footer values (mp_ts ``net_totals`` schema).
    totals: Dict[str, float] = field(default_factory=dict)


def _month_close_series(bench_df: Optional[pd.DataFrame]) -> pd.Series:
    if bench_df is None or bench_df.empty:
        return pd.Series(dtype=float)
    return bench_df.set_index("Date")["Close"].sort_index()


def _month_end_close(series: pd.Series, period: pd.Period) -> float:
    """Last benchmark close within the calendar month (official month-end)."""
    if series.empty:
        return float("nan")
    in_month = series[(series.index >= period.start_time) & (series.index <= period.end_time)]
    if in_month.empty:
        return float("nan")
    return float(in_month.iloc[-1])


def _close_on(series: pd.Series, date: pd.Timestamp) -> float:
    """Benchmark close on *date* (falls back to the last close on/before it)."""
    if series.empty:
        return float("nan")
    upto = series[series.index <= date]
    if upto.empty:
        return float("nan")
    return float(upto.iloc[-1])


def compute_agm_monthly_summary(
    accounting_table: pd.DataFrame,
    crystallized: List[dict],
    spx_df: Optional[pd.DataFrame],
    ndx_df: Optional[pd.DataFrame],
    inception: pd.Timestamp,
    nominal: float = NOMINAL_CAPITAL,
) -> AgmMonthlySummary:
    """
    Derive the monthly Performance Summary from the accepted daily models.

    accounting_table : algominds_daily_accounting table (Date/client_net_value/...).
    crystallized     : algominds_daily_fees month-end crystallizations
                       ([{"month": "YYYY-MM", "fee": float}, ...]).
    spx_df / ndx_df  : algominds_benchmark_daily frames (Date/Close).
    """
    empty = AgmMonthlySummary(table=pd.DataFrame(columns=SUMMARY_COLUMNS))
    if accounting_table is None or accounting_table.empty:
        return empty

    inception = pd.Timestamp(inception).normalize()
    acct = accounting_table[accounting_table["Date"] >= inception].reset_index(drop=True)
    if acct.empty:
        return empty

    fee_by_month = {c["month"]: float(c["fee"]) for c in (crystallized or [])}
    spx = _month_close_series(spx_df)
    ndx = _month_close_series(ndx_df)

    periods = acct["Date"].dt.to_period("M")
    ordered_periods = list(periods.drop_duplicates())
    # A month is complete only when a later balance date exists in a newer
    # month — the file's final, in-progress month never becomes a row.
    complete_periods = ordered_periods[:-1]
    if not complete_periods:
        return empty

    starting_capital = float(acct["client_net_value"].iloc[0])

    rows = []
    prev_bot_end = starting_capital
    prev_spx_end = _close_on(spx, inception)
    prev_ndx_end = _close_on(ndx, inception)
    for period in complete_periods:
        month_rows = acct[periods == period]
        bot_end = float(month_rows["client_net_value"].iloc[-1])
        fee = fee_by_month.get(str(period), 0.0)

        spx_start, spx_end = prev_spx_end, _month_end_close(spx, period)
        ndx_start, ndx_end = prev_ndx_end, _month_end_close(ndx, period)

        bot_net_ret = (bot_end - prev_bot_end) / nominal
        bot_fees_pct = fee / nominal
        rows.append({
            "date": period.to_timestamp(),  # month stub, like the workbook
            "spx_start": spx_start,
            "spx_end": spx_end,
            "ndx_start": ndx_start,
            "ndx_end": ndx_end,
            "bot_start": prev_bot_end,
            "bot_end_after_fees": bot_end,
            "spx_ret": (spx_end / spx_start - 1.0) if pd.notna(spx_start) and pd.notna(spx_end) and spx_start else float("nan"),
            "ndx_ret": (ndx_end / ndx_start - 1.0) if pd.notna(ndx_start) and pd.notna(ndx_end) and ndx_start else float("nan"),
            "bot_gross_ret": bot_net_ret + bot_fees_pct,
            "bot_fees_pct": bot_fees_pct,
            "bot_net_ret": bot_net_ret,
            "cumulative_net": (bot_end - starting_capital) / nominal,
        })
        prev_bot_end = bot_end
        if pd.notna(spx_end):
            prev_spx_end = spx_end
        if pd.notna(ndx_end):
            prev_ndx_end = ndx_end

    table = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    table["date"] = pd.to_datetime(table["date"])

    def _col_sum(col: str) -> float:
        return float(table[col].fillna(0.0).sum())

    totals = {
        "spx_net_pct": _col_sum("spx_ret"),
        "ndx_net_pct": _col_sum("ndx_ret"),
        "bot_gross_pct": _col_sum("bot_gross_ret"),
        "bot_fees_pct": _col_sum("bot_fees_pct"),
        "bot_net_pct": _col_sum("bot_net_ret"),
    }
    totals.update({
        "spx_net_dollar": totals["spx_net_pct"] * nominal,
        "ndx_net_dollar": totals["ndx_net_pct"] * nominal,
        "bot_gross_dollar": totals["bot_gross_pct"] * nominal,
        "bot_fees_dollar": totals["bot_fees_pct"] * nominal,
        "bot_net_dollar": totals["bot_net_pct"] * nominal,
    })
    return AgmMonthlySummary(table=table, totals=totals)
