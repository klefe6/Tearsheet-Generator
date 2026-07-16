"""Authoritative export-mode status for Glenn Uploader UI and /health.

Display layers must derive from these fields — not from the legacy
EXPORT_ENABLED flag or APP_ENV=sandbox alone.
"""

from __future__ import annotations

from typing import Any, Literal

from .config import Settings

ExportMode = Literal["live", "dry_run", "disabled"]


def build_export_status(settings: Settings) -> dict[str, Any]:
    """Single source of truth for export-mode indicators."""
    downstream = bool(settings.export_downstream_enabled)
    dry_run = bool(settings.export_dry_run)
    target = settings.export_target_env
    real_writes = downstream and not dry_run
    transport = downstream and target == "production"

    if not downstream:
        mode: ExportMode = "disabled"
    elif dry_run:
        mode = "dry_run"
    else:
        mode = "live"

    return {
        "downstream_export_enabled": downstream,
        "dry_run": dry_run,
        "target_environment": target,
        "real_writes_enabled": real_writes,
        "transport_implemented": transport,
        "export_mode": mode,
        # Hosting label only — must not imply non-production downstream writes.
        "app_env": settings.app_env,
        "legacy_export_enabled": settings.export_enabled,
    }


def export_mode_banner_message(status: dict[str, Any]) -> str:
    """Operational banner copy shown above the export controls."""
    mode = status["export_mode"]
    if mode == "live":
        target = status["target_environment"]
        label = "Production" if target == "production" else target.title()
        return (
            f"Live export enabled — Export All writes to {label} TKP, TCP, and AGM. "
            "Y&Q is intentionally skipped."
        )
    if mode == "dry_run":
        return "Dry run — no downstream data will be written."
    return "Export disabled — downstream export is not enabled on this backend."


def export_batch_message(
    status: dict[str, Any],
    *,
    total_rows: int,
    downstream_attempted: bool = False,
) -> str:
    """User-facing message for POST /api/export/all responses."""
    mode = status["export_mode"]
    if mode == "live":
        if total_rows == 0:
            return (
                "Live export enabled — no eligible rows in this batch. "
                "Downstream writes occur only for eligible manual rows."
            )
        if downstream_attempted:
            return (
                "Live export — Export All wrote to production TKP, TCP, and AGM "
                f"({total_rows} row{'s' if total_rows != 1 else ''} in this batch)."
            )
        return (
            "Live export enabled — Export All writes to production TKP, TCP, and AGM."
        )
    if mode == "dry_run":
        if total_rows == 0:
            return "Dry run — no eligible rows in this batch; nothing would be written."
        return "Dry run — downstream payloads validated; no data was written."
    if total_rows == 0:
        return "Export preview — no eligible rows in this batch."
    return "Export disabled — downstream export is not enabled on this backend."
