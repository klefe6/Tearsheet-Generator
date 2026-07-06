"""
Algominds v2 snapshot/state integration — persist latest fee snapshots in preview JSON.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from algominds_v2_snapshots import (
    AlgomindsV2FeeSnapshot,
    AlgomindsV2FeeSnapshotResult,
    compute_fee_snapshot,
    snapshot_from_dict,
    snapshot_to_dict,
)
from algominds_v2_state import (
    AlgomindsV2PreviewState,
    PreviewStateSchemaError,
    empty_preview_state,
    read_preview_state,
    write_preview_state,
)


def load_latest_snapshot(path: Path) -> Optional[AlgomindsV2FeeSnapshot]:
    """Load the latest fee snapshot from preview state, if present."""
    preview = read_preview_state(path)
    if preview.latest_snapshot is None:
        return None
    try:
        return snapshot_from_dict(preview.latest_snapshot)
    except ValueError as exc:
        raise PreviewStateSchemaError(
            f"state file {path}: invalid latest_snapshot payload"
        ) from exc


def save_latest_snapshot(path: Path, snapshot: AlgomindsV2FeeSnapshot) -> None:
    """Persist latest fee snapshot while preserving existing preview-state fields."""
    if path.exists():
        preview = read_preview_state(path)
    else:
        preview = empty_preview_state()

    updated = AlgomindsV2PreviewState(
        last_updated_utc=preview.last_updated_utc,
        account_balance=preview.account_balance,
        fee_removal=preview.fee_removal,
        notes=preview.notes,
        latest_snapshot=snapshot_to_dict(snapshot),
    )
    write_preview_state(path, updated)


def compute_latest_snapshot_result(
    path: Path,
) -> Optional[AlgomindsV2FeeSnapshotResult]:
    """Load and compute the latest fee snapshot result, if a snapshot is stored."""
    snapshot = load_latest_snapshot(path)
    if snapshot is None:
        return None
    return compute_fee_snapshot(snapshot)
