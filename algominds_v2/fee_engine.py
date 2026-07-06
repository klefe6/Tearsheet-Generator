"""
Pure Algominds v2 fee engine.

All financial arithmetic uses Decimal. No I/O, no rounding to cents.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

SLAB_RATES: Tuple[Decimal, ...] = (
    Decimal("0.10"),
    Decimal("0.20"),
    Decimal("0.30"),
    Decimal("0.40"),
    Decimal("0.50"),
)

NEGATIVE_BDR_RATE = Decimal("0.50")


def _require_decimal(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _validate_non_negative(name: str, value: Decimal) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")


def calculate_benchmark_dollar_return(
    spx_start: Decimal,
    spx_end: Decimal,
    benchmark_base: Decimal = Decimal("30000"),
) -> Decimal:
    """S&P 500 price-index benchmark dollar return on a fixed nominal base."""
    spx_start = _require_decimal("spx_start", spx_start)
    spx_end = _require_decimal("spx_end", spx_end)
    benchmark_base = _require_decimal("benchmark_base", benchmark_base)

    if spx_start <= 0:
        raise ValueError(f"spx_start must be positive, got {spx_start}")
    _validate_non_negative("benchmark_base", benchmark_base)

    spx_return = (spx_end - spx_start) / spx_start
    return benchmark_base * spx_return


@dataclass(frozen=True)
class SlabFeeResult:
    eligible_profit: Decimal
    benchmark_dollar_return: Decimal

    slab_1_amount: Decimal
    slab_2_amount: Decimal
    slab_3_amount: Decimal
    slab_4_amount: Decimal
    slab_5_amount: Decimal

    slab_1_fee: Decimal
    slab_2_fee: Decimal
    slab_3_fee: Decimal
    slab_4_fee: Decimal
    slab_5_fee: Decimal

    total_fee: Decimal


def calculate_slab_fee(
    eligible_profit: Decimal,
    benchmark_dollar_return: Decimal,
) -> SlabFeeResult:
    """Compute five-tier marginal fee or flat 50% when BDR <= 0."""
    eligible_profit = _require_decimal("eligible_profit", eligible_profit)
    benchmark_dollar_return = _require_decimal(
        "benchmark_dollar_return", benchmark_dollar_return
    )
    _validate_non_negative("eligible_profit", eligible_profit)

    if eligible_profit == 0:
        zero = Decimal("0")
        return SlabFeeResult(
            eligible_profit=zero,
            benchmark_dollar_return=benchmark_dollar_return,
            slab_1_amount=zero,
            slab_2_amount=zero,
            slab_3_amount=zero,
            slab_4_amount=zero,
            slab_5_amount=zero,
            slab_1_fee=zero,
            slab_2_fee=zero,
            slab_3_fee=zero,
            slab_4_fee=zero,
            slab_5_fee=zero,
            total_fee=zero,
        )

    if benchmark_dollar_return <= 0:
        slab_5_fee = eligible_profit * NEGATIVE_BDR_RATE
        zero = Decimal("0")
        return SlabFeeResult(
            eligible_profit=eligible_profit,
            benchmark_dollar_return=benchmark_dollar_return,
            slab_1_amount=zero,
            slab_2_amount=zero,
            slab_3_amount=zero,
            slab_4_amount=zero,
            slab_5_amount=eligible_profit,
            slab_1_fee=zero,
            slab_2_fee=zero,
            slab_3_fee=zero,
            slab_4_fee=zero,
            slab_5_fee=slab_5_fee,
            total_fee=slab_5_fee,
        )

    bdr = benchmark_dollar_return
    remaining = eligible_profit
    amounts: list[Decimal] = []
    fees: list[Decimal] = []

    for rate in SLAB_RATES[:4]:
        slab_amount = min(remaining, bdr)
        amounts.append(slab_amount)
        fees.append(slab_amount * rate)
        remaining -= slab_amount

    slab_5_amount = remaining
    slab_5_fee = slab_5_amount * SLAB_RATES[4]
    amounts.append(slab_5_amount)
    fees.append(slab_5_fee)

    total_fee = sum(fees, Decimal("0"))

    return SlabFeeResult(
        eligible_profit=eligible_profit,
        benchmark_dollar_return=benchmark_dollar_return,
        slab_1_amount=amounts[0],
        slab_2_amount=amounts[1],
        slab_3_amount=amounts[2],
        slab_4_amount=amounts[3],
        slab_5_amount=amounts[4],
        slab_1_fee=fees[0],
        slab_2_fee=fees[1],
        slab_3_fee=fees[2],
        slab_4_fee=fees[3],
        slab_5_fee=fees[4],
        total_fee=total_fee,
    )


@dataclass(frozen=True)
class MonthlyCrystallizationResult:
    raw_gross_account_balance: Decimal
    crystallized_fee_payable_outstanding: Decimal
    fee_basis: Decimal
    prior_high_water_mark: Decimal
    eligible_profit: Decimal
    benchmark_dollar_return: Decimal
    current_period_fee: Decimal
    after_fee_nlv: Decimal
    next_high_water_mark: Decimal
    slab: SlabFeeResult


def crystallize_month(
    raw_gross_account_balance: Decimal,
    crystallized_fee_payable_outstanding: Decimal,
    prior_high_water_mark: Decimal,
    spx_start: Decimal,
    spx_end: Decimal,
    benchmark_base: Decimal = Decimal("30000"),
) -> MonthlyCrystallizationResult:
    """Recompute month-end fee from authoritative inputs and ratchet HWM."""
    raw_gross_account_balance = _require_decimal(
        "raw_gross_account_balance", raw_gross_account_balance
    )
    crystallized_fee_payable_outstanding = _require_decimal(
        "crystallized_fee_payable_outstanding", crystallized_fee_payable_outstanding
    )
    prior_high_water_mark = _require_decimal(
        "prior_high_water_mark", prior_high_water_mark
    )

    _validate_non_negative(
        "crystallized_fee_payable_outstanding", crystallized_fee_payable_outstanding
    )
    _validate_non_negative("prior_high_water_mark", prior_high_water_mark)

    if raw_gross_account_balance < crystallized_fee_payable_outstanding:
        raise ValueError(
            "raw_gross_account_balance must be >= crystallized_fee_payable_outstanding"
        )

    benchmark_dollar_return = calculate_benchmark_dollar_return(
        spx_start, spx_end, benchmark_base
    )
    fee_basis = raw_gross_account_balance - crystallized_fee_payable_outstanding
    eligible_profit = max(Decimal("0"), fee_basis - prior_high_water_mark)

    slab = calculate_slab_fee(eligible_profit, benchmark_dollar_return)
    current_period_fee = slab.total_fee
    after_fee_nlv = fee_basis - current_period_fee
    next_high_water_mark = max(prior_high_water_mark, after_fee_nlv)

    return MonthlyCrystallizationResult(
        raw_gross_account_balance=raw_gross_account_balance,
        crystallized_fee_payable_outstanding=crystallized_fee_payable_outstanding,
        fee_basis=fee_basis,
        prior_high_water_mark=prior_high_water_mark,
        eligible_profit=eligible_profit,
        benchmark_dollar_return=benchmark_dollar_return,
        current_period_fee=current_period_fee,
        after_fee_nlv=after_fee_nlv,
        next_high_water_mark=next_high_water_mark,
        slab=slab,
    )
