"""
Algominds v2 account profile registry — read-only in-code profiles for /{account_slug} URLs.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping, Tuple

from algominds_v2_accounts import AccountProfile, validate_account_slug

D = Decimal


class AccountProfileNotFoundError(LookupError):
    """Raised when no registry entry matches the requested account_slug."""


_PROFILES: Tuple[AccountProfile, ...] = (
    AccountProfile(
        account_slug="prop",
        display_name="Proprietary Aggregate",
        inception_date=date(2025, 11, 1),
        benchmark_base=D("30000"),
        starting_spx=D("6737.49"),
        starting_balance=D("30000"),
        is_default=True,
    ),
    AccountProfile(
        account_slug="acct-60k",
        display_name="60k Benchmark Account",
        inception_date=date(2026, 1, 1),
        benchmark_base=D("60000"),
        starting_spx=D("7408.5"),
        starting_balance=D("60000"),
    ),
)

_PROFILE_BY_SLUG: Mapping[str, AccountProfile] = {
    profile.account_slug: profile for profile in _PROFILES
}


def get_account_profile(slug: str) -> AccountProfile:
    """Return the registry profile for a validated account_slug."""
    normalized = validate_account_slug(slug)
    try:
        return _PROFILE_BY_SLUG[normalized]
    except KeyError as exc:
        raise AccountProfileNotFoundError(
            f"unknown account_slug: {normalized!r}"
        ) from exc


def list_account_profiles() -> Tuple[AccountProfile, ...]:
    """Return all registry profiles in deterministic order."""
    return _PROFILES


def get_default_account_profile() -> AccountProfile:
    """Return the single profile marked is_default=True."""
    defaults = tuple(profile for profile in _PROFILES if profile.is_default)
    if len(defaults) != 1:
        raise RuntimeError("registry must define exactly one default account profile")
    return defaults[0]
