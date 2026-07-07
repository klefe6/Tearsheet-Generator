"""
Explicit registry of Algominds/Momentum Pacer participating accounts for the admin Portal.

Values are derived from mp_ts.py's own live workbook-computed figures (the same
numbers shown on the public tearsheet) -- not fabricated here. Account number,
per-account "Units", weekly return, and a single "Exchange fee tier" value are
not tracked anywhere in the current AGM data model (fees are graduated slabs
vs. a monthly S&P 500 benchmark, not a flat exchange tier), so those cells are
intentionally left blank -- the shared Portal template renders blanks as "-"
rather than inventing a number.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

FEE_TIER_LABEL = "Graduated vs S&P 500 (see Fee Slab Structure)"


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
    """One row per participating account. AGM currently has exactly one live account.

    since_inception_pct_display is accepted pre-formatted (e.g. "49.65%") so the
    Portal always shows the exact figure already computed by mp_ts.py's own
    calc_performance_metrics(), instead of re-deriving it and risking drift.
    """
    return [
        {
            "account": program_name,
            "account_number": None,
            "starting_date": inception_date.strftime("%Y-%m-%d"),
            "benchmark_base": benchmark_base,
            "units": None,
            "after_fee_nlv": f"${after_fee_nlv:,.2f}" if after_fee_nlv is not None else None,
            "week_pct": None,
            "month_pct": f"{month_pct:.2f}%" if month_pct is not None else None,
            "since_inception_pct": since_inception_pct_display,
            "fee_tier": FEE_TIER_LABEL,
            "last_updated": last_updated,
            # The single CSV-backed live account links to the current daily
            # admin tearsheet entry; future accounts default to "Coming soon".
            "tearsheet_href": "/",
        }
    ]
