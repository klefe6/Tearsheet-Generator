"""Read-only downstream ingest preflight for Glenn Uploader.

Probes each configured TKP/TCP/AGM ingest URL with ``dry_run: true`` payloads.
Never calls ``/api/export/all`` and never marks uploader rows exported.

Usage (from uploader/backend/):
    python scripts/verify_downstream_ingest.py
    python scripts/verify_downstream_ingest.py --strict

See docs/downstream_export_go_live_runbook.md for the full go-live procedure.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import Settings  # noqa: E402

PROGRAMS = ("TKP", "TCP", "AGM")

# Far-future date: strictly after any live ledger row on append-only apps (TKP/TCP),
# and valid for AGM's "must be after latest daily row" rule. If a target rejects
# this date, pass --probe-date with a later ISO date or see the runbook.
DEFAULT_PROBE_DATE = "2099-01-01"

# Field names match tearsheet_uploader_ingest.py per-program contracts (TCP uses
# stonex_nlv, not nlv — it maps to TCP Cash Balance / NLV in tcp_uploader_ingest).
_PROBE_FIELD_TEMPLATES: dict[str, dict[str, Any]] = {
    "TKP": {
        "stonex_nlv": 100000,
        "plus500_nlv": 50000,
        "cash_transfer": 0,
    },
    "TCP": {
        "stonex_nlv": 100000,
        "cash_transfer": 0,
    },
    "AGM": {
        "tradestation_nlv": 100000,
        "cash_transfer": 0,
        "fee": 0,
    },
}

HARD_FAILURE_STATUSES = frozenset(
    {
        "missing_url",
        "missing_token",
        "unreachable",
        "unauthorized",
        "ingest_disabled",
        "rejected_validation",
        "unexpected_error",
    }
)


@dataclass
class ProgramProbeResult:
    program: str
    status: str
    url: Optional[str] = None
    http_status: Optional[int] = None
    message: str = ""
    action: Optional[str] = None


def build_probe_payload(program: str, probe_date: str = DEFAULT_PROBE_DATE) -> dict[str, Any]:
    """Build a dry-run-only probe body for ``program`` (TKP / TCP / AGM)."""
    program = program.upper()
    if program not in _PROBE_FIELD_TEMPLATES:
        raise ValueError(f"unsupported program: {program}")
    return {
        "program": program,
        "date": probe_date,
        "source": "glenn_uploader_preflight",
        "dry_run": True,
        **_PROBE_FIELD_TEMPLATES[program],
    }


def _ingest_url_for(settings: Settings, program: str) -> Optional[str]:
    return settings.ingest_url(program)


def classify_probe_response(
    http_status: Optional[int],
    body: Optional[dict[str, Any]],
    *,
    connection_error: Optional[str] = None,
) -> tuple[str, str]:
    """Map an HTTP probe outcome to (status, human_message)."""
    if connection_error is not None:
        return "unreachable", connection_error

    if http_status is None:
        return "unexpected_error", "no HTTP response"

    message = ""
    if isinstance(body, dict):
        message = str(body.get("message") or "")

    if http_status == 401:
        return "unauthorized", message or "Missing or invalid ingest token (HTTP 401)."

    if http_status == 403:
        lowered = message.lower()
        if "ingest is disabled" in lowered or "glenn_uploader_ingest_enabled" in lowered:
            return "ingest_disabled", message or "Ingest disabled on target app (HTTP 403)."
        if "dry-run ingest is disabled" in lowered or "dry_run_allowed" in lowered:
            return "ingest_disabled", message or "Dry-run probes disabled on target app (HTTP 403)."
        if "not configured" in lowered and "token" in lowered:
            return "ingest_disabled", message or "Target ingest token not configured (HTTP 403)."
        return "ingest_disabled", message or f"Ingest refused (HTTP 403)."

    if http_status == 422:
        return "rejected_validation", message or "Payload rejected by ingest validation (HTTP 422)."

    if http_status == 200 and isinstance(body, dict):
        if body.get("accepted") is True and body.get("dry_run") is True:
            action = body.get("action") or "validated"
            return "dry_run_validated", message or f"Dry-run accepted (action={action})."
        if body.get("accepted") is False:
            return "rejected_validation", message or "Ingest rejected the probe payload."

    if http_status and http_status >= 400:
        return "unexpected_error", message or f"Unexpected HTTP {http_status}."

    return "unexpected_error", message or "Unexpected ingest response."


def probe_ingest_url(
    program: str,
    url: str,
    token: str,
    probe_date: str = DEFAULT_PROBE_DATE,
    *,
    timeout: float = 20.0,
    opener: Any = None,
) -> ProgramProbeResult:
    """POST one dry-run probe to a tearsheet ingest URL. Read-only — no uploader DB."""
    payload = build_probe_payload(program, probe_date)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            http_status = getattr(resp, "status", None) or resp.getcode()
    except urllib.error.HTTPError as exc:
        http_status = exc.code
        try:
            raw = exc.read().decode("utf-8")
        except (ValueError, OSError):
            raw = "{}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status, msg = classify_probe_response(None, None, connection_error=str(exc))
        return ProgramProbeResult(program=program, status=status, url=url, message=msg)

    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {}

    status, msg = classify_probe_response(http_status, body)
    action = body.get("action") if isinstance(body, dict) else None
    return ProgramProbeResult(
        program=program,
        status=status,
        url=url,
        http_status=http_status,
        message=msg,
        action=action if isinstance(action, str) else None,
    )


def run_preflight(
    settings: Settings,
    *,
    probe_date: str = DEFAULT_PROBE_DATE,
    opener: Any = None,
) -> list[ProgramProbeResult]:
    """Probe TKP, TCP, and AGM using uploader-side ingest env configuration."""
    token = settings.ingest_token
    results: list[ProgramProbeResult] = []

    for program in PROGRAMS:
        url = _ingest_url_for(settings, program)
        if not url:
            results.append(
                ProgramProbeResult(
                    program=program,
                    status="missing_url",
                    message=f"{program}_INGEST_URL is not set; no probe sent.",
                )
            )
            continue
        if not token:
            results.append(
                ProgramProbeResult(
                    program=program,
                    status="missing_token",
                    url=url,
                    message="DOWNSTREAM_INGEST_TOKEN is not set; no probe sent.",
                )
            )
            continue
        results.append(
            probe_ingest_url(program, url, token, probe_date, opener=opener)
        )
    return results


def _mask_token_present(token: Optional[str]) -> str:
    if not token:
        return "(not set)"
    return f"(set, {len(token)} chars)"


def print_config_summary(settings: Settings, *, probe_date: str = DEFAULT_PROBE_DATE) -> None:
    """Print uploader export config without exposing secrets."""
    print("Uploader export configuration (read-only):")
    print(f"  EXPORT_DOWNSTREAM_ENABLED = {settings.export_downstream_enabled}")
    print(f"  EXPORT_DRY_RUN            = {settings.export_dry_run}")
    print(f"  EXPORT_TARGET_ENV         = {settings.export_target_env}")
    print(f"  TKP_INGEST_URL            = {settings.tkp_ingest_url or '(not set)'}")
    print(f"  TCP_INGEST_URL            = {settings.tcp_ingest_url or '(not set)'}")
    print(f"  AGM_INGEST_URL            = {settings.agm_ingest_url or '(not set)'}")
    print(f"  DOWNSTREAM_INGEST_TOKEN   = {_mask_token_present(settings.ingest_token)}")
    print(f"  probe_date                = {probe_date}")
    print()


def print_results(results: list[ProgramProbeResult]) -> None:
    print("Per-program preflight status:")
    for r in results:
        line = f"  {r.program}: {r.status}"
        if r.url:
            line += f"  url={r.url}"
        if r.http_status is not None:
            line += f"  http={r.http_status}"
        if r.action:
            line += f"  action={r.action}"
        print(line)
        if r.message:
            print(f"    {r.message}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only dry-run probe of TKP/TCP/AGM ingest endpoints."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any program is not dry_run_validated.",
    )
    parser.add_argument(
        "--probe-date",
        default=DEFAULT_PROBE_DATE,
        metavar="YYYY-MM-DD",
        help=f"ISO date for probe payloads (default: {DEFAULT_PROBE_DATE}).",
    )
    args = parser.parse_args()

    settings = Settings()
    print_config_summary(settings, probe_date=args.probe_date)

    results = run_preflight(settings, probe_date=args.probe_date)
    print_results(results)

    if args.strict:
        failures = [r for r in results if r.status in HARD_FAILURE_STATUSES]
        if failures:
            print(
                f"STRICT: {len(failures)} program(s) did not reach dry_run_validated.",
                file=sys.stderr,
            )
            return 1
        if not all(r.status == "dry_run_validated" for r in results):
            print("STRICT: unexpected status mix.", file=sys.stderr)
            return 1
        print("STRICT: all programs dry_run_validated.")
    else:
        print("Diagnostic mode (default): exit 0. Re-run with --strict to fail on errors.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
