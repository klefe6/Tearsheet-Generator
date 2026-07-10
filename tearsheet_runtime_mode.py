"""
Shared tearsheet runtime mode and bind-port helpers.

Safe to import: no server start, no secrets in source, no workbook/JSON writes.

Default mode is ``legacy`` when ``TEARSHEET_MODE`` is unset so current production
behavior remains unchanged unless an operator opts into a future mode explicitly.
"""
from __future__ import annotations

import os
from typing import Any, Literal, Optional

Strategy = Literal["tkp", "tcp", "agm"]
RuntimeMode = Literal["legacy", "public", "staff", "portal"]

TEARSHEET_MODE_ENV = "TEARSHEET_MODE"

VALID_MODES: tuple[RuntimeMode, ...] = ("legacy", "public", "staff", "portal")
DEFAULT_MODE: RuntimeMode = "legacy"

# Current public production ports (unchanged in legacy mode).
DEFAULT_TKP_BIND_PORT = 8301
DEFAULT_TCP_BIND_PORT = 8302
DEFAULT_AGM_BIND_PORT = 8304

# Future staff/portal ports (not launched in PR A; 8401 occupied by TWIFO).
STAFF_BIND_PORTS: dict[Strategy, int] = {
    "tkp": 8321,
    "tcp": 8322,
    "agm": 8324,
}
PORTAL_BIND_PORTS: dict[Strategy, int] = {
    "tkp": 8331,
    "tcp": 8332,
    "agm": 8334,
}

SESSION_COOKIE_NAMES: dict[Strategy, str] = {
    "tkp": "tkp_session",
    "tcp": "tcp_session",
    "agm": "agm_session",
}

TKP_BIND_PORT_ENV = "TKP_BIND_PORT"
AGM_BIND_PORT_ENV = "AGM_BIND_PORT"


def _normalize_mode(raw: Optional[str]) -> Optional[RuntimeMode]:
    if raw is None:
        return None
    stripped = str(raw).strip().lower()
    if not stripped:
        return None
    if stripped in VALID_MODES:
        return stripped  # type: ignore[return-value]
    return None


def parse_tearsheet_mode(raw: Optional[str] = None) -> RuntimeMode:
    """Parse ``TEARSHEET_MODE``; invalid or empty values fall back to ``legacy``."""
    if raw is None:
        raw = os.environ.get(TEARSHEET_MODE_ENV)
    normalized = _normalize_mode(raw)
    return normalized if normalized is not None else DEFAULT_MODE


def load_runtime_mode() -> RuntimeMode:
    return parse_tearsheet_mode()


def is_legacy(mode: Optional[str] = None) -> bool:
    resolved = parse_tearsheet_mode(mode) if mode is not None else load_runtime_mode()
    return resolved == "legacy"


def is_public(mode: Optional[str] = None) -> bool:
    resolved = parse_tearsheet_mode(mode) if mode is not None else load_runtime_mode()
    return resolved == "public"


def is_staff(mode: Optional[str] = None) -> bool:
    resolved = parse_tearsheet_mode(mode) if mode is not None else load_runtime_mode()
    return resolved == "staff"


def is_portal(mode: Optional[str] = None) -> bool:
    resolved = parse_tearsheet_mode(mode) if mode is not None else load_runtime_mode()
    return resolved == "portal"


def _parse_port_env(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def resolve_tkp_bind_port() -> int:
    """Explicit ``TKP_BIND_PORT`` wins; otherwise 8321 in staff mode, else 8301."""
    default = STAFF_BIND_PORTS["tkp"] if is_staff() else DEFAULT_TKP_BIND_PORT
    return _parse_port_env(TKP_BIND_PORT_ENV, default)


def resolve_agm_bind_port() -> int:
    """Explicit ``AGM_BIND_PORT`` wins; otherwise 8324 in staff mode, else 8304."""
    default = STAFF_BIND_PORTS["agm"] if is_staff() else DEFAULT_AGM_BIND_PORT
    return _parse_port_env(AGM_BIND_PORT_ENV, default)


def resolve_tcp_bind_port(cfg: Any) -> int:
    """Delegate to ``tcp_config.resolve_bind_port`` (``TCP_V2_BIND_PORT`` override)."""
    from tcp_config import resolve_bind_port

    return resolve_bind_port(cfg)


def resolve_planned_bind_port(strategy: Strategy, mode: Optional[RuntimeMode] = None) -> int:
    """Document future port plan; legacy/public use current public bind ports."""
    resolved_mode = mode if mode is not None else load_runtime_mode()
    if resolved_mode in ("legacy", "public"):
        if strategy == "tkp":
            return resolve_tkp_bind_port()
        if strategy == "tcp":
            return DEFAULT_TCP_BIND_PORT
        return resolve_agm_bind_port()
    if resolved_mode == "staff":
        return STAFF_BIND_PORTS[strategy]
    if resolved_mode == "portal":
        return PORTAL_BIND_PORTS[strategy]
    raise ValueError(f"unsupported runtime mode: {resolved_mode!r}")


def resolve_session_cookie_name(
    strategy: Strategy,
    mode: Optional[RuntimeMode] = None,
) -> Optional[str]:
    """Legacy mode keeps Flask's default cookie name (``session``)."""
    resolved_mode = mode if mode is not None else load_runtime_mode()
    if resolved_mode == "legacy":
        return None
    return SESSION_COOKIE_NAMES[strategy]


def apply_runtime_session_config(
    server: Any,
    settings: Any,
    strategy: Strategy,
    *,
    secure_cookies: bool = False,
) -> RuntimeMode:
    """Apply Flask session secret and optional strategy cookie name for non-legacy modes."""
    from tcp_admin import configure_flask_session_secret

    mode = load_runtime_mode()
    cookie_name = resolve_session_cookie_name(strategy, mode)
    configure_flask_session_secret(
        server,
        settings,
        secure_cookies=secure_cookies,
        session_cookie_name=cookie_name,
    )
    return mode


def register_monthly_backup_404(server: Any) -> None:
    """Register explicit 404 for ``/monthly`` (workbook is backend-only)."""
    if any(
        getattr(rule, "rule", None) == "/monthly"
        for rule in server.url_map.iter_rules()
    ):
        return

    @server.route("/monthly")
    def _monthly_backup_not_exposed():  # noqa: ANN202
        return "Not found", 404
