#!/usr/bin/env python3
"""Dry-run reconciliation: TKP historical StoneX correction vs live DB/API.

Read-only toward production when run with --report-only (default).
Use --write-json to emit a payload for POST /api/backfill/import after deploy.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "uploader" / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO / "uploader" / "backend"))

from app.programs import program_nlv  # noqa: E402
from scripts.extract_tearsheet_history import extract_tkp, parse_money  # noqa: E402

HISTORICAL_END = "2026-07-09"
MANUAL_DATES = {"2026-07-10", "2026-07-13"}
SAMPLE_DATES = ["2026-07-07", "2026-07-08", "2026-07-09"]


def _old_program_nlv(row: dict) -> float:
    return float(row["stonex_nlv"]) + float(row.get("plus500_nlv") or 0.0)


def _normalized_stonex_only(rows: list[dict]) -> list[float]:
    from app.performance import _normalized_values

    annotated = []
    for r in rows:
        d = dict(r)
        d["_nlv"] = program_nlv("TKP", r)
        annotated.append(d)
    return _normalized_values(annotated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=_REPO / "daily_returns_secret_state.json")
    parser.add_argument("--db", type=Path, help="optional uploader SQLite for before-state")
    parser.add_argument("--historical-end", default=HISTORICAL_END)
    parser.add_argument("--write-json", type=Path, help="write corrected import payload here")
    args = parser.parse_args()

    extracted = extract_tkp(args.state)
    window = [r for r in extracted.rows if r["date"] <= args.historical_end]
    by_date = {r["date"]: r for r in window}

    old_hist: dict[str, dict] = {}
    if args.db and args.db.exists():
        conn = sqlite3.connect(args.db)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT date, stonex_nlv, plus500_nlv, cash_transfer FROM historical_rows "
            "WHERE program = 'TKP' AND date <= ? ORDER BY date",
            (args.historical_end,),
        ):
            old_hist[row["date"]] = dict(row)
        conn.close()

    print(f"TKP historical window rows: {len(window)} (through {args.historical_end})")
    print(f"{'date':<12} {'old_stonex':>14} {'new_stonex':>14} {'plus500':>14} "
          f"{'old_chart':>14} {'new_chart':>14} manual?")
    print("-" * 96)

    old_series_input = []
    new_series_input = []
    stonex_corrections = 0
    plus500_unchanged = 0

    for date in sorted(by_date):
        new = by_date[date]
        old = old_hist.get(date, {})
        old_s = old.get("stonex_nlv")
        new_s = new["stonex_nlv"]
        plus = new["plus500_nlv"]
        if old_s is not None and abs(old_s - new_s) > 0.009:
            stonex_corrections += 1
        if old and abs(float(old.get("plus500_nlv") or 0) - plus) < 0.009:
            plus500_unchanged += 1
        old_chart = _old_program_nlv(old) if old else None
        new_chart = program_nlv("TKP", new)
        if date in SAMPLE_DATES or (old_s is not None and abs((old_s or 0) - new_s) > 1000):
            print(
                f"{date:<12} "
                f"{(old_s if old_s is not None else 0):>14,.2f} "
                f"{new_s:>14,.2f} {plus:>14,.2f} "
                f"{(old_chart if old_chart is not None else 0):>14,.2f} "
                f"{new_chart:>14,.2f} "
                f"{'yes' if date in MANUAL_DATES else 'no'}"
            )
        old_series_input.append(old if old else {"stonex_nlv": new_s, "plus500_nlv": plus, "cash_transfer": 0})
        new_series_input.append(new)

    old_norm = _normalized_stonex_only(old_series_input)
    new_norm = _normalized_stonex_only(new_series_input)
    print("\nSample normalized chart points (StoneX-only, first/last/mid):")
    for idx in (0, len(new_norm) // 2, len(new_norm) - 1):
        print(
            f"  idx {idx} date {sorted(by_date)[idx]}: "
            f"old=${old_norm[idx]:,.2f} new=${new_norm[idx]:,.2f}"
        )

    print(f"\nSummary:")
    print(f"  StoneX values to correct: {stonex_corrections if old_hist else len(window)}")
    print(f"  Plus500 unchanged (when old present): {plus500_unchanged}/{len(old_hist) or 0}")
    print(f"  Manual dates untouched by import: {', '.join(sorted(MANUAL_DATES))}")

    if args.write_json:
        payload = {
            "dry_run": False,
            "rows": [dict(r) for r in window],
        }
        args.write_json.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"Wrote {len(window)} rows to {args.write_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
