"""
TCP v2 runtime data-source orchestration for preview loading and JSON mutations.

No Dash server start or workbook writes on import.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tcp_admin import simulate_add_row
from tcp_config import TCPConfig
from tcp_dashboard import canonical_nav_records_from_ledger
from tcp_ledger import LedgerLoadResult, LedgerMetadata, LedgerRecord, TCPLedgerError, load_ledger
from tcp_state import (
    RevisionConflictError,
    StateLoadError,
    StateLockError,
    StateNotFound,
    StatePaths,
    StateValidationError,
    StateWriteError,
    TCPStateError,
    build_state_from_ledger,
    load_state,
    save_state,
    state_layer_status,
    validate_state,
)

MINIMUM_COMPLETED_ROWS = 1


@dataclass(frozen=True)
class RuntimeSnapshot:
    ledger: LedgerLoadResult
    canonical_nav: List[Dict[str, Any]]
    data_source: str
    state_mode: str
    state_revision: Optional[int]
    writable: bool
    recovery_status: str
    warning: Optional[str]
    state_diagnostics: Dict[str, str]

    @property
    def records(self) -> Tuple[LedgerRecord, ...]:
        return self.ledger.completed_records


@dataclass(frozen=True)
class MutationResult:
    success: bool
    snapshot: Optional[RuntimeSnapshot] = None
    error_message: Optional[str] = None
    saved_date: Optional[str] = None
    saved_nav: Optional[float] = None
    revision: Optional[int] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_date_value(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Invalid Date value: {value!r}")


def state_record_to_fields(record: Mapping[str, Any]) -> Dict[str, Any]:
    fields = dict(record)
    raw_date = fields.get("Date")
    if isinstance(raw_date, str):
        fields["Date"] = date.fromisoformat(raw_date)
    return fields


def ledger_from_state_envelope(
    state: Mapping[str, Any],
    *,
    cfg: TCPConfig,
    source_label: str,
) -> LedgerLoadResult:
    records = state.get("records", [])
    completed: List[LedgerRecord] = []
    for index, record in enumerate(records):
        fields = state_record_to_fields(record)
        completed.append(LedgerRecord(excel_row_number=index + 1, fields=fields))

    first_date = _record_date_value(records[0]["Date"]) if records else None
    latest_date = _record_date_value(records[-1]["Date"]) if records else None
    metadata = LedgerMetadata(
        source_filename=state.get("source_workbook_filename") or cfg.workbook_filename,
        sheet_name=state.get("source_sheet") or cfg.sheet_name,
        header_mapping={},
        total_candidate_rows=len(records),
        completed_row_count=len(records),
        first_completed_date=first_date,
        latest_completed_date=latest_date,
        latest_completed_excel_row=len(records) if records else None,
    )
    return LedgerLoadResult(
        candidate_records=tuple(completed),
        completed_records=tuple(completed),
        metadata=metadata,
    )


def _build_state_from_records(
    records: Sequence[Mapping[str, Any]],
    *,
    cfg: TCPConfig,
    revision: int,
    source: str,
    prior_state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    serialized = []
    for record in records:
        row = dict(record)
        raw_date = row.get("Date")
        if isinstance(raw_date, date):
            row["Date"] = raw_date.isoformat()
        serialized.append(row)

    first_date = serialized[0]["Date"] if serialized else None
    latest_date = serialized[-1]["Date"] if serialized else None
    state: Dict[str, Any] = {
        "schema_version": 1,
        "app": "tcp",
        "revision": revision,
        "updated_at": _utc_now_iso(),
        "source": source,
        "records": serialized,
        "record_count": len(serialized),
        "source_workbook_filename": (
            prior_state.get("source_workbook_filename") if prior_state else cfg.workbook_filename
        ),
        "source_sheet": prior_state.get("source_sheet") if prior_state else cfg.sheet_name,
    }
    if first_date:
        state["first_completed_date"] = first_date
    if latest_date:
        state["latest_completed_date"] = latest_date
    validate_state(state)
    return state


def _writable_for_source(data_source: str, cfg: TCPConfig) -> bool:
    return cfg.persistence_enabled and data_source == "json"


def _load_workbook_snapshot(cfg: TCPConfig, paths: StatePaths) -> RuntimeSnapshot:
    ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)
    canonical_nav = canonical_nav_records_from_ledger(ledger.completed_records)
    diagnostics = state_layer_status(paths)
    return RuntimeSnapshot(
        ledger=ledger,
        canonical_nav=canonical_nav,
        data_source="workbook",
        state_mode=cfg.state_mode,
        state_revision=None,
        writable=False,
        recovery_status="normal",
        warning=None,
        state_diagnostics=diagnostics,
    )


def load_runtime_snapshot(cfg: TCPConfig, paths: StatePaths) -> RuntimeSnapshot:
    """Select workbook or JSON mode and return one authoritative snapshot."""
    diagnostics = state_layer_status(paths)

    if cfg.state_mode == "workbook":
        return _load_workbook_snapshot(cfg, paths)

    try:
        loaded = load_state(paths)
    except StateNotFound:
        if cfg.allow_workbook_fallback:
            snapshot = _load_workbook_snapshot(cfg, paths)
            return RuntimeSnapshot(
                ledger=snapshot.ledger,
                canonical_nav=snapshot.canonical_nav,
                data_source="workbook_fallback",
                state_mode=cfg.state_mode,
                state_revision=None,
                writable=False,
                recovery_status="workbook_fallback",
                warning="Active JSON state is missing. Workbook fallback is read-only.",
                state_diagnostics=diagnostics,
            )
        raise
    except StateLoadError:
        if cfg.allow_workbook_fallback:
            snapshot = _load_workbook_snapshot(cfg, paths)
            return RuntimeSnapshot(
                ledger=snapshot.ledger,
                canonical_nav=snapshot.canonical_nav,
                data_source="workbook_fallback",
                state_mode=cfg.state_mode,
                state_revision=None,
                writable=False,
                recovery_status="workbook_fallback",
                warning="Active and backup JSON state are unavailable. Workbook fallback is read-only.",
                state_diagnostics=diagnostics,
            )
        raise

    if loaded.loaded_from == "backup":
        ledger = ledger_from_state_envelope(loaded.state, cfg=cfg, source_label="json_backup")
        canonical_nav = canonical_nav_records_from_ledger(ledger.completed_records)
        return RuntimeSnapshot(
            ledger=ledger,
            canonical_nav=canonical_nav,
            data_source="json_backup",
            state_mode=cfg.state_mode,
            state_revision=int(loaded.state["revision"]),
            writable=False,
            recovery_status="recovered_backup",
            warning="Active JSON state is corrupt. Backup recovery is read-only.",
            state_diagnostics=diagnostics,
        )

    ledger = ledger_from_state_envelope(loaded.state, cfg=cfg, source_label="json")
    canonical_nav = canonical_nav_records_from_ledger(ledger.completed_records)
    return RuntimeSnapshot(
        ledger=ledger,
        canonical_nav=canonical_nav,
        data_source="json",
        state_mode=cfg.state_mode,
        state_revision=int(loaded.state["revision"]),
        writable=True,
        recovery_status="normal",
        warning=None,
        state_diagnostics=diagnostics,
    )


def health_fields_from_snapshot(snapshot: RuntimeSnapshot, *, auth_configured: bool) -> Dict[str, Any]:
    active_state = snapshot.state_diagnostics.get("active_state", "not_initialized")
    if snapshot.data_source == "json":
        active_state = "ready"
    elif snapshot.data_source == "json_backup":
        active_state = "recovered_backup"
    elif snapshot.data_source == "workbook_fallback":
        active_state = "fallback"
    elif snapshot.data_source == "workbook":
        active_state = snapshot.state_diagnostics.get("active_state", "not_initialized")

    writes_allowed = snapshot.writable and auth_configured
    return {
        "state_mode": snapshot.state_mode,
        "data_source": snapshot.data_source,
        "active_state": active_state,
        "state_revision": snapshot.state_revision,
        "state_writable": snapshot.writable,
        "recovery_status": snapshot.recovery_status,
        "admin_editor": "active" if snapshot.state_mode == "json_active" else "simulation_only",
        "row_save": "enabled" if writes_allowed else "disabled",
        "row_delete": "enabled" if writes_allowed else "disabled",
        "state_write": "enabled" if writes_allowed else "disabled",
    }


def persist_add_row(
    cfg: TCPConfig,
    paths: StatePaths,
    *,
    expected_revision: int,
    row_date: Any,
    cash_balance: Any,
    cash_transfers: Any,
    tranche_count: Any,
    authenticated: bool,
) -> MutationResult:
    if not authenticated:
        return MutationResult(success=False, error_message="Authentication is required.")
    if cfg.state_mode != "json_active":
        return MutationResult(success=False, error_message="Persistence is disabled in workbook mode.")
    try:
        current = load_runtime_snapshot(cfg, paths)
    except (StateNotFound, StateLoadError) as exc:
        return MutationResult(success=False, error_message=str(exc))
    if not current.writable or current.data_source != "json":
        return MutationResult(
            success=False,
            error_message="Writes are disabled until valid active JSON state is available.",
        )
    if current.state_revision != expected_revision:
        return MutationResult(
            success=False,
            error_message=f"Stale revision {expected_revision}; current revision is {current.state_revision}.",
        )

    prior_row = state_record_to_fields(current.records[-1].fields)
    simulation = simulate_add_row(
        prior_row,
        row_date=row_date,
        cash_balance=cash_balance,
        cash_transfers=cash_transfers,
        tranche_count=tranche_count,
    )
    if not simulation.success or simulation.proposed_row is None:
        return MutationResult(success=False, error_message=simulation.error_message or "Invalid row inputs.")

    try:
        loaded = load_state(paths)
        if int(loaded.state["revision"]) != expected_revision:
            return MutationResult(
                success=False,
                error_message=f"Stale revision {expected_revision}; current revision is {loaded.state['revision']}.",
            )
        records = list(loaded.state["records"])
        proposed = dict(simulation.proposed_row)
        raw_date = proposed.get("Date")
        if isinstance(raw_date, date):
            proposed["Date"] = raw_date.isoformat()
        records.append(proposed)
        new_state = _build_state_from_records(
            records,
            cfg=cfg,
            revision=expected_revision + 1,
            source="website_edit",
            prior_state=loaded.state,
        )
        save_state(new_state, paths, expected_revision=expected_revision)
    except (RevisionConflictError, StateLockError, StateValidationError, StateWriteError, TCPStateError) as exc:
        return MutationResult(success=False, error_message=str(exc))

    snapshot = load_runtime_snapshot(cfg, paths)
    latest = snapshot.records[-1].fields
    return MutationResult(
        success=True,
        snapshot=snapshot,
        saved_date=_record_date_value(latest["Date"]).isoformat(),
        saved_nav=float(latest["nav-x1"]),
        revision=snapshot.state_revision,
    )


def persist_delete_last_row(
    cfg: TCPConfig,
    paths: StatePaths,
    *,
    expected_revision: int,
    expected_final_date: str,
    authenticated: bool,
) -> MutationResult:
    if not authenticated:
        return MutationResult(success=False, error_message="Authentication is required.")
    if cfg.state_mode != "json_active":
        return MutationResult(success=False, error_message="Persistence is disabled in workbook mode.")
    try:
        current = load_runtime_snapshot(cfg, paths)
    except (StateNotFound, StateLoadError) as exc:
        return MutationResult(success=False, error_message=str(exc))
    if not current.writable or current.data_source != "json":
        return MutationResult(
            success=False,
            error_message="Writes are disabled until valid active JSON state is available.",
        )
    if current.state_revision != expected_revision:
        return MutationResult(
            success=False,
            error_message=f"Stale revision {expected_revision}; current revision is {current.state_revision}.",
        )
    if len(current.records) <= MINIMUM_COMPLETED_ROWS:
        return MutationResult(success=False, error_message="Cannot delete the protected minimum ledger row.")

    final_fields = current.records[-1].fields
    final_date = _record_date_value(final_fields["Date"]).isoformat()
    if final_date != expected_final_date:
        return MutationResult(
            success=False,
            error_message="Final row changed since preview. Refresh and try again.",
        )

    try:
        loaded = load_state(paths)
        if int(loaded.state["revision"]) != expected_revision:
            return MutationResult(
                success=False,
                error_message=f"Stale revision {expected_revision}; current revision is {loaded.state['revision']}.",
            )
        records = list(loaded.state["records"])
        if len(records) <= MINIMUM_COMPLETED_ROWS:
            return MutationResult(success=False, error_message="Cannot delete the protected minimum ledger row.")
        actual_final = _record_date_value(records[-1]["Date"]).isoformat()
        if actual_final != expected_final_date:
            return MutationResult(
                success=False,
                error_message="Final row changed since preview. Refresh and try again.",
            )
        records.pop()
        new_state = _build_state_from_records(
            records,
            cfg=cfg,
            revision=expected_revision + 1,
            source="website_edit",
            prior_state=loaded.state,
        )
        save_state(new_state, paths, expected_revision=expected_revision)
    except (RevisionConflictError, StateLockError, StateValidationError, StateWriteError, TCPStateError) as exc:
        return MutationResult(success=False, error_message=str(exc))

    snapshot = load_runtime_snapshot(cfg, paths)
    latest = snapshot.records[-1].fields if snapshot.records else {}
    return MutationResult(
        success=True,
        snapshot=snapshot,
        saved_date=_record_date_value(latest["Date"]).isoformat() if latest else None,
        saved_nav=float(latest["nav-x1"]) if latest else None,
        revision=snapshot.state_revision,
    )


def bootstrap_state_from_workbook(cfg: TCPConfig, ledger: LedgerLoadResult) -> Dict[str, Any]:
    """Build revision-1 seed envelope from a validated workbook ledger."""
    return build_state_from_ledger(ledger, source="excel_bootstrap", revision=1)
