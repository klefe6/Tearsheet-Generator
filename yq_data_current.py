"""Pure helpers for Y&Q data-current labeling (monthly CSV source of truth)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Mapping, Optional, Union

import pandas as pd

# Single source of truth for Y&Q CSV resolution lives in tearsheet_paths. This
# module re-exports it so callers/tests keep a stable import while there is only
# ONE resolver + one default literal to maintain across the codebase.
from tearsheet_paths import (
    DEFAULT_YQ_REPO_ROOT_CSV as DEFAULT_REPO_ROOT_CSV,
    resolve_yq_csv_path as _resolve_yq_csv_path,
)


def resolve_yq_csv_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    module_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve the authoritative Y&Q CSV path.

    Thin delegate to :func:`tearsheet_paths.resolve_yq_csv_path`. Precedence:
    ``YQ_CSV_PATH`` → ``HC_YQ_DATA_ROOT``/yq.csv → sibling ``yq.csv`` →
    VPS profile → repo-root ``yq.csv``. Kept here for import stability only.
    """
    return _resolve_yq_csv_path(env=env, module_dir=module_dir)


def max_valid_period(index_like) -> pd.Timestamp:
    """Return the latest valid period timestamp from a DatetimeIndex / Series."""
    idx = pd.to_datetime(pd.Index(index_like)).dropna()
    if idx.empty:
        raise ValueError("Y&Q source contains no valid periods")
    return pd.Timestamp(idx.max()).normalize()


def format_yq_data_current_label(period: Union[pd.Timestamp, date, str]) -> str:
    """Human label derived solely from the authoritative source period."""
    ts = pd.Timestamp(period)
    return f"Data current through {ts.strftime('%B %Y')}"


def format_yq_statistics_range(start_period, end_period) -> str:
    start = pd.Timestamp(start_period)
    end = pd.Timestamp(end_period)
    return (
        "Statistics calculated from actual monthly return data from "
        f"{start.strftime('%B %Y')} to {end.strftime('%B %Y')}."
    )


def expected_latest_closed_month(as_of: Optional[Union[pd.Timestamp, date]] = None) -> pd.Timestamp:
    """First day of the prior calendar month relative to ``as_of`` (default today)."""
    today = pd.Timestamp(as_of if as_of is not None else date.today()).normalize()
    first_of_this_month = today.replace(day=1)
    return (first_of_this_month - pd.offsets.MonthBegin(1)).normalize()


def yq_source_is_stale(
    period: Union[pd.Timestamp, date, str],
    *,
    as_of: Optional[Union[pd.Timestamp, date]] = None,
) -> bool:
    """True when the source max month is older than the prior closed calendar month."""
    max_period = pd.Timestamp(period).replace(day=1).normalize()
    expected = expected_latest_closed_month(as_of)
    return max_period < expected


def yq_stale_warning_text(period: Union[pd.Timestamp, date, str]) -> str:
    label = format_yq_data_current_label(period)
    return (
        f"{label}. Y&Q reports monthly; the authoritative CSV has not been "
        "updated through the latest closed calendar month."
    )
