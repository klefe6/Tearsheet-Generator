"""Tests for Algominds v2 account profile registry."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_account_registry as registry
import algominds_v2_daily_source as daily_source

D = Decimal
TOLERANCE = D("0.01")


def test_list_account_profiles_returns_all_investors() -> None:
    profiles = registry.list_account_profiles()
    slugs = {profile.account_slug for profile in profiles}
    assert len(slugs) == 16
    assert "algominds" in slugs
    assert "vikram-suman" in slugs


def test_get_account_profile_algominds() -> None:
    profile = registry.get_account_profile("algominds")
    assert profile.account_slug == "algominds"
    assert profile.display_name == "Algominds"
    assert profile.account_number == "210TSG51"


def test_get_account_profile_vikram_suman() -> None:
    profile = registry.get_account_profile("vikram-suman")
    assert profile.account_slug == "vikram-suman"
    assert profile.benchmark_base == D("60000")
    assert profile.account_number == "210WAD38"


def test_unknown_slug_raises_clear_error() -> None:
    with pytest.raises(registry.AccountProfileNotFoundError, match="unknown account_slug: 'client-a'"):
        registry.get_account_profile("client-a")


@pytest.mark.parametrize("slug", ["PROP", "prop acct", "prop/acct", "", "12345678901"])
def test_invalid_slug_raises_clear_error(slug: str) -> None:
    with pytest.raises(ValueError):
        registry.get_account_profile(slug)


def test_exactly_one_default_account_exists() -> None:
    defaults = [profile for profile in registry.list_account_profiles() if profile.is_default]
    assert len(defaults) == 1


def test_default_account_is_algominds() -> None:
    assert registry.get_default_account_profile().account_slug == "algominds"


def test_all_registry_slugs_validate() -> None:
    from algominds_v2_accounts import validate_account_slug

    for profile in registry.list_account_profiles():
        assert validate_account_slug(profile.account_slug) == profile.account_slug


def test_profiles_have_per_account_benchmark_base() -> None:
    by_slug = {profile.account_slug: profile for profile in registry.list_account_profiles()}
    assert by_slug["algominds"].benchmark_base == D("30000")
    assert by_slug["vikram-suman"].benchmark_base == D("60000")


def test_vikram_suman_benchmark_base_is_60000() -> None:
    assert registry.get_account_profile("vikram-suman").benchmark_base == D("60000")


def test_algominds_profile_settings() -> None:
    profile = registry.get_account_profile("algominds")
    assert profile.number_of_units == 1
    assert profile.exchange_fee_tier == "non-member"
    assert profile.benchmark_base == D("30000")


def test_vikram_suman_profile_settings() -> None:
    profile = registry.get_account_profile("vikram-suman")
    assert profile.number_of_units == 2
    assert profile.exchange_fee_tier == "member"
    assert profile.benchmark_base == D("60000")


def test_registry_output_is_immutable() -> None:
    profiles = registry.list_account_profiles()
    assert isinstance(profiles, tuple)
    with pytest.raises(TypeError):
        profiles[0] = registry.get_account_profile("algominds")  # type: ignore[index]
    assert registry.get_account_profile("algominds").account_slug == "algominds"


def test_no_private_account_number_like_slugs() -> None:
    for profile in registry.list_account_profiles():
        digits_only = profile.account_slug.replace("-", "")
        assert not (digits_only.isdigit() and len(digits_only) >= 8)


def test_forbidden_import_scan() -> None:
    source_path = Path(registry.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "dash",
        "flask",
        "openpyxl",
        "pandas",
        "tkp_ts",
        "tcp_ts",
        "mp_ts",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots


def test_build_fee_snapshot_for_account_slug_algominds() -> None:
    snapshot = daily_source.build_fee_snapshot_for_account_slug(
        "algominds",
        daily_source.DailyBalanceRow(
            account_slug="algominds",
            as_of_date=date(2026, 5, 31),
            account_balance=D("50125.21"),
            fee_removal=D("0"),
            source_label="manual-entry",
        ),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("44483.423270"),
    )
    assert snapshot.benchmark_base == D("30000")


def test_build_fee_snapshot_for_account_slug_vikram_suman() -> None:
    snapshot = daily_source.build_fee_snapshot_for_account_slug(
        "vikram-suman",
        daily_source.DailyBalanceRow(
            account_slug="vikram-suman",
            as_of_date=date(2026, 5, 31),
            account_balance=D("60868.19"),
            fee_removal=D("0"),
            source_label="manual-entry",
        ),
        spx_start=D("7408.5"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("60000"),
    )
    assert snapshot.benchmark_base == D("60000")


def test_compute_by_account_slug_rejects_row_profile_slug_mismatch() -> None:
    with pytest.raises(ValueError, match="account_slug must match"):
        daily_source.compute_daily_fee_result_for_account_slug(
            "algominds",
            daily_source.DailyBalanceRow(
                account_slug="vikram-suman",
                as_of_date=date(2026, 5, 31),
                account_balance=D("100"),
                fee_removal=D("0"),
                source_label="x",
            ),
            spx_start=D("100"),
            spx_end=D("110"),
            prior_high_water_mark=D("0"),
        )


def test_algominds_may_2026_fee_via_account_slug() -> None:
    result = daily_source.compute_daily_fee_result_for_account_slug(
        "algominds",
        daily_source.DailyBalanceRow(
            account_slug="algominds",
            as_of_date=date(2026, 5, 31),
            account_balance=D("50125.21"),
            fee_removal=D("0"),
            source_label="golden",
        ),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("44483.423270"),
    )
    assert abs(result.current_estimated_fee - D("1330.249061")) < TOLERANCE


def test_vikram_suman_fee_via_account_slug() -> None:
    result = daily_source.compute_daily_fee_result_for_account_slug(
        "vikram-suman",
        daily_source.DailyBalanceRow(
            account_slug="vikram-suman",
            as_of_date=date(2026, 5, 31),
            account_balance=D("60868.19"),
            fee_removal=D("0"),
            source_label="golden",
        ),
        spx_start=D("7408.5"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("60000"),
    )
    assert abs(result.current_estimated_fee - D("86.819")) < TOLERANCE
