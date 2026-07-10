"""Historical backfill import — sandbox-only, read-only toward the tearsheets.

This module accepts rows EXTRACTED from the four tearsheet apps' historical
stores (see ``scripts/extract_tearsheet_history.py`` and
``docs/historical_backfill.md``) and lands them in the separate
``historical_rows`` table. Safety contract:

  * SANDBOX ONLY. The API route refuses in production by construction — there
    is deliberately no flag that enables a production import in this build.
  * READ-ONLY toward TKP/TCP/AGM/Y&Q. This service never opens a tearsheet
    file; the extractor script that produces the payload only ever reads.
  * NEVER touches ``daily_rows``. Glenn's manual entries and the export path
    (which reads only ``daily_rows``) are unaffected; backfilled rows can never
    be exported downstream.
  * IDEMPOTENT. Re-importing the same payload reports every row "unchanged"
    and writes nothing.
  * LABELED. Every stored row carries the machine source label it came from
    (e.g. ``tkp_state_json``) — nothing imported can masquerade as a manual
    entry ("manual" is a reserved label and is rejected).
  * REVERSIBLE. ``DELETE /api/backfill`` clears historical rows without going
    near ``daily_rows``.

Precedence: a manual daily_rows entry always supersedes a historical row on
the same (program, date) — enforced in ``Database.get_merged_rows`` and
reported at import time via the ``overridden_by_manual`` count.
"""

from __future__ import annotations

from typing import Any, Optional

from .programs import PROGRAMS, normalize_program
from .validation import RowValidationError, validate_row

# Row fields that are import metadata, not program data columns.
_META_FIELDS = ("program", "source", "source_detail")

# Reserved for Glenn's own entries in merged views; an import may never use it.
RESERVED_SOURCE = "manual"

MAX_REPORTED_ROW_ERRORS = 50


def _empty_program_report() -> dict:
    return {
        "received": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "overridden_by_manual": 0,
        "first_date": None,
        "last_date": None,
    }


def run_backfill_import(
    db,
    settings,
    actor: str,
    rows: list[dict],
    dry_run: bool,
) -> dict:
    """Validate and (unless ``dry_run``) land extracted historical rows.

    Returns the audit report: per-program created/updated/unchanged counts,
    date ranges, manual-override collisions, and any per-row validation
    errors. The same classification code path runs in both modes, so the
    dry-run preview always matches the import that follows it.
    """
    programs_report: dict[str, dict] = {code: _empty_program_report() for code in PROGRAMS}
    row_errors: list[dict] = []
    accepted: list[tuple[str, dict, str, Optional[str]]] = []

    for idx, raw in enumerate(rows):
        if not isinstance(raw, dict):
            row_errors.append({"index": idx, "errors": {"row": "expected a JSON object"}})
            continue

        code = normalize_program(str(raw.get("program") or ""))
        if code is None:
            row_errors.append(
                {"index": idx, "errors": {"program": f"unknown program '{raw.get('program')}'"}}
            )
            continue

        source = raw.get("source")
        if not isinstance(source, str) or not source.strip():
            row_errors.append(
                {"index": idx, "program": code, "errors": {"source": "source label is required"}}
            )
            continue
        source = source.strip()
        if source.lower() == RESERVED_SOURCE:
            row_errors.append(
                {
                    "index": idx,
                    "program": code,
                    "errors": {"source": "'manual' is reserved for Glenn's own entries"},
                }
            )
            continue

        source_detail = raw.get("source_detail")
        if source_detail is not None and not isinstance(source_detail, str):
            source_detail = str(source_detail)

        payload = {k: v for k, v in raw.items() if k not in _META_FIELDS}
        try:
            normalized = validate_row(code, payload)
        except RowValidationError as exc:
            row_errors.append({"index": idx, "program": code, "errors": exc.errors})
            continue

        programs_report[code]["received"] += 1
        accepted.append((code, normalized, source, source_detail))

    # Manual-collision detection: which accepted rows are superseded by an
    # existing manual entry. They are still stored (so history is complete if
    # the manual row is ever deleted) but reported so the operator sees them.
    manual_dates = {code: {r["date"] for r in db.get_all_rows(code)} for code in PROGRAMS}

    batch_id = db.add_backfill_batch(
        app_env=settings.app_env,
        dry_run=dry_run,
        actor=actor,
        row_count=len(accepted),
        summary={"received": len(rows), "row_errors": len(row_errors)},
    )

    for code, normalized, source, source_detail in accepted:
        action = db.upsert_historical_row(
            code,
            normalized,
            source=source,
            source_detail=source_detail,
            batch_id=batch_id,
            dry_run=dry_run,
        )
        report = programs_report[code]
        report[action] += 1
        if normalized["date"] in manual_dates[code]:
            report["overridden_by_manual"] += 1
        if report["first_date"] is None or normalized["date"] < report["first_date"]:
            report["first_date"] = normalized["date"]
        if report["last_date"] is None or normalized["date"] > report["last_date"]:
            report["last_date"] = normalized["date"]

    db.add_audit(
        action="backfill_dry_run" if dry_run else "backfill_import",
        actor=actor,
        detail={
            "batch_id": batch_id,
            "rows_received": len(rows),
            "rows_accepted": len(accepted),
            "row_errors": len(row_errors),
            "programs": {
                code: {
                    k: rep[k]
                    for k in ("received", "created", "updated", "unchanged", "overridden_by_manual")
                }
                for code, rep in programs_report.items()
                if rep["received"]
            },
        },
    )

    if dry_run:
        message = (
            "DRY RUN — preview only. Nothing was written to historical_rows; "
            "counts show what a real import would do. daily_rows and the "
            "tearsheet apps are never touched by backfill."
        )
    else:
        message = (
            "Backfill imported into historical_rows only. daily_rows (Glenn's "
            "manual entries) and the tearsheet apps were not touched; manual "
            "entries supersede imported history on any shared date."
        )

    return {
        "dry_run": dry_run,
        "app_env": settings.app_env,
        "batch_id": batch_id,
        "total_rows_received": len(rows),
        "total_rows_accepted": len(accepted),
        "programs": programs_report,
        "row_errors": row_errors[:MAX_REPORTED_ROW_ERRORS],
        "row_error_count": len(row_errors),
        "message": message,
    }


def sandbox_only_detail() -> str:
    return (
        "Historical backfill is sandbox-only in this build. There is no flag "
        "that enables it in production; a production backfill would be a "
        "separate, reviewed change."
    )
