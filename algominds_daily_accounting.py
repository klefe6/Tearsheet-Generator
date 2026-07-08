"""
Algominds / Momentum Pacer — pure daily accounting model (AGM-only).

Combines TradeStation daily balances, evidenced fee accrual, and aligned SPX
closes into one deterministic daily table and the client-performance series
needed before UI wiring.

Core invariant (every aligned row):

    actual_nlv = client_net_value + accrued_unpaid_fees

Definitions
-----------
actual_nlv           Raw TradeStation CSV "Net Worth" (never fee-adjusted).
accrued_unpaid_fees  Daily fee liability net of evidenced payments/removals
                     (``accrued_total`` from algominds_daily_fees).
client_net_value     actual_nlv - accrued_unpaid_fees

Payment/removal policy
----------------------
Only honestly detected fee events from the fee engine are applied. Missing
evidence means accrued fees carry forward — nothing is fabricated.

Safe to import: no server start, no network. Callers supply dataframes or
use ``build_agm_daily_accounting`` with optional paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

import algominds_benchmark_daily as agm_bench
import algominds_daily_balances as agm_bal
import algominds_daily_fees as agm_fees

# Re-export for callers that anchor accounting at program inception.
DEFAULT_INCEPTION = agm_fees.DEFAULT_INCEPTION

# Balance columns carried through to the daily table (when present).
BALANCE_DETAIL_COLUMNS: List[str] = [
    "Cash Balance",
    "Unrealized P/L",
    "Initial Margin Req.",
    "Maint Margin Req.",
    "Buying Power/Margin Deficit",
]


@dataclass
class AgmDailyAccounting:
    """Result of compute_agm_daily_accounting()."""

    # One row per AGM balance date, oldest→newest.
    table: pd.DataFrame
    # Evidenced fee payments/removals from the fee engine.
    payments: List[dict] = field(default_factory=list)

    @property
    def actual_nlv_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(self.table["actual_nlv"].values, index=idx, name="actual_nlv")

    @property
    def accrued_unpaid_fees_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(
            self.table["accrued_unpaid_fees"].values, index=idx, name="accrued_unpaid_fees"
        )

    @property
    def client_net_value_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(
            self.table["client_net_value"].values, index=idx, name="client_net_value"
        )

    @property
    def spx_close_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(self.table["spx_close"].values, index=idx, name="spx_close")

    @property
    def momentum_daily_pct_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(
            self.table["momentum_daily_pct"].values, index=idx, name="momentum_daily_pct"
        )

    @property
    def spx_daily_pct_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(self.table["spx_daily_pct"].values, index=idx, name="spx_daily_pct")

    @property
    def momentum_vs_spx_daily_spread_pct_series(self) -> pd.Series:
        idx = pd.DatetimeIndex(self.table["Date"])
        return pd.Series(
            self.table["momentum_vs_spx_daily_spread_pct"].values,
            index=idx,
            name="momentum_vs_spx_daily_spread_pct",
        )


def _payment_marker_series(
    dates: pd.Series,
    payments: List[dict],
) -> pd.Series:
    """NaN except on evidenced payment dates (payment amount, $)."""
    by_date: dict = {}
    for p in payments:
        dt = pd.Timestamp(p["date"]).normalize()
        by_date[dt] = float(p["amount"])
    return dates.map(lambda d: by_date.get(pd.Timestamp(d).normalize(), float("nan")))


def compute_agm_daily_accounting(
    balances_df: pd.DataFrame,
    spx_df: pd.DataFrame,
    fee_accrual: Optional[agm_fees.DailyFeeAccrual] = None,
    inception: pd.Timestamp = DEFAULT_INCEPTION,
    monthly_reference: Optional[pd.DataFrame] = None,
) -> AgmDailyAccounting:
    """
    Build the AGM daily accounting table and derived performance series.

    balances_df : algominds_daily_balances.load_daily_balances() output.
    spx_df      : algominds_benchmark_daily.load_daily_benchmark() output.
    fee_accrual : optional pre-computed accrual; computed when omitted.
    """
    empty = pd.DataFrame(
        columns=[
            "Date",
            "actual_nlv",
            "client_net_value",
            "accrued_unpaid_fees",
            "spx_close",
            "momentum_daily_pct",
            "spx_daily_pct",
            "momentum_vs_spx_daily_spread_pct",
            *BALANCE_DETAIL_COLUMNS,
            "daily_dollar",
            "daily_pct",
            "since_inception_pct",
            "fee_payment",
        ]
    )
    if balances_df is None or balances_df.empty:
        return AgmDailyAccounting(table=empty)

    bal = balances_df.sort_values("Date").reset_index(drop=True)
    inception = pd.Timestamp(inception).normalize()

    if fee_accrual is None:
        fee_accrual = agm_fees.compute_daily_fee_accrual(
            bal,
            spx_df,
            inception=inception,
            monthly_reference=monthly_reference,
        )

    fee_by_date = (
        fee_accrual.daily.set_index("Date")
        if not fee_accrual.daily.empty
        else pd.DataFrame()
    )

    spx_aligned = agm_bench.align_to_dates(spx_df, bal["Date"])

    rows = []
    for i in range(len(bal)):
        date = pd.Timestamp(bal["Date"].iloc[i])
        actual_nlv = float(bal["Net Worth"].iloc[i])

        if date >= inception and not fee_by_date.empty and date in fee_by_date.index:
            accrued = float(fee_by_date.loc[date, "accrued_total"])
        else:
            accrued = 0.0

        client_net = actual_nlv - accrued
        row = {
            "Date": date,
            "actual_nlv": actual_nlv,
            "client_net_value": client_net,
            "accrued_unpaid_fees": accrued,
            "spx_close": float(spx_aligned.iloc[i]) if pd.notna(spx_aligned.iloc[i]) else float("nan"),
        }
        for col in BALANCE_DETAIL_COLUMNS:
            row[col] = bal[col].iloc[i] if col in bal.columns else float("nan")
        rows.append(row)

    table = pd.DataFrame(rows)
    table["fee_payment"] = _payment_marker_series(table["Date"], fee_accrual.payments)

    client = table["client_net_value"].astype(float)
    spx = table["spx_close"].astype(float)

    table["momentum_daily_pct"] = agm_bal.daily_pct_change(client)
    table["spx_daily_pct"] = agm_bal.daily_pct_change(spx)
    table["momentum_vs_spx_daily_spread_pct"] = (
        table["momentum_daily_pct"] - table["spx_daily_pct"]
    )

    table["daily_dollar"] = client.diff()
    table["daily_pct"] = table["momentum_daily_pct"]
    first_client = float(client.iloc[0])
    table["since_inception_pct"] = (
        (client / first_client - 1.0) * 100.0 if first_client else pd.NA
    )

    return AgmDailyAccounting(table=table, payments=list(fee_accrual.payments))


def build_agm_daily_accounting(
    balances_path=None,
    spx_df: Optional[pd.DataFrame] = None,
    inception: pd.Timestamp = DEFAULT_INCEPTION,
    monthly_reference: Optional[pd.DataFrame] = None,
) -> AgmDailyAccounting:
    """
    Convenience loader: read balances CSV, align SPX from cache, compute table.
    """
    bal = agm_bal.load_daily_balances(balances_path)
    if bal.empty:
        return compute_agm_daily_accounting(bal, pd.DataFrame(), inception=inception)

    if spx_df is None:
        start = bal["Date"].min() - pd.Timedelta(days=45)
        end = bal["Date"].max()
        spx_df = agm_bench.load_daily_benchmark(agm_bench.SPX_TICKER, start, end)

    return compute_agm_daily_accounting(
        bal,
        spx_df,
        inception=inception,
        monthly_reference=monthly_reference,
    )


def verify_accounting_invariant(table: pd.DataFrame, tol: float = 1e-6) -> bool:
    """True when actual_nlv = client_net_value + accrued_unpaid_fees on every row."""
    if table.empty:
        return True
    lhs = table["actual_nlv"].astype(float)
    rhs = table["client_net_value"].astype(float) + table["accrued_unpaid_fees"].astype(float)
    return bool((lhs - rhs).abs().max() <= tol)
