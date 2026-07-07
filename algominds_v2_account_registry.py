"""
Algominds v2 account profile registry — read-only in-code profiles for /{account_slug} URLs.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping, Tuple

from algominds_v2_accounts import AccountProfile, validate_account_slug

D = Decimal

_DEFAULT_INCEPTION = date(2026, 1, 1)
_ONE_UNIT_BENCHMARK = D("30000")
_TWO_UNIT_BENCHMARK = D("60000")
_ONE_UNIT_SPX = D("6737.49")
_TWO_UNIT_SPX = D("7408.5")


class AccountProfileNotFoundError(LookupError):
    """Raised when no registry entry matches the requested account_slug."""


def _investor_profile(
    *,
    account_slug: str,
    display_name: str,
    account_number: str,
    number_of_units: int,
    inception_date: date = _DEFAULT_INCEPTION,
    is_default: bool = False,
) -> AccountProfile:
    benchmark_base = _TWO_UNIT_BENCHMARK if number_of_units >= 2 else _ONE_UNIT_BENCHMARK
    starting_spx = _TWO_UNIT_SPX if number_of_units >= 2 else _ONE_UNIT_SPX
    exchange_fee_tier = "member" if number_of_units >= 2 else "non-member"
    return AccountProfile(
        account_slug=account_slug,
        display_name=display_name,
        account_number=account_number,
        inception_date=inception_date,
        benchmark_base=benchmark_base,
        starting_spx=starting_spx,
        starting_balance=benchmark_base,
        number_of_units=number_of_units,
        exchange_fee_tier=exchange_fee_tier,
        is_default=is_default,
    )


_PROFILES: Tuple[AccountProfile, ...] = (
    _investor_profile(
        account_slug="srinivas-sundarapandian",
        display_name="Srinivas Sundarapandian",
        account_number="210WAV45",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="algominds",
        display_name="Algominds",
        account_number="210TSG51",
        number_of_units=1,
        inception_date=date(2025, 11, 1),
        is_default=True,
    ),
    _investor_profile(
        account_slug="rajeev-fernando",
        display_name="Dr. Rajeev Fernando",
        account_number="210WAV48",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="vishal-khemka",
        display_name="Vishal Khemka",
        account_number="210WAV44",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="karthik-swaminathan",
        display_name="Karthik Swaminathan",
        account_number="210WAP24",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="kaladhar-palaniappan",
        display_name="Kaladhar Palaniappan",
        account_number="210WAN32",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="hughson-company",
        display_name="Hughson & Company LLC",
        account_number="210WAN24",
        number_of_units=2,
    ),
    _investor_profile(
        account_slug="pratik-sharma",
        display_name="Pratik Sharma",
        account_number="210WAD52",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="vikram-suman",
        display_name="Vikram Suman",
        account_number="210WAD38",
        number_of_units=2,
    ),
    _investor_profile(
        account_slug="vijay-nathan",
        display_name="Vijay Nathan",
        account_number="210WAP28",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="prasad-gumpaneni",
        display_name="Prasad Gumpaneni",
        account_number="210WAV30",
        number_of_units=2,
    ),
    _investor_profile(
        account_slug="ramachandran-kuppusamy",
        display_name="Ramachandran Kuppusamy",
        account_number="210WAV50",
        number_of_units=2,
    ),
    _investor_profile(
        account_slug="prithiviraj-ulaganathan",
        display_name="Prithiviraj Ulaganathan",
        account_number="210WAV50",
        number_of_units=2,
    ),
    _investor_profile(
        account_slug="new-investor-05",
        display_name="New Investor (05)",
        account_number="210WAV38",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="new-investor-06",
        display_name="New Investor (06)",
        account_number="210WAV10",
        number_of_units=1,
    ),
    _investor_profile(
        account_slug="tesla-in-the-sang",
        display_name="Tesla in the Sang Pty Ltd",
        account_number="210WAV30",
        number_of_units=2,
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
