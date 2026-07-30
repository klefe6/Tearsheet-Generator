"""Pure helpers for Y&Q data-current labeling (monthly CSV source of truth)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Optional, Union

import pandas as pd

# Authoritative monthly CSV lives at the Tearsheet Generator repo root.
DEFAULT_REPO_ROOT_CSV = Path(r"C:\Coding Projects\Tearsheet Generator\yq.csv")


def resolve_yq_csv_path(
    *,
    env: Optional[dict] = None,
    module_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve the authoritative Y&Q CSV path.

    Precedence:
    1. ``YQ_CSV_PATH`` environment variable (explicit operator/config override)
    2. ``yq.csv`` beside the running module (when present)
    3. Repo-root ``yq.csv`` (canonical production source)
    """
    environ = env if env is not None else os.environ
    override = (environ.get("YQ_CSV_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if module_dir is not None:
        sibling = Path(module_dir) / "yq.csv"
        if sibling.is_file():
            return sibling.resolve()

    return DEFAULT_REPO_ROOT_CSV.resolve()


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
