"""
Algominds / Momentum Pacer — Account Stats for the public tearsheet (AGM-only).

Derives the Investor Information → Account Stats table from the same monthly
summary frame and footer totals used elsewhere on the page (derived daily
accounting pipeline when available; workbook slice only as mp_ts fallback).

Also builds the TKP/TCP-style Proprietary | Client program account-stats
rows from AGM_PROGRAM_BUCKET_CONFIG (program-level counts including closed
tranches; not derivable from the open-account registry alone).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from algominds_daily_fees import NOMINAL_CAPITAL
from program_account_stats import (
    NA_DISPLAY,
    PROGRAM_ACCOUNT_STAT_LABELS,
    ProgramAccountStats,
    ProgramBucketStats,
    format_program_account_stats_rows,
)

# Public NAV chart title — matches TKP wording; not annualized / audited.
NAV_SINCE_INCEPTION_CHART_TITLE = "<u>Non-Compounded NAV Since Inception</u>"

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


@dataclass(frozen=True)
class AgmProgramBucketConfig:
    """Program-level account/tranche stats for one Proprietary or Client column."""

    tranches_opened: int
    tranches_currently_open: int
    closed_profitably: int
    closed_unprofitably: int
    # None → display N/A (no closed accounts in this bucket).
    closed_return_range: Optional[str] = None


# Program-level facts for the client-facing Account Stats table.
# INVESTOR_REGISTRY lists only currently participating accounts (portal board);
# it does not include closed tranches, so opened/current/closed counts live here.
# TODO: replace with a closed-tranche ledger when that source exists.
AGM_PROGRAM_BUCKET_CONFIG: Dict[str, AgmProgramBucketConfig] = {
    "proprietary": AgmProgramBucketConfig(
        tranches_opened=5,
        tranches_currently_open=5,
        closed_profitably=0,
        closed_unprofitably=0,
        closed_return_range=None,
    ),
    "client": AgmProgramBucketConfig(
        tranches_opened=7,
        tranches_currently_open=6,
        closed_profitably=1,
        closed_unprofitably=0,
        closed_return_range="0–1%",
    ),
}


@dataclass(frozen=True)
class AgmProgramBucketStats(ProgramBucketStats):
    """AGM program bucket — alias of shared ProgramBucketStats."""


@dataclass(frozen=True)
class AgmProgramAccountStats(ProgramAccountStats):
    """AGM program stats with derived Total (see program_account_stats)."""


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


def _bucket_from_config(
    config: AgmProgramBucketConfig,
    *,
    nominal_per_unit: float,
) -> AgmProgramBucketStats:
    return AgmProgramBucketStats(
        nominal_assets=float(config.tranches_opened) * float(nominal_per_unit),
        total_opened=config.tranches_opened,
        currently_open=config.tranches_currently_open,
        closed_profitably=config.closed_profitably,
        closed_unprofitably=config.closed_unprofitably,
        closed_return_range=config.closed_return_range,
    )


def compute_agm_program_account_stats(
    registry_entries: Iterable[Mapping] | None = None,
    *,
    proprietary_account_number: str = "",
    nominal_per_unit: float = NOMINAL_CAPITAL,
) -> AgmProgramAccountStats:
    """
    Build TKP-style Proprietary | Client program stats for the tearsheet table.

    Counts come from AGM_PROGRAM_BUCKET_CONFIG (includes closed tranches).
    registry_entries / proprietary_account_number are accepted for call-site
    stability but are not used until a closed-tranche ledger is wired.
    Nominal assets = tranches_opened × nominal_per_unit ($30k per tranche).
    """
    del registry_entries, proprietary_account_number
    prop_cfg = AGM_PROGRAM_BUCKET_CONFIG["proprietary"]
    client_cfg = AGM_PROGRAM_BUCKET_CONFIG["client"]
    return AgmProgramAccountStats(
        proprietary=_bucket_from_config(prop_cfg, nominal_per_unit=nominal_per_unit),
        client=_bucket_from_config(client_cfg, nominal_per_unit=nominal_per_unit),
    )


def format_agm_program_account_stats(
    stats: AgmProgramAccountStats,
) -> List[Tuple[str, str, str, str]]:
    """Rows of (label, total, client, proprietary) for the HTML table."""
    return format_program_account_stats_rows(stats, include_total=True)
