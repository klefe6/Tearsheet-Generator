"""Read-only dry-run probes of TKP/TCP/AGM ingest URLs before live export.

Shared by ``scripts/verify_downstream_ingest.py`` and ``POST /api/export/all``.
Never marks uploader rows exported.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from .config import Settings

PROGRAMS = ("TKP", "TCP", "AGM")

DEFAULT_PROBE_DATE = "2099-01-01"

_HTTP_USER_AGENT = (
    "Mozilla/5.0 (compatible; GlennUploaderPreflight/1.0; +https://hcresearch.ltd)"
)

_PROBE_FIELD_TEMPLATES: dict[str, dict[str, Any]] = {
    "TKP": {"stonex_nlv": 100000, "plus500_nlv": 50000, "cash_transfer": 0},
    "TCP": {"stonex_nlv": 100000, "cash_transfer": 0},
    "AGM": {"tradestation_nlv": 100000, "cash_transfer": 0, "fee": 0},
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


def classify_probe_response(
    http_status: Optional[int],
    body: Optional[dict[str, Any]],
    *,
    connection_error: Optional[str] = None,
) -> tuple[str, str]:
    if connection_error is not None:
        return "unreachable", connection_error

    if http_status is None:
        return "unexpected_error", "no HTTP response"

    message = ""
    if isinstance(body, dict):
        message = str(body.get("message") or "")

    if http_status == 401:
        return "unauthorized", message or "Missing or invalid ingest token (HTTP 401)."

    if http_status == 530:
        return (
            "unreachable",
            "Tearsheet app unreachable (HTTP 530 — Cloudflare could not reach the "
            "origin; the tearsheet process or tunnel is likely offline).",
        )

    if http_status == 403:
        raw_hint = message or (json.dumps(body) if body else "")
        if "1010" in raw_hint:
            return (
                "unreachable",
                "Cloudflare blocked this client (error 1010). "
                "Use a non-blocked User-Agent or probe via localhost.",
            )
        lowered = message.lower()
        if "ingest is disabled" in lowered or "glenn_uploader_ingest_enabled" in lowered:
            return "ingest_disabled", message or "Ingest disabled on target app (HTTP 403)."
        if "dry-run ingest is disabled" in lowered or "dry_run_allowed" in lowered:
            return "ingest_disabled", message or "Dry-run probes disabled on target app (HTTP 403)."
        if "not configured" in lowered and "token" in lowered:
            return "ingest_disabled", message or "Target ingest token not configured (HTTP 403)."
        return "ingest_disabled", message or "Ingest refused (HTTP 403)."

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
    payload = build_probe_payload(program, probe_date)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": _HTTP_USER_AGENT,
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
        body = {"message": raw.strip()} if raw.strip() else {}

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
    token = settings.ingest_token
    results: list[ProgramProbeResult] = []

    for program in PROGRAMS:
        url = settings.ingest_url(program)
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


def preflight_passed(results: list[ProgramProbeResult]) -> bool:
    return all(r.status == "dry_run_validated" for r in results)


def humanize_ingest_http_error(program: str, http_code: int, message: str = "") -> str:
    if http_code == 530:
        return (
            f"{program} tearsheet ingest unreachable (HTTP 530). Cloudflare could not "
            f"reach the tearsheet app — start or repair the {program} process/tunnel, "
            f"then retry Export All. Saved uploader rows were not changed."
        )
    if message:
        return message
    return f"{program} ingest returned HTTP {http_code}"
