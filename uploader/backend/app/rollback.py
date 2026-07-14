"""Rollback of the most recent committed downstream export batch.

This is a real compensating-transaction (saga) reversal, not a UI-state reset.
It reverses each downstream write, verifies the destination is byte-for-byte
back at its pre-export state, and only THEN restores the uploader rows' export
eligibility. If any destination fails it recovers the ones it already touched,
leaves the uploader rows exported, and reports failure — never partial success.

What is reversible today
------------------------
Only ``target_env == "sandbox"`` batches: the JSON destination files this
backend itself owns. Those files hold RAW INPUT fields only (stonex_nlv,
plus500_nlv, cash_transfer, fee) — no NAV, no HWM, no fee ledger — so reversing
a write is a key-scoped compensation with no derived accounting to replay.

``target_env == "production"`` batches are NOT reversible and are blocked with
``no_downstream_reversal_route``. The only downstream route that exists is
``POST /api/uploader/ingest-daily-row``; there is no delete/revert route on the
TKP/TCP/AGM tearsheet apps, and this backend cannot reach their state files
(they live on the operator's host, not on this one). Reversing a production
export therefore requires new code deployed to those three apps — deliberately
out of scope here rather than faked.

Y&Q has no destination at all, so it can never have a committed downstream
mutation to reverse; it is reported as such rather than given invented support.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from . import db as dbmod
from .downstream_export import payload_hash, read_sandbox_row, rollback_sandbox_row, sandbox_path

# How long a preview's confirmation token stays valid.
TOKEN_TTL_SECONDS = 600


class RollbackBlocked(Exception):
    """Rollback cannot proceed. Carries structured, user-facing reasons."""

    def __init__(self, reasons: list[dict[str, str]]):
        self.reasons = reasons
        super().__init__("; ".join(r["message"] for r in reasons))


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- capability -------------------------------------------------------------
def capability(settings: Any) -> dict[str, Any]:
    """What the frontend needs to decide whether to show/enable the button."""
    if not settings.export_rollback_enabled:
        return {
            "rollback_supported": True,
            "rollback_enabled": False,
            "reason": "Feature disabled by configuration (EXPORT_ROLLBACK_ENABLED=false).",
        }
    if not settings.admin_api_token:
        return {
            "rollback_supported": True,
            "rollback_enabled": False,
            "reason": (
                "ADMIN_API_TOKEN is not configured; rollback is refused "
                "fail-closed because it always requires an authenticated operator."
            ),
        }
    return {"rollback_supported": True, "rollback_enabled": True, "reason": None}


def require_enabled(settings: Any) -> None:
    cap = capability(settings)
    if not cap["rollback_enabled"]:
        raise RollbackBlocked([_reason("rollback_disabled", cap["reason"])])


# --- confirmation token -----------------------------------------------------
def _token_key(settings: Any) -> bytes:
    # Rollback always requires ADMIN_API_TOKEN (see capability()), so it is
    # always available here and doubles as the token-signing key.
    return str(settings.admin_api_token).encode("utf-8")


def issue_token(settings: Any, batch_id: int, fingerprint: str, actor: str) -> tuple[str, str]:
    """One-time-use token bound to (batch, previewed downstream state, actor).

    Returns (token, expires_at). The binding is what makes it one-time in
    practice: the fingerprint is recomputed from live downstream state at
    confirm, so once the rollback has run (or anything else has changed the
    destination) the same token no longer validates.
    """
    expires = _utcnow() + timedelta(seconds=TOKEN_TTL_SECONDS)
    payload = {
        "batch_id": batch_id,
        "fingerprint": fingerprint,
        "actor": actor,
        "expires_at": expires.isoformat(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_token_key(settings), raw, hashlib.sha256).hexdigest()
    return f"{body}.{sig}", expires.isoformat()


def verify_token(
    settings: Any, token: str, batch_id: int, fingerprint: str, actor: str
) -> None:
    """Raise RollbackBlocked unless `token` is valid for exactly this rollback."""
    bad = _reason("invalid_confirmation_token", "Confirmation token is missing or invalid.")
    if not token or "." not in token:
        raise RollbackBlocked([bad])
    body, _, sig = token.partition(".")
    try:
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise RollbackBlocked([bad])

    expected_sig = hmac.new(_token_key(settings), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise RollbackBlocked([bad])

    if payload.get("batch_id") != batch_id:
        raise RollbackBlocked(
            [_reason("token_batch_mismatch", "Confirmation token is for a different batch.")]
        )
    if _utcnow() > datetime.fromisoformat(payload["expires_at"]):
        raise RollbackBlocked(
            [_reason("token_expired", "Confirmation token has expired; preview again.")]
        )
    if payload.get("actor") != actor:
        raise RollbackBlocked(
            [_reason("token_actor_mismatch", "Confirmation token was issued to another operator.")]
        )
    if payload.get("fingerprint") != fingerprint:
        raise RollbackBlocked(
            [
                _reason(
                    "destination_changed_since_preview",
                    "Downstream state changed after the preview was taken. "
                    "Re-run the preview and review the new plan.",
                )
            ]
        )


# --- destination inspection -------------------------------------------------
def _current_downstream(settings: Any, item: dict) -> Optional[dict]:
    """Live downstream record for `item`, or None if it is absent."""
    if item["target_env"] != "sandbox":
        return None
    return read_sandbox_row(
        Path(settings.downstream_sandbox_dir), item["program"], item["date"]
    )


def _fingerprint(items: list[dict], settings: Any) -> str:
    """Checksum over the CURRENT downstream state of every item in the batch.

    This is the compare-and-swap anchor: it is computed at preview, embedded in
    the confirmation token, and recomputed at confirm. Any drift in between —
    a manual edit, a newer export, a concurrent rollback — changes it and the
    confirm is refused.
    """
    parts = []
    for it in items:
        current = _current_downstream(settings, it)
        parts.append(f"{it['program']}|{it['date']}|{payload_hash(current)}")
    blob = "\n".join(sorted(parts)).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


# --- reversibility ----------------------------------------------------------
def evaluate(
    db: Any, settings: Any, batch: dict, holding_lock: bool = False
) -> dict[str, Any]:
    """Decide whether `batch` is reversible and build the per-program plan.

    Read-only. Every condition that fails contributes an explicit blocking
    reason — a destination is never silently skipped and then reported as fine.

    ``holding_lock`` must be True when called from inside confirm(), which has
    already taken the export/rollback lock: otherwise the caller would see its
    OWN lock and block itself.
    """
    reasons: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    batch_id = int(batch["id"])
    status = batch.get("status") or dbmod.BATCH_LEGACY

    if status == dbmod.BATCH_LEGACY:
        reasons.append(
            _reason(
                "legacy_batch_missing_snapshot",
                f"Batch {batch_id} pre-dates the rollback snapshot system; it has no "
                "before/after state and cannot be automatically reversed.",
            )
        )
    # NB: the batch's `dry_run` COLUMN describes the legacy uploader-only export
    # path (it is always 1 in sandbox) and says nothing about whether a
    # downstream write landed. Only the status does — a batch is promoted to
    # committed/partially_failed exclusively when a real downstream write
    # succeeded. Gating on the column here would block every genuine sandbox
    # export from ever being rolled back.
    if status == dbmod.BATCH_DRY_RUN:
        reasons.append(
            _reason(
                "dry_run_no_mutation",
                "Nothing was pushed downstream; no rollback is required.",
            )
        )
    if status == dbmod.BATCH_ROLLED_BACK:
        reasons.append(
            _reason("already_rolled_back", f"Batch {batch_id} has already been rolled back.")
        )
    if status == dbmod.BATCH_ROLLBACK_IN_PROGRESS:
        reasons.append(
            _reason("rollback_in_progress", f"A rollback of batch {batch_id} is already running.")
        )
    if status == dbmod.BATCH_NO_MUTATION:
        reasons.append(
            _reason(
                "no_downstream_mutation",
                "This batch committed no downstream write; there is nothing to reverse.",
            )
        )
    if db.has_newer_mutating_batch(batch_id):
        reasons.append(
            _reason(
                "newer_batch_exists",
                "A newer export batch has committed downstream since this one; "
                "reverse that batch first.",
            )
        )
    if not holding_lock:
        lock = db.get_lock()
        if lock:
            reasons.append(
                _reason(
                    "concurrent_operation",
                    f"An export or rollback is already in progress (holder: {lock['holder']}).",
                )
            )

    items = db.get_batch_items(batch_id)
    committed = [i for i in items if i["export_result"] == "success"]

    if not items and status not in (dbmod.BATCH_LEGACY,):
        reasons.append(
            _reason(
                "legacy_batch_missing_downstream_identity",
                f"Batch {batch_id} has no recorded downstream record mapping.",
            )
        )
    if items and not committed:
        reasons.append(
            _reason(
                "no_downstream_mutation",
                "No downstream write in this batch succeeded; there is nothing to reverse.",
            )
        )

    programs: dict[str, dict[str, Any]] = {}
    for item in committed:
        program = item["program"]
        entry = programs.setdefault(
            program, {"program": program, "source_row_ids": [], "downstream_operations": []}
        )
        if item.get("source_row_id") is not None:
            entry["source_row_ids"].append(item["source_row_id"])

        if item["target_env"] != "sandbox":
            reasons.append(
                _reason(
                    "no_downstream_reversal_route",
                    f"{program} {item['date']} was pushed to the live tearsheet ingest "
                    "route, which has no reversal endpoint. Production exports cannot "
                    "be rolled back by this backend.",
                )
            )
            continue

        if not item.get("downstream_identifier"):
            reasons.append(
                _reason(
                    "legacy_batch_missing_downstream_identity",
                    f"{program} {item['date']} has no stable downstream identifier.",
                )
            )
            continue
        if item["operation"] == "updated" and item.get("before_state") is None:
            reasons.append(
                _reason(
                    "missing_snapshot",
                    f"{program} {item['date']} replaced an existing record but no "
                    "pre-export snapshot was captured; it cannot be restored exactly.",
                )
            )
            continue

        current = _current_downstream(settings, item)
        matches = payload_hash(current) == item.get("after_checksum")
        if not matches:
            reasons.append(
                _reason(
                    "downstream_modified_since_export",
                    f"{program} {item['date']} no longer matches what this batch wrote; "
                    "it was changed after the export. Refusing to overwrite that change.",
                )
            )

        entry["downstream_operations"].append(
            {
                "operation": (
                    "delete_created_row"
                    if item["operation"] == "created"
                    else "restore_prior_row"
                ),
                "downstream_identifier": item["downstream_identifier"],
                "date": item["date"],
                "current_state_matches_export": matches,
                # The sandbox destination stores raw input fields only — no NAV,
                # HWM, fee or cumulative series — so there is no derived
                # accounting to replay. Stated explicitly rather than implied.
                "replay_required": False,
                "replay_reason": (
                    "sandbox destination stores raw inputs only; no derived "
                    "accounting is persisted there"
                ),
            }
        )

    for program in ("YQ",):
        if any(i["program"] == program for i in items):
            warnings.append(
                _reason(
                    "yq_no_destination",
                    "Y&Q has no downstream destination; it was skipped at export and "
                    "has nothing to reverse.",
                )
            )

    return {
        "batch_id": batch_id,
        "batch_status": status,
        "created_at": batch.get("ts"),
        "target_env": batch.get("target_env"),
        "programs": list(programs.values()),
        "blocking_reasons": reasons,
        "warnings": warnings,
        "items": committed,
        "reversible": not reasons,
    }


# --- preview ----------------------------------------------------------------
def preview(db: Any, settings: Any, actor: str, batch_id: Optional[int] = None) -> dict[str, Any]:
    """Read-only. Never mutates a destination, a row, or a batch status."""
    require_enabled(settings)

    batch = (
        db.get_export_batch(batch_id) if batch_id is not None else db.get_latest_mutating_batch()
    )
    if batch is None:
        raise RollbackBlocked(
            [
                _reason(
                    "no_batches",
                    f"Export batch {batch_id} was not found."
                    if batch_id is not None
                    else "There is no committed downstream export batch to roll back.",
                )
            ]
        )

    plan = evaluate(db, settings, batch)
    items = plan.pop("items")

    result: dict[str, Any] = {
        "ok": True,
        **plan,
        "confirmation_token": None,
        "expires_at": None,
    }

    if plan["reversible"]:
        token, expires_at = issue_token(
            settings, plan["batch_id"], _fingerprint(items, settings), actor
        )
        result["confirmation_token"] = token
        result["expires_at"] = expires_at
    return result


# --- backups ----------------------------------------------------------------
def _backup_destinations(settings: Any, items: list[dict], batch_id: int) -> dict[str, str]:
    """Copy every affected destination file aside BEFORE any mutation.

    Raises OSError if any backup cannot be written — the caller aborts before
    touching a single destination, so "backup failed" never means "half rolled
    back".
    """
    backup_dir = Path(settings.rollback_backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow().strftime("%Y%m%dT%H%M%SZ")
    backups: dict[str, str] = {}
    for program in sorted({i["program"] for i in items}):
        src = sandbox_path(Path(settings.downstream_sandbox_dir), program)
        if not src.exists():
            continue
        dst = backup_dir / f"{stamp}-batch{batch_id}-{program.lower()}_rows.json"
        shutil.copy2(src, dst)
        backups[program] = str(dst)
    return backups


def _restore_backup(settings: Any, program: str, backup_path: str) -> None:
    dst = sandbox_path(Path(settings.downstream_sandbox_dir), program)
    shutil.copy2(backup_path, dst)


# --- confirm ----------------------------------------------------------------
def confirm(
    db: Any,
    settings: Any,
    actor: str,
    batch_id: int,
    confirmation_token: str,
    reason: str,
) -> dict[str, Any]:
    """Execute the rollback. Ordering is the whole safety argument:

      lock -> revalidate -> back up -> compensate -> verify -> free rows -> unlock

    The uploader's own rows are the LAST thing touched, so a downstream failure
    can never leave a row advertised as re-exportable when its downstream write
    is still in place.
    """
    require_enabled(settings)
    if not (reason or "").strip():
        raise RollbackBlocked(
            [_reason("reason_required", "A reason is required to roll back an export.")]
        )

    batch = db.get_export_batch(batch_id)
    if batch is None:
        raise RollbackBlocked([_reason("no_batches", f"Export batch {batch_id} was not found.")])

    # Idempotency: replaying a confirm for an already-reversed batch returns the
    # original result and mutates nothing. A client that lost the response to a
    # successful rollback can safely retry.
    if (batch.get("status") or "") == dbmod.BATCH_ROLLED_BACK:
        prior = db.get_rollback_for_batch(batch_id) or {}
        return {
            "ok": True,
            "idempotent_replay": True,
            "rollback_id": prior.get("id"),
            "batch_id": batch_id,
            "status": dbmod.BATCH_ROLLED_BACK,
            "programs": prior.get("programs") or [],
            "source_rows_unexported": (prior.get("verification") or {}).get(
                "source_rows_unexported", 0
            ),
            "warnings": [],
        }

    holder = f"rollback:{actor}"
    if not db.acquire_lock(holder):
        raise RollbackBlocked(
            [_reason("concurrent_operation", "An export or rollback is already in progress.")]
        )

    try:
        # Re-evaluate under the lock: everything checked at preview must STILL
        # hold now. This is what closes the preview->confirm race.
        plan = evaluate(db, settings, db.get_export_batch(batch_id), holding_lock=True)
        items = plan.pop("items")
        if not plan["reversible"]:
            raise RollbackBlocked(plan["blocking_reasons"])

        verify_token(
            settings, confirmation_token, batch_id, _fingerprint(items, settings), actor
        )

        rollback_id = db.start_rollback(batch_id, actor, reason)
        db.set_batch_status(batch_id, dbmod.BATCH_ROLLBACK_IN_PROGRESS)
        db.add_audit(
            action="export_rollback_started",
            actor=actor,
            detail={"batch_id": batch_id, "rollback_id": rollback_id, "reason": reason},
        )

        # --- back up every destination BEFORE mutating any of them ----------
        try:
            backups = _backup_destinations(settings, items, batch_id)
        except OSError as exc:
            db.set_batch_status(batch_id, dbmod.BATCH_ROLLBACK_FAILED)
            db.finish_rollback(
                rollback_id, dbmod.ROLLBACK_FAILED, error=f"backup_failed: {exc}"
            )
            raise RollbackBlocked(
                [
                    _reason(
                        "backup_failed",
                        f"Could not back up a destination before mutating it ({exc}). "
                        "No destination was changed.",
                    )
                ]
            )

        # --- compensate, with saga recovery on failure ----------------------
        mutated_programs: set[str] = set()
        per_program: dict[str, dict[str, Any]] = {}
        try:
            for item in items:
                rollback_sandbox_row(
                    Path(settings.downstream_sandbox_dir),
                    item["program"],
                    item["date"],
                    item.get("before_state"),
                )
                mutated_programs.add(item["program"])
                db.set_item_rollback_result(item["id"], "reversed")
                entry = per_program.setdefault(
                    item["program"],
                    {
                        "program": item["program"],
                        "records_reversed": 0,
                        "replay_completed": True,
                        "replay_from_date": None,
                    },
                )
                entry["records_reversed"] += 1
                earliest = entry["replay_from_date"]
                if earliest is None or item["date"] < earliest:
                    entry["replay_from_date"] = item["date"]

            verification = _verify(settings, items)
            if not verification["ok"]:
                raise RuntimeError(
                    "post-rollback verification failed: " + json.dumps(verification["failures"])
                )
        except Exception as exc:  # noqa: BLE001 — any failure must recover
            recovery = _recover(settings, backups, mutated_programs)
            db.set_batch_status(batch_id, dbmod.BATCH_ROLLBACK_FAILED)
            db.finish_rollback(
                rollback_id,
                dbmod.ROLLBACK_FAILED,
                programs=list(per_program.values()),
                backups=backups,
                verification={"recovery": recovery},
                error=str(exc),
            )
            db.add_audit(
                action="export_rollback_failed",
                actor=actor,
                detail={
                    "batch_id": batch_id,
                    "rollback_id": rollback_id,
                    "error": str(exc),
                    "recovery": recovery,
                },
            )
            raise RollbackBlocked(
                [
                    _reason(
                        "rollback_failed",
                        f"Rollback failed ({exc}). Destinations were restored from backup: "
                        f"{recovery}. Uploader rows were left exported.",
                    )
                ]
            )

        # --- downstream is verified clean: NOW free the uploader rows -------
        unexported = 0
        warnings: list[dict[str, str]] = []
        for item in items:
            if db.unmark_exported(item["program"], item["date"], batch_id):
                unexported += 1
            else:
                warnings.append(
                    _reason(
                        "source_row_reexported",
                        f"{item['program']} {item['date']} is now owned by a newer export "
                        "batch; its exported flag was left untouched.",
                    )
                )

        verification["source_rows_unexported"] = unexported
        db.set_batch_status(batch_id, dbmod.BATCH_ROLLED_BACK)
        db.finish_rollback(
            rollback_id,
            dbmod.ROLLBACK_DONE,
            programs=list(per_program.values()),
            backups=backups,
            verification=verification,
        )
        db.add_audit(
            action="export_rollback_completed",
            actor=actor,
            detail={
                "batch_id": batch_id,
                "rollback_id": rollback_id,
                "reason": reason,
                "source_rows_unexported": unexported,
            },
        )

        return {
            "ok": True,
            "rollback_id": rollback_id,
            "batch_id": batch_id,
            "status": dbmod.BATCH_ROLLED_BACK,
            "programs": list(per_program.values()),
            "source_rows_unexported": unexported,
            "warnings": warnings,
        }
    finally:
        db.release_lock()


def _verify(settings: Any, items: list[dict]) -> dict[str, Any]:
    """Every reversed record must now equal its exact pre-export state.

    For a created row that means the key is GONE; for a replaced row it means
    the destination checksum equals the captured before_checksum. Anything else
    is a failed rollback, not a warning.
    """
    failures = []
    for item in items:
        current = _current_downstream(settings, item)
        expected = item.get("before_checksum")  # None => must not exist
        actual = payload_hash(current)
        if actual != expected:
            failures.append(
                {
                    "program": item["program"],
                    "date": item["date"],
                    "expected_checksum": expected,
                    "actual_checksum": actual,
                }
            )
    return {"ok": not failures, "failures": failures, "records_verified": len(items)}


def _recover(settings: Any, backups: dict[str, str], mutated: set[str]) -> dict[str, str]:
    """Restore every destination we already touched from its pre-rollback backup."""
    recovery: dict[str, str] = {}
    for program in sorted(mutated):
        backup = backups.get(program)
        if not backup:
            recovery[program] = "no_backup_available"
            continue
        try:
            _restore_backup(settings, program, backup)
            recovery[program] = "restored"
        except OSError as exc:
            recovery[program] = f"restore_failed: {exc}"
    return recovery
