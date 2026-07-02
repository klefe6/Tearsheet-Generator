#!/usr/bin/env python3
"""
Test-only full-ledger replay helper for TCP v2 calculator validation.

Not production application logic.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tcp_calculations import (
    CALCULATED_FIELDS,
    TCPInceptionContext,
    TCPRules,
    TCPEntry,
    build_seed_row,
    compare_field,
    compute_tcp_row,
)
from tcp_config import load_config
from tcp_ledger import LedgerLoadResult, LedgerRecord, load_ledger

CURRENCY_FIELDS = (
    "NLV",
    "$PL",
    "Inc. Fee",
    "cumm fee",
    "Day PnL",
    "nav-x1",
    "Loss Carry",
    "HWM",
)
PERCENT_FIELDS = ("%Net", "S net cummulative %")


@dataclass
class RowMismatch:
    excel_row_number: int
    row_date: str
    field: str
    calculated: Any
    observed: Any
    difference: float


@dataclass
class ReplayReport:
    completed_rows: int = 0
    seed_rows: int = 0
    rows_attempted: int = 0
    rows_matched: int = 0
    rows_mismatched: int = 0
    first_mismatch: Optional[RowMismatch] = None
    mismatches: List[RowMismatch] = field(default_factory=list)
    max_currency_difference: float = 0.0
    max_percentage_difference: float = 0.0
    max_currency_field: Optional[str] = None
    max_percentage_field: Optional[str] = None
    final_calculated_nav: Optional[float] = None
    workbook_final_nav: Optional[float] = None
    final_nav_difference: Optional[float] = None
    final_hwm_difference: Optional[float] = None
    final_loss_carry_difference: Optional[float] = None
    final_cumm_fee_difference: Optional[float] = None
    formula_transition_boundaries: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completed_rows": self.completed_rows,
            "seed_rows": self.seed_rows,
            "rows_attempted": self.rows_attempted,
            "rows_matched": self.rows_matched,
            "rows_mismatched": self.rows_mismatched,
            "first_mismatch": (
                {
                    "excel_row_number": self.first_mismatch.excel_row_number,
                    "date": self.first_mismatch.row_date,
                    "field": self.first_mismatch.field,
                    "calculated": self.first_mismatch.calculated,
                    "observed": self.first_mismatch.observed,
                    "difference": self.first_mismatch.difference,
                }
                if self.first_mismatch
                else None
            ),
            "max_currency_difference": self.max_currency_difference,
            "max_currency_field": self.max_currency_field,
            "max_percentage_difference": self.max_percentage_difference,
            "max_percentage_field": self.max_percentage_field,
            "final_calculated_nav": self.final_calculated_nav,
            "workbook_final_nav": self.workbook_final_nav,
            "final_nav_difference": self.final_nav_difference,
            "final_hwm_difference": self.final_hwm_difference,
            "final_loss_carry_difference": self.final_loss_carry_difference,
            "final_cumm_fee_difference": self.final_cumm_fee_difference,
            "formula_transition_boundaries": self.formula_transition_boundaries,
            "mismatch_count": len(self.mismatches),
        }


def entry_from_record(record: LedgerRecord) -> TCPEntry:
    fields = record.fields
    return TCPEntry(
        row_date=fields["Date"],
        cash_balance=Decimal(str(fields["Cash Balance"])),
        cash_transfers=Decimal(str(fields.get("Cash Transfers") or 0)),
        tranche_count=int(fields["#"]),
        trading_days=int(fields["Trading Days"]),
    )


def replay_ledger(
    ledger: LedgerLoadResult,
    *,
    rules: Optional[TCPRules] = None,
) -> ReplayReport:
    rules = rules or TCPRules()
    report = ReplayReport(completed_rows=len(ledger.completed_records))
    if not ledger.completed_records:
        return report

    first = ledger.completed_records[0]
    seed_entry = entry_from_record(first)
    calculated = build_seed_row(seed_entry, TCPInceptionContext(), rules=rules)
    report.seed_rows = 1
    _compare_row(report, first, calculated, rules)

    for record in ledger.completed_records[1:]:
        entry = entry_from_record(record)
        calculated = compute_tcp_row(calculated, entry, rules=rules)
        _compare_row(report, record, calculated, rules)

    last_observed = ledger.completed_records[-1].fields
    report.workbook_final_nav = float(last_observed["nav-x1"])
    report.final_calculated_nav = float(calculated["nav-x1"])
    report.final_nav_difference = abs(
        report.final_calculated_nav - report.workbook_final_nav
    )
    report.final_hwm_difference = abs(
        float(calculated["HWM"]) - float(last_observed["HWM"])
    )
    report.final_loss_carry_difference = abs(
        float(calculated["Loss Carry"]) - float(last_observed["Loss Carry"])
    )
    report.final_cumm_fee_difference = abs(
        float(calculated["cumm fee"]) - float(last_observed["cumm fee"])
    )
    report.formula_transition_boundaries = [
        "Inc. Fee: row 3 uses I$1 reference; row 4+ uses U$10 (equivalent 0.20 rate)",
        "cumm fee: row 3 =I only; row 4+ =I+J_prev",
        "Day PnL: row 3 literal 0; row 4+ =H-I",
        "nav-x1: row 3 =U6 seed; row 4+ =L_prev+(H-I)/G",
        "HWM: row 3 =MAX(L$3:L3); row 4+ tranche-aware IF/MAX blend",
        "%Net: rows 3-6 =/L$3; row 7+ =/(L$3*G) (equivalent when G=1)",
        "S net cummulative %: rows 3-4 =O; row 5+ =O+P_prev (via Trading Days<=1 rule)",
    ]
    return report


def _compare_row(
    report: ReplayReport,
    record: LedgerRecord,
    calculated: Dict[str, Any],
    rules: TCPRules,
) -> None:
    report.rows_attempted += 1
    row_ok = True
    for field in sorted(CALCULATED_FIELDS):
        observed = record.fields.get(field)
        calc_val = calculated.get(field)
        ok, diff = compare_field(field, calc_val, observed, rules=rules)
        if field in CURRENCY_FIELDS and diff > report.max_currency_difference:
            report.max_currency_difference = diff
            report.max_currency_field = field
        if field in PERCENT_FIELDS and diff > report.max_percentage_difference:
            report.max_percentage_difference = diff
            report.max_percentage_field = field
        if not ok:
            row_ok = False
            mismatch = RowMismatch(
                excel_row_number=record.excel_row_number,
                row_date=str(record.fields["Date"]),
                field=field,
                calculated=calc_val,
                observed=observed,
                difference=diff,
            )
            report.mismatches.append(mismatch)
            if report.first_mismatch is None:
                report.first_mismatch = mismatch
    if row_ok:
        report.rows_matched += 1
    else:
        report.rows_mismatched += 1


def main() -> int:
    cfg = load_config()
    wb_path = Path(cfg.workbook_path)
    if not wb_path.is_file():
        print(f"Workbook not available: {wb_path}")
        return 1
    ledger = load_ledger(str(wb_path))
    report = replay_ledger(ledger)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.rows_mismatched == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
