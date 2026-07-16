"""Glenn Uploader -> tearsheet ingest route (shared framework).

Each tearsheet app (TKP / TCP v2 / AGM) registers ONE authenticated route on
its own Flask server:

    POST /api/uploader/ingest-daily-row

by calling :func:`register_uploader_ingest` with an app-specific ``apply``
callable that reuses the app's OWN row-derivation and persistence logic (the
same code path its admin "Add Row" uses). This module owns everything else:

  * Gating — requests are refused unless the app's process env sets
    ``GLENN_UPLOADER_INGEST_ENABLED=true`` AND a non-empty
    ``GLENN_UPLOADER_INGEST_TOKEN``. Both are read PER REQUEST, and the
    default is OFF: merely deploying this code changes nothing until an
    operator explicitly enables it. ``GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED``
    (default true) can additionally refuse dry-run probes.
  * Auth — ``Authorization: Bearer <token>`` or ``X-Glenn-Uploader-Token``,
    compared constant-time. Missing/wrong token -> 401. Fail-closed.
  * Validation — ISO date, numeric coercion, required/optional fields per
    program, and rejection of ANY unknown field (so e.g. ``fee`` sent to
    TKP/TCP is rejected loudly instead of silently dropped).
  * Idempotency — the ``apply`` callable classifies by (program, date):
    same date + same values => "unchanged" (no write), same date + new
    values => "updated" (replace), new date => "created". Never a duplicate.
  * Dry-run — ``dry_run: true`` runs the exact same validation and
    classification but ``apply`` MUST NOT write (the framework passes the
    flag through and the response echoes it).
  * Audit — one JSON line per attempt (accepted or rejected) appended to the
    app-side audit file, plus the structured response body:
    {accepted, dry_run, program, date, action, message, before, after}.

Concurrency: a per-process lock serializes ``apply`` calls — the TKP/AGM
state writers are non-atomic single-writer by design, and this keeps the
ingest route from ever racing itself.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

INGEST_ROUTE = "/api/uploader/ingest-daily-row"

ENABLED_ENV = "GLENN_UPLOADER_INGEST_ENABLED"
TOKEN_ENV = "GLENN_UPLOADER_INGEST_TOKEN"
DRY_RUN_ALLOWED_ENV = "GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED"

# Payload keys that are ingest metadata rather than program value fields.
_META_KEYS = {"program", "date", "source", "dry_run"}

_APPLY_LOCK = threading.Lock()


class IngestRejected(Exception):
    """Raised by an app's ``apply`` to refuse a payload (HTTP 422)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class IngestOutcome:
    """What an app's ``apply`` did (or would do, when dry_run)."""

    action: str  # "created" | "updated" | "unchanged"
    before: Optional[dict] = None
    after: Optional[dict] = None
    message: str = ""
    # Set by the app's apply() on real writes. The framework echoes these on
    # the HTTP response so Glenn Uploader can require durable proof before
    # marking a row exported.
    persisted: bool = False
    state_revision: Optional[int] = None
    storage_target: Optional[str] = None
    display_refreshed: bool = False


@dataclass
class IngestConfig:
    program: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    # (payload: {date + numeric fields}, dry_run: bool) -> IngestOutcome.
    # MUST NOT write anything when dry_run is True. May raise IngestRejected.
    apply: Callable[[dict, bool], IngestOutcome]
    audit_path: Optional[Path] = None
    storage_target: Optional[str] = None
    # Called after a real (non-dry-run) persist so the app can reload its
    # in-memory snapshot / schedule a Dash refresh.
    on_persisted: Optional[Callable[[IngestOutcome, dict], None]] = None
    extra_meta: dict = field(default_factory=dict)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _extract_token(headers: Any) -> Optional[str]:
    direct = headers.get("X-Glenn-Uploader-Token")
    if direct and direct.strip():
        return direct.strip()
    auth = headers.get("Authorization") or ""
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _coerce_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise IngestRejected(f"{name} must be numeric")
    try:
        return float(str(value).strip()) if isinstance(value, str) else float(value)
    except ValueError:
        raise IngestRejected(f"{name} must be numeric")


def _validate_payload(config: IngestConfig, body: Any) -> tuple[dict, bool]:
    if not isinstance(body, dict):
        raise IngestRejected("expected a JSON object")

    program = str(body.get("program") or "").strip().upper()
    if program != config.program:
        raise IngestRejected(
            f"this endpoint ingests {config.program} rows only, got {program or '(missing)'}"
        )

    dry_run = body.get("dry_run", True)
    if not isinstance(dry_run, bool):
        raise IngestRejected("dry_run must be a boolean")

    raw_date = str(body.get("date") or "").strip()
    try:
        date = datetime.strptime(raw_date, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise IngestRejected(f"invalid date {raw_date!r}, expected ISO YYYY-MM-DD")

    allowed = set(config.required_fields) | set(config.optional_fields)
    unknown = sorted(k for k in body if k not in _META_KEYS and k not in allowed)
    if unknown:
        raise IngestRejected(
            f"unknown field(s) for {config.program}: {', '.join(unknown)} "
            f"(allowed: {', '.join(sorted(allowed))})"
        )

    clean: dict[str, Any] = {"date": date}
    for name in config.required_fields:
        if body.get(name) is None:
            raise IngestRejected(f"{name} is required for {config.program}")
        clean[name] = _coerce_number(name, body[name])
    for name in config.optional_fields:
        clean[name] = _coerce_number(name, body[name]) if body.get(name) is not None else 0.0
    return clean, dry_run


def _append_audit(config: IngestConfig, record: dict) -> None:
    if config.audit_path is None:
        return
    try:
        config.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config.audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass  # auditing must never take the ingest (or the app) down


def handle_ingest_request(config: IngestConfig, headers: Any, body: Any, remote_addr: str) -> tuple[dict, int]:
    """Framework core (transport-agnostic, unit-testable without Flask).

    Returns (response_json, http_status).
    """

    def rejected(message: str, status: int, dry_run: Optional[bool] = None) -> tuple[dict, int]:
        response = {
            "accepted": False,
            "dry_run": dry_run,
            "program": config.program,
            "date": (body or {}).get("date") if isinstance(body, dict) else None,
            "action": "rejected",
            "message": message,
            "before": None,
            "after": None,
        }
        _append_audit(
            config,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "glenn_uploader_ingest",
                "remote_addr": remote_addr,
                **{k: response[k] for k in ("program", "date", "action", "dry_run", "message")},
                "accepted": False,
            },
        )
        return response, status

    if not _env_flag(ENABLED_ENV, default=False):
        return rejected(
            f"Glenn Uploader ingest is disabled on this app (set {ENABLED_ENV}=true).", 403
        )

    expected = (os.environ.get(TOKEN_ENV) or "").strip()
    if not expected:
        return rejected(
            f"{TOKEN_ENV} is not configured on this app; refusing ingest (fail-closed).", 403
        )
    supplied = _extract_token(headers)
    if not supplied or not secrets.compare_digest(supplied, expected):
        return rejected("Missing or invalid Glenn Uploader ingest token.", 401)

    try:
        clean, dry_run = _validate_payload(config, body)
    except IngestRejected as exc:
        return rejected(exc.message, 422)

    if dry_run and not _env_flag(DRY_RUN_ALLOWED_ENV, default=True):
        return rejected(
            f"dry-run ingest is disabled on this app ({DRY_RUN_ALLOWED_ENV}=false).", 403,
            dry_run=True,
        )

    try:
        with _APPLY_LOCK:
            outcome = config.apply(clean, dry_run)
    except IngestRejected as exc:
        return rejected(exc.message, 422, dry_run=dry_run)

    if not dry_run and outcome.action in ("created", "updated", "unchanged"):
        if not outcome.storage_target and config.storage_target:
            outcome.storage_target = config.storage_target
        # Idempotent unchanged rows still prove durable downstream state.
        outcome.persisted = True
        if config.on_persisted and outcome.persisted:
            config.on_persisted(outcome, clean)

    response = {
        "accepted": True,
        "dry_run": dry_run,
        "program": config.program,
        "date": clean["date"],
        "action": outcome.action,
        "message": outcome.message
        or (
            f"{'DRY RUN — would be ' if dry_run else ''}{outcome.action}"
            f" for {config.program} {clean['date']}"
        ),
        "before": outcome.before,
        "after": outcome.after,
        "persisted": bool(outcome.persisted and not dry_run),
        "authoritative_record_date": clean["date"],
        "state_revision": outcome.state_revision,
        "storage_target": outcome.storage_target or config.storage_target,
        "display_refreshed": outcome.display_refreshed,
    }
    _append_audit(
        config,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "glenn_uploader_ingest",
            "remote_addr": remote_addr,
            "program": config.program,
            "date": clean["date"],
            "action": outcome.action,
            "dry_run": dry_run,
            "accepted": True,
        },
    )
    return response, 200


def register_uploader_ingest(server: Any, config: IngestConfig) -> None:
    """Register POST /api/uploader/ingest-daily-row on a Dash app's Flask
    server. Inert until the operator sets GLENN_UPLOADER_INGEST_ENABLED and
    a token in the app's process env (both read per request)."""
    from flask import jsonify, request  # deferred: apps already ship Flask

    endpoint = f"glenn_uploader_ingest_{config.program.lower()}"

    def _route():
        body = request.get_json(silent=True)
        response, status = handle_ingest_request(
            config, request.headers, body, request.remote_addr or "?"
        )
        return jsonify(response), status

    server.add_url_rule(INGEST_ROUTE, endpoint=endpoint, view_func=_route, methods=["POST"])
