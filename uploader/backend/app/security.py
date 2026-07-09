"""Simple bearer-token auth for mutations.

Auth behavior (also documented in the README):

  * sandbox    -> auth is intentionally RELAXED. Mutations are allowed without a
                  token so local dev is friction-free. A token, if supplied, is
                  still recorded on the audit actor.
  * production -> mutations REQUIRE a valid token. If ADMIN_API_TOKEN is not
                  configured, mutations fail closed (503) rather than open.

Accepted headers (either one):
    Authorization: Bearer <token>
    X-API-Token: <token>
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request, status


def _extract_token(
    authorization: Optional[str], x_api_token: Optional[str]
) -> Optional[str]:
    if x_api_token and x_api_token.strip():
        return x_api_token.strip()
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return None


def require_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None, alias="X-API-Token"),
) -> str:
    """FastAPI dependency: authorize a mutation and return the actor label."""
    settings = request.app.state.settings
    token = _extract_token(authorization, x_api_token)

    if settings.is_sandbox:
        # Relaxed for local dev — allow with or without a token.
        return "sandbox+token" if token else "sandbox"

    # Production: token required and must match.
    expected = settings.admin_api_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ADMIN_API_TOKEN is not configured; refusing mutations in "
                "production (fail-closed)."
            ),
        )
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "admin"
