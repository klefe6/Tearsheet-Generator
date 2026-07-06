"""
Algominds v2 per-account preview state paths — pure path resolution and slug validation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from algominds_v2_accounts import validate_account_slug
from algominds_v2_config import ENV_PREFIX
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot
from algominds_v2_snapshot_state import load_latest_snapshot, save_latest_snapshot

ACCOUNT_STATE_ROOT_ENV = f"{ENV_PREFIX}ACCOUNT_STATE_ROOT"
DEFAULT_ACCOUNT_STATE_DIRNAME = "algominds_v2_account_state"


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parent


def resolve_account_state_root(
    state_root: Path | str | None = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """Resolve the directory root for per-account preview state files."""
    if state_root is not None:
        candidate = Path(state_root)
        if not candidate.is_absolute():
            root = _repo_root_default() if repo_root is None else Path(repo_root)
            candidate = root / candidate
        return candidate

    source = os.environ if env is None else env
    root = _repo_root_default() if repo_root is None else Path(repo_root)
    override = source.get(ACCOUNT_STATE_ROOT_ENV)
    if override is None or not override.strip():
        return root / DEFAULT_ACCOUNT_STATE_DIRNAME

    candidate = Path(override.strip())
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate


def resolve_preview_state_path(
    account_slug: str,
    *,
    state_root: Path | str | None = None,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """
    Resolve per-account preview state file path: <state_root>/{account_slug}.json.

    Does not create directories or read/write state.
    """
    normalized = validate_account_slug(account_slug)
    root = resolve_account_state_root(state_root, env=env, repo_root=repo_root)
    candidate = (root / f"{normalized}.json").resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("resolved state path escapes state root") from exc
    return candidate


def validate_snapshot_account_slug(
    snapshot: AlgomindsV2FeeSnapshot,
    expected_account_slug: str,
) -> None:
    """Ensure snapshot identity matches the expected account route when present."""
    expected = validate_account_slug(expected_account_slug)
    if snapshot.account_slug is None:
        return
    if snapshot.account_slug != expected:
        raise ValueError(
            f"snapshot account_slug {snapshot.account_slug!r} does not match "
            f"expected {expected!r}"
        )


def load_latest_snapshot_for_account(
    account_slug: str,
    *,
    state_root: Path | str | None = None,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
):
    """Load latest snapshot from the per-account preview state file."""
    path = resolve_preview_state_path(
        account_slug,
        state_root=state_root,
        env=env,
        repo_root=repo_root,
    )
    snapshot = load_latest_snapshot(path)
    if snapshot is not None:
        validate_snapshot_account_slug(snapshot, account_slug)
    return snapshot


def save_latest_snapshot_for_account(
    account_slug: str,
    snapshot: AlgomindsV2FeeSnapshot,
    *,
    state_root: Path | str | None = None,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> None:
    """Persist latest snapshot to the per-account preview state file."""
    validate_snapshot_account_slug(snapshot, account_slug)
    path = resolve_preview_state_path(
        account_slug,
        state_root=state_root,
        env=env,
        repo_root=repo_root,
    )
    save_latest_snapshot(path, snapshot)
