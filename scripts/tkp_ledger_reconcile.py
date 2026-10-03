"""Read-only cent-level TKP ledger reconciliation (Decimal arithmetic)."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import tkp_ts as m  # noqa: E402

STATE = REPO / "daily_returns_secret_state.json"


def _d(x) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    if isinstance(x, (int, float, Decimal)):
        return Decimal(str(x))
    s = str(x).replace("$", "").replace(",", "").strip()
    return Decimal(s) if s else Decimal("0")


def main() -> int:
    rows = json.loads(STATE.read_text(encoding="utf-8"))
    rows_sorted = sorted(rows, key=lambda r: str(r.get("Date", "")))
    auth = [r for r in rows_sorted if r.get("StoneX") and r.get("NAV")]

    bl = Decimal(str(m.BASELINE_AMOUNT))
    sum_gross = sum((_d(r.get("$PL")) for r in auth), Decimal("0"))
    sum_fee = sum((_d(r.get("Fee (20%)")) for r in auth), Decimal("0"))
    sum_net = sum((_d(r.get("Net P&L")) for r in auth), Decimal("0"))
    dep_pos = sum((max(_d(r.get("Deposit")), Decimal("0")) for r in auth), Decimal("0"))
    dep_neg = sum((min(_d(r.get("Deposit")), Decimal("0")) for r in auth), Decimal("0"))

    last_nav = _d(auth[-1]["NAV"])
    perf = m._performance_series_from_secret_rows(rows_sorted)
    chart_end = Decimal(str(perf.iloc[-1])).quantize(Decimal("0.01"))

    bl_plus_net = (bl + sum_net).quantize(Decimal("0.01"))
    bl_plus_gross_minus_fee = (bl + sum_gross - sum_fee).quantize(Decimal("0.01"))

    recs = m._recompute_monthly_records(perf, float(bl), secret_rows=rows_sorted)
    month_sum = Decimal("0")
    for rec in recs:
        for mon in (
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ):
            v = rec.get(mon, "")
            if v:
                month_sum += Decimal(v.rstrip("%"))

    chart_cum = (chart_end - bl) / bl * Decimal("100")
    implied_from_months = (bl * (Decimal("1") + month_sum / Decimal("100"))).quantize(
        Decimal("0.01")
    )

    apr_2023 = None
    for rec in recs:
        if rec.get("Year") == "2023":
            apr_2023 = rec.get("Apr", "").rstrip("%")

    print("=== TKP ledger reconciliation ===")
    print(f"state file: {STATE}")
    print(f"rows: {len(rows_sorted)} authoritative: {len(auth)}")
    print(f"first date: {auth[0]['Date']}  last date: {auth[-1]['Date']}")
    print(f"baseline: {bl}")
    print(f"sum $PL: {sum_gross}")
    print(f"sum Fee (20%): {sum_fee}")
    print(f"sum Net P&L: {sum_net}")
    print(f"gross - fee (ledger cols): {sum_gross - sum_fee}")
    print(f"net vs gross-fee delta: {sum_net - (sum_gross - sum_fee)}")
    print(f"deposits (+): {dep_pos}  withdrawals (-): {dep_neg}")
    print(f"final persisted NAV (last auth row): {last_nav}")
    print(f"baseline + sum(Net P&L): {bl_plus_net}")
    print(f"baseline + gross - fee: {bl_plus_gross_minus_fee}")
    print(f"chart ending NAV: {chart_end}")
    print(f"chart cumulative %: {chart_cum.quantize(Decimal('0.0001'))}")
    print(f"sum monthly nominal %: {month_sum.quantize(Decimal('0.0001'))}")
    print(f"ending implied by month sum: {implied_from_months}")
    print(f"April 2023 month cell: {apr_2023}%")
    print("--- deltas (cents) ---")
    print(f"chart - persisted NAV: {(chart_end - last_nav).quantize(Decimal('0.01'))}")
    print(f"BL+net - persisted NAV: {(bl_plus_net - last_nav).quantize(Decimal('0.01'))}")
    print(f"BL+gross-fee - persisted: {(bl_plus_gross_minus_fee - last_nav).quantize(Decimal('0.01'))}")
    print(f"months-implied - persisted: {(implied_from_months - last_nav).quantize(Decimal('0.01'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
