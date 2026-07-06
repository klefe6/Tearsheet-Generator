"""Tests for Algominds v2 fee liability ledger."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from algominds_v2.fee_engine import crystallize_month
from algominds_v2.fee_ledger import (
    FeePayment,
    apply_payment,
    apply_payments_sequential,
    calculate_liability,
    crystallize_estimate,
)

D = Decimal
APRIL_FEE = D("2967.84673")


def test_liability_invariants() -> None:
    liability = calculate_liability(D("50000"), D("1000"), D("250"))
    assert liability.displayed_fee_owed >= 0
    assert liability.signed_fee_liability <= 0
    assert liability.nlv == liability.raw_gross_account_balance + liability.signed_fee_liability
    assert liability.total_fee_owed == D("1250")


def test_estimate_decreasing_without_negative_display() -> None:
    high = calculate_liability(D("50000"), D("0"), D("500"))
    low = calculate_liability(D("48000"), D("0"), D("200"))
    assert high.current_estimated_fee > low.current_estimated_fee
    assert low.displayed_fee_owed >= 0


def test_crystallization_reclassification_preserves_nlv() -> None:
    raw = D("47451.27")
    estimate = D("2967.846349")
    prior = calculate_liability(raw, D("0"), estimate)
    transition = crystallize_estimate(raw, D("0"), estimate, estimate)
    assert transition.nlv_unchanged
    assert prior.nlv == transition.resulting_liability.nlv
    assert transition.resulting_liability.crystallized_outstanding == estimate
    assert transition.resulting_liability.current_estimated_fee == 0


def test_crystallization_does_not_debit_cash() -> None:
    raw = D("47451.27")
    estimate = D("2967.846349")
    transition = crystallize_estimate(raw, D("0"), estimate, estimate)
    assert transition.resulting_liability.raw_gross_account_balance == raw


def test_immediate_full_payment() -> None:
    raw = D("47451.27")
    outstanding = APRIL_FEE
    estimate = D("0")
    payment = FeePayment(date(2026, 5, 1), outstanding)
    transition = apply_payment(raw, outstanding, estimate, payment)
    assert transition.nlv_unchanged
    assert transition.resulting_liability.crystallized_outstanding == 0
    assert transition.resulting_liability.raw_gross_account_balance == raw - outstanding


def test_delayed_full_payment_april_to_may_principle() -> None:
    """Synthetic delayed payment: April fee crystallized but unpaid reduces May fee basis."""
    raw_may = D("50000")
    outstanding = APRIL_FEE
    fee_basis = raw_may - outstanding
    result = crystallize_month(
        raw_may,
        outstanding,
        D("40000"),
        D("6528.52"),
        D("7209.01"),
    )
    assert result.fee_basis == fee_basis
    assert result.raw_gross_account_balance == raw_may


def test_multiple_partial_payments() -> None:
    raw = D("47451.27")
    outstanding = APRIL_FEE
    payments = (
        FeePayment(date(2026, 5, 10), D("1000")),
        FeePayment(date(2026, 5, 20), D("1500")),
        FeePayment(date(2026, 6, 1), outstanding - D("2500")),
    )
    state, transitions = apply_payments_sequential(raw, outstanding, D("0"), payments)
    assert state.crystallized_outstanding == 0
    assert len(state.payment_history) == 3
    assert all(t.nlv_unchanged for t in transitions)
    assert state.raw_gross_account_balance == raw - outstanding


def test_overpayment_rejected() -> None:
    with pytest.raises(ValueError, match="payment exceeds"):
        apply_payment(
            D("47451.27"),
            D("100"),
            D("0"),
            FeePayment(date(2026, 5, 1), D("200")),
        )


def test_zero_payment_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        FeePayment(date(2026, 5, 1), D("0"))


def test_negative_payment_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        FeePayment(date(2026, 5, 1), D("-1"))


def test_payment_against_estimate_only_rejected() -> None:
    with pytest.raises(ValueError, match="payment exceeds"):
        apply_payment(
            D("50000"),
            D("0"),
            D("500"),
            FeePayment(date(2026, 5, 1), D("100")),
        )


def test_current_estimate_unaffected_by_payment() -> None:
    estimate = D("250")
    transition = apply_payment(
        D("50000"),
        D("1000"),
        estimate,
        FeePayment(date(2026, 5, 1), D("400")),
    )
    assert transition.resulting_liability.current_estimated_fee == estimate


def test_payment_preserves_nlv() -> None:
    raw = D("44483.42365")
    outstanding = APRIL_FEE
    prior = calculate_liability(raw, outstanding, D("0"))
    transition = apply_payment(
        raw,
        outstanding,
        D("0"),
        FeePayment(date(2026, 5, 15), D("1000")),
    )
    assert transition.nlv_unchanged
    assert prior.nlv == transition.resulting_liability.nlv


def test_crystallize_estimate_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="accepted_estimate must equal"):
        crystallize_estimate(D("50000"), D("0"), D("100"), D("200"))


def test_negative_estimate_rejected() -> None:
    with pytest.raises(ValueError, match="current_estimated_fee"):
        calculate_liability(D("50000"), D("0"), D("-1"))
