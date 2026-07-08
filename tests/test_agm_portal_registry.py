"""Unit tests for the AGM admin Portal investor/account registry."""
from __future__ import annotations

from datetime import datetime

import algominds_portal_registry as registry


def _sample_live_kwargs() -> dict:
    return {
        "program_name": "Momentum Pacer",
        "inception_date": datetime(2025, 11, 1),
        "benchmark_base": "S&P 500 (SPX)",
        "after_fee_nlv": 45335.28,
        "month_pct": 1.23,
        "since_inception_pct_display": "49.65%",
        "last_updated": "2026-07-06",
    }


def test_registry_includes_all_listed_investors():
    names = {row["account"] for row in registry.INVESTOR_REGISTRY}
    expected = {
        "Srinivas Sundaragopal",
        "Algominds",
        "Dr. Rajeev Fernando",
        "Vishal Khemka",
        "Karthik Swaminathan",
        "Kaladhar Palaniappan",
        "Hughes & Company LLC",
        "Pratik Sharma",
        "Vikram Suman",
        "Prasad Surapaneni",
        "Tesla in the Gong Pty Ltd",
        "Ramachandran Kuppusamy",
        "Pridhiraj Ulaganathan",
    }
    assert names == expected
    assert len(registry.INVESTOR_REGISTRY) == 13


def test_account_numbers_match_exactly():
    by_name = {row["account"]: row["account_number"] for row in registry.INVESTOR_REGISTRY}
    assert by_name["Srinivas Sundaragopal"] == "210RWY45"
    assert by_name["Algominds"] == "210TGG51"
    assert by_name["Dr. Rajeev Fernando"] == "210WFP24"
    assert by_name["Vishal Khemka"] == "210WHA83"
    assert by_name["Karthik Swaminathan"] == "210WHA74"
    assert by_name["Kaladhar Palaniappan"] == "210WHE52"
    assert by_name["Hughes & Company LLC"] == "210RFQ36"
    assert by_name["Pratik Sharma"] == "210WLF36"
    assert by_name["Vikram Suman"] == "210WLW88"
    assert by_name["Prasad Surapaneni"] == "210WNX58"
    assert by_name["Tesla in the Gong Pty Ltd"] == "210WVK60"
    assert by_name["Ramachandran Kuppusamy"] == "210WVG99"
    assert by_name["Pridhiraj Ulaganathan"] == "210WVX15"


def test_algominds_account_remains_active_tearsheet_account():
    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    algominds = next(r for r in rows if r["account_number"] == "210TGG51")
    assert algominds["account"] == "Algominds"
    assert algominds["tearsheet_href"] == "/"
    assert algominds["after_fee_nlv"] == "$45,335.28"
    assert algominds["since_inception_pct"] == "49.65%"
    assert algominds["fee_tier"] == registry.EXCHANGE_FEE_NON_MEMBER


def test_fernando_and_kaladhar_have_two_units():
    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    by_name = {row["account"]: row for row in rows}
    assert by_name["Dr. Rajeev Fernando"]["units"] == 2
    assert by_name["Kaladhar Palaniappan"]["units"] == 2


def test_other_listed_investors_have_units_one():
    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    two_unit_accounts = {"Dr. Rajeev Fernando", "Kaladhar Palaniappan"}
    for row in rows:
        if row["account"] in two_unit_accounts:
            continue
        assert row["units"] == 1, row["account"]


def test_hughes_is_only_member_exchange_fee_tier():
    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    by_name = {row["account"]: row["fee_tier"] for row in rows}
    assert by_name["Hughes & Company LLC"] == registry.EXCHANGE_FEE_MEMBER
    for name, tier in by_name.items():
        if name == "Hughes & Company LLC":
            continue
        assert tier == registry.EXCHANGE_FEE_NON_MEMBER, name


def test_agm_portal_columns_omit_status():
    assert "Status" not in registry.AGM_PORTAL_COLUMNS
    assert "status" not in registry.AGM_PORTAL_ROW_FIELDS


def test_non_live_accounts_do_not_guess_financial_fields():
    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    srinivas = next(r for r in rows if r["account"] == "Srinivas Sundaragopal")
    assert srinivas["after_fee_nlv"] is None
    assert srinivas["month_pct"] is None
    assert srinivas["since_inception_pct"] is None
    assert srinivas["fee_tier"] == registry.EXCHANGE_FEE_NON_MEMBER
    assert srinivas["starting_date"] is None
    assert srinivas["benchmark_base"] is None
    assert srinivas["last_updated"] is None
    assert srinivas["tearsheet_href"] is None


def test_non_live_accounts_use_coming_soon_tearsheet_placeholder():
    from tearsheet_portal import TEARSHEET_NOT_WIRED_TEXT, _tearsheet_cell

    rows = registry.build_participating_accounts(**_sample_live_kwargs())
    srinivas = next(r for r in rows if r["account"] == "Srinivas Sundaragopal")
    assert _tearsheet_cell(srinivas) == TEARSHEET_NOT_WIRED_TEXT
