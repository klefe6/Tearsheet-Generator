"""
Algominds / Momentum Pacer — Account Stats for the public tearsheet (AGM-only).

Derives the Investor Information → Account Stats table from the same monthly
summary frame and footer totals used elsewhere on the page (derived daily
accounting pipeline when available; workbook slice only as mp_ts fallback).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from algominds_daily_fees import NOMINAL_CAPITAL

# Public NAV chart title — must not claim compounded / annualized / audited.
NAV_SINCE_INCEPTION_CHART_TITLE = "<u>NAV Since Inception</u>"

DAYS_PER_MONTH_APPROX = 365.25 / 12.0


@dataclass(frozen=True)
class AgmAccountStats:
    starting_capital: float
    current_nav_after_fees: float
    total_net_gain: float
    total_fees_paid: float
    inception_date: datetime
    latest_report_date: datetime
    months_trading_approx: float


def months_trading_elapsed_approx(
    inception: datetime,
    latest_report_date: datetime,
    *,
    days_per_month: float = DAYS_PER_MONTH_APPROX,
) -> float:
    """Decimal months from live inception to the latest summary report date."""
    start = pd.Timestamp(inception).normalize().to_pydatetime()
    end = pd.Timestamp(latest_report_date).normalize().to_pydatetime()
    delta = end - start
    if delta.days <= 0:
        return 0.0
    return round(delta.days / days_per_month, 1)


def compute_agm_account_stats(
    display_summary_df: pd.DataFrame,
    net_totals: Dict[str, float],
    inception: datetime,
    *,
    nominal_capital: float = NOMINAL_CAPITAL,
) -> Optional[AgmAccountStats]:
    """
    Build Account Stats from the displayed monthly summary and footer totals.

    Conventions (match algominds_monthly_summary / workbook):
      - Starting capital: first displayed row's bot_start (inception account value).
      - Current NAV: last row's bot_end_after_fees.
      - Total net gain / fees: footer Net$ fields (cashflow-aware monthly chain).
    """
    if display_summary_df is None or display_summary_df.empty or not net_totals:
        return None

    df = display_summary_df.sort_values("date").reset_index(drop=True)
    starting = float(df["bot_start"].iloc[0])
    current_nav = float(df["bot_end_after_fees"].iloc[-1])
    latest_report = pd.Timestamp(df["date"].max()).to_pydatetime()

    total_net_gain = float(net_totals.get("bot_net_dollar", 0.0))
    total_fees_paid = float(net_totals.get("bot_fees_dollar", 0.0))
    months = months_trading_elapsed_approx(inception, latest_report)

    return AgmAccountStats(
        starting_capital=starting,
        current_nav_after_fees=current_nav,
        total_net_gain=total_net_gain,
        total_fees_paid=total_fees_paid,
        inception_date=inception,
        latest_report_date=latest_report,
        months_trading_approx=months,
    )


def format_agm_account_stats(stats: AgmAccountStats) -> Dict[str, str]:
    """Display-ready strings for the Account Stats table."""
    return {
        "starting_capital": f"${stats.starting_capital:,.0f}",
        "current_nav_after_fees": f"${stats.current_nav_after_fees:,.2f}",
        "total_net_gain": f"${stats.total_net_gain:,.2f}",
        "total_fees_paid": f"${stats.total_fees_paid:,.2f}",
        "inception_date": stats.inception_date.strftime("%B %d, %Y"),
        "months_trading_approx": f"{stats.months_trading_approx:.1f}",
    }
