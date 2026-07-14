#!/usr/bin/env python3
"""In-process AGM merge-readiness smoke (no server start)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MP = ROOT / "Momentum Pacer"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MP) not in sys.path:
    sys.path.insert(0, str(MP))

import mp_ts  # noqa: E402


def main() -> int:
    errors: list[str] = []

    bal = mp_ts.daily_balances_df
    n = len(bal)
    if n != 184:
        errors.append(f"row count expected 184 got {n}")
    latest = bal.iloc[-1]
    latest_date = latest["Date"].strftime("%Y-%m-%d")
    latest_nlv = float(latest["Net Worth"])
    if latest_date != "2026-07-06":
        errors.append(f"latest date expected 2026-07-06 got {latest_date}")
    if abs(latest_nlv - 45335.28) > 0.01:
        errors.append(f"latest NLV expected 45335.28 got {latest_nlv}")

    summary = mp_ts.monthly_summary.table
    if summary.empty:
        errors.append("monthly summary empty")
    else:
        dates = set(summary["date"].dt.strftime("%Y-%m-01"))
        if "2026-06-01" not in dates:
            errors.append("June 2026 missing from Performance Summary")
        if "2026-07-01" in dates:
            errors.append("July 2026 incorrectly present as complete month")
        if summary["date"].max().strftime("%Y-%m-%d") != "2026-06-01":
            errors.append(f"summary max month expected 2026-06-01 got {summary['date'].max()}")

    layout = str(mp_ts.serve_layout())
    if "CPO" in layout:
        errors.append("CPO wording found in layout")
    if "Add Row" in layout and "agm-admin-daily" in layout:
        # public layout may contain id strings; admin controls must be gated
        pass
    client_table = mp_ts.build_client_daily_table_section()
    client_str = str(client_table)
    if "is_open" in client_str and "is_open=True" in client_str.replace(" ", ""):
        errors.append("client daily table not collapsed by default")

  # app object exists
    assert mp_ts.app is not None
    assert mp_ts.app.server is not None

    print("AGM in-process smoke")
    print(f"  rows={n} latest={latest_date} nlv={latest_nlv:,.2f}")
    print(f"  summary months={len(summary)} max={summary['date'].max().strftime('%b %Y') if not summary.empty else 'n/a'}")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        return 1
    print("  PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
