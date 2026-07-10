"""Program registry, field rules, and row serialization.

This is the single source of truth for *which* fields each program has. The
validation layer, the metadata endpoint, and the row serializer all read from
here so the rules stay consistent.

Field rules (from the spec):
  * TKP -> date, stonex_nlv, plus500_nlv, cash_transfer
  * TCP -> date, stonex_nlv, cash_transfer
  * AGM -> date, tradestation_nlv, cash_transfer, fee
  * YQ  -> date, stonex_nlv, cash_transfer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    type: str  # "date" | "number"
    required: bool
    default: Optional[float] = None
    account_label: Optional[str] = None
    account_number: Optional[str] = None
    copy_to_clipboard: bool = False


# Ordered field definitions per program.
PROGRAM_FIELDS: dict[str, list[FieldSpec]] = {
    "TKP": [
        FieldSpec("date", "Date", "date", True),
        FieldSpec(
            "stonex_nlv",
            "StoneX NLV",
            "number",
            True,
            account_label="StoneX",
            account_number="69060709",
            copy_to_clipboard=True,
        ),
        FieldSpec(
            "plus500_nlv",
            "Plus500 NLV",
            "number",
            True,
            account_label="Plus500",
            account_number="50110102",
            copy_to_clipboard=True,
        ),
        FieldSpec("cash_transfer", "Cash Transfer", "number", False, 0.0),
    ],
    "TCP": [
        FieldSpec("date", "Date", "date", True),
        FieldSpec(
            "stonex_nlv",
            "StoneX NLV",
            "number",
            True,
            account_label="StoneX",
            account_number="69060795",
            copy_to_clipboard=True,
        ),
        FieldSpec("cash_transfer", "Cash Transfer", "number", False, 0.0),
    ],
    "AGM": [
        FieldSpec("date", "Date", "date", True),
        FieldSpec(
            "tradestation_nlv",
            "TradeStation NLV",
            "number",
            True,
            account_label="TradeStation",
            account_number="210TGG51",
            copy_to_clipboard=True,
        ),
        FieldSpec("cash_transfer", "Cash Transfer", "number", False, 0.0),
        FieldSpec("fee", "Fee", "number", False, 0.0),
    ],
    "YQ": [
        FieldSpec("date", "Date", "date", True),
        FieldSpec("stonex_nlv", "StoneX NLV", "number", True),
        FieldSpec("cash_transfer", "Cash Transfer", "number", False, 0.0),
    ],
}

# Canonical program codes and their display labels.
PROGRAMS: list[str] = list(PROGRAM_FIELDS.keys())
PROGRAM_LABELS: dict[str, str] = {
    "TKP": "TKP",
    "TCP": "TCP",
    "AGM": "AGM",
    "YQ": "Y&Q",
}

# Every physical value column that can appear in the daily_rows table. The set
# union across all programs; a given program only uses a subset.
DATA_COLUMNS: list[str] = [
    "stonex_nlv",
    "plus500_nlv",
    "tradestation_nlv",
    "cash_transfer",
    "fee",
]


def normalize_program(program: str) -> Optional[str]:
    """Return the canonical program code (upper-cased) or None if unknown."""
    code = (program or "").strip().upper()
    return code if code in PROGRAM_FIELDS else None


def _field_metadata(spec: FieldSpec) -> dict:
    """Serialize one field spec for GET /api/programs."""
    out: dict = {
        "name": spec.name,
        "label": spec.label,
        "type": spec.type,
        "required": spec.required,
        "default": spec.default,
        "copy_to_clipboard": spec.copy_to_clipboard,
    }
    if spec.account_label is not None:
        out["account_label"] = spec.account_label
    if spec.account_number is not None:
        out["account_number"] = spec.account_number
    return out


def program_metadata() -> list[dict]:
    """JSON-serializable field metadata for every program (for the frontend)."""
    out = []
    for code, specs in PROGRAM_FIELDS.items():
        out.append(
            {
                "code": code,
                "label": PROGRAM_LABELS[code],
                "fields": [_field_metadata(f) for f in specs],
            }
        )
    return out


def program_nlv(program: str, row: dict) -> Optional[float]:
    """Total NLV for one stored row, per program's accounting rule:

      * TKP = stonex_nlv + plus500_nlv
      * TCP = stonex_nlv
      * AGM = tradestation_nlv
      * YQ  = stonex_nlv

    AGM's `fee` is deliberately NOT read here. Whether `fee` is already netted
    out of `tradestation_nlv` by the broker or billed separately is not yet
    confirmed, so per the "do not silently mix it into performance" rule this
    is a conservative, documented placeholder: performance is computed from
    `tradestation_nlv` alone until the real fee/NLV relationship is confirmed.
    See app/performance.py for where this feeds the return calculation.

    Returns None if a required component is missing (defensive — validation
    should already guarantee required NLV fields are present).
    """
    code = program.upper()
    if code == "TKP":
        stonex = row.get("stonex_nlv")
        plus500 = row.get("plus500_nlv")
        if stonex is None or plus500 is None:
            return None
        return float(stonex) + float(plus500)
    if code in ("TCP", "YQ"):
        stonex = row.get("stonex_nlv")
        return float(stonex) if stonex is not None else None
    if code == "AGM":
        tradestation = row.get("tradestation_nlv")
        return float(tradestation) if tradestation is not None else None
    return None


def public_row(program: str, raw: dict) -> dict:
    """Project a raw daily_rows record down to just the fields for `program`."""
    code = program.upper()
    specs = PROGRAM_FIELDS[code]
    out: dict = {"program": code, "date": raw["date"]}
    for f in specs:
        if f.name == "date":
            continue
        out[f.name] = raw.get(f.name)
    out["exported"] = bool(raw.get("exported", 0))
    out["created_at"] = raw.get("created_at")
    out["updated_at"] = raw.get("updated_at")
    return out
