"""Row validation.

Enforces the per-program field rules described in ``programs.py`` plus the
global rules:

  * Date required, ISO YYYY-MM-DD.
  * NLV values required and numeric.
  * Cash transfer numeric, default 0 if blank.
  * Fee only exists for AGM (rejected for TKP/TCP/YQ).
  * Plus500 NLV rejected for non-TKP.
  * TradeStation NLV rejected for non-AGM.

On failure a :class:`RowValidationError` carrying a per-field error map is
raised; the API layer turns that into an HTTP 422.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .programs import PROGRAM_FIELDS, normalize_program

# Fields that belong to exactly one program. Used to produce friendly rejection
# messages (e.g. "fee is only valid for AGM").
EXCLUSIVE_FIELDS = {
    "plus500_nlv": "TKP",
    "tradestation_nlv": "AGM",
    "fee": "AGM",
}


class RowValidationError(Exception):
    """Raised when a submitted row fails validation.

    Attributes:
        errors: mapping of field name -> human readable error message.
    """

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_number(value: Any) -> float:
    """Coerce a JSON value to float, rejecting booleans and non-numeric text."""
    if isinstance(value, bool):  # bool is a subclass of int — reject explicitly
        raise ValueError("must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())  # raises ValueError on non-numeric text
    raise ValueError("must be numeric")


def validate_row(program: str, payload: dict) -> dict:
    """Validate & normalize a submitted row for `program`.

    Returns a normalized dict containing exactly the program's fields, with
    ``date`` as an ISO string and numeric fields as floats (cash_transfer / fee
    defaulted to 0 when blank). Raises :class:`RowValidationError` otherwise.
    """
    code = normalize_program(program)
    if code is None:
        raise RowValidationError({"program": f"unknown program '{program}'"})

    if not isinstance(payload, dict):
        raise RowValidationError({"body": "expected a JSON object"})

    specs = PROGRAM_FIELDS[code]
    allowed = {f.name for f in specs}
    errors: dict[str, str] = {}
    normalized: dict[str, Any] = {}

    # 1) Reject any field that does not belong to this program.
    for key in payload:
        if key not in allowed:
            if key in EXCLUSIVE_FIELDS:
                errors[key] = (
                    f"{key} is only valid for {EXCLUSIVE_FIELDS[key]}, not {code}"
                )
            else:
                errors[key] = f"unexpected field for {code}"

    # 2) Validate each declared field.
    for f in specs:
        raw = payload.get(f.name)

        if f.name == "date":
            if _is_blank(raw):
                errors["date"] = "date is required (ISO YYYY-MM-DD)"
                continue
            try:
                parsed = datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
                normalized["date"] = parsed.isoformat()
            except ValueError:
                errors["date"] = f"invalid date '{raw}', expected ISO YYYY-MM-DD"
            continue

        # numeric fields
        if _is_blank(raw):
            if f.required:
                errors[f.name] = f"{f.name} is required and must be numeric"
            else:
                normalized[f.name] = float(f.default if f.default is not None else 0.0)
            continue

        try:
            normalized[f.name] = _to_number(raw)
        except (ValueError, TypeError):
            errors[f.name] = f"{f.name} must be numeric"

    if errors:
        raise RowValidationError(errors)
    return normalized
