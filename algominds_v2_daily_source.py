"""
Algominds v2 daily balance data source — multi-account rows to fee snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from algominds_v2_accounts import AccountProfile, validate_account_slug
from algominds_v2_account_registry import get_account_profile
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot, compute_fee_snapshot


@dataclass(frozen=True)
class DailyBalanceRow:
    account_slug: str
    as_of_date: date
    account_balance: Decimal
    fee_removal: Decimal
    source_label: str
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        validate_account_slug(self.account_slug)
        validate_daily_balance_row(self)


def validate_daily_balance_row(row: DailyBalanceRow) -> None:
    """Validate raw daily balance inputs."""
    if not isinstance(row.account_balance, Decimal):
        raise TypeError("account_balance must be Decimal")
    if not isinstance(row.fee_removal, Decimal):
        raise TypeError("fee_removal must be Decimal")
    if row.account_balance < 0:
        raise ValueError("account_balance must be non-negative")
    if row.fee_removal < 0:
        raise ValueError("fee_removal must be non-negative")
    if row.account_balance < row.fee_removal:
        raise ValueError("account_balance must be >= fee_removal")
    if not row.source_label.strip():
        raise ValueError("source_label must not be empty")


def build_fee_snapshot(
    profile: AccountProfile,
    row: DailyBalanceRow,
    *,
    spx_start: Decimal,
    spx_end: Decimal,
    prior_high_water_mark: Decimal,
) -> AlgomindsV2FeeSnapshot:
    """
    Build a fee snapshot from account profile, daily row, and market inputs.

    account_slug is carried on the row/profile models only; the pure fee snapshot
    carries the numeric inputs required by the fee engine.
    """
    if row.account_slug != profile.account_slug:
        raise ValueError("daily row account_slug must match account profile")

    if not isinstance(spx_start, Decimal) or spx_start <= 0:
        raise ValueError("spx_start must be a positive Decimal")
    if not isinstance(spx_end, Decimal):
        raise TypeError("spx_end must be Decimal")
    if not isinstance(prior_high_water_mark, Decimal) or prior_high_water_mark < 0:
        raise ValueError("prior_high_water_mark must be a non-negative Decimal")

    return AlgomindsV2FeeSnapshot(
        as_of_date=row.as_of_date,
        account_balance=row.account_balance,
        fee_removal=row.fee_removal,
        prior_high_water_mark=prior_high_water_mark,
        spx_start=spx_start,
        spx_end=spx_end,
        benchmark_base=profile.benchmark_base,
        notes=row.notes,
    )


def compute_daily_fee_result(
    profile: AccountProfile,
    row: DailyBalanceRow,
    *,
    spx_start: Decimal,
    spx_end: Decimal,
    prior_high_water_mark: Decimal,
):
    """Build snapshot and compute fee result in one step."""
    snapshot = build_fee_snapshot(
        profile,
        row,
        spx_start=spx_start,
        spx_end=spx_end,
        prior_high_water_mark=prior_high_water_mark,
    )
    return compute_fee_snapshot(snapshot)


def build_fee_snapshot_for_account_slug(
    account_slug: str,
    row: DailyBalanceRow,
    *,
    spx_start: Decimal,
    spx_end: Decimal,
    prior_high_water_mark: Decimal,
) -> AlgomindsV2FeeSnapshot:
    """Resolve profile from registry and build a fee snapshot."""
    profile = get_account_profile(account_slug)
    return build_fee_snapshot(
        profile,
        row,
        spx_start=spx_start,
        spx_end=spx_end,
        prior_high_water_mark=prior_high_water_mark,
    )


def compute_daily_fee_result_for_account_slug(
    account_slug: str,
    row: DailyBalanceRow,
    *,
    spx_start: Decimal,
    spx_end: Decimal,
    prior_high_water_mark: Decimal,
):
    """Resolve profile from registry and compute fee result in one step."""
    profile = get_account_profile(account_slug)
    return compute_daily_fee_result(
        profile,
        row,
        spx_start=spx_start,
        spx_end=spx_end,
        prior_high_water_mark=prior_high_water_mark,
    )
