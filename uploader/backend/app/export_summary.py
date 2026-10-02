"""Build read-only export summary for the UI from batches + audit events."""
from __future__ import annotations

import json
from typing import Any, Optional

from .programs import PROGRAMS


def _parse_detail(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def reconstruct_downstream_from_audit(
    batch_id: int,
    audit_events: list[dict[str, Any]],
    *,
    target_env: str = "production",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rebuild downstream.results shape from downstream_export_* audit rows."""
    by_program: dict[str, list[dict[str, Any]]] = {code: [] for code in PROGRAMS}

    for event in audit_events:
        detail = _parse_detail(event.get("detail"))
        if detail.get("batch_id") != batch_id:
            continue
        action = event.get("action") or ""
        program = event.get("program")
        date = event.get("date")
        if program not in by_program or not date:
            continue

        if action == "downstream_export_success":
            verification = detail.get("verification") or "verified"
            row_status = "pending_refresh" if verification == "pending_refresh" else "success"
            by_program[program].append(
                {
                    "date": date,
                    "status": row_status,
                    "verification": verification,
                }
            )
        elif action == "downstream_export_failure":
            by_program[program].append(
                {
                    "date": date,
                    "status": "failure",
                    "reason": detail.get("error_message")
                    or detail.get("error_code")
                    or "Export failed",
                }
            )
        elif action == "downstream_export_dry_run":
            by_program[program].append({"date": date, "status": "dry_run"})
        elif action == "downstream_export_skipped":
            by_program[program].append(
                {
                    "date": date,
                    "status": "skipped",
                    "reason": detail.get("reason") or "skipped",
                }
            )

    results: dict[str, dict[str, Any]] = {}
    for program in PROGRAMS:
        date_results = by_program[program]
        if not date_results:
            results[program] = {"status": "no_rows", "date_results": []}
            continue

        statuses = {r["status"] for r in date_results}
        any_failure = any(
            s in ("failure", "not_confirmed") for s in statuses
        )
        any_success = any(s in ("success", "pending_refresh", "dry_run") for s in statuses)
        if any_failure and any_success:
            program_status = "partial_failure"
        elif any_failure:
            program_status = "failure"
        elif any(s == "pending_refresh" for s in statuses):
            program_status = "pending_refresh"
        elif dry_run:
            program_status = "dry_run"
        elif program == "YQ" and all(s == "skipped" for s in statuses):
            program_status = "skipped"
        else:
            program_status = "success"

        results[program] = {"status": program_status, "date_results": date_results}

    return {
        "target_env": target_env,
        "dry_run": dry_run,
        "results": results,
    }


def build_preflight_blocked_downstream(
    rows: list[dict[str, Any]],
    probe_results: list[Any],
    *,
    target_env: str,
    dry_run: bool,
) -> dict[str, Any]:
    """When ingest preflight fails, describe blocked rows without calling export."""
    probe_by_program = {r.program: r for r in probe_results}
    by_program: dict[str, list[dict[str, Any]]] = {code: [] for code in PROGRAMS}
    for row in rows:
        by_program.setdefault(row["program"], []).append(row)

    results: dict[str, dict[str, Any]] = {}
    for program in PROGRAMS:
        program_rows = by_program.get(program) or []
        probe = probe_by_program.get(program)
        if program == "YQ" and program_rows:
            date_results = [
                {
                    "date": r["date"],
                    "status": "skipped",
                    "reason": "Y&Q downstream export not implemented yet.",
                }
                for r in program_rows
            ]
            results[program] = {"status": "skipped", "date_results": date_results}
            continue
        if not program_rows:
            results[program] = {"status": "no_rows", "date_results": []}
            continue

        reason = (
            f"Preflight blocked export — {probe.message}"
            if probe and probe.message
            else "Preflight blocked export — ingest endpoint not ready."
        )
        date_results = [
            {"date": r["date"], "status": "failure", "reason": reason}
            for r in program_rows
        ]
        results[program] = {"status": "failure", "date_results": date_results}

    return {"target_env": target_env, "dry_run": dry_run, "results": results}


def latest_export_summary(db: Any, settings: Any) -> Optional[dict[str, Any]]:
    batch = db.get_latest_downstream_export_batch()
    if batch is None:
        return None

    batch_id = int(batch["id"])
    stored = batch.get("downstream_result")
    downstream: Optional[dict[str, Any]] = None
    if stored:
        try:
            downstream = json.loads(stored) if isinstance(stored, str) else stored
        except (ValueError, TypeError):
            downstream = None

    if downstream is None:
        events = db.get_audit(limit=500)
        downstream = reconstruct_downstream_from_audit(
            batch_id,
            events,
            target_env=batch.get("target_env") or settings.export_target_env,
            dry_run=bool(batch.get("dry_run")),
        )

    counts = db.export_row_counts()
    return {
        "batch_id": batch_id,
        "ts": batch.get("ts"),
        "batch_status": batch.get("status"),
        "row_count": batch.get("row_count"),
        "target_env": batch.get("target_env"),
        "dry_run": bool(batch.get("dry_run")),
        "downstream": downstream,
        "eligible_count": counts["eligible"],
        "exported_count": counts["exported"],
        "manual_total": counts["manual_total"],
    }
