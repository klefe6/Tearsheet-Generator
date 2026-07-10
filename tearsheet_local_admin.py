"""
Local-development-only direct admin tearsheet access (``/admin/tearsheet``).

Safe to import: no server start, no secrets in source, no workbook/JSON writes.

Two independent guards must BOTH pass before the password gate is bypassed:

1. ``TEARSHEET_LOCAL_DIRECT_ADMIN=1`` must be set in the process environment.
   No production reboot script sets it, so a normally-launched production
   process never honors the bypass.
2. The request must originate from this machine (loopback peer address) AND
   be addressed to a loopback host. Production traffic through the Cloudflare
   tunnel connects from 127.0.0.1 but carries its public Host header
   (e.g. tcp-ts.hcresearch.ltd), so it is denied by the host check even if
   the env var ever leaked into a production launch.

When either guard fails, callers leave the normal gate flow untouched — the
URL renders the standard disclaimer screen and exposes nothing admin.
"""
from __future__ import annotations

import os
from typing import Optional

from flask import has_request_context, request

LOCAL_DIRECT_ADMIN_ENV = "TEARSHEET_LOCAL_DIRECT_ADMIN"
LOCAL_DIRECT_ADMIN_PATH = "/admin/tearsheet"

_TRUTHY = ("1", "true", "yes")
_LOOPBACK_ADDRS = frozenset({"127.0.0.1", "::1"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def local_direct_admin_enabled() -> bool:
    return os.environ.get(LOCAL_DIRECT_ADMIN_ENV, "").strip().lower() in _TRUTHY


def _request_host_name() -> str:
    """Host header without the port ("127.0.0.1:8301" -> "127.0.0.1")."""
    host = (request.host or "").strip().lower()
    if host.startswith("["):  # bracketed IPv6, e.g. "[::1]:8301"
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


def _is_loopback_request() -> bool:
    if not has_request_context():
        return False
    if (request.remote_addr or "") not in _LOOPBACK_ADDRS:
        return False
    return _request_host_name() in _LOOPBACK_HOSTS


def is_local_direct_admin_request(pathname: Optional[str]) -> bool:
    """True only when pathname is /admin/tearsheet AND env opt-in AND loopback request."""
    normalized = (pathname or "").rstrip("/") or "/"
    if normalized != LOCAL_DIRECT_ADMIN_PATH:
        return False
    return local_direct_admin_enabled() and _is_loopback_request()
