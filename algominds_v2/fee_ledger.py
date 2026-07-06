"""
Algominds v2 fee liability ledger — pure transitions, no persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple


def _require_decimal(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class FeePayment:
    payment_date: date
    amount: Decimal
    reference: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _require_decimal("amount", self.amount))
        if self.amount <= 0:
            raise ValueError("payment amount must be positive")


@dataclass(frozen=True)
class FeeLiability:
    raw_gross_account_balance: Decimal
    crystallized_outstanding: Decimal
    current_estimated_fee: Decimal
    total_fee_owed: Decimal
    signed_fee_liability: Decimal
    displayed_fee_owed: Decimal
    nlv: Decimal

    def __post_init__(self) -> None:
        if self.displayed_fee_owed < 0:
            raise ValueError("displayed_fee_owed must be non-negative")
        if self.signed_fee_liability > 0:
            raise ValueError("signed_fee_liability must be non-positive")
        expected_nlv = self.raw_gross_account_balance + self.signed_fee_liability
        if self.nlv != expected_nlv:
            raise ValueError("NLV invariant violated in FeeLiability")


@dataclass(frozen=True)
class CrystallizationTransition:
    prior_liability: FeeLiability
    accepted_estimate: Decimal
    resulting_liability: FeeLiability
    nlv_unchanged: bool


@dataclass(frozen=True)
class PaymentTransition:
    prior_liability: FeeLiability
    payment: FeePayment
    resulting_liability: FeeLiability
    nlv_unchanged: bool


@dataclass(frozen=True)
class LedgerState:
    raw_gross_account_balance: Decimal
    crystallized_outstanding: Decimal
    current_estimated_fee: Decimal
    payment_history: Tuple[FeePayment, ...] = ()

    def liability(self) -> FeeLiability:
        return calculate_liability(
            self.raw_gross_account_balance,
            self.crystallized_outstanding,
            self.current_estimated_fee,
        )


def calculate_liability(
    raw_gross_account_balance: Decimal,
    crystallized_outstanding: Decimal,
    current_estimated_fee: Decimal,
) -> FeeLiability:
    raw_gross_account_balance = _require_decimal(
        "raw_gross_account_balance", raw_gross_account_balance
    )
    crystallized_outstanding = _require_decimal(
        "crystallized_outstanding", crystallized_outstanding
    )
    current_estimated_fee = _require_decimal(
        "current_estimated_fee", current_estimated_fee
    )

    if crystallized_outstanding < 0:
        raise ValueError("crystallized_outstanding must be non-negative")
    if current_estimated_fee < 0:
        raise ValueError("current_estimated_fee must be non-negative")

    total_fee_owed = crystallized_outstanding + current_estimated_fee
    signed_fee_liability = -total_fee_owed
    nlv = raw_gross_account_balance + signed_fee_liability

    return FeeLiability(
        raw_gross_account_balance=raw_gross_account_balance,
        crystallized_outstanding=crystallized_outstanding,
        current_estimated_fee=current_estimated_fee,
        total_fee_owed=total_fee_owed,
        signed_fee_liability=signed_fee_liability,
        displayed_fee_owed=total_fee_owed,
        nlv=nlv,
    )


def crystallize_estimate(
    raw_gross_account_balance: Decimal,
    crystallized_outstanding: Decimal,
    current_estimated_fee: Decimal,
    accepted_estimate: Decimal,
) -> CrystallizationTransition:
    """Move accepted estimate into crystallized payable without debiting cash."""
    prior = calculate_liability(
        raw_gross_account_balance,
        crystallized_outstanding,
        current_estimated_fee,
    )
    accepted_estimate = _require_decimal("accepted_estimate", accepted_estimate)
    if accepted_estimate < 0:
        raise ValueError("accepted_estimate must be non-negative")
    if accepted_estimate != current_estimated_fee:
        raise ValueError(
            "accepted_estimate must equal current_estimated_fee at crystallization"
        )

    new_crystallized = crystallized_outstanding + accepted_estimate
    resulting = calculate_liability(
        raw_gross_account_balance,
        new_crystallized,
        Decimal("0"),
    )

    return CrystallizationTransition(
        prior_liability=prior,
        accepted_estimate=accepted_estimate,
        resulting_liability=resulting,
        nlv_unchanged=prior.nlv == resulting.nlv,
    )


def apply_payment(
    raw_gross_account_balance: Decimal,
    crystallized_outstanding: Decimal,
    current_estimated_fee: Decimal,
    payment: FeePayment,
) -> PaymentTransition:
    """Reduce cash and crystallized liability equally; preserve current estimate."""
    prior = calculate_liability(
        raw_gross_account_balance,
        crystallized_outstanding,
        current_estimated_fee,
    )

    if payment.amount > crystallized_outstanding:
        raise ValueError("payment exceeds crystallized outstanding balance")

    new_raw = raw_gross_account_balance - payment.amount
    new_crystallized = crystallized_outstanding - payment.amount

    resulting = calculate_liability(
        new_raw,
        new_crystallized,
        current_estimated_fee,
    )

    return PaymentTransition(
        prior_liability=prior,
        payment=payment,
        resulting_liability=resulting,
        nlv_unchanged=prior.nlv == resulting.nlv,
    )


def apply_payments_sequential(
    raw_gross_account_balance: Decimal,
    crystallized_outstanding: Decimal,
    current_estimated_fee: Decimal,
    payments: Tuple[FeePayment, ...],
) -> Tuple[LedgerState, Tuple[PaymentTransition, ...]]:
    """Apply multiple partial payments in order, accumulating history."""
    transitions: list[PaymentTransition] = []
    raw = raw_gross_account_balance
    crystallized = crystallized_outstanding
    estimate = current_estimated_fee
    history: list[FeePayment] = []

    for payment in payments:
        transition = apply_payment(raw, crystallized, estimate, payment)
        transitions.append(transition)
        history.append(payment)
        raw = transition.resulting_liability.raw_gross_account_balance
        crystallized = transition.resulting_liability.crystallized_outstanding
        estimate = transition.resulting_liability.current_estimated_fee

    state = LedgerState(
        raw_gross_account_balance=raw,
        crystallized_outstanding=crystallized,
        current_estimated_fee=estimate,
        payment_history=tuple(history),
    )
    return state, tuple(transitions)
