"""Tests for Algominds v2 account profiles."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_accounts as accounts

D = Decimal


def test_prop_account_profile() -> None:
    profile = accounts.AccountProfile(
        account_slug="prop",
        display_name="Proprietary Aggregate",
        inception_date=date(2025, 11, 1),
        benchmark_base=D("30000"),
        starting_spx=D("6737.49"),
        starting_balance=D("30000"),
        is_default=True,
    )
    assert profile.account_slug == "prop"
    assert profile.fee_schedule_id == accounts.DEFAULT_FEE_SCHEDULE_ID


def test_acct_60k_profile() -> None:
    profile = accounts.AccountProfile(
        account_slug="acct-60k",
        display_name="60k Benchmark Account",
        inception_date=date(2026, 1, 1),
        benchmark_base=D("60000"),
        starting_spx=D("7408.5"),
        starting_balance=D("60000"),
    )
    assert profile.benchmark_base == D("60000")


def test_different_inception_and_starting_spx() -> None:
    early = accounts.AccountProfile(
        account_slug="prop",
        display_name="Prop",
        inception_date=date(2025, 11, 1),
        benchmark_base=D("30000"),
        starting_spx=D("6737.49"),
        starting_balance=D("30000"),
        is_default=True,
    )
    later = accounts.AccountProfile(
        account_slug="acct-midmonth-2026-05",
        display_name="Mid-month Inception",
        inception_date=date(2026, 5, 15),
        benchmark_base=D("30000"),
        starting_spx=D("7365.12"),
        starting_balance=D("30000"),
    )
    assert early.starting_spx != later.starting_spx
    assert early.inception_date < later.inception_date


@pytest.mark.parametrize(
    "slug",
    ["PROP", "prop acct", "prop/acct", "", "12345678901"],
)
def test_invalid_account_slug_rejected(slug: str) -> None:
    with pytest.raises(ValueError):
        accounts.validate_account_slug(slug)


def test_commission_rate_metadata_only() -> None:
    profile = accounts.AccountProfile(
        account_slug="client-a",
        display_name="Client A",
        inception_date=date(2026, 1, 1),
        benchmark_base=D("30000"),
        starting_spx=D("7000"),
        starting_balance=D("30000"),
        commission_rate=D("0.05"),
    )
    assert profile.commission_rate == D("0.05")


def test_forbidden_import_scan() -> None:
    source_path = Path(accounts.__file__)
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
