"""
Explicit registry of Algominds/Momentum Pacer participating accounts for the admin Portal.

Static investor/account rows come from the onboarding tracker. Live workbook- and
CSV-derived figures (NLV, month %, since-inception %) are merged only onto the
single CSV-backed tearsheet account (210TGG51 / Algominds). All other fields left
blank on registry-only rows render as "-" in the shared Portal template.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

FEE_TIER_LABEL = "Graduated vs S&P 500 (see Fee Slab Structure)"
EXCHANGE_FEE_MEMBER = "Member"
EXCHANGE_FEE_NON_MEMBER = "Non-Member"
MEMBER_EXCHANGE_FEE_ACCOUNT = "Hughes & Company LLC"

# CSV-backed live tearsheet account — must keep tearsheet_href wired to "/".
ACTIVE_TEARSHEET_ACCOUNT_NUMBER = "210TGG51"

# AGM Portal columns (no onboarding Status — not shown on the registry board).
AGM_PORTAL_COLUMNS: List[str] = [
    "Account",
    "Account number",
    "Starting date",
    "Benchmark base",
    "Units",
    "After-fee NLV",
    "Week %",
    "Month %",
    "Since inception %",
    "Exchange fee tier",
    "Last updated",
    "Tearsheet",
]

AGM_PORTAL_ROW_FIELDS: List[str] = [
    "account",
    "account_number",
    "starting_date",
    "benchmark_base",
    "units",
    "after_fee_nlv",
    "week_pct",
    "month_pct",
    "since_inception_pct",
    "fee_tier",
    "last_updated",
    "tearsheet",
]

# Canonical investor registry (row id, name, account #, units).
INVESTOR_REGISTRY: List[Dict[str, Any]] = [
    {"row_id": "0", "account": "Srinivas Sundaragopal", "account_number": "210RWY45", "units": 1},
    {"row_id": "00", "account": "Algominds", "account_number": ACTIVE_TEARSHEET_ACCOUNT_NUMBER, "units": 1},
    {"row_id": "01", "account": "Dr. Rajeev Fernando", "account_number": "210WFP24", "units": 2},
    {"row_id": "02", "account": "Vishal Khemka", "account_number": "210WHA83", "units": 1},
    {"row_id": "03", "account": "Karthik Swaminathan", "account_number": "210WHA74", "units": 1},
    {"row_id": "04", "account": "Kaladhar Palaniappan", "account_number": "210WHE52", "units": 2},
    {"row_id": "05", "account": MEMBER_EXCHANGE_FEE_ACCOUNT, "account_number": "210RFQ36", "units": 1},
    {"row_id": "06", "account": "Pratik Sharma", "account_number": "210WLF36", "units": 1},
    {"row_id": "07", "account": "Vikram Suman", "account_number": "210WLW88", "units": 1},
    {"row_id": "09", "account": "Prasad Surapaneni", "account_number": "210WNX58", "units": 1},
    {"row_id": "10", "account": "Tesla in the Gong Pty Ltd", "account_number": "210WVK60", "units": 1},
    {"row_id": "11", "account": "Ramachandran Kuppusamy", "account_number": "210WVG99", "units": 1},
    {"row_id": "12", "account": "Pridhiraj Ulaganathan", "account_number": "210WVX15", "units": 1},
]


def _blank_portal_fields() -> Dict[str, Any]:
    return {
        "starting_date": None,
        "benchmark_base": None,
        "after_fee_nlv": None,
        "week_pct": None,
        "month_pct": None,
        "since_inception_pct": None,
        "fee_tier": None,
        "last_updated": None,
        "tearsheet_href": None,
    }


def build_participating_accounts(
    *,
    program_name: str,
    inception_date: datetime,
    benchmark_base: str,
    after_fee_nlv: Optional[float],
    month_pct: Optional[float],
    since_inception_pct_display: Optional[str],
    last_updated: str,
) -> List[Dict[str, Any]]:
    """One row per registered investor. Live metrics attach only to 210TGG51.

    program_name is accepted for call-site compatibility with mp_ts.py but is not
    used as a registry row label — the Algominds account row uses the static name.
    since_inception_pct_display is accepted pre-formatted (e.g. "49.65%") so the
    Portal always shows the exact figure already computed by mp_ts.py.
    """
    del program_name  # registry uses static investor names; kept for stable API

    rows: List[Dict[str, Any]] = []
    for entry in INVESTOR_REGISTRY:
        exchange_fee = (
            EXCHANGE_FEE_MEMBER
            if entry["account"] == MEMBER_EXCHANGE_FEE_ACCOUNT
            else EXCHANGE_FEE_NON_MEMBER
        )
        row: Dict[str, Any] = {
            "account": entry["account"],
            "account_number": entry["account_number"],
            "units": entry.get("units"),
            **_blank_portal_fields(),
            "fee_tier": exchange_fee,
        }
        if entry["account_number"] == ACTIVE_TEARSHEET_ACCOUNT_NUMBER:
            row.update(
                {
                    "starting_date": inception_date.strftime("%Y-%m-%d"),
                    "benchmark_base": benchmark_base,
                    "after_fee_nlv": f"${after_fee_nlv:,.2f}" if after_fee_nlv is not None else None,
                    "month_pct": f"{month_pct:.2f}%" if month_pct is not None else None,
                    "since_inception_pct": since_inception_pct_display,
                    "last_updated": last_updated,
                    "tearsheet_href": "/",
                }
            )
        rows.append(row)
    return rows
