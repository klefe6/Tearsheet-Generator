"""
Direct admin tearsheet access without the password gate.

Safe to import: no server start, no secrets in source, no workbook/JSON writes.

Two independent triggers exist; each is guarded separately:

**Local-dev bypass** (``/admin/tearsheet`` on the client ports). Both guards
must pass:

1. ``TEARSHEET_LOCAL_DIRECT_ADMIN=1`` must be set in the process environment.
   No production reboot script sets it, so a normally-launched production
   process never honors the bypass.
2. The request must originate from this machine (loopback peer address) AND
   be addressed to a loopback host. Production traffic through the Cloudflare
   tunnel connects from 127.0.0.1 but carries its public Host header
   (e.g. tcp-ts.hcresearch.ltd), so it is denied by the host check even if
   the env var ever leaked into a production launch.

**Staff mode** (dedicated admin ports 8321/8322/8324, any route). Guards:

1. ``TEARSHEET_MODE=staff`` must be set (only the ``reboot_*_staff`` launchers
   set it; client/production launchers never do).
2. The request peer must be loopback (staff processes bind 127.0.0.1 only;
   cloudflared also connects from loopback).
3. The Host header must be loopback OR explicitly allow-listed via
   ``TEARSHEET_STAFF_ALLOWED_HOSTS`` (comma-separated, e.g. the
   ``*-admin.hcresearch.ltd`` tunnel hostnames). Fail-closed: a client
   hostname accidentally pointed at a staff port is denied and falls through
   to the normal gate.

Staff ports carry no in-app password; public exposure MUST sit behind
Cloudflare Access on the admin hostnames.

When the guards fail, callers leave the normal gate flow untouched — the
URL renders the standard disclaimer screen and exposes nothing admin.
"""
from __future__ import annotations

import os
from typing import FrozenSet, Optional

from flask import has_request_context, request

from tearsheet_runtime_mode import is_staff

LOCAL_DIRECT_ADMIN_ENV = "TEARSHEET_LOCAL_DIRECT_ADMIN"
LOCAL_DIRECT_ADMIN_PATH = "/admin/tearsheet"
STAFF_ALLOWED_HOSTS_ENV = "TEARSHEET_STAFF_ALLOWED_HOSTS"

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


def _staff_allowed_hosts() -> FrozenSet[str]:
    """Loopback hosts plus the operator's allow-listed admin tunnel hostnames."""
    raw = os.environ.get(STAFF_ALLOWED_HOSTS_ENV, "")
    extra = {h.strip().lower() for h in raw.split(",") if h.strip()}
    return _LOOPBACK_HOSTS | frozenset(extra)


def is_staff_direct_admin_request() -> bool:
    """True on a staff-mode process (any route) for loopback-peer requests whose
    Host is loopback or allow-listed (the admin tunnel hostname). Client-port
    processes never run in staff mode, so this is always False there."""
    if not is_staff():
        return False
    if not has_request_context():
        return False
    if (request.remote_addr or "") not in _LOOPBACK_ADDRS:
        return False
    return _request_host_name() in _staff_allowed_hosts()


def is_direct_admin_request(pathname: Optional[str]) -> bool:
    """Direct-admin trigger shared by all three tearsheets: staff mode serves
    the admin tearsheet on every route; otherwise only the local-dev
    /admin/tearsheet bypass applies."""
    if is_staff_direct_admin_request():
        return True
    return is_local_direct_admin_request(pathname)
