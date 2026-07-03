"""
Pure TCP drawdown analysis — committed v1 baseline-relative methodology.

Side-effect free: no Dash, Flask, workbook, or JSON I/O.
"""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from tcp_dashboard import (
    STRATEGY_NAME,
    canonical_records_to_series,
)

US_BUSINESS_DAY = CustomBusinessDay(calendar=USFederalHolidayCalendar())

DRAWDOWN_METRIC_ORDER: Tuple[str, ...] = (
    "Depth",
    "Decline Period",
    "Recovery Period",
    "Total Duration",
    "Start Date",
    "Valley Date",
    "End Date",
)

STRATEGY_INCEPTION_COLUMN = f"{STRATEGY_NAME} (Inception)"

DRAWDOWN_FOOTNOTE = (
    "Both TCP & SPXTR drawdown stats are reflective of the same $150,000 fixed nominal "
    "exposure at start of drawdown period."
)


class TCPDrawdownError(Exception):
    """Base drawdown error."""


@dataclass(frozen=True)
class DrawdownPeriod:
    depth_decimal: float
    decline_days: int
    recovery_days_text: str
    total_duration_text: str
    start_date: str
    valley_date: str
    end_date: str
    recovered: bool

    def to_display_row(self) -> Dict[str, str]:
        return {
            "Depth": f"{self.depth_decimal:.1f}%",
            "Decline Period": f"{self.decline_days} days",
            "Recovery Period": self.recovery_days_text,
            "Total Duration": self.total_duration_text,
            "Start Date": self.start_date,
            "Valley Date": self.valley_date,
            "End Date": self.end_date,
        }


def _record_fields(record: Union[Mapping[str, Any], Any]) -> Mapping[str, Any]:
    if hasattr(record, "fields"):
        return record.fields
    return record


def normalize_drawdown_nav_records(
    records: Sequence[Mapping[str, Any]],
    *,
    business_day_forward_fill: bool = True,
) -> pd.Series:
    """
    Build a drawdown NAV series from canonical records.

    Committed v1 applies US business-day ``asfreq`` + forward-fill before drawdown.
    Canonical ledger records themselves remain sparse elsewhere in TCP v2.
    """
    if not records:
        return pd.Series(dtype=float)

    sparse = canonical_records_to_series(records)
    if sparse.empty:
        return sparse

    if sparse.index.has_duplicates:
        sparse = sparse[~sparse.index.duplicated(keep="first")]

    if not business_day_forward_fill:
        return sparse

    filled = sparse.asfreq(US_BUSINESS_DAY)
    return filled.ffill()


def worst_drawdown_profile(
    nav: pd.Series,
    *,
    baseline: Optional[float] = None,
    use_quantstats: bool = False,
    show_price: bool = False,
) -> DrawdownPeriod:
    """
    Replicate committed v1 ``drawdown_profile`` for the worst episode.

  - TCP uses baseline-relative depth: ``(nav - running_max) / baseline * 100``
  - Durations use calendar-day ``.days`` between observation timestamps
    (v1 business-day-filled index positions)
    """
    if nav.empty:
        raise TCPDrawdownError("NAV series is empty")
    if len(nav) == 1:
        only = nav.index[0]
        only_date = only.strftime("%Y-%m-%d")
        return DrawdownPeriod(
            depth_decimal=0.0,
            decline_days=0,
            recovery_days_text="0 days",
            total_duration_text="0 days",
            start_date=only_date,
            valley_date=only_date,
            end_date=only_date,
            recovered=True,
        )

    baseline_value = float(baseline if baseline is not None else nav.iloc[0])
    if baseline_value == 0:
        raise TCPDrawdownError("Baseline NAV cannot be zero")

    running_max = nav.cummax()
    if use_quantstats:
        dd_series = (nav / running_max - 1) * 100
    else:
        dd_series = (nav - running_max) / baseline_value * 100

    trough = dd_series.idxmin()
    peak = nav.loc[:trough].idxmax()

    peak_date = peak.strftime("%Y-%m-%d")
    valley_date = trough.strftime("%Y-%m-%d")

    if show_price:
        peak_str = f"{peak_date} - {nav.loc[peak]:,.2f}"
        valley_str = f"{valley_date} - {nav.loc[trough]:,.2f}"
    else:
        peak_str = peak_date
        valley_str = valley_date

    decline_days = int((trough - peak).days)
    recovered_slice = nav.loc[trough:][nav.loc[trough:] >= nav.loc[peak]]
    rec_idx = recovered_slice.index[0] if not recovered_slice.empty else None

    if rec_idx is not None:
        end_date = rec_idx.strftime("%Y-%m-%d")
        end_str = f"{end_date} - {nav.loc[rec_idx]:,.2f}" if show_price else end_date
        recovery_days = int((rec_idx - trough).days)
        total_days = int((rec_idx - peak).days)
        recovery_text = f"{recovery_days} days"
        total_text = f"{total_days} days"
        recovered = True
    else:
        last_date = nav.index.max()
        last_price = float(nav.loc[last_date])
        peak_price = float(nav.loc[peak])
        trough_price = float(nav.loc[trough])
        if show_price:
            if peak_price != trough_price:
                remaining_pct = (peak_price - last_price) / (peak_price - trough_price) * 100
            else:
                remaining_pct = 0.0
            end_str = (
                f"TBD - Current Price is {last_price:,.2f}, "
                f"{remaining_pct:.1f} % of the current drawdown is left for a full recovery"
            )
        else:
            end_str = "TBD"
        recovery_days = int((last_date - trough).days)
        total_days = int((last_date - peak).days)
        recovery_text = f"Ongoing for {recovery_days} days"
        total_text = f"Ongoing for {total_days} days"
        recovered = False

    depth = float(dd_series.min())
    if not math.isfinite(depth):
        raise TCPDrawdownError("Drawdown depth is non-finite")

    return DrawdownPeriod(
        depth_decimal=depth,
        decline_days=decline_days,
        recovery_days_text=recovery_text,
        total_duration_text=total_text,
        start_date=peak_str,
        valley_date=valley_str,
        end_date=end_str,
        recovered=recovered,
    )


def build_drawdown_summary(period: DrawdownPeriod) -> Dict[str, str]:
    return period.to_display_row()


def format_drawdown_table_records(period: DrawdownPeriod) -> pd.DataFrame:
    row = period.to_display_row()
    return pd.DataFrame(
        {
            "Metric": list(DRAWDOWN_METRIC_ORDER),
            STRATEGY_INCEPTION_COLUMN: [row[m] for m in DRAWDOWN_METRIC_ORDER],
        }
    )


def build_drawdown_dataframe(
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    business_day_forward_fill: bool = True,
) -> pd.DataFrame:
    """Return v1-shaped worst-drawdown table for TCP (Inception) only."""
    records_copy = deepcopy(list(canonical_records))
    nav = normalize_drawdown_nav_records(records_copy, business_day_forward_fill=business_day_forward_fill)
    if nav.empty:
        return pd.DataFrame(columns=["Metric", STRATEGY_INCEPTION_COLUMN])

    baseline = float(nav.iloc[0])
    period = worst_drawdown_profile(nav, baseline=baseline, use_quantstats=False, show_price=False)
    return format_drawdown_table_records(period)


def build_drawdown_series(
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    business_day_forward_fill: bool = True,
) -> pd.Series:
    nav = normalize_drawdown_nav_records(canonical_records, business_day_forward_fill=business_day_forward_fill)
    if nav.empty:
        return pd.Series(dtype=float)
    baseline = float(nav.iloc[0])
    running_max = nav.cummax()
    return (nav - running_max) / baseline * 100
