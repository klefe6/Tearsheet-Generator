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


# Aggregate fund-level inputs extracted read-only from Momentum Fee Calculation.xlsx
# monthly sheets (Nov 2025 – Apr 2026). Tests do not read the workbook at runtime.
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
]

# May 2026 is excluded: workbook contains an unexplained manual adjustment (~$425)
# on the Summary row and is not used as a crystallized golden oracle.


def _within_cent(actual: Decimal, expected: str) -> bool:
    return abs(actual - D(expected)) < TOLERANCE


@pytest.mark.parametrize("case", GOLDEN_MONTHS, ids=[c["month"] for c in GOLDEN_MONTHS])
def test_golden_month_fee_parity(case: dict) -> None:
    result = crystallize_month(
        D(case["raw_gross"]),
        D(case["crystallized_outstanding"]),
        D(case["prior_hwm"]),
        D(case["spx_start"]),
        D(case["spx_end"]),
    )
    assert _within_cent(result.current_period_fee, case["expected_fee"])
    assert _within_cent(result.after_fee_nlv, case["expected_after_fee_nlv"])
    assert _within_cent(result.next_high_water_mark, case["expected_next_hwm"])


@pytest.mark.parametrize("case", [c for c in GOLDEN_MONTHS if "slab_fees" in c], ids=[c["month"] for c in GOLDEN_MONTHS if "slab_fees" in c])
def test_golden_slab_allocation(case: dict) -> None:
    result = crystallize_month(
        D(case["raw_gross"]),
        D(case["crystallized_outstanding"]),
        D(case["prior_hwm"]),
        D(case["spx_start"]),
        D(case["spx_end"]),
    )
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


def test_hwm_chain_ratchet() -> None:
    hwm = D("30000")
    for case in GOLDEN_MONTHS:
        result = crystallize_month(
            D(case["raw_gross"]),
            D(case["crystallized_outstanding"]),
            hwm,
            D(case["spx_start"]),
            D(case["spx_end"]),
        )
        assert result.next_high_water_mark >= hwm
        hwm = result.next_high_water_mark
    assert _within_cent(hwm, GOLDEN_MONTHS[-1]["expected_next_hwm"])


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
    assert slab.total_fee == D("1000") * D("0.10") + D("1000") * D("0.20") + D("1000") * D("0.30") + D("1000") * D("0.40") + D("6000") * D("0.50")


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


def test_may_2026_not_in_golden_table() -> None:
    months = {c["month"] for c in GOLDEN_MONTHS}
    assert "2026-05" not in months
