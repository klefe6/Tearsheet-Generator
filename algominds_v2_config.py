"""
Algominds v2 configuration — pure constants and parsing, no runtime side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

ENV_PREFIX = "ALGOMINDS_V2_"
DEFAULT_PREVIEW_PORT = 8311
DEFAULT_STATE_FILENAME = "algominds_daily_returns_secret_state.json"
DEFAULT_ENV_FILENAME = ".algominds_production.env"

PREVIEW_PORT_ENV = f"{ENV_PREFIX}PREVIEW_PORT"
STATE_PATH_ENV = f"{ENV_PREFIX}STATE_PATH"

PROTECTED_PORTS = frozenset({8301, 8302, 8304})
MIN_PORT = 1
MAX_PORT = 65535


@dataclass(frozen=True)
class AlgomindsV2Config:
    preview_port: int
    state_path: Path
    env_prefix: str = ENV_PREFIX


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parent


def parse_preview_port(raw: str) -> int:
    """Parse and validate a preview port string."""
    stripped = raw.strip()
    if not stripped:
        raise ValueError("preview port must not be empty")
    try:
        port = int(stripped)
    except ValueError as exc:
        raise ValueError(f"preview port must be an integer, got {raw!r}") from exc
    validate_preview_port(port)
    return port


def validate_preview_port(port: int) -> None:
    """Reject invalid or protected preview ports."""
    if not isinstance(port, int):
        raise TypeError(f"preview port must be int, got {type(port).__name__}")
    if port < MIN_PORT or port > MAX_PORT:
        raise ValueError(f"preview port must be between {MIN_PORT} and {MAX_PORT}, got {port}")
    if port in PROTECTED_PORTS:
        raise ValueError(f"preview port {port} is reserved for production tearsheets")


def resolve_state_path(
    env: Mapping[str, str],
    repo_root: Path,
) -> Path:
    """Resolve state file path without creating directories or files."""
    override = env.get(STATE_PATH_ENV)
    if override is None or not override.strip():
        return repo_root / DEFAULT_STATE_FILENAME
    candidate = Path(override.strip())
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate


def load_algominds_v2_config(
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> AlgomindsV2Config:
    """Build Algominds v2 config from defaults and optional environment overrides."""
    import os

    source = os.environ if env is None else env
    root = _repo_root_default() if repo_root is None else Path(repo_root)

    raw_port = source.get(PREVIEW_PORT_ENV)
    if raw_port is None or not raw_port.strip():
        preview_port = DEFAULT_PREVIEW_PORT
        validate_preview_port(preview_port)
    else:
        preview_port = parse_preview_port(raw_port)

    state_path = resolve_state_path(source, root)

    return AlgomindsV2Config(
        preview_port=preview_port,
        state_path=state_path,
    )
