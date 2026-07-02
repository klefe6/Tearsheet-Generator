"""
Pure TCP dashboard recomputation for TCP v2.

Side-effect free: no Dash, Flask, JSON persistence, or workbook I/O on import.
"""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import pandas as pd
import plotly.graph_objs as go

from tcp_ledger import LedgerRecord

PRIMARY_COLOR = "#0D3562"
GREY_BG = "#EBEBEB"
WHITE_BG = "#ffffff"
STRATEGY_NAME = "TCP"

MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

METRIC_LABELS = [
    "Cumulative Return",
    "Annualized Return",
    "Avg Daily Return",
    "Number of Trading Days",
    "% Winning Days",
    "% Losing Days",
    "Best 3 Days",
    "Worst 3 Days",
]

LABEL_HEADER = "Data current to"
LABEL_UNAVAILABLE = "Data unavailable"
LABEL_DATE_SUFFIX = " close"


class TCPDashboardError(Exception):
    """Base dashboard error."""


class EmptyLedgerError(TCPDashboardError):
    """No canonical NAV records supplied."""


class DuplicateCanonicalDate(TCPDashboardError):
    """Duplicate completed Date in canonical records."""


class InvalidCanonicalNAV(TCPDashboardError):
    """NAV is missing or non-finite."""


class NonChronologicalCanonicalDate(TCPDashboardError):
    """Canonical records are not in ascending date order."""


@dataclass(frozen=True)
class CurrentDataLabels:
    header: str
    date_line: str
    source_date: Optional[date]


@dataclass(frozen=True)
class DashboardPropagation:
    canonical_records: List[Dict[str, Any]]
    monthly_calendar: pd.DataFrame
    daily_performance: pd.DataFrame
    nav_figure: go.Figure
    desktop_label: CurrentDataLabels
    mobile_label: CurrentDataLabels
    latest_date: Optional[date]
    latest_nav: Optional[float]
    baseline_nav: Optional[float]
    nav_point_count: int


def _coerce_row_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise InvalidCanonicalNAV(f"Invalid Date value: {value!r}")


def _coerce_nav(value: Any) -> float:
    if value is None:
        raise InvalidCanonicalNAV("NAV is required")
    try:
        nav = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidCanonicalNAV(f"Invalid NAV value: {value!r}") from exc
    if not math.isfinite(nav):
        raise InvalidCanonicalNAV(f"NAV must be finite, got {value!r}")
    return nav


def _record_fields(record: Union[LedgerRecord, Mapping[str, Any]]) -> Mapping[str, Any]:
    if isinstance(record, LedgerRecord):
        return record.fields
    return record


def canonical_nav_records_from_ledger(
    records: Sequence[Union[LedgerRecord, Mapping[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Build canonical Date/NAV records from ledger rows.

    Internal daily returns use decimal representation (0.01 == 1%).
    Monthly table values use percentage points (4.58 == 4.58%).
    """
    canonical: List[Dict[str, Any]] = []
    seen_dates: set[date] = set()
    previous_date: Optional[date] = None

    for record in records:
        fields = _record_fields(record)
        row_date = _coerce_row_date(fields.get("Date"))
        if row_date in seen_dates:
            raise DuplicateCanonicalDate(f"Duplicate Date {row_date.isoformat()}")
        seen_dates.add(row_date)
        if previous_date is not None and row_date < previous_date:
            raise NonChronologicalCanonicalDate(
                f"Date {row_date} is out of order after {previous_date}"
            )
        previous_date = row_date
        nav = _coerce_nav(fields.get("nav-x1"))
        canonical.append({"Date": row_date.isoformat(), "NAV": nav})

    return canonical


def canonical_records_to_series(
    canonical_records: Sequence[Mapping[str, Any]],
) -> pd.Series:
    if not canonical_records:
        return pd.Series(dtype=float)
    dates = [_coerce_row_date(row["Date"]) for row in canonical_records]
    nav_values = [_coerce_nav(row["NAV"]) for row in canonical_records]
    series = pd.Series(nav_values, index=pd.to_datetime(dates))
    return series.sort_index()


def recompute_tcp_monthly_performance(
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    baseline_nav: Optional[float] = None,
) -> pd.DataFrame:
    """Rebuild TCP monthly calendar using first NAV as baseline (no legacy overrides)."""
    nav_series = canonical_records_to_series(canonical_records)
    if nav_series.empty:
        return pd.DataFrame(columns=["Year", *MONTH_LABELS, "Year Total"])

    baseline = baseline_nav if baseline_nav is not None else float(nav_series.iloc[0])
    if baseline == 0:
        raise InvalidCanonicalNAV("Baseline NAV cannot be zero")

    month_periods = nav_series.index.to_period("M")
    month_last = nav_series.groupby(month_periods).last()
    month_first = pd.Series(index=month_last.index, dtype=float)
    for period in month_last.index:
        month_start = period.start_time
        nav_before_month = nav_series[nav_series.index < month_start]
        if len(nav_before_month) > 0:
            month_first.loc[period] = float(nav_before_month.iloc[-1])
        else:
            month_first.loc[period] = baseline

    monthly_simple = (month_last - month_first) / baseline * 100.0
    yearly_simple = monthly_simple.groupby(monthly_simple.index.year).sum()

    years = sorted(monthly_simple.index.year.unique())
    monthly_data: Dict[str, List[str]] = {"Year": [str(y) for y in years]}
    for idx, month_name in enumerate(MONTH_LABELS, start=1):
        monthly_data[month_name] = []
        for year in years:
            period = pd.Period(f"{year}-{idx:02d}", freq="M")
            if period in monthly_simple.index:
                monthly_data[month_name].append(f"{monthly_simple.loc[period]:.4f}%")
            else:
                monthly_data[month_name].append("")

    monthly_data["Year Total"] = [f"{yearly_simple.get(y, 0):.4f}%" for y in years]
    return pd.DataFrame(monthly_data)


def _short_period_metrics() -> Dict[str, str]:
    return {
        "Cumulative Return": "0.0%",
        "Annualized Return": "0.0%",
        "Avg Daily Return": "0.000%",
        "Number of Trading Days": "0",
        "% Winning Days": "0 (0.0%)",
        "% Losing Days": "0 (0.0%)",
        "Best 3 Days": "0.00%, 0.00%, 0.00%",
        "Worst 3 Days": "0.00%, 0.00%, 0.00%",
    }


def calculate_period_metrics(
    returns: pd.Series,
    start_date: pd.Timestamp,
) -> Dict[str, str]:
    """
    TCP non-compounded daily metrics.

    Daily returns are decimal fractions; displayed values multiply by 100.
    Annualization uses 365 calendar days. No risk-free rate. No Sharpe ratio.
    Zero-return days are neither wins nor losses.
    """
    if len(returns) < 2:
        return _short_period_metrics()

    cum = float(returns.sum())
    days = len(returns)
    span_days = (returns.index.max() - start_date).days
    annualized = cum if span_days == 0 else cum * 365.0 / span_days
    avg = float(returns.mean())

    wins = int((returns > 0).sum())
    losses = int((returns < 0).sum())

    top3 = returns.nlargest(3) * 100.0
    bot3 = returns.nsmallest(3) * 100.0

    return {
        "Cumulative Return": f"{cum * 100:.1f}%",
        "Annualized Return": f"{annualized * 100:.1f}%",
        "Avg Daily Return": f"{avg * 100:.3f}%",
        "Number of Trading Days": str(days),
        "% Winning Days": f"{wins} ({wins / days * 100:.1f}%)",
        "% Losing Days": f"{losses} ({losses / days * 100:.1f}%)",
        "Best 3 Days": ", ".join(f"{v:.2f}%" for v in top3),
        "Worst 3 Days": ", ".join(f"{v:.2f}%" for v in bot3),
    }


def recompute_tcp_daily_metrics(
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    baseline_nav: Optional[float] = None,
    strategy_name: str = STRATEGY_NAME,
) -> pd.DataFrame:
    """Rebuild TCP Performance Metrics table from canonical NAV records."""
    nav_series = canonical_records_to_series(canonical_records)
    if nav_series.empty:
        return pd.DataFrame(
            {
                "Metric": METRIC_LABELS,
                f"{strategy_name} (1 Year/TTM)": [
                    _short_period_metrics()[m] for m in METRIC_LABELS
                ],
                f"{strategy_name} (Inception)": [
                    _short_period_metrics()[m] for m in METRIC_LABELS
                ],
            }
        )

    baseline = baseline_nav if baseline_nav is not None else float(nav_series.iloc[0])
    if baseline == 0:
        raise InvalidCanonicalNAV("Baseline NAV cannot be zero")

    daily_returns = nav_series.diff().div(baseline).dropna()
    inception_start = nav_series.index.min()
    ttm_start = nav_series.index.max() - pd.DateOffset(years=1)

    one_year_returns = daily_returns.loc[ttm_start:].dropna()
    inception_returns = daily_returns.copy()

    one_year_metrics = calculate_period_metrics(one_year_returns, ttm_start)
    inception_metrics = calculate_period_metrics(inception_returns, inception_start)

    return pd.DataFrame(
        {
            "Metric": METRIC_LABELS,
            f"{strategy_name} (1 Year/TTM)": [one_year_metrics[m] for m in METRIC_LABELS],
            f"{strategy_name} (Inception)": [inception_metrics[m] for m in METRIC_LABELS],
        }
    )


def build_tcp_nav_figure(
    canonical_records: Sequence[Mapping[str, Any]],
    *,
    show_percentage_axis: bool = False,
) -> go.Figure:
    """Build TCP NAV chart from canonical records (no benchmark trace, no % axis by default)."""
    if show_percentage_axis:
        raise ValueError("TCP percentage NAV axis is out of scope for Step 7")

    nav_series = canonical_records_to_series(canonical_records)
    if nav_series.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No NAV data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        fig.update_layout(
            title={
                "text": "<u>Non-Compounded NAV Since Inception</u>",
                "x": 0.5,
                "xanchor": "center",
            },
            template="ggplot2",
            plot_bgcolor=GREY_BG,
            paper_bgcolor=WHITE_BG,
            xaxis_title="Date",
            yaxis_title="NAV",
        )
        return fig

    fig = go.Figure(
        go.Scatter(
            x=nav_series.index,
            y=nav_series.values,
            mode="lines",
            line={"color": PRIMARY_COLOR},
            name="NAV",
            hovertemplate="Date=%{x|%Y-%m-%d}<br>NAV=%{y:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={
            "text": "<u>Non-Compounded NAV Since Inception</u>",
            "x": 0.5,
            "xanchor": "center",
        },
        template="ggplot2",
        plot_bgcolor=GREY_BG,
        paper_bgcolor=WHITE_BG,
        xaxis_title="Date",
        yaxis_title="NAV",
        autosize=True,
        margin={"l": 40, "r": 10, "t": 40, "b": 40},
    )
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    return fig


def _format_label_date(row_date: date) -> str:
    return f"{row_date.strftime('%B %d, %Y')}{LABEL_DATE_SUFFIX}"


def build_tcp_current_data_labels(
    canonical_records: Sequence[Mapping[str, Any]],
) -> CurrentDataLabels:
    """Desktop and mobile labels share the same latest completed ledger date."""
    if not canonical_records:
        return CurrentDataLabels(
            header=LABEL_UNAVAILABLE,
            date_line="",
            source_date=None,
        )

    latest = _coerce_row_date(canonical_records[-1]["Date"])
    date_line = _format_label_date(latest)
    return CurrentDataLabels(header=LABEL_HEADER, date_line=date_line, source_date=latest)


def propagate_tcp_dashboard(
    canonical_records: Sequence[Mapping[str, Any]],
) -> DashboardPropagation:
    """Recompute all Step 7 dynamic outputs from one canonical NAV snapshot."""
    records_copy = deepcopy(list(canonical_records))
    nav_series = canonical_records_to_series(records_copy)
    baseline = float(nav_series.iloc[0]) if not nav_series.empty else None
    latest_date = _coerce_row_date(records_copy[-1]["Date"]) if records_copy else None
    latest_nav = _coerce_nav(records_copy[-1]["NAV"]) if records_copy else None
    labels = build_tcp_current_data_labels(records_copy)

    return DashboardPropagation(
        canonical_records=records_copy,
        monthly_calendar=recompute_tcp_monthly_performance(records_copy, baseline_nav=baseline),
        daily_performance=recompute_tcp_daily_metrics(records_copy, baseline_nav=baseline),
        nav_figure=build_tcp_nav_figure(records_copy),
        desktop_label=labels,
        mobile_label=labels,
        latest_date=latest_date,
        latest_nav=latest_nav,
        baseline_nav=baseline,
        nav_point_count=len(records_copy),
    )
