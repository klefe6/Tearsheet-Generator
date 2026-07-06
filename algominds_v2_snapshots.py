"""
Algominds v2 fee snapshot helpers — bridge preview inputs into the pure fee engine.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from algominds_v2.fee_engine import crystallize_month
from algominds_v2.fee_ledger import calculate_liability
from algominds_v2_accounts import validate_account_slug

DEFAULT_BENCHMARK_BASE = Decimal("30000")


@dataclass(frozen=True)
class AlgomindsV2FeeSnapshot:
    as_of_date: date
    account_balance: Decimal
    fee_removal: Decimal
    prior_high_water_mark: Decimal
    spx_start: Decimal
    spx_end: Decimal
    benchmark_base: Decimal = DEFAULT_BENCHMARK_BASE
    notes: Optional[str] = None
    account_slug: Optional[str] = None


@dataclass(frozen=True)
class AlgomindsV2FeeSnapshotResult:
    as_of_date: date
    fee_basis: Decimal
    eligible_profit: Decimal
    benchmark_dollar_return: Decimal
    current_estimated_fee: Decimal
    after_fee_nlv: Decimal
    next_high_water_mark: Decimal
    displayed_fee_owed: Decimal
    signed_fee_liability: Decimal
    nlv: Decimal


def _require_decimal(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
    return value


def validate_snapshot_inputs(snapshot: AlgomindsV2FeeSnapshot) -> None:
    """Validate raw snapshot inputs before fee-engine computation."""
    account_balance = _require_decimal("account_balance", snapshot.account_balance)
    fee_removal = _require_decimal("fee_removal", snapshot.fee_removal)
    prior_hwm = _require_decimal("prior_high_water_mark", snapshot.prior_high_water_mark)
    spx_start = _require_decimal("spx_start", snapshot.spx_start)
    spx_end = _require_decimal("spx_end", snapshot.spx_end)
    benchmark_base = _require_decimal("benchmark_base", snapshot.benchmark_base)

    if account_balance < 0:
        raise ValueError("account_balance must be non-negative")
    if fee_removal < 0:
        raise ValueError("fee_removal must be non-negative")
    if prior_hwm < 0:
        raise ValueError("prior_high_water_mark must be non-negative")
    if account_balance < fee_removal:
        raise ValueError("account_balance must be >= fee_removal")
    if spx_start <= 0:
        raise ValueError("spx_start must be positive")
    if benchmark_base <= 0:
        raise ValueError("benchmark_base must be positive")
    if snapshot.account_slug is not None:
        validate_account_slug(snapshot.account_slug)


def compute_fee_snapshot(snapshot: AlgomindsV2FeeSnapshot) -> AlgomindsV2FeeSnapshotResult:
    """
    Compute estimated fee and liability display fields from a raw balance snapshot.

    account_balance is raw gross balance; fee_removal is crystallized payable outstanding.
    """
    validate_snapshot_inputs(snapshot)

    crystallized = crystallize_month(
        snapshot.account_balance,
        snapshot.fee_removal,
        snapshot.prior_high_water_mark,
        snapshot.spx_start,
        snapshot.spx_end,
        snapshot.benchmark_base,
    )
    liability = calculate_liability(
        snapshot.account_balance,
        snapshot.fee_removal,
        crystallized.current_period_fee,
    )

    if liability.nlv != crystallized.after_fee_nlv:
        raise RuntimeError("NLV invariant mismatch between fee engine and liability ledger")

    return AlgomindsV2FeeSnapshotResult(
        as_of_date=snapshot.as_of_date,
        fee_basis=crystallized.fee_basis,
        eligible_profit=crystallized.eligible_profit,
        benchmark_dollar_return=crystallized.benchmark_dollar_return,
        current_estimated_fee=crystallized.current_period_fee,
        after_fee_nlv=crystallized.after_fee_nlv,
        next_high_water_mark=crystallized.next_high_water_mark,
        displayed_fee_owed=liability.displayed_fee_owed,
        signed_fee_liability=liability.signed_fee_liability,
        nlv=liability.nlv,
    )


def snapshot_to_dict(snapshot: AlgomindsV2FeeSnapshot) -> dict[str, Any]:
    """Serialize a snapshot for JSON persistence (Decimal values as strings)."""
    payload: dict[str, Any] = {
        "as_of_date": snapshot.as_of_date.isoformat(),
        "account_balance": format(snapshot.account_balance, "f"),
        "fee_removal": format(snapshot.fee_removal, "f"),
        "prior_high_water_mark": format(snapshot.prior_high_water_mark, "f"),
        "spx_start": format(snapshot.spx_start, "f"),
        "spx_end": format(snapshot.spx_end, "f"),
        "benchmark_base": format(snapshot.benchmark_base, "f"),
    }
    if snapshot.notes is not None:
        payload["notes"] = snapshot.notes
    if snapshot.account_slug is not None:
        payload["account_slug"] = snapshot.account_slug
    return payload


def snapshot_from_dict(payload: dict[str, Any]) -> AlgomindsV2FeeSnapshot:
    """Deserialize a snapshot from JSON-compatible dict data."""
    try:
        as_of_date = date.fromisoformat(str(payload["as_of_date"]))
        account_balance = Decimal(str(payload["account_balance"]))
        fee_removal = Decimal(str(payload["fee_removal"]))
        prior_high_water_mark = Decimal(str(payload["prior_high_water_mark"]))
        spx_start = Decimal(str(payload["spx_start"]))
        spx_end = Decimal(str(payload["spx_end"]))
        benchmark_base = Decimal(str(payload.get("benchmark_base", DEFAULT_BENCHMARK_BASE)))
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid fee snapshot payload") from exc

    notes = payload.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("notes must be a string or null")

    account_slug = payload.get("account_slug")
    if account_slug is not None:
        if not isinstance(account_slug, str):
            raise ValueError("account_slug must be a string or null")
        account_slug = validate_account_slug(account_slug)

    return AlgomindsV2FeeSnapshot(
        as_of_date=as_of_date,
        account_balance=account_balance,
        fee_removal=fee_removal,
        prior_high_water_mark=prior_high_water_mark,
        spx_start=spx_start,
        spx_end=spx_end,
        benchmark_base=benchmark_base,
        notes=notes,
        account_slug=account_slug,
    )


def snapshot_to_json(snapshot: AlgomindsV2FeeSnapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), indent=2, sort_keys=True) + "\n"
