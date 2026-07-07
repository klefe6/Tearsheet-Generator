"""Tests for Algominds v2 daily balance data source."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_accounts as accounts
import algominds_v2_daily_source as daily_source

D = Decimal
TOLERANCE = D("0.01")


def _prop_profile() -> accounts.AccountProfile:
    return accounts.AccountProfile(
        account_slug="algominds",
        display_name="Algominds",
        account_number="210TSG51",
        inception_date=date(2025, 11, 1),
        benchmark_base=D("30000"),
        starting_spx=D("6737.49"),
        starting_balance=D("30000"),
        number_of_units=1,
        exchange_fee_tier="non-member",
        is_default=True,
    )


def _acct_60k_profile() -> accounts.AccountProfile:
    return accounts.AccountProfile(
        account_slug="vikram-suman",
        display_name="Vikram Suman",
        account_number="210WAD38",
        inception_date=date(2026, 1, 1),
        benchmark_base=D("60000"),
        starting_spx=D("7408.5"),
        starting_balance=D("60000"),
        number_of_units=2,
        exchange_fee_tier="member",
    )


def test_valid_daily_row() -> None:
    row = daily_source.DailyBalanceRow(
        account_slug="algominds",
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        source_label="manual-entry",
    )
    assert row.account_balance == D("50125.21")


@pytest.mark.parametrize(
    "balance,removal,match",
    [
        (D("-1"), D("0"), "account_balance"),
        (D("100"), D("-1"), "fee_removal"),
        (D("100"), D("200"), "account_balance must be >= fee_removal"),
    ],
)
def test_daily_row_validation_rejected(balance: Decimal, removal: Decimal, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        daily_source.DailyBalanceRow(
            account_slug="algominds",
            as_of_date=date(2026, 5, 31),
            account_balance=balance,
            fee_removal=removal,
            source_label="manual-entry",
        )


def test_invalid_account_slug_on_row_rejected() -> None:
    with pytest.raises(ValueError):
        daily_source.DailyBalanceRow(
            account_slug="Bad Slug",
            as_of_date=date(2026, 5, 31),
            account_balance=D("100"),
            fee_removal=D("0"),
            source_label="manual-entry",
        )


def test_build_snapshot_from_prop_row() -> None:
    profile = _prop_profile()
    row = daily_source.DailyBalanceRow(
        account_slug="algominds",
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        source_label="manual-entry",
    )
    snapshot = daily_source.build_fee_snapshot(
        profile,
        row,
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("44483.423270"),
    )
    assert snapshot.benchmark_base == D("30000")
    assert snapshot.account_balance == row.account_balance
    assert snapshot.account_slug == "algominds"


def test_build_snapshot_from_60k_account() -> None:
    profile = _acct_60k_profile()
    row = daily_source.DailyBalanceRow(
        account_slug="vikram-suman",
        as_of_date=date(2026, 5, 31),
        account_balance=D("60868.19"),
        fee_removal=D("0"),
        source_label="manual-entry",
    )
    snapshot = daily_source.build_fee_snapshot(
        profile,
        row,
        spx_start=D("7408.5"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("60000"),
    )
    assert snapshot.benchmark_base == D("60000")
    assert snapshot.account_slug == "vikram-suman"


def test_different_starting_spx_by_profile() -> None:
    prop = _prop_profile()
    midmonth = accounts.AccountProfile(
        account_slug="acct-midmonth-2026-05",
        display_name="Mid-month Inception",
        account_number="210WAV99",
        inception_date=date(2026, 5, 15),
        benchmark_base=D("30000"),
        starting_spx=D("7365.12"),
        starting_balance=D("30000"),
        number_of_units=1,
        exchange_fee_tier="non-member",
    )
    assert prop.starting_spx == D("6737.49")
    assert midmonth.starting_spx == D("7365.12")


def test_built_snapshot_computes_through_fee_snapshot() -> None:
    profile = _prop_profile()
    row = daily_source.DailyBalanceRow(
        account_slug="algominds",
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        source_label="manual-entry",
    )
    result = daily_source.compute_daily_fee_result(
        profile,
        row,
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        prior_high_water_mark=D("44483.423270"),
    )
    assert abs(result.current_estimated_fee - D("1330.249061")) < TOLERANCE


def test_may_2026_prop_like_fee() -> None:
    result = daily_source.compute_daily_fee_result(
        _prop_profile(),
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


def test_acct_60k_expected_fee() -> None:
    result = daily_source.compute_daily_fee_result(
        _acct_60k_profile(),
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


def test_profile_row_slug_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="account_slug must match"):
        daily_source.build_fee_snapshot(
            _prop_profile(),
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


def test_build_fee_snapshot_for_account_slug_sets_identity() -> None:
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
    assert snapshot.account_slug == "algominds"


def test_forbidden_import_scan() -> None:
    source_path = Path(daily_source.__file__)
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
