"""
Algominds v2 account profiles — multi-account metadata for future /{account_slug} URLs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

DEFAULT_FEE_SCHEDULE_ID = "algominds-tiered-spx-relative"

_ACCOUNT_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class AccountProfile:
    account_slug: str
    display_name: str
    inception_date: date
    benchmark_base: Decimal
    starting_spx: Decimal
    starting_balance: Decimal
    fee_schedule_id: str = DEFAULT_FEE_SCHEDULE_ID
    commission_rate: Optional[Decimal] = None
    is_default: bool = False

    def __post_init__(self) -> None:
        validate_account_slug(self.account_slug)
        if self.benchmark_base <= 0:
            raise ValueError("benchmark_base must be positive")
        if self.starting_spx <= 0:
            raise ValueError("starting_spx must be positive")
        if self.starting_balance < 0:
            raise ValueError("starting_balance must be non-negative")
        if not self.fee_schedule_id.strip():
            raise ValueError("fee_schedule_id must not be empty")
        if self.commission_rate is not None:
            if not isinstance(self.commission_rate, Decimal):
                raise TypeError("commission_rate must be Decimal or None")
            if self.commission_rate < 0:
                raise ValueError("commission_rate must be non-negative")


def validate_account_slug(slug: str) -> str:
    """Validate URL-safe account slug for future /{account_slug} routes."""
    if not isinstance(slug, str):
        raise TypeError("account_slug must be a string")
    stripped = slug.strip()
    if not stripped:
        raise ValueError("account_slug must not be empty")
    if stripped != stripped.lower():
        raise ValueError("account_slug must be lowercase")
    if "/" in stripped or " " in stripped:
        raise ValueError("account_slug must not contain slash or spaces")
    if not _ACCOUNT_SLUG_PATTERN.match(stripped):
        raise ValueError(
            "account_slug must contain only lowercase letters, numbers, and hyphens"
        )
    if _looks_like_private_account_number(stripped):
        raise ValueError("account_slug must not resemble a private account number")
    return stripped


def _looks_like_private_account_number(slug: str) -> bool:
    digits_only = slug.replace("-", "")
    return digits_only.isdigit() and len(digits_only) >= 8
