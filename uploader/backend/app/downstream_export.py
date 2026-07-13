"""Downstream export: TKP / TCP / AGM sandbox destinations.

See docs/downstream_export_contract.md for the full contract. Summary:

  - Y&Q is ALWAYS reported "skipped" (reason "destination not configured") —
    it has no destination, sandbox or production, in this build.
  - "sandbox" target: an atomic upsert-by-date write into a JSON file this
    backend owns (data/downstream_sandbox/{program}_rows.json). No real
    TKP/TCP/AGM app file, state, or process is touched.
  - "production" target: NOT IMPLEMENTED. Selecting it always returns a
    "failure" result per row, by construction — the same hard guarantee
    `POST /api/export/all` already gave for the pre-existing uploader-only
    export (`transport_implemented: false`). This is not a config check that
    could be misconfigured around; the transport code simply does not exist.
  - Idempotency key is always `"{program}:{date}"`. A sandbox re-export of the
    same key overwrites that one entry in place (upsert), never appends a
    duplicate.
  - A row is marked `exported=true` in the uploader's own database ONLY when
    its downstream write actually succeeds. Failed/skipped rows are left
    alone so the next export batch retries them naturally.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .programs import PROGRAM_FIELDS, PROGRAMS

# Y&Q has no configured destination of any kind yet.
NO_DESTINATION_PROGRAMS = {"YQ"}


def payload_hash(payload: Optional[dict[str, Any]]) -> Optional[str]:
    """sha256 of the canonical (sorted-key) JSON payload, for audit comparison.

    ``None`` in, ``None`` out — a downstream record that does not exist has no
    checksum, and that absence is itself the "before" state of a created row.
    """
    if payload is None:
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_export_id(batch_id: int, source_row_id: Any, program: str) -> str:
    """Stable idempotency/export identifier for one exported row."""
    return f"{batch_id}:{source_row_id}:{program}"


def _export_fields_for(program: str, row: dict[str, Any]) -> dict[str, Any]:
    """Project a stored row down to just the fields this contract sends
    downstream for `program` (mirrors `programs.public_row`, export-specific)."""
    specs = PROGRAM_FIELDS[program]
    out: dict[str, Any] = {}
    for f in specs:
        if f.name == "date":
            continue
        out[f.name] = row.get(f.name)
    return out


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def sandbox_path(sandbox_dir: Path, program: str) -> Path:
    """The one file this backend owns as `program`'s sandbox destination."""
    return sandbox_dir / f"{program.lower()}_rows.json"


def read_sandbox_row(
    sandbox_dir: Path, program: str, date: str
) -> Optional[dict[str, Any]]:
    """Current stored fields for (program, date) downstream, or None if absent.

    This is the canonical read used to re-derive a destination's checksum during
    rollback preview/confirm, so a record changed since export is detected
    instead of silently overwritten.
    """
    doc = _read_json(sandbox_path(sandbox_dir, program))
    rows = doc.get("rows") or {}
    value = rows.get(date)
    return dict(value) if isinstance(value, dict) else None


def export_row_to_sandbox(
    sandbox_dir: Path, program: str, date: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Upsert one row into this backend's own sandbox destination file for
    `program`, keyed by `date`. Atomic (temp file + os.replace), so a crash
    mid-write never corrupts the existing sandbox file.

    Returns {"action", "before", "after"} — ``before`` is the exact record this
    write replaced (None when it created a new one), which is what makes the
    write reversible. Capturing it HERE, inside the only code path that mutates
    the destination, is what guarantees a snapshot can never go missing for a
    row that was actually written.
    """
    path = sandbox_path(sandbox_dir, program)
    doc = _read_json(path)
    rows: dict[str, Any] = doc.setdefault("rows", {})
    previous = rows.get(date)
    before = dict(previous) if isinstance(previous, dict) else None
    action = "updated" if date in rows else "created"
    rows[date] = fields
    doc["program"] = program
    _atomic_write_json(path, doc)
    return {"action": action, "before": before, "after": dict(fields)}


def rollback_sandbox_row(
    sandbox_dir: Path, program: str, date: str, before: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Compensating operation for one sandbox write.

    ``before is None`` (the export CREATED the record) -> remove the key.
    Otherwise (the export REPLACED a record) -> restore the exact prior record.

    This is a logical, key-scoped compensation, not a whole-file restore: any
    OTHER date written to the same file after the export is deliberately left
    untouched. Atomic, like the forward write.
    """
    path = sandbox_path(sandbox_dir, program)
    doc = _read_json(path)
    rows: dict[str, Any] = doc.setdefault("rows", {})
    if before is None:
        removed = rows.pop(date, None)
        action = "deleted_created_row" if removed is not None else "already_absent"
    else:
        rows[date] = dict(before)
        action = "restored_prior_row"
    doc["program"] = program
    _atomic_write_json(path, doc)
    return {"action": action}


def export_row_to_production(
    program: str,
    date: str,
    fields: dict[str, Any],
    settings: Any,
    dry_run: bool,
) -> dict[str, Any]:
    """Real downstream transport: POST one row to the program's tearsheet
    ingest route (tearsheet_uploader_ingest.py's
    POST /api/uploader/ingest-daily-row), authenticated with the shared
    ingest token.

    Fail-closed WITHOUT any external call when the program's *_INGEST_URL or
    the token is not configured. ``dry_run=True`` sends ``dry_run: true`` —
    the downstream app validates and classifies (created/updated/unchanged)
    but mutates nothing. Idempotency is downstream's contract: same
    program + date + values => "unchanged", never a duplicate.
    """
    url = settings.ingest_url(program)
    if not url:
        return {
            "external_call": False,
            "accepted": False,
            "error_code": "ingest_url_not_configured",
            "error_message": (
                f"{program}_INGEST_URL is not configured; no external call was made."
            ),
        }
    token = settings.ingest_token
    if not token:
        return {
            "external_call": False,
            "accepted": False,
            "error_code": "ingest_token_not_configured",
            "error_message": (
                "DOWNSTREAM_INGEST_TOKEN is not configured; no external call was made."
            ),
        }

    payload = {
        "program": program,
        "date": date,
        "source": "glenn_uploader",
        "dry_run": dry_run,
        **{k: v for k, v in fields.items() if v is not None},
    }
    # Cloudflare Bot Fight (error 1010) rejects Python-urllib's default UA
    # against public tearsheet hostnames; send an explicit client identity.
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (compatible; GlennUploaderExport/1.0; +https://hcresearch.ltd)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            body = {}
        return {
            "external_call": True,
            "accepted": False,
            "error_code": f"http_{exc.code}",
            "error_message": body.get("message") or f"{program} ingest returned HTTP {exc.code}",
            "response": body,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "external_call": True,
            "accepted": False,
            "error_code": "ingest_unreachable",
            "error_message": f"{program} ingest not reachable: {exc}",
        }

    return {
        "external_call": True,
        "accepted": bool(body.get("accepted")),
        "action": body.get("action"),
        "response": body,
    }


def run_downstream_export(
    db: Any,
    settings: Any,
    actor: str,
    batch_id: int,
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Attempt downstream export for every row in `rows`, grouped per program.

    Returns ({program: {"status": ..., "date_results": [...]}}, external_calls)
    for every program in PROGRAMS (TKP/TCP/AGM/YQ) — always all four, so
    callers never have to guess whether a program was silently omitted.
    ``external_calls`` counts real HTTP requests made to tearsheet ingest
    routes (always 0 for the sandbox-file target and for dry-run against it).

    Target semantics:
      * "sandbox": local JSON files this backend owns; EXPORT_DRY_RUN=true
        previews without writing (no external call ever) — unchanged from the
        original contract.
      * "production": real POST to each program's *_INGEST_URL;
        EXPORT_DRY_RUN=true sends dry_run:true (downstream validates but
        mutates nothing, and rows are NOT marked exported).

    Mutates `db`: calls `mark_exported(program, date)` for every row whose
    real (non-dry-run) downstream write is accepted, and writes one audit
    event per row attempt via `db.add_audit`.
    """
    sandbox_dir = Path(settings.downstream_sandbox_dir)
    by_program: dict[str, list[dict[str, Any]]] = {code: [] for code in PROGRAMS}
    for row in rows:
        by_program.setdefault(row["program"], []).append(row)

    results: dict[str, dict[str, Any]] = {}
    external_calls = 0

    for program in PROGRAMS:
        program_rows = by_program.get(program, [])

        # Y&Q has no destination at all yet, regardless of EXPORT_INCLUDE_YQ —
        # that flag is forward-compatible for once a real destination exists.
        if program in NO_DESTINATION_PROGRAMS:
            date_results = []
            for row in program_rows:
                date_results.append(
                    {
                        "date": row["date"],
                        "status": "skipped",
                        "reason": "Y&Q downstream export not implemented yet.",
                    }
                )
                db.add_audit(
                    action="downstream_export_skipped",
                    actor=actor,
                    program=program,
                    date=row["date"],
                    detail={
                        "batch_id": batch_id,
                        "target_env": settings.export_target_env,
                        "reason": "Y&Q downstream export not implemented yet.",
                    },
                )
            results[program] = {"status": "skipped", "date_results": date_results}
            continue

        date_results = []
        any_failure = False
        any_success = False
        for row in program_rows:
            date = row["date"]
            fields = _export_fields_for(program, row)
            hash_ = payload_hash(fields)

            if settings.export_target_env == "production":
                push = export_row_to_production(
                    program, date, fields, settings, dry_run=settings.export_dry_run
                )
                if push.get("external_call"):
                    external_calls += 1
                if push.get("accepted"):
                    if settings.export_dry_run:
                        date_results.append(
                            {
                                "date": date,
                                "status": "dry_run",
                                "payload_hash": hash_,
                                "downstream_response": push.get("response"),
                            }
                        )
                        db.add_audit(
                            action="downstream_export_dry_run",
                            actor=actor,
                            program=program,
                            date=date,
                            detail={
                                "batch_id": batch_id,
                                "target_env": "production",
                                "payload_hash": hash_,
                                "downstream_response": push.get("response"),
                            },
                        )
                    else:
                        resp = push.get("response") or {}
                        db.add_batch_item(
                            batch_id=batch_id,
                            source_row_id=row.get("id"),
                            program=program,
                            date=date,
                            export_id=make_export_id(batch_id, row.get("id"), program),
                            target_env="production",
                            operation=push.get("action") or "unknown",
                            downstream_target=settings.ingest_url(program),
                            downstream_identifier=f"{program}:{date}",
                            before_state=resp.get("before"),
                            after_state=resp.get("after"),
                            before_checksum=payload_hash(resp.get("before")),
                            after_checksum=payload_hash(resp.get("after")),
                            export_result="success",
                        )
                        db.mark_exported(program, date, batch_id)
                        any_success = True
                        date_results.append(
                            {
                                "date": date,
                                "status": "success",
                                "payload_hash": hash_,
                                "downstream_response": push.get("response"),
                            }
                        )
                        db.add_audit(
                            action="downstream_export_success",
                            actor=actor,
                            program=program,
                            date=date,
                            detail={
                                "batch_id": batch_id,
                                "target_env": "production",
                                "payload_hash": hash_,
                                "downstream_response": push.get("response"),
                            },
                        )
                else:
                    any_failure = True
                    date_results.append(
                        {
                            "date": date,
                            "status": "failure",
                            "payload_hash": hash_,
                            "reason": push.get("error_message"),
                            "downstream_response": push.get("response"),
                        }
                    )
                    db.add_audit(
                        action="downstream_export_failure",
                        actor=actor,
                        program=program,
                        date=date,
                        detail={
                            "batch_id": batch_id,
                            "target_env": "production",
                            "payload_hash": hash_,
                            "error_code": push.get("error_code"),
                            "error_message": push.get("error_message"),
                            "downstream_response": push.get("response"),
                        },
                    )
                continue

            # --- sandbox-file target (original contract, unchanged) --------
            if settings.export_dry_run:
                date_results.append({"date": date, "status": "dry_run", "payload_hash": hash_})
                db.add_audit(
                    action="downstream_export_dry_run",
                    actor=actor,
                    program=program,
                    date=date,
                    detail={
                        "batch_id": batch_id,
                        "target_env": settings.export_target_env,
                        "payload_hash": hash_,
                    },
                )
                continue

            written = export_row_to_sandbox(sandbox_dir, program, date, fields)
            before = written["before"]
            after = written["after"]
            db.add_batch_item(
                batch_id=batch_id,
                source_row_id=row.get("id"),
                program=program,
                date=date,
                export_id=make_export_id(batch_id, row.get("id"), program),
                target_env="sandbox",
                operation=written["action"],  # "created" | "updated"
                downstream_target=str(sandbox_path(sandbox_dir, program)),
                downstream_identifier=f"{program.lower()}_rows.json#rows.{date}",
                before_state=before,
                after_state=after,
                before_checksum=payload_hash(before),
                after_checksum=payload_hash(after),
                export_result="success",
            )
            db.mark_exported(program, date, batch_id)
            any_success = True
            downstream_response = {"action": written["action"]}
            date_results.append(
                {"date": date, "status": "success", "payload_hash": hash_, "downstream_response": downstream_response}
            )
            db.add_audit(
                action="downstream_export_success",
                actor=actor,
                program=program,
                date=date,
                detail={
                    "batch_id": batch_id,
                    "target_env": settings.export_target_env,
                    "payload_hash": hash_,
                    "downstream_response": downstream_response,
                },
            )

        if not program_rows:
            program_status = "no_rows"
        elif any_failure and any(
            r["status"] in ("success", "dry_run") for r in date_results
        ):
            program_status = "partial_failure"
        elif any_failure:
            program_status = "failure"
        elif settings.export_dry_run:
            program_status = "dry_run"
        else:
            program_status = "success"

        results[program] = {"status": program_status, "date_results": date_results}

    return results, external_calls
