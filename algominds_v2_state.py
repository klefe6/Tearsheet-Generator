"""
Algominds v2 preview state — pure JSON persistence helpers, no app runtime.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Optional

from algominds_v2_config import AlgomindsV2Config, load_algominds_v2_config

SCHEMA_VERSION = 1
LOCK_SUFFIX = ".lock"


class PreviewStateError(Exception):
    """Base error for preview state operations."""


class PreviewStateCorruptedError(PreviewStateError):
    """Raised when state JSON cannot be parsed."""


class PreviewStateSchemaError(PreviewStateError):
    """Raised when state JSON fails schema validation."""


class PreviewStateLockError(PreviewStateError):
    """Raised when a write lock file is already present."""


@dataclass(frozen=True)
class AlgomindsV2PreviewState:
    last_updated_utc: Optional[str] = None
    account_balance: Optional[Decimal] = None
    fee_removal: Optional[Decimal] = None
    notes: Optional[str] = None


def empty_preview_state() -> AlgomindsV2PreviewState:
    return AlgomindsV2PreviewState()


def resolve_preview_state_path(
    config: Optional[AlgomindsV2Config] = None,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """Resolve preview state path via config without creating files."""
    if config is not None:
        return config.state_path
    return load_algominds_v2_config(env=env, repo_root=repo_root).state_path


def read_preview_state(path: Path) -> AlgomindsV2PreviewState:
    """Read preview state; missing file returns empty state."""
    if not path.exists():
        return empty_preview_state()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreviewStateCorruptedError(f"unable to read state file {path}") from exc
    if not raw.strip():
        raise PreviewStateCorruptedError(f"state file {path} is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PreviewStateCorruptedError(
            f"state file {path} contains invalid JSON"
        ) from exc
    return _parse_state_payload(payload, path)


def write_preview_state(path: Path, state: AlgomindsV2PreviewState) -> None:
    """
    Atomically write preview state.

    Uses a sibling temp file and os.replace. A short-lived lock file prevents
  concurrent writers in the same process tree; cross-process locking is not
    guaranteed beyond atomic replace semantics.
    """
    lock_path = Path(str(path) + LOCK_SUFFIX)
    if lock_path.exists():
        raise PreviewStateLockError(f"state write lock already exists: {lock_path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        _state_to_dict(state),
        indent=2,
        sort_keys=True,
    ) + "\n"

    lock_path.touch()
    tmp_path: Optional[Path] = None
    try:
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
            tmp_path = None
        except Exception as exc:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise PreviewStateError(f"failed to write state file {path}") from exc
    finally:
        lock_path.unlink(missing_ok=True)


def _decimal_to_json(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value, "f")


def _parse_decimal_field(
    field_name: str,
    value: Any,
    path: Path,
) -> Optional[Decimal]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PreviewStateSchemaError(
            f"state file {path}: {field_name} must be a decimal string, got {type(value).__name__}"
        )
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise PreviewStateSchemaError(
            f"state file {path}: {field_name} is not a valid decimal string"
        ) from exc


def _parse_state_payload(payload: Any, path: Path) -> AlgomindsV2PreviewState:
    if not isinstance(payload, dict):
        raise PreviewStateSchemaError(
            f"state file {path}: root value must be a JSON object"
        )

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise PreviewStateSchemaError(
            f"state file {path}: unsupported schema_version {version!r}"
        )

    last_updated_utc = payload.get("last_updated_utc")
    if last_updated_utc is not None and not isinstance(last_updated_utc, str):
        raise PreviewStateSchemaError(
            f"state file {path}: last_updated_utc must be a string or null"
        )

    notes = payload.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise PreviewStateSchemaError(
            f"state file {path}: notes must be a string or null"
        )

    unknown_keys = set(payload) - {
        "schema_version",
        "last_updated_utc",
        "account_balance",
        "fee_removal",
        "notes",
    }
    if unknown_keys:
        raise PreviewStateSchemaError(
            f"state file {path}: unknown fields: {sorted(unknown_keys)}"
        )

    return AlgomindsV2PreviewState(
        last_updated_utc=last_updated_utc,
        account_balance=_parse_decimal_field(
            "account_balance", payload.get("account_balance"), path
        ),
        fee_removal=_parse_decimal_field("fee_removal", payload.get("fee_removal"), path),
        notes=notes,
    )


def _state_to_dict(state: AlgomindsV2PreviewState) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    if state.last_updated_utc is not None:
        payload["last_updated_utc"] = state.last_updated_utc
    if state.account_balance is not None:
        payload["account_balance"] = _decimal_to_json(state.account_balance)
    if state.fee_removal is not None:
        payload["fee_removal"] = _decimal_to_json(state.fee_removal)
    if state.notes is not None:
        payload["notes"] = state.notes
    return payload
