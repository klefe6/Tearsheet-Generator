"""Tests for Algominds v2 pure fee engine."""
from __future__ import annotations

from decimal import Decimal

import pytest

from algominds_v2.fee_engine import (
    calculate_benchmark_dollar_return,
    calculate_slab_fee,
    crystallize_month,
)

D = Decimal
TOLERANCE = D("0.01")

# Proprietary aggregate inputs (Sri All Accts / Summary Proprietary lineage).
# Hard-coded from read-only workbook extraction; tests do not read the workbook at runtime.
GOLDEN_MONTHS = [
    {
        "month": "2025-11",
        "raw_gross": "37683.16",
        "crystallized_outstanding": "0",
        "prior_hwm": "30000",
        "spx_start": "6737.49",
        "spx_end": "6849.09",
        "expected_fee": "3344.65904",
        "expected_after_fee_nlv": "34338.50096",
        "expected_next_hwm": "34338.50096",
        "slab_fees": (
            "49.69209602",
            "99.38419204",
            "149.0762881",
            "198.7683841",
            "2847.73808",
        ),
    },
    {
        "month": "2025-12",
        "raw_gross": "31694.0",
        "crystallized_outstanding": "0",
        "prior_hwm": "34338.50096017954",
        "spx_start": "6849.09",
        "spx_end": "6845.5",
        "expected_fee": "0",
        "expected_after_fee_nlv": "31694.0",
        "expected_next_hwm": "34338.50096",
    },
    {
        "month": "2026-01",
        "raw_gross": "34654.12",
        "crystallized_outstanding": "0",
        "prior_hwm": "34338.50096017954",
        "spx_start": "6845.5",
        "spx_end": "6939.03",
        "expected_fee": "31.56190398",
        "expected_after_fee_nlv": "34622.5581",
        "expected_next_hwm": "34622.5581",
        "slab_fees": ("31.56190398", "0", "0", "0", "0"),
    },
    {
        "month": "2026-02",
        "raw_gross": "36059.74",
        "crystallized_outstanding": "0",
        "prior_hwm": "34622.5581",
        "spx_start": "6939.03",
        "spx_end": "6878.88",
        "expected_fee": "718.590952",
        "expected_after_fee_nlv": "35341.15",
        "expected_next_hwm": "35341.15",
        "slab_fees": ("0", "0", "0", "0", "718.59"),
    },
    {
        "month": "2026-03",
        "raw_gross": "33079.89",
        "crystallized_outstanding": "0",
        "prior_hwm": "35341.15",
        "spx_start": "6878.88",
        "spx_end": "6528.52",
        "expected_fee": "0",
        "expected_after_fee_nlv": "33079.89",
        "expected_next_hwm": "35341.15",
    },
    {
        "month": "2026-04",
        "raw_gross": "47451.27",
        "crystallized_outstanding": "0",
        "prior_hwm": "35341.15",
        "spx_start": "6528.52",
        "spx_end": "7209.01",
        "expected_fee": "2967.84673",
        "expected_after_fee_nlv": "44483.42365",
        "expected_next_hwm": "44483.42365",
        "slab_fees": (
            "312.7002751",
            "625.4005502",
            "938.1008253",
            "1091.644699",
            "0",
        ),
    },
    {
        "month": "2026-05",
        "raw_gross": "50125.21",
        "crystallized_outstanding": "0",
        "prior_hwm": "44483.423270",
        "spx_start": "7209.01",
        "spx_end": "7580.06",
        "benchmark_base": "30000",
        "expected_fee": "1330.249061",
        "expected_after_fee_nlv": "48794.960939",
        "expected_next_hwm": "48794.960939",
        "slab_amounts": (
            "1544.109385",
            "1544.109385",
            "1544.109385",
            "1009.458515",
            "0",
        ),
    },
    {
        "month": "2026-06",
        "raw_gross": "48049.07",
        "crystallized_outstanding": "0",
        "prior_hwm": "48794.960939",
        "spx_start": "7580.06",
        "spx_end": "7499.36",
        "benchmark_base": "30000",
        "expected_fee": "0",
        "expected_after_fee_nlv": "48049.07",
        "expected_next_hwm": "48794.960939",
    },
]

# July 2026 is excluded: placeholder month with carried SPX and carried balance.

VARIABLE_BASE_CASES = [
    {
        "case": "acct-60k-2026-05",
        "raw_gross": "60868.19",
        "crystallized_outstanding": "0",
        "prior_hwm": "60000",
        "spx_start": "7408.5",
        "spx_end": "7580.06",
        "benchmark_base": "60000",
        "expected_fee": "86.819",
        "expected_after_fee_nlv": "60781.371",
        "expected_next_hwm": "60781.371",
    },
]

INCEPTION_CASES = [
    {
        "case": "acct-midmonth-2026-05",
        "raw_gross": "32417.03",
        "crystallized_outstanding": "0",
        "prior_hwm": "30000",
        "spx_start": "7365.12",
        "spx_end": "7580.06",
        "benchmark_base": "30000",
        "expected_fee": "462.457475",
        "expected_after_fee_nlv": "31954.572525",
        "expected_next_hwm": "31954.572525",
    },
]


def _within_cent(actual: Decimal, expected: str) -> bool:
    return abs(actual - D(expected)) < TOLERANCE


def _crystallize(case: dict):
    kwargs = dict(
        raw_gross_account_balance=D(case["raw_gross"]),
        crystallized_fee_payable_outstanding=D(case["crystallized_outstanding"]),
        prior_high_water_mark=D(case["prior_hwm"]),
        spx_start=D(case["spx_start"]),
        spx_end=D(case["spx_end"]),
    )
    if "benchmark_base" in case:
        kwargs["benchmark_base"] = D(case["benchmark_base"])
    return crystallize_month(**kwargs)


@pytest.mark.parametrize("case", GOLDEN_MONTHS, ids=[c["month"] for c in GOLDEN_MONTHS])
def test_golden_month_fee_parity(case: dict) -> None:
    result = _crystallize(case)
    assert _within_cent(result.current_period_fee, case["expected_fee"])
    assert _within_cent(result.after_fee_nlv, case["expected_after_fee_nlv"])
    assert _within_cent(result.next_high_water_mark, case["expected_next_hwm"])


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN_MONTHS if "slab_fees" in c],
    ids=[c["month"] for c in GOLDEN_MONTHS if "slab_fees" in c],
)
def test_golden_slab_fee_allocation(case: dict) -> None:
    result = _crystallize(case)
    expected_fees = case["slab_fees"]
    actual_fees = (
        result.slab.slab_1_fee,
        result.slab.slab_2_fee,
        result.slab.slab_3_fee,
        result.slab.slab_4_fee,
        result.slab.slab_5_fee,
    )
    for actual, exp in zip(actual_fees, expected_fees):
        assert _within_cent(actual, exp)


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN_MONTHS if "slab_amounts" in c],
    ids=[c["month"] for c in GOLDEN_MONTHS if "slab_amounts" in c],
)
def test_golden_slab_amount_allocation(case: dict) -> None:
    result = _crystallize(case)
    expected_amounts = case["slab_amounts"]
    actual_amounts = (
        result.slab.slab_1_amount,
        result.slab.slab_2_amount,
        result.slab.slab_3_amount,
        result.slab.slab_4_amount,
        result.slab.slab_5_amount,
    )
    for actual, exp in zip(actual_amounts, expected_amounts):
        assert _within_cent(actual, exp)


@pytest.mark.parametrize("case", VARIABLE_BASE_CASES, ids=[c["case"] for c in VARIABLE_BASE_CASES])
def test_variable_benchmark_base_golden(case: dict) -> None:
    result = _crystallize(case)
    assert _within_cent(result.current_period_fee, case["expected_fee"])
    assert _within_cent(result.after_fee_nlv, case["expected_after_fee_nlv"])
    assert _within_cent(result.next_high_water_mark, case["expected_next_hwm"])


@pytest.mark.parametrize("case", INCEPTION_CASES, ids=[c["case"] for c in INCEPTION_CASES])
def test_mid_month_inception_golden(case: dict) -> None:
    result = _crystallize(case)
    assert _within_cent(result.current_period_fee, case["expected_fee"])
    assert _within_cent(result.after_fee_nlv, case["expected_after_fee_nlv"])
    assert _within_cent(result.next_high_water_mark, case["expected_next_hwm"])


def test_proprietary_spx_chain_nov_2025_through_jun_2026() -> None:
    """Each month's spx_start equals the prior month's spx_end."""
    for prior, current in zip(GOLDEN_MONTHS, GOLDEN_MONTHS[1:]):
        assert D(current["spx_start"]) == D(prior["spx_end"]), (
            f"SPX chain break between {prior['month']} and {current['month']}"
        )


def test_manual_waiver_is_not_engine_behavior() -> None:
    """Engine returns formulaic fee; operator waivers are layered on top."""
    # Workbook hazard: formula produces ~43.379 but a manual waiver hard-types zero.
    result = crystallize_month(
        D("30433.79"),
        D("0"),
        D("30000"),
        D("7408.5"),
        D("7580.06"),
        D("30000"),
    )
    assert _within_cent(result.current_period_fee, "43.379")
    assert result.current_period_fee != D("0")
    # Manual fee waivers are operator overrides layered on top of engine output.
    # The pure fee engine must not reproduce waived zero-fee rows automatically.


def test_hwm_chain_ratchet() -> None:
    for case in GOLDEN_MONTHS:
        prior = D(case["prior_hwm"])
        result = _crystallize(case)
        assert result.next_high_water_mark >= prior - TOLERANCE
        assert _within_cent(result.next_high_water_mark, case["expected_next_hwm"])


def test_benchmark_dollar_return() -> None:
    bdr = calculate_benchmark_dollar_return(D("6737.49"), D("6849.09"))
    assert _within_cent(bdr, "496.9209602")


def test_eligible_profit_below_zero_becomes_zero_fee() -> None:
    result = crystallize_month(D("30000"), D("0"), D("35000"), D("100"), D("110"))
    assert result.eligible_profit == 0
    assert result.current_period_fee == 0


def test_eligible_profit_exactly_zero() -> None:
    result = crystallize_month(D("35000"), D("0"), D("35000"), D("100"), D("110"))
    assert result.eligible_profit == 0
    assert result.current_period_fee == 0


def test_positive_bdr_five_slab_tiers() -> None:
    slab = calculate_slab_fee(D("10000"), D("1000"))
    assert slab.slab_1_amount == D("1000")
    assert slab.slab_5_amount == D("6000")
    assert slab.total_fee == (
        D("1000") * D("0.10")
        + D("1000") * D("0.20")
        + D("1000") * D("0.30")
        + D("1000") * D("0.40")
        + D("6000") * D("0.50")
    )


def test_zero_bdr_flat_fifty_percent() -> None:
    slab = calculate_slab_fee(D("1000"), D("0"))
    assert slab.slab_5_fee == D("500")
    assert slab.total_fee == D("500")


def test_negative_bdr_flat_fifty_percent() -> None:
    slab = calculate_slab_fee(D("2000"), D("-100"))
    assert slab.total_fee == D("1000")


def test_slab_one_only() -> None:
    slab = calculate_slab_fee(D("100"), D("500"))
    assert slab.slab_1_amount == D("100")
    assert slab.slab_2_amount == 0
    assert slab.total_fee == D("10")


@pytest.mark.parametrize(
    "eligible,bdr,expected_slab1",
    [
        (D("1000"), D("1000"), D("1000")),
        (D("2000"), D("1000"), D("1000")),
        (D("4000"), D("1000"), D("1000")),
        (D("5000"), D("1000"), D("1000")),
    ],
)
def test_exact_slab_boundaries(eligible: Decimal, bdr: Decimal, expected_slab1: Decimal) -> None:
    slab = calculate_slab_fee(eligible, bdr)
    assert slab.slab_1_amount == expected_slab1


def test_continuity_around_bdr_zero() -> None:
    profit = D("1000")
    fee_pos = calculate_slab_fee(profit, D("0.01")).total_fee
    fee_zero = calculate_slab_fee(profit, D("0")).total_fee
    fee_neg = calculate_slab_fee(profit, D("-0.01")).total_fee
    assert fee_zero == fee_neg == D("500")
    assert fee_pos < fee_zero


def test_hwm_unchanged_below_prior_peak() -> None:
    result = crystallize_month(D("32000"), D("0"), D("34338.50096"), D("6849.09"), D("6845.5"))
    assert result.next_high_water_mark == D("34338.50096")


def test_hwm_ratchet_on_new_after_fee_peak() -> None:
    result = crystallize_month(
        D("37683.16"), D("0"), D("30000"), D("6737.49"), D("6849.09")
    )
    assert result.next_high_water_mark == result.after_fee_nlv
    assert result.next_high_water_mark > D("30000")


def test_crystallized_unpaid_fee_reduces_fee_basis() -> None:
    outstanding = D("2967.84673")
    raw = D("50000")
    result = crystallize_month(
        raw,
        outstanding,
        D("40000"),
        D("6528.52"),
        D("7209.01"),
    )
    assert result.fee_basis == raw - outstanding
    assert result.fee_basis < raw


def test_estimate_recomputed_not_accumulated_from_daily_deltas() -> None:
    """Two independent recomputations from the same inputs must match."""
    kwargs = dict(
        raw_gross_account_balance=D("36059.74"),
        crystallized_fee_payable_outstanding=D("0"),
        prior_high_water_mark=D("34622.5581"),
        spx_start=D("6939.03"),
        spx_end=D("6878.88"),
    )
    first = crystallize_month(**kwargs)
    second = crystallize_month(**kwargs)
    assert first.current_period_fee == second.current_period_fee


def test_invalid_spx_start() -> None:
    with pytest.raises(ValueError, match="spx_start must be positive"):
        calculate_benchmark_dollar_return(D("0"), D("100"))


def test_invalid_decimal_nan() -> None:
    with pytest.raises(ValueError, match="finite"):
        calculate_slab_fee(Decimal("NaN"), D("100"))


def test_negative_crystallized_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="crystallized_fee_payable_outstanding"):
        crystallize_month(D("10000"), D("-1"), D("0"), D("100"), D("110"))


def test_gross_less_than_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="raw_gross_account_balance"):
        crystallize_month(D("100"), D("200"), D("0"), D("100"), D("110"))


def test_july_2026_not_in_golden_table() -> None:
    months = {c["month"] for c in GOLDEN_MONTHS}
    assert "2026-05" in months
    assert "2026-06" in months
    assert "2026-07" not in months
