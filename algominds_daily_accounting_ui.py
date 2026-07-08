"""
Algominds / Momentum Pacer — UI-facing adapter for the daily accounting model.

Wraps ``algominds_daily_accounting`` with display column labels, row dicts for
Dash tables, and chart-ready series (including aligned/rebased NDX). Safe for
``mp_ts.py`` to import without re-implementing accounting math.

Core invariant (delegated to the pure model, never recomputed here):

    actual_nlv = client_net_value + accrued_unpaid_fees
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import pandas as pd

import algominds_benchmark_daily as agm_bench
import algominds_daily_accounting as agm_acct
import algominds_daily_balances as agm_bal
from algominds_daily_fees import NOMINAL_CAPITAL as DEFAULT_STARTING_CAPITAL

DEFAULT_INCEPTION = agm_acct.DEFAULT_INCEPTION

# Internal DataFrame column -> UI display label (stable contract for mp_ts tables).
UI_TABLE_COLUMNS: List[tuple[str, str]] = [
    ("Date", "Date"),
    ("actual_nlv", "Actual NLV / TradeStation Net Worth"),
    ("client_net_value", "Client Net Value / Net of Accrued Fees"),
    ("accrued_unpaid_fees", "Accrued Unpaid Fees"),
    ("spx_close", "SPX Close"),
    ("momentum_daily_pct", "Momentum daily %"),
    ("spx_daily_pct", "SPX daily %"),
    ("momentum_vs_spx_daily_spread_pct", "Momentum vs SPX daily spread %"),
    ("Cash Balance", "Cash Balance"),
    ("Unrealized P/L", "Unrealized P/L"),
    ("Initial Margin Req.", "Initial Margin Req."),
    ("Maint Margin Req.", "Maint Margin Req."),
    ("Buying Power/Margin Deficit", "Buying Power/Margin Deficit"),
    ("daily_dollar", "Daily $"),
    ("daily_pct", "Daily %"),
    ("since_inception_pct", "Since inception %"),
    ("fee_payment", "Fee payment"),
]

UI_TABLE_INTERNAL_KEYS: List[str] = [k for k, _ in UI_TABLE_COLUMNS]
UI_TABLE_DISPLAY_LABELS: List[str] = [label for _, label in UI_TABLE_COLUMNS]


@dataclass(frozen=True)
class AgmChartSeries:
    """Chart-ready daily series indexed by Date (post-inception slice by default)."""

    dates: pd.DatetimeIndex
    client_net_value: pd.Series
    actual_nlv: pd.Series
    accrued_unpaid_fees: pd.Series
    spx_close: pd.Series
    spx_rebased: pd.Series
    ndx_close: pd.Series
    ndx_rebased: pd.Series
    momentum_daily_pct: pd.Series
    spx_daily_pct: pd.Series
    momentum_vs_spx_daily_spread_pct: pd.Series


@dataclass
class AgmDailyAccountingUI:
    """
    UI adapter over ``AgmDailyAccounting``.

    ``table`` holds internal column names (same as the pure model).
    Use ``display_table()`` / ``table_rows()`` for Dash rendering.
    """

    accounting: agm_acct.AgmDailyAccounting
    chart: AgmChartSeries
    inception: pd.Timestamp
    starting_capital: float

    @property
    def payments(self) -> List[dict]:
        return self.accounting.payments

    @property
    def table(self) -> pd.DataFrame:
        return self.accounting.table

    def display_table(self, newest_first: bool = True) -> pd.DataFrame:
        """Accounting table with UI display column labels."""
        df = self._ordered_table(newest_first=newest_first)
        return df.rename(columns=dict(UI_TABLE_COLUMNS))

    def table_rows(self, newest_first: bool = True) -> List[dict]:
        """One dict per row keyed by UI display labels (Dash-friendly)."""
        display = self.display_table(newest_first=newest_first)
        rows: List[dict] = []
        for _, row in display.iterrows():
            out = {}
            for col in display.columns:
                val = row[col]
                if isinstance(val, pd.Timestamp):
                    out[col] = val.strftime("%Y-%m-%d")
                elif isinstance(val, float) and pd.isna(val):
                    out[col] = None
                else:
                    out[col] = val
            rows.append(out)
        return rows

    def inception_table(self, newest_first: bool = False) -> pd.DataFrame:
        """Post-inception rows only (internal column names)."""
        mask = self.table["Date"] >= self.inception
        df = self.table.loc[mask].reset_index(drop=True)
        if newest_first:
            df = df.iloc[::-1].reset_index(drop=True)
        return df

    def _ordered_table(self, newest_first: bool) -> pd.DataFrame:
        df = self.table
        if newest_first:
            df = df.iloc[::-1].reset_index(drop=True)
        return df


def _build_chart_series(
    table: pd.DataFrame,
    ndx_df: Optional[pd.DataFrame],
    inception: pd.Timestamp,
    starting_capital: float,
) -> AgmChartSeries:
    inception = pd.Timestamp(inception).normalize()
    post = table[table["Date"] >= inception].reset_index(drop=True)
    if post.empty:
        idx = pd.DatetimeIndex([], name="Date")
        nan = pd.Series(dtype=float, index=idx)
        return AgmChartSeries(
            dates=idx,
            client_net_value=nan,
            actual_nlv=nan,
            accrued_unpaid_fees=nan,
            spx_close=nan,
            spx_rebased=nan,
            ndx_close=nan,
            ndx_rebased=nan,
            momentum_daily_pct=nan,
            spx_daily_pct=nan,
            momentum_vs_spx_daily_spread_pct=nan,
        )

    dates = pd.DatetimeIndex(post["Date"])
    spx_close = pd.Series(post["spx_close"].values, index=dates, name="spx_close")
    spx_rebased = agm_bench.rebase(spx_close, starting_capital)

    if ndx_df is not None and not ndx_df.empty:
        ndx_aligned = agm_bench.align_to_dates(ndx_df, dates)
        ndx_close = pd.Series(ndx_aligned.values, index=dates, name="ndx_close")
        ndx_rebased = agm_bench.rebase(ndx_close, starting_capital)
    else:
        ndx_close = pd.Series([float("nan")] * len(dates), index=dates, name="ndx_close")
        ndx_rebased = ndx_close.copy()
        ndx_rebased.name = "ndx_rebased"

    return AgmChartSeries(
        dates=dates,
        client_net_value=pd.Series(post["client_net_value"].values, index=dates, name="client_net_value"),
        actual_nlv=pd.Series(post["actual_nlv"].values, index=dates, name="actual_nlv"),
        accrued_unpaid_fees=pd.Series(
            post["accrued_unpaid_fees"].values, index=dates, name="accrued_unpaid_fees"
        ),
        spx_close=spx_close,
        spx_rebased=spx_rebased,
        ndx_close=ndx_close,
        ndx_rebased=ndx_rebased,
        momentum_daily_pct=pd.Series(
            post["momentum_daily_pct"].values, index=dates, name="momentum_daily_pct"
        ),
        spx_daily_pct=pd.Series(post["spx_daily_pct"].values, index=dates, name="spx_daily_pct"),
        momentum_vs_spx_daily_spread_pct=pd.Series(
            post["momentum_vs_spx_daily_spread_pct"].values,
            index=dates,
            name="momentum_vs_spx_daily_spread_pct",
        ),
    )


def build_agm_daily_accounting_ui(
    accounting: agm_acct.AgmDailyAccounting,
    ndx_df: Optional[pd.DataFrame] = None,
    inception: pd.Timestamp = DEFAULT_INCEPTION,
    starting_capital: float = DEFAULT_STARTING_CAPITAL,
) -> AgmDailyAccountingUI:
    """
    Wrap a computed ``AgmDailyAccounting`` for UI consumption.

    Does not mutate *accounting* or re-run fee math.
    """
    chart = _build_chart_series(
        accounting.table,
        ndx_df=ndx_df,
        inception=inception,
        starting_capital=starting_capital,
    )
    return AgmDailyAccountingUI(
        accounting=accounting,
        chart=chart,
        inception=pd.Timestamp(inception).normalize(),
        starting_capital=float(starting_capital),
    )


def load_agm_daily_accounting_ui(
    balances_path=None,
    spx_df: Optional[pd.DataFrame] = None,
    ndx_df: Optional[pd.DataFrame] = None,
    inception: pd.Timestamp = DEFAULT_INCEPTION,
    monthly_reference: Optional[pd.DataFrame] = None,
    starting_capital: float = DEFAULT_STARTING_CAPITAL,
    fetcher=None,
) -> AgmDailyAccountingUI:
    """
    One-shot loader: balances CSV + cached benchmarks -> UI adapter.

    *fetcher* is forwarded to ``load_daily_benchmark`` when SPX/NDX frames are
    loaded from cache (tests pass a raising stub to forbid network).
    """
    bal = agm_bal.load_daily_balances(balances_path)
    if bal.empty:
        empty = agm_acct.compute_agm_daily_accounting(bal, pd.DataFrame(), inception=inception)
        return build_agm_daily_accounting_ui(
            empty,
            ndx_df=ndx_df,
            inception=inception,
            starting_capital=starting_capital,
        )

    start = bal["Date"].min() - pd.Timedelta(days=45)
    end = bal["Date"].max()
    kwargs = {}
    if fetcher is not None:
        kwargs["fetcher"] = fetcher

    if spx_df is None:
        spx_df = agm_bench.load_daily_benchmark(agm_bench.SPX_TICKER, start, end, **kwargs)
    if ndx_df is None:
        ndx_df = agm_bench.load_daily_benchmark(agm_bench.NDX_TICKER, start, end, **kwargs)

    accounting = agm_acct.compute_agm_daily_accounting(
        bal,
        spx_df,
        inception=inception,
        monthly_reference=monthly_reference,
    )
    return build_agm_daily_accounting_ui(
        accounting,
        ndx_df=ndx_df,
        inception=inception,
        starting_capital=starting_capital,
    )


def required_ui_table_labels() -> Sequence[str]:
    """Display labels the admin daily table must expose (stable UI contract)."""
    return tuple(UI_TABLE_DISPLAY_LABELS)
