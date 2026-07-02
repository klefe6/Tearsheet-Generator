"""
TCP v2 versioned JSON state layer.

No Dash, Flask, server-launch, workbook-write, or import-time filesystem side effects.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from tcp_ledger import REQUIRED_HEADERS, LedgerLoadResult, LedgerRecord

SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})
APP_CODE = "tcp"

SUPPORTED_SOURCES = frozenset(
    {
        "excel_bootstrap",
        "website_edit",
        "recovered_backup",
        "test",
    }
)

REQUIRED_ENVELOPE_FIELDS = (
    "schema_version",
    "app",
    "revision",
    "updated_at",
    "source",
    "records",
)

OPTIONAL_METADATA_FIELDS = frozenset(
    {
        "record_count",
        "first_completed_date",
        "latest_completed_date",
        "source_workbook_filename",
        "source_sheet",
    }
)

REQUIRED_RECORD_FIELDS = tuple(REQUIRED_HEADERS)

DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_INTERVAL_SECONDS = 0.05


class TCPStateError(Exception):
    """Base state-layer error."""


class StateValidationError(TCPStateError):
    """State envelope or records failed validation."""


class UnsupportedSchemaVersion(StateValidationError):
    """schema_version is not supported."""


class InvalidStateApp(StateValidationError):
    """app field is not tcp."""


class InvalidRevision(StateValidationError):
    """revision is missing or not a positive integer."""


class InvalidStateTimestamp(StateValidationError):
    """updated_at is not valid ISO-8601."""


class InvalidStateRecord(StateValidationError):
    """A record failed validation."""


class DuplicateStateDate(StateValidationError):
    """Duplicate completed Date in records."""


class StateMetadataMismatch(StateValidationError):
    """Optional metadata does not match records."""


class UnsupportedStateSource(StateValidationError):
    """source value is not supported."""


class StateNotFound(TCPStateError):
    """Active state file does not exist."""


class StateLoadError(TCPStateError):
    """State could not be loaded from active or backup."""


class RevisionConflictError(TCPStateError):
    """expected_revision does not match the persisted revision."""


class StateLockError(TCPStateError):
    """Could not acquire the state lock within the timeout."""


class StateWriteError(TCPStateError):
    """Atomic state write failed."""


@dataclass(frozen=True)
class StatePaths:
    active_path: Path
    backup_path: Path
    lock_path: Path


@dataclass(frozen=True)
class PersistResult:
    revision: int
    updated_at: str
    active_path: Path
    backup_path: Path


@dataclass(frozen=True)
class LoadResult:
    state: Dict[str, Any]
    loaded_from: str
    recovery: Optional[str] = None
    active_error: Optional[str] = None
    backup_error: Optional[str] = None

    def public_dict(self) -> Dict[str, Any]:
        return {
            "loaded_from": self.loaded_from,
            "recovery": self.recovery,
            "revision": self.state.get("revision"),
            "record_count": len(self.state.get("records", [])),
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidStateTimestamp(f"Invalid updated_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _record_date_value(record: Mapping[str, Any]) -> date:
    raw = record.get("Date")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise InvalidStateRecord(f"Invalid Date value: {raw!r}") from exc
    raise InvalidStateRecord(f"Invalid Date value: {raw!r}")


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_numeric_field(name: str, value: Any, *, record_index: int) -> None:
    if value is None:
        return
    if not _is_finite_number(value):
        raise InvalidStateRecord(
            f"Record {record_index} field {name!r} must be finite numeric or null, got {value!r}"
        )


def validate_state(state: Mapping[str, Any]) -> None:
    """Side-effect-free validation of a complete state envelope."""
    missing = [field for field in REQUIRED_ENVELOPE_FIELDS if field not in state]
    if missing:
        raise StateValidationError(f"Missing envelope fields: {', '.join(missing)}")

    schema_version = state["schema_version"]
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersion(f"Unsupported schema_version: {schema_version!r}")

    if state["app"] != APP_CODE:
        raise InvalidStateApp(f"app must be {APP_CODE!r}, got {state['app']!r}")

    revision = state["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise InvalidRevision(f"revision must be a positive integer, got {revision!r}")

    _parse_iso_timestamp(str(state["updated_at"]))

    source = state["source"]
    if source not in SUPPORTED_SOURCES:
        raise UnsupportedStateSource(f"Unsupported source: {source!r}")

    records = state["records"]
    if not isinstance(records, list):
        raise StateValidationError("records must be a list")

    seen_dates: set[date] = set()
    previous_date: Optional[date] = None

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise InvalidStateRecord(f"Record {index} must be an object")

        missing_fields = [field for field in REQUIRED_RECORD_FIELDS if field not in record]
        if missing_fields:
            raise InvalidStateRecord(
                f"Record {index} missing fields: {', '.join(missing_fields)}"
            )

        row_date = _record_date_value(record)
        if row_date in seen_dates:
            raise DuplicateStateDate(f"Duplicate Date {row_date.isoformat()} at record {index}")
        seen_dates.add(row_date)

        if previous_date is not None and row_date < previous_date:
            raise InvalidStateRecord(
                f"Record {index} Date {row_date} is out of order after {previous_date}"
            )
        previous_date = row_date

        nav = record.get("nav-x1")
        if nav is None or not _is_finite_number(nav):
            raise InvalidStateRecord(f"Record {index} requires completed nav-x1")

        units = record.get("#")
        if units is not None:
            if not _is_finite_number(units) or float(units) < 1:
                raise InvalidStateRecord(f"Record {index} # must be >= 1 when present")

        trading_days = record.get("Trading Days")
        if trading_days is not None and not _is_finite_number(trading_days):
            raise InvalidStateRecord(f"Record {index} Trading Days must be numeric or null")

        for field_name in REQUIRED_RECORD_FIELDS:
            if field_name in {"Date"}:
                continue
            _validate_numeric_field(field_name, record.get(field_name), record_index=index)

    record_count = state.get("record_count")
    if record_count is not None and record_count != len(records):
        raise StateMetadataMismatch(
            f"record_count {record_count} does not match records length {len(records)}"
        )

    if records:
        first_date = _record_date_value(records[0])
        latest_date = _record_date_value(records[-1])
        meta_first = state.get("first_completed_date")
        if meta_first is not None and meta_first != first_date.isoformat():
            raise StateMetadataMismatch("first_completed_date does not match first record")
        meta_latest = state.get("latest_completed_date")
        if meta_latest is not None and meta_latest != latest_date.isoformat():
            raise StateMetadataMismatch("latest_completed_date does not match last record")


def _serialize_record_fields(fields: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, datetime):
            out[key] = value.date().isoformat()
        elif isinstance(value, date):
            out[key] = value.isoformat()
        elif value is None:
            out[key] = None
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(float(value)):
                raise StateValidationError(f"Non-finite numeric value for {key!r}")
            out[key] = value
        else:
            out[key] = value
    return out


def serialize_state(state: Mapping[str, Any]) -> str:
    """Deterministic UTF-8 JSON serialization after validation."""
    validate_state(state)
    normalized = json.loads(json.dumps(state, default=_json_default, ensure_ascii=False))
    return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def ledger_record_to_state_record(record: LedgerRecord) -> Dict[str, Any]:
    return _serialize_record_fields(record.fields)


def build_state_from_ledger(
    ledger: LedgerLoadResult,
    *,
    source: str = "excel_bootstrap",
    revision: int = 1,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a valid in-memory state envelope from adapter output.
    Does not write to disk and does not mutate adapter records.
    """
    if source not in SUPPORTED_SOURCES:
        raise UnsupportedStateSource(f"Unsupported source: {source!r}")

    records = [ledger_record_to_state_record(record) for record in ledger.completed_records]
    meta = ledger.metadata
    state: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "app": APP_CODE,
        "revision": revision,
        "updated_at": updated_at or _utc_now_iso(),
        "source": source,
        "records": records,
        "record_count": len(records),
        "source_workbook_filename": meta.source_filename,
        "source_sheet": meta.sheet_name,
    }
    if meta.first_completed_date is not None:
        state["first_completed_date"] = meta.first_completed_date.isoformat()
    if meta.latest_completed_date is not None:
        state["latest_completed_date"] = meta.latest_completed_date.isoformat()

    validate_state(state)
    return state


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class StateFileLock:
    """
    Windows-compatible exclusive lock using a dedicated lock file.

  Uses msvcrt byte-range locking when available; falls back to exclusive create.
    """

    def __init__(self, lock_path: Path, timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        self.lock_path = lock_path
        self.timeout = timeout
        self._handle: Optional[Any] = None

    def __enter__(self) -> "StateFileLock":
        _ensure_parent_dir(self.lock_path)
        deadline = time.monotonic() + self.timeout
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            try:
                self._handle = open(self.lock_path, "a+b")
                try:
                    import msvcrt

                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    self._handle.close()
                    self._handle = None
                    last_error = exc
                    time.sleep(LOCK_POLL_INTERVAL_SECONDS)
                    continue
                self._handle.seek(0)
                self._handle.write(b"1")
                self._handle.flush()
                return self
            except OSError as exc:
                last_error = exc
                time.sleep(LOCK_POLL_INTERVAL_SECONDS)

        raise StateLockError(
            f"Timed out acquiring lock {self.lock_path} after {self.timeout}s"
        ) from last_error

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            try:
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            self._handle.close()
            self._handle = None


def _read_json_file(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _current_revision(paths: StatePaths) -> Optional[int]:
    if not paths.active_path.is_file():
        return None
    try:
        active = _read_json_file(paths.active_path)
        validate_state(active)
        return int(active["revision"])
    except (OSError, json.JSONDecodeError, TCPStateError):
        return None


def save_state(
    state: Mapping[str, Any],
    paths: StatePaths,
    *,
    expected_revision: Optional[int] = None,
    lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> PersistResult:
    """
    Validate and atomically persist state.

    Backup semantics: when replacing a valid active state, the prior valid active
    state is copied to the backup path before the new state is installed.
    """
    validate_state(state)
    proposed_revision = int(state["revision"])

    with StateFileLock(paths.lock_path, timeout=lock_timeout):
        current_revision = _current_revision(paths)
        if paths.active_path.is_file():
            if expected_revision is None:
                raise RevisionConflictError(
                    "expected_revision is required when replacing existing state"
                )
            if current_revision is None:
                raise StateWriteError("Existing active state is unreadable or invalid")
            if expected_revision != current_revision:
                raise RevisionConflictError(
                    f"expected_revision {expected_revision} does not match active {current_revision}"
                )
            if proposed_revision != current_revision + 1:
                raise InvalidRevision(
                    f"proposed revision {proposed_revision} must equal {current_revision + 1}"
                )
            prior_active = _read_json_file(paths.active_path)
            validate_state(prior_active)
            _atomic_write_json(paths.backup_path, prior_active)
        else:
            if expected_revision is not None:
                raise RevisionConflictError("Cannot supply expected_revision for first write")
            if proposed_revision != 1:
                raise InvalidRevision("Initial persisted state must use revision 1")

        _atomic_write_json(paths.active_path, state)

    return PersistResult(
        revision=proposed_revision,
        updated_at=str(state["updated_at"]),
        active_path=paths.active_path,
        backup_path=paths.backup_path,
    )


def _atomic_write_json(path: Path, state: Mapping[str, Any]) -> None:
    payload = serialize_state(state)
    _ensure_parent_dir(path)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise StateWriteError(f"Failed to write state file {path}") from exc


def load_state(paths: StatePaths) -> LoadResult:
    """Load and validate active state. Does not auto-bootstrap from Excel."""
    if not paths.active_path.is_file():
        raise StateNotFound(f"Active state not found: {paths.active_path.name}")

    active_error: Optional[str] = None
    try:
        active = _read_json_file(paths.active_path)
        validate_state(active)
        return LoadResult(state=active, loaded_from="active")
    except (json.JSONDecodeError, TCPStateError) as exc:
        active_error = str(exc)

    backup_error: Optional[str] = None
    if paths.backup_path.is_file():
        try:
            backup = _read_json_file(paths.backup_path)
            validate_state(backup)
            return LoadResult(
                state=backup,
                loaded_from="backup",
                recovery="backup_recovery",
                active_error=active_error,
                backup_error=None,
            )
        except (json.JSONDecodeError, TCPStateError) as exc:
            backup_error = str(exc)

    raise StateLoadError(
        f"Active state invalid ({active_error}); backup unavailable or invalid ({backup_error})"
    )


def state_layer_status(paths: StatePaths) -> Dict[str, str]:
    """Side-effect-free summary for preview/health diagnostics."""
    if paths.active_path.is_file():
        try:
            active = _read_json_file(paths.active_path)
            validate_state(active)
            return {
                "state_layer": "available",
                "active_state": "initialized",
                "revision": str(active["revision"]),
            }
        except (json.JSONDecodeError, TCPStateError):
            if paths.backup_path.is_file():
                return {
                    "state_layer": "available",
                    "active_state": "corrupt_backup_available",
                }
            return {
                "state_layer": "available",
                "active_state": "corrupt",
            }
    return {
        "state_layer": "available",
        "active_state": "not_initialized",
    }
