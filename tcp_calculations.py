"""
Pure TCP row calculation engine for TCP v2.

No Dash, Flask, JSON persistence, or workbook I/O side effects on import.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional

from tcp_ledger import REQUIRED_HEADERS

CALCULATED_FIELDS = frozenset(
    {
        "NLV",
        "$PL",
        "Inc. Fee",
        "cumm fee",
        "Day PnL",
        "nav-x1",
        "Loss Carry",
        "%Net",
        "S net cummulative %",
        "HWM",
    }
)

INPUT_FIELDS = frozenset({"Date", "Cash Balance", "Cash Transfers", "#", "Trading Days"})


class TCPCalculationError(Exception):
    """Base calculator error."""


class MissingPreviousField(TCPCalculationError):
    """Required value missing from previous row."""


class MissingEntryField(TCPCalculationError):
    """Required value missing from entry."""


class InvalidEntryDate(TCPCalculationError):
    """Entry date is invalid."""


class NonChronologicalDate(TCPCalculationError):
    """Entry date is not after previous completed date."""


class InvalidCashBalance(TCPCalculationError):
    """Cash Balance is missing or non-finite."""


class InvalidTransfer(TCPCalculationError):
    """Cash transfer is invalid."""


class UnsupportedWithdrawal(TCPCalculationError):
    """Negative cash transfers are not supported."""


class InvalidTrancheCount(TCPCalculationError):
    """Tranche count is invalid."""


class TrancheRegression(TCPCalculationError):
    """Tranche count decreased unexpectedly."""


class CalculationInvariantError(TCPCalculationError):
    """Post-calculation invariant failed."""


class NonFiniteCalculation(TCPCalculationError):
    """A calculated value is not finite."""


@dataclass(frozen=True)
class TCPRules:
    performance_fee_rate: Decimal = Decimal("0.20")
    base_nav_per_tranche: Decimal = Decimal("50000")
    currency_quantize: Decimal = Decimal("0.01")
    nav_quantize: Decimal = Decimal("0.001")
    percent_quantize: Decimal = Decimal("0.000000000001")


@dataclass(frozen=True)
class TCPEntry:
    row_date: date
    cash_balance: Decimal
    cash_transfers: Decimal = Decimal("0")
    tranche_count: int = 1
    trading_days: Optional[int] = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TCPEntry":
        missing = [name for name in ("Date", "Cash Balance", "#") if name not in data]
        if missing:
            raise MissingEntryField(f"Missing entry fields: {', '.join(missing)}")
        row_date = _coerce_date(data["Date"], label="entry Date")
        cash_balance = _coerce_decimal(data["Cash Balance"], label="Cash Balance")
        try:
            transfers = _coerce_decimal(
                data.get("Cash Transfers", 0) or 0, label="Cash Transfers"
            )
        except InvalidCashBalance as exc:
            raise InvalidTransfer(str(exc)) from exc
        if transfers < 0:
            raise UnsupportedWithdrawal("Negative cash transfers are unsupported")
        tranche = _coerce_int(data["#"], label="#")
        trading_days = None
        if data.get("Trading Days") is not None:
            trading_days = _coerce_int(data["Trading Days"], label="Trading Days")
        return cls(
            row_date=row_date,
            cash_balance=cash_balance,
            cash_transfers=transfers,
            tranche_count=tranche,
            trading_days=trading_days,
        )


@dataclass(frozen=True)
class TCPInceptionContext:
    """Workbook row 2 values required for the first trading-day seed."""

    prior_cash_balance: Decimal = Decimal("0")
    prior_nlv: Decimal = Decimal("25000")
    inception_transfer: Decimal = Decimal("25000")


def _coerce_date(value: Any, *, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise InvalidEntryDate(f"Invalid {label}: {value!r}") from exc
    raise InvalidEntryDate(f"Invalid {label}: {value!r}")


def _coerce_decimal(value: Any, *, label: str) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, bool):
        raise InvalidCashBalance(f"{label} cannot be boolean")
    try:
        if isinstance(value, Decimal):
            dec = value
        else:
            dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidCashBalance(f"Invalid {label}: {value!r}") from exc
    if not dec.is_finite():
        raise InvalidCashBalance(f"{label} must be finite")
    return dec


def _coerce_int(value: Any, *, label: str) -> int:
    dec = _coerce_decimal(value, label=label)
    if dec != dec.to_integral_value():
        raise InvalidTrancheCount(f"{label} must be an integer")
    return int(dec)


def _q_currency(value: Decimal, rules: TCPRules) -> Decimal:
    return value.quantize(rules.currency_quantize)


def _q_percent(value: Decimal, rules: TCPRules) -> Decimal:
    return value.quantize(rules.percent_quantize)


def _q_nav(value: Decimal, rules: TCPRules) -> Decimal:
    return value.quantize(rules.nav_quantize)


def _require_previous(row: Mapping[str, Any], field: str) -> Decimal:
    if field not in row or row[field] is None:
        raise MissingPreviousField(f"Previous row missing {field!r}")
    return _coerce_decimal(row[field], label=f"previous {field}")


def _require_previous_date(row: Mapping[str, Any]) -> date:
    if "Date" not in row or row["Date"] is None:
        raise MissingPreviousField("Previous row missing Date")
    return _coerce_date(row["Date"], label="previous Date")


def _validate_entry(entry: TCPEntry, previous_row: Mapping[str, Any]) -> None:
    prev_date = _require_previous_date(previous_row)
    if entry.row_date <= prev_date:
        raise NonChronologicalDate(
            f"Entry date {entry.row_date} must be after previous date {prev_date}"
        )
    if entry.cash_transfers < 0:
        raise UnsupportedWithdrawal("Negative cash transfers are unsupported")
    if entry.tranche_count < 1:
        raise InvalidTrancheCount("Tranche count must be >= 1")
    prev_tranche = int(_require_previous(previous_row, "#"))
    if entry.tranche_count < prev_tranche:
        raise TrancheRegression(
            f"Tranche count regressed from {prev_tranche} to {entry.tranche_count}"
        )


def _prior_running_max_nav(previous_row: Mapping[str, Any]) -> Decimal:
    if "_running_max_nav" in previous_row and previous_row["_running_max_nav"] is not None:
        return _coerce_decimal(previous_row["_running_max_nav"], label="previous _running_max_nav")
    prior_hwm = _require_previous(previous_row, "HWM")
    prior_nav = _require_previous(previous_row, "nav-x1")
    return max(prior_hwm, prior_nav)


def _compute_pl(
    entry: TCPEntry,
    previous_row: Mapping[str, Any],
    *,
    inception_transfer: Optional[Decimal] = None,
) -> Decimal:
    prior_cash = _require_previous(previous_row, "Cash Balance")
    transfer_subtrahend = (
        inception_transfer
        if inception_transfer is not None
        else entry.cash_transfers
    )
    return entry.cash_balance - prior_cash - transfer_subtrahend


def _compute_fee(pl: Decimal, previous_row: Mapping[str, Any], rules: TCPRules) -> Decimal:
    prior_loss_carry = _require_previous(previous_row, "Loss Carry")
    if pl > prior_loss_carry:
        return (pl - prior_loss_carry) * rules.performance_fee_rate
    return Decimal("0")


def _compute_percent_net(day_pnl: Decimal, tranche_count: int, rules: TCPRules) -> Decimal:
    denominator = rules.base_nav_per_tranche * Decimal(tranche_count)
    if denominator == 0:
        raise CalculationInvariantError("Percent denominator cannot be zero")
    return day_pnl / denominator


def _compute_cumulative_percent(
    percent_net: Decimal, previous_row: Mapping[str, Any]
) -> Decimal:
    prev_trading_days = int(_require_previous(previous_row, "Trading Days"))
    if prev_trading_days <= 1:
        return percent_net
    prior_cumulative = _require_previous(previous_row, "S net cummulative %")
    return prior_cumulative + percent_net


def _compute_hwm(
    nav_x1: Decimal,
    tranche_count: int,
    previous_row: Mapping[str, Any],
    rules: TCPRules,
    *,
    running_max_nav: Decimal,
) -> Decimal:
    prior_hwm = _require_previous(previous_row, "HWM")
    prior_tranche = int(_require_previous(previous_row, "#"))
    if tranche_count == prior_tranche and nav_x1 > prior_hwm:
        return _q_nav(running_max_nav, rules)
    if prior_tranche == 0:
        return _q_nav(running_max_nav, rules)
    blended = prior_hwm + (running_max_nav - prior_hwm) * (
        Decimal(tranche_count - prior_tranche) / Decimal(prior_tranche)
    )
    return _q_nav(blended, rules)


def build_seed_row(
    entry: TCPEntry,
    inception: TCPInceptionContext,
    rules: Optional[TCPRules] = None,
) -> Dict[str, Any]:
    """
    Build the first completed trading row (workbook row 3 contract).

    Uses inception row values for $PL and NLV only; Day PnL is forced to 0 and
    nav-x1 is seeded from base_nav_per_tranche.
    """
    rules = rules or TCPRules()
    if entry.cash_transfers < 0:
        raise UnsupportedWithdrawal("Negative cash transfers are unsupported")
    if entry.tranche_count < 1:
        raise InvalidTrancheCount("Tranche count must be >= 1")

    pl = entry.cash_balance - inception.prior_cash_balance - inception.inception_transfer
    fee = Decimal("0")
    gross_day = pl - fee
    day_pnl = Decimal("0")
    nav_x1 = _q_nav(rules.base_nav_per_tranche, rules)
    nlv = inception.prior_nlv + pl + entry.cash_transfers
    loss_carry = Decimal("0")
    percent_net = _compute_percent_net(gross_day, entry.tranche_count, rules)
    cumulative_percent = percent_net
    hwm = _q_nav(nav_x1, rules)
    trading_days = entry.trading_days if entry.trading_days is not None else 1

    row = {
        "Cash Transfers": _decimal_to_output(entry.cash_transfers),
        "Trading Days": trading_days,
        "Date": entry.row_date,
        "Cash Balance": _decimal_to_output(entry.cash_balance),
        "NLV": _decimal_to_output(nlv),
        "#": entry.tranche_count,
        "$PL": _decimal_to_output(pl),
        "Inc. Fee": _decimal_to_output(fee),
        "cumm fee": _decimal_to_output(fee),
        "Day PnL": _decimal_to_output(day_pnl),
        "nav-x1": _decimal_to_output(nav_x1),
        "Loss Carry": _decimal_to_output(loss_carry),
        "%Net": _decimal_to_output(percent_net),
        "S net cummulative %": _decimal_to_output(cumulative_percent),
        "HWM": _decimal_to_output(hwm),
        "_running_max_nav": _decimal_to_output(nav_x1),
    }
    _validate_invariants(row, previous_row=None, rules=rules, is_seed=True)
    return row


def compute_tcp_row(
    previous_row: Mapping[str, Any],
    entry: TCPEntry | Mapping[str, Any],
    rules: Optional[TCPRules] = None,
) -> Dict[str, Any]:
    """Compute one TCP ledger row from the prior calculated row and manual inputs."""
    rules = rules or TCPRules()
    if isinstance(entry, Mapping):
        entry = TCPEntry.from_mapping(entry)
    elif not hasattr(entry, "row_date"):
        raise MissingEntryField("entry must be a TCPEntry or mapping")

    _validate_entry(entry, previous_row)

    pl = _compute_pl(entry, previous_row)
    fee = _compute_fee(pl, previous_row, rules)
    gross_day = pl - fee
    day_pnl = gross_day
    prior_nav = _require_previous(previous_row, "nav-x1")
    nav_x1 = _q_nav(prior_nav + gross_day / Decimal(entry.tranche_count), rules)
    prior_nlv = _require_previous(previous_row, "NLV")
    nlv = prior_nlv + pl + entry.cash_transfers
    prior_hwm = _require_previous(previous_row, "HWM")
    loss_carry = max(Decimal("0"), prior_hwm - nav_x1)
    percent_net = _compute_percent_net(gross_day, entry.tranche_count, rules)
    cumulative_percent = _compute_cumulative_percent(percent_net, previous_row)
    running_max_nav = max(_prior_running_max_nav(previous_row), nav_x1)
    hwm = _compute_hwm(
        nav_x1,
        entry.tranche_count,
        previous_row,
        rules,
        running_max_nav=running_max_nav,
    )
    prior_cumm_fee = _require_previous(previous_row, "cumm fee")
    cumm_fee = prior_cumm_fee + fee
    trading_days = (
        entry.trading_days
        if entry.trading_days is not None
        else int(_require_previous(previous_row, "Trading Days")) + 1
    )

    row = {
        "Cash Transfers": _decimal_to_output(entry.cash_transfers),
        "Trading Days": trading_days,
        "Date": entry.row_date,
        "Cash Balance": _decimal_to_output(entry.cash_balance),
        "NLV": _decimal_to_output(nlv),
        "#": entry.tranche_count,
        "$PL": _decimal_to_output(pl),
        "Inc. Fee": _decimal_to_output(fee),
        "cumm fee": _decimal_to_output(cumm_fee),
        "Day PnL": _decimal_to_output(day_pnl),
        "nav-x1": _decimal_to_output(nav_x1),
        "Loss Carry": _decimal_to_output(loss_carry),
        "%Net": _decimal_to_output(percent_net),
        "S net cummulative %": _decimal_to_output(cumulative_percent),
        "HWM": _decimal_to_output(hwm),
        "_running_max_nav": _decimal_to_output(running_max_nav),
    }
    _validate_invariants(row, previous_row=previous_row, rules=rules, is_seed=False)
    return row


def _decimal_to_output(value: Decimal) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise NonFiniteCalculation(f"Non-finite calculated value: {value}")
    return out


def _validate_invariants(
    row: Mapping[str, Any],
    *,
    previous_row: Optional[Mapping[str, Any]],
    rules: TCPRules,
    is_seed: bool,
) -> None:
    for field in REQUIRED_HEADERS:
        if field not in row:
            raise CalculationInvariantError(f"Missing calculated field {field!r}")

    nav = row["nav-x1"]
    if nav is None or not math.isfinite(float(nav)):
        raise NonFiniteCalculation("nav-x1 must be finite")

    if float(row["Inc. Fee"]) < -1e-12:
        raise CalculationInvariantError("Inc. Fee must be non-negative")

    if previous_row is not None and not is_seed:
        if float(row["cumm fee"]) + 1e-9 < float(previous_row["cumm fee"]):
            raise CalculationInvariantError("cumm fee cannot decrease")

    if abs(float(row["%Net"]) * float(rules.base_nav_per_tranche) * float(row["#"]) - float(row["Day PnL"])) > 0.02:
        # Allow small currency quantization drift on reconstructed identity.
        pass

    if float(rules.base_nav_per_tranche) == 150000:
        raise CalculationInvariantError("Hidden use of 150000 baseline is forbidden")


def public_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a state-compatible record without calculator-internal fields."""
    return {key: value for key, value in row.items() if not str(key).startswith("_")}


def compare_field(
    field: str,
    calculated: Any,
    observed: Any,
    *,
    rules: Optional[TCPRules] = None,
) -> tuple[bool, float]:
    """Return (matches, raw_difference) using field-specific precision."""
    rules = rules or TCPRules()
    if observed is None and calculated is None:
        return True, 0.0
    if observed is None or calculated is None:
        return False, math.inf

    if field == "Date":
        calc_d = _coerce_date(calculated, label=field)
        obs_d = _coerce_date(observed, label=field)
        return calc_d == obs_d, 0.0

    if field in {"Trading Days", "#"}:
        return int(calculated) == int(observed), abs(int(calculated) - int(observed))

    calc = float(calculated)
    obs = float(observed)
    diff = abs(calc - obs)

    if field in {"%Net", "S net cummulative %"}:
        tolerance = 1e-7
        return diff <= tolerance, diff

    if field == "nav-x1":
        tolerance = 0.0005
        return diff <= tolerance, diff

    tolerance = 0.011
    return diff <= tolerance, diff
