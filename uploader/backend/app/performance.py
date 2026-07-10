"""Chart-ready performance series for GET /api/performance.

Two modes:

  * combined — one normalized ($100,000) series per PROGRAM only (TKP/TCP/AGM/
    YQ). X-axis is each program's own trading-day index (0, 1, 2, ... — the
    frontend labels these "Day N"), so a program with fewer rows simply ends
    earlier; no shared calendar alignment. Benchmarks are never included.

  * program — the selected program's own series, X-axis = real calendar
    dates, optionally overlaid with SPX/NDX/BTC benchmarks rebased to
    $100,000 as of the program's first available date.

Accounting:
  * Program NLV per row comes from `programs.program_nlv` (TKP=StoneX+Plus500,
    TCP/YQ=StoneX, AGM=TradeStation — AGM's `fee` is a documented exclusion,
    see that function's docstring).
  * Cash transfers are neutralized so deposits/withdrawals never show up as
    performance:
        daily_return = (ending_nlv - cash_transfer) / prior_ending_nlv - 1
    The first row of a series has no "prior" — it is simply the $100,000
    anchor point, so its own cash_transfer never affects the series.

Benchmarks (program mode only):
  * Real daily closes from ``benchmark_store`` (yfinance + CSV cache).
  * Aligned with ``prior_close_within_5_calendar_days`` — weekends/holidays
    use the latest prior close within 5 calendar days (documented in warnings).
  * Program-start rebasing may roll forward up to 14 days when the first entry
    date has no close (e.g. weekend), with an explicit warning.

This module reads directly from the database on every call (no caching), so
the chart is always current after a row create/update/delete or an export
preview.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from .benchmarks import (
    BENCHMARK_ALIGN_POLICY,
    BENCHMARK_SYMBOLS,
    aggregate_benchmark_source,
    get_store,
)
from .programs import PROGRAM_LABELS, PROGRAMS, normalize_program, program_nlv

BASE_VALUE = 100_000.0

PROGRAM_DATA_SOURCE = "uploader_daily_rows"


def _rows_with_nlv(db, program: str) -> list[dict]:
    """This program's rows (oldest first), each annotated with its `_nlv`.

    Rows missing a required NLV component are dropped defensively — validation
    at write time should already guarantee this never happens.
    """
    out = []
    for row in db.get_all_rows(program):
        nlv = program_nlv(program, row)
        if nlv is None:
            continue
        row = dict(row)
        row["_nlv"] = nlv
        out.append(row)
    return out


def _normalized_values(rows: list[dict]) -> list[float]:
    """Compound `rows` (oldest first, each with `_nlv`) into a $100,000 series."""
    values: list[float] = []
    normalized = BASE_VALUE
    prior_raw = None
    for i, row in enumerate(rows):
        raw = row["_nlv"]
        if i == 0:
            normalized = BASE_VALUE
        else:
            cash_transfer = row.get("cash_transfer") or 0.0
            adjusted = raw - cash_transfer
            if not prior_raw:
                daily_return = 0.0
            else:
                daily_return = adjusted / prior_raw - 1.0
            normalized = normalized * (1.0 + daily_return)
        values.append(round(normalized, 4))
        prior_raw = raw
    return values


def _last_updated_at(db) -> str:
    ts = db.get_last_activity_ts()
    return ts or datetime.now(timezone.utc).isoformat()


def _empty_program_series(code: str) -> tuple[list[dict], dict[str, list]]:
    series = [{"key": code, "label": PROGRAM_LABELS[code], "kind": "program", "point_count": 0}]
    return series, {code: []}


def build_combined(db) -> dict:
    """Combined mode: one program-only series per program, trading-day index."""
    warnings: list[str] = []
    series_meta: list[dict] = []
    points: dict[str, list[dict]] = {}

    for code in PROGRAMS:
        rows = _rows_with_nlv(db, code)
        if not rows:
            warnings.append(f"{code}: no data yet.")
            s, p = _empty_program_series(code)
            series_meta.extend(s)
            points.update(p)
            continue
        values = _normalized_values(rows)
        series_meta.append(
            {"key": code, "label": PROGRAM_LABELS[code], "kind": "program", "point_count": len(values)}
        )
        points[code] = [{"x": i, "y": v} for i, v in enumerate(values)]

    return {
        "mode": "combined",
        "x_axis": "trading_day",
        "base_value": BASE_VALUE,
        "program": None,
        "benchmarks": [],
        "series": series_meta,
        "points": points,
        "last_updated_at": _last_updated_at(db),
        "warnings": warnings,
        "program_data_source": PROGRAM_DATA_SOURCE,
        "benchmark_data_source": None,
        "benchmark_align_policy": None,
    }


def build_program(db, program: str, benchmark_symbols: list[str]) -> dict:
    """Program mode: the selected program's own series plus optional benchmarks."""
    code = normalize_program(program)
    warnings: list[str] = []

    rows = _rows_with_nlv(db, code)
    if not rows:
        warnings.append(f"{code}: no data yet.")
        series_meta, points = _empty_program_series(code)
        return {
            "mode": "program",
            "x_axis": "date",
            "base_value": BASE_VALUE,
            "program": code,
            "benchmarks": [],
            "series": series_meta,
            "points": points,
            "last_updated_at": _last_updated_at(db),
            "warnings": warnings,
            "program_data_source": PROGRAM_DATA_SOURCE,
            "benchmark_data_source": None,
            "benchmark_align_policy": None,
        }

    values = _normalized_values(rows)
    dates = [r["date"] for r in rows]
    series_meta: list[dict] = [
        {"key": code, "label": PROGRAM_LABELS[code], "kind": "program", "point_count": len(values)}
    ]
    points: dict[str, list[dict]] = {code: [{"x": d, "y": v} for d, v in zip(dates, values)]}

    resolved_benchmarks: list[str] = []
    benchmark_requested = bool(benchmark_symbols)
    store = get_store()
    store.reset_session()
    seen_warnings: set[str] = set()

    def add_warning(msg: Optional[str]) -> None:
        if msg and msg not in seen_warnings:
            seen_warnings.add(msg)
            warnings.append(msg)

    if benchmark_symbols:
        start_date = date.fromisoformat(dates[0])
        for sym in benchmark_symbols:
            if sym not in BENCHMARK_SYMBOLS:
                warnings.append(f"Unknown benchmark '{sym}' ignored.")
                continue

            base = store.close_on_or_after(sym, start_date)
            add_warning(base.warning)
            if base.value is None:
                warnings.append(
                    f"{sym}: no benchmark data available near {dates[0]}; series omitted."
                )
                continue

            bench_points = []
            for d_str in dates:
                aligned = store.close_on_or_before(sym, date.fromisoformat(d_str))
                add_warning(aligned.warning)
                if aligned.value is None:
                    continue
                bench_points.append(
                    {"x": d_str, "y": round(BASE_VALUE * aligned.value / base.value, 4)}
                )

            if not bench_points:
                warnings.append(f"{sym}: no aligned benchmark points; series omitted.")
                continue

            resolved_benchmarks.append(sym)
            series_meta.append(
                {"key": sym, "label": sym, "kind": "benchmark", "point_count": len(bench_points)}
            )
            points[sym] = bench_points

    bench_source = aggregate_benchmark_source(
        benchmark_requested, len(resolved_benchmarks), store
    )

    return {
        "mode": "program",
        "x_axis": "date",
        "base_value": BASE_VALUE,
        "program": code,
        "benchmarks": resolved_benchmarks,
        "series": series_meta,
        "points": points,
        "last_updated_at": _last_updated_at(db),
        "warnings": warnings,
        "program_data_source": PROGRAM_DATA_SOURCE,
        "benchmark_data_source": bench_source,
        "benchmark_align_policy": (
            BENCHMARK_ALIGN_POLICY if resolved_benchmarks else None
        ),
    }
