"""
Shared tearsheet gate admin-entry UI and auth helpers (TCP + TKP + Algominds).

Safe to import: no server start, no workbook/JSON writes, no secrets in source.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import dash_bootstrap_components as dbc
from dash import html

from tcp_config import AdminAuthSettings

GATE_PASSWORD_ROW_ID = "gate-admin-password-row"
GATE_PASSWORD_INPUT_ID = "gate-admin-password-input"
GATE_PASSWORD_SUBMIT_ID = "gate-admin-password-submit"
GATE_PASSWORD_PORTAL_ID = "gate-admin-password-portal"
GATE_PASSWORD_ERROR_ID = "gate-admin-password-error"
GATE_PASSWORD_VISIBLE_STORE_ID = "gate-password-visible-store"

GATE_PASSWORD_ROW_CLASS = "tearsheet-gate-password-row"
GATE_PASSWORD_INPUT_CLASS = "tearsheet-gate-password-input"
GATE_PASSWORD_ACTIONS_CLASS = "tearsheet-gate-password-actions"
GATE_PASSWORD_SUBMIT_CLASS = "tearsheet-gate-password-submit"
GATE_PASSWORD_PORTAL_CLASS = "tearsheet-gate-password-portal"
GATE_PASSWORD_ERROR_CLASS = "tearsheet-gate-password-error"

GATE_PASSWORD_TEARSHEET_LABEL = "TearSheet"
GATE_PASSWORD_PORTAL_LABEL = "Portal"

# Post-auth destinations (no secrets in URLs).
ADMIN_DAILY_ENTRY_PATH = "/"
ADMIN_PORTAL_PATH = "/admin"

INVALID_PASSWORD_MESSAGE = "Invalid password"
GATE_PASSWORD_PLACEHOLDER = "Admin password"

HIDDEN_STYLE: Dict[str, str] = {"display": "none"}
VISIBLE_ROW_STYLE: Dict[str, str] = {
    "display": "block",
    "width": "100%",
    "maxWidth": "520px",
    "margin": "0.75rem auto 0",
}

TCP_SESSION_KEY = "tcp_v2_admin_authenticated"
TKP_SESSION_KEY = "tkp_admin_authenticated"
AGM_SESSION_KEY = "agm_admin_authenticated"


def load_tkp_admin_auth_settings() -> AdminAuthSettings:
    token = os.environ.get("TKP_ADMIN_TOKEN")
    secret = os.environ.get("TKP_SESSION_SECRET")
    return AdminAuthSettings(
        admin_token=token if token else None,
        session_secret=secret if secret else None,
    )


def load_agm_admin_auth_settings() -> AdminAuthSettings:
    token = os.environ.get("AGM_ADMIN_TOKEN")
    secret = os.environ.get("AGM_SESSION_SECRET")
    return AdminAuthSettings(
        admin_token=token if token else None,
        session_secret=secret if secret else None,
    )


def build_gate_password_row() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    dbc.Input(
                        id=GATE_PASSWORD_INPUT_ID,
                        type="password",
                        placeholder=GATE_PASSWORD_PLACEHOLDER,
                        className=GATE_PASSWORD_INPUT_CLASS,
                        autoComplete="new-password",
                        n_submit=0,
                    ),
                    html.Div(
                        [
                            dbc.Button(
                                GATE_PASSWORD_TEARSHEET_LABEL,
                                id=GATE_PASSWORD_SUBMIT_ID,
                                color="primary",
                                size="sm",
                                className=GATE_PASSWORD_SUBMIT_CLASS,
                                n_clicks=0,
                            ),
                            dbc.Button(
                                GATE_PASSWORD_PORTAL_LABEL,
                                id=GATE_PASSWORD_PORTAL_ID,
                                color="primary",
                                size="sm",
                                className=GATE_PASSWORD_PORTAL_CLASS,
                                n_clicks=0,
                            ),
                        ],
                        className=GATE_PASSWORD_ACTIONS_CLASS,
                    ),
                ],
                className=GATE_PASSWORD_ROW_CLASS,
            ),
            html.Div(id=GATE_PASSWORD_ERROR_ID, className=GATE_PASSWORD_ERROR_CLASS),
        ],
        id=GATE_PASSWORD_ROW_ID,
        style=HIDDEN_STYLE,
    )


def gate_password_row_style(visible: Optional[bool]) -> Dict[str, str]:
    return VISIBLE_ROW_STYLE if visible else HIDDEN_STYLE
