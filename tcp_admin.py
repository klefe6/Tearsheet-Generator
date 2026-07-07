"""
TCP v2 admin editor helpers and server-side authorization utilities.

No state persistence, workbook writes, or server start on import.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import dash_bootstrap_components as dbc
from dash import dash_table, html
from flask import render_template_string

from tcp_calculations import (
    CalculationInvariantError,
    InvalidCashBalance,
    InvalidEntryDate,
    InvalidTrancheCount,
    InvalidTransfer,
    MissingEntryField,
    MissingPreviousField,
    NonChronologicalDate,
    TCPCalculationError,
    TCPEntry,
    TrancheRegression,
    UnsupportedWithdrawal,
    compute_tcp_row,
    public_row,
)
from tcp_public_sections import ADMIN_MODAL_CLASS
from tcp_ledger import CURRENCY_HEADERS, INTEGER_HEADERS, PERCENTAGE_HEADERS, REQUIRED_HEADERS, LedgerRecord

SESSION_KEY = "tcp_v2_admin_authenticated"
SIMULATION_BANNER_TEXT = "TCP v2 Admin — Simulation Only"
ACTIVE_BANNER_TEXT = "TCP v2 Admin — JSON Active"
SIMULATION_WARNING = "No changes will be saved"
ADD_ROW_CONFIRM_LABEL = "Calculation Verified"
ADD_ROW_SAVE_LABEL = "Save Row"
DELETE_CONFIRM_MESSAGE = "Deletion simulation complete — no data was changed"
DELETE_PERSIST_MESSAGE = "Row deleted — state saved"
EXPORT_DISABLED_LABEL = "Export will be enabled after persistence parity validation"

LEDGER_TABLE_COLUMNS: List[str] = list(REQUIRED_HEADERS)
DEFAULT_PAGE_SIZE = 15


@dataclass(frozen=True)
class AddRowSimulationResult:
    success: bool
    proposed_row: Optional[Dict[str, Any]] = None
    prior_row: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    field_errors: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteSimulationResult:
    success: bool
    deleted_row: Optional[Dict[str, Any]] = None
    prior_row: Optional[Dict[str, Any]] = None
    resulting_latest_date: Optional[date] = None
    resulting_latest_nav: Optional[float] = None
    resulting_label_date: Optional[str] = None
    message: str = DELETE_CONFIRM_MESSAGE
    error_message: Optional[str] = None


class AdminAuthManager:
    """Server-side preview admin authentication."""

    def __init__(self, settings: AdminAuthSettings, *, session_key: str = SESSION_KEY):
        self._settings = settings
        self._session_key = session_key

    @property
    def settings(self) -> AdminAuthSettings:
        return self._settings

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    def auth_status_label(self) -> str:
        return "configured" if self.is_configured else "not_configured"

    def verify_token(self, token: str) -> bool:
        if not self.is_configured or not token:
            return False
        expected = self._settings.admin_token.encode("utf-8")
        provided = token.encode("utf-8")
        return hmac.compare_digest(expected, provided)

    def login(self, session: Any, token: str) -> tuple[bool, str]:
        if not self.is_configured:
            return False, "Admin access is not configured."
        if self.verify_token(token):
            session[self._session_key] = True
            if hasattr(session, "permanent"):
                session.permanent = False
            return True, ""
        return False, "Invalid password"

    def logout(self, session: Any) -> None:
        session.pop(self._session_key, None)

    def is_authenticated(self, session: Mapping[str, Any]) -> bool:
        return self.is_configured and bool(session.get(self._session_key))


def configure_flask_session_secret(
    server: Any,
    settings: AdminAuthSettings,
    *,
    secure_cookies: bool = False,
) -> None:
    if settings.session_secret:
        server.secret_key = settings.session_secret
    server.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    server.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    if secure_cookies:
        server.config.setdefault("SESSION_COOKIE_SECURE", True)


def map_calculator_error(exc: Exception) -> str:
    if isinstance(exc, UnsupportedWithdrawal):
        return "Negative cash transfers are unsupported until a withdrawal rule is confirmed."
    if isinstance(exc, NonChronologicalDate):
        return "Date must be after the latest completed row."
    if isinstance(exc, InvalidEntryDate):
        return "Enter a valid date."
    if isinstance(exc, MissingEntryField):
        return "Required input is missing."
    if isinstance(exc, (InvalidCashBalance, InvalidTransfer)):
        return "Cash Balance or transfer is invalid."
    if isinstance(exc, InvalidTrancheCount):
        return "Tranche count must be a positive integer."
    if isinstance(exc, TrancheRegression):
        return "Tranche count cannot decrease."
    if isinstance(exc, MissingPreviousField):
        return "Prior row data is incomplete for calculation."
    if isinstance(exc, (CalculationInvariantError, TCPCalculationError)):
        return "Calculation could not be completed with the supplied inputs."
    return "Unable to complete simulation."


def _record_to_row(record: Union[LedgerRecord, Mapping[str, Any]], *, highlight: bool = False) -> Dict[str, Any]:
    fields = record.fields if isinstance(record, LedgerRecord) else record
    row: Dict[str, Any] = {"_highlight": "true" if highlight else "false"}
    for column in LEDGER_TABLE_COLUMNS:
        row[column] = _format_cell_value(column, fields.get(column))
    return row


def _format_cell_value(column: str, value: Any) -> Any:
    if value is None:
        return ""
    if column == "Date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)
    if column in INTEGER_HEADERS:
        return int(value)
    if column in PERCENTAGE_HEADERS:
        return float(value)
    if column in CURRENCY_HEADERS:
        return float(value)
    return value


def ledger_records_to_rows(records: Sequence[LedgerRecord]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    last_index = len(records) - 1
    for index, record in enumerate(records):
        rows.append(_record_to_row(record, highlight=index == last_index))
    return rows


def datatable_column_defs(visible_columns: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    columns = list(visible_columns or LEDGER_TABLE_COLUMNS)
    defs: List[Dict[str, Any]] = []
    for column in columns:
        col_def: Dict[str, Any] = {"name": column, "id": column}
        if column == "Date":
            col_def["type"] = "text"
        elif column in INTEGER_HEADERS:
            col_def["type"] = "numeric"
            col_def["format"] = {"specifier": "d"}
        elif column in PERCENTAGE_HEADERS:
            col_def["type"] = "numeric"
            col_def["format"] = {"specifier": ".6f"}
        elif column in CURRENCY_HEADERS:
            col_def["type"] = "numeric"
            col_def["format"] = {"specifier": ",.3f"}
        else:
            col_def["type"] = "numeric"
            col_def["format"] = {"specifier": ",.3f"}
        defs.append(col_def)
    return defs


def build_column_selector() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader("Column visibility"),
            dbc.CardBody(
                dbc.Checklist(
                    id="admin-column-selector",
                    options=[{"label": col, "value": col} for col in LEDGER_TABLE_COLUMNS],
                    value=list(LEDGER_TABLE_COLUMNS),
                    inline=True,
                )
            ),
        ],
        className="mb-3",
    )


def build_ledger_datatable(rows: List[Dict[str, Any]], visible_columns: Sequence[str]) -> dash_table.DataTable:
    display_rows = [{k: v for k, v in row.items() if k != "_highlight"} for row in rows]
    table = dash_table.DataTable(
        id="admin-ledger-table",
        columns=datatable_column_defs(visible_columns),
        data=display_rows,
        page_action="native",
        page_size=DEFAULT_PAGE_SIZE,
        sort_action="native",
        editable=False,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "right", "padding": "6px", "fontSize": "12px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#EBEBEB"},
    )
    return table


def ledger_table_style_conditional(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    styles: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        if row.get("_highlight") == "true":
            styles.append(
                {
                    "if": {"row_index": index},
                    "backgroundColor": "#E8F0FE",
                    "fontWeight": "bold",
                }
            )
    return styles


def build_simulation_banner(*, persistence_enabled: bool = False) -> dbc.Alert:
    if persistence_enabled:
        return dbc.Alert(
            [html.Strong(ACTIVE_BANNER_TEXT), html.Br(), "Authenticated changes persist to JSON state."],
            color="success",
            className="text-center fw-bold",
        )
    return dbc.Alert(
        [html.Strong(SIMULATION_BANNER_TEXT), html.Br(), SIMULATION_WARNING],
        color="warning",
        className="text-center fw-bold",
    )


def build_admin_status_card(
    *,
    completed_rows: int,
    latest_date: Optional[str],
    data_source: str,
    state_revision: Optional[int] = None,
    persistence_enabled: bool = False,
    writable: bool = False,
    warning: Optional[str] = None,
) -> dbc.Card:
    persistence_label = "enabled" if persistence_enabled and writable else "disabled"
    body: List[Any] = [
        html.P([html.Strong("Mode: "), "admin_active" if persistence_enabled else "admin_simulation"], className="mb-1"),
        html.P([html.Strong("Completed rows: "), str(completed_rows)], className="mb-1"),
        html.P([html.Strong("Latest completed date: "), latest_date or "—"], className="mb-1"),
        html.P([html.Strong("Data source: "), data_source], className="mb-1"),
        html.P([html.Strong("State revision: "), str(state_revision) if state_revision is not None else "—"], className="mb-1"),
        html.P([html.Strong("Persistence: "), persistence_label], className="mb-0"),
    ]
    if warning:
        body.insert(0, dbc.Alert(warning, color="warning", className="mb-2"))
    return dbc.Card(
        [
            dbc.CardHeader("Admin status"),
            dbc.CardBody(body),
        ],
        className="mb-3",
    )


def build_export_disabled_control() -> dbc.Button:
    return dbc.Button(EXPORT_DISABLED_LABEL, id="admin-export-disabled", color="secondary", disabled=True)


def default_add_row_values(latest_record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "date": "",
        "cash_balance": "",
        "cash_transfers": 0,
        "tranche_count": int(latest_record.get("#") or 1),
    }


def _parse_decimal(value: Any, *, label: str) -> Decimal:
    if value is None or value == "":
        raise InvalidCashBalance(f"{label} is required")
    return Decimal(str(value))


def simulate_add_row(
    prior_row: Mapping[str, Any],
    *,
    row_date: Any,
    cash_balance: Any,
    cash_transfers: Any,
    tranche_count: Any,
) -> AddRowSimulationResult:
    field_errors: Dict[str, str] = {}
    if not row_date:
        field_errors["date"] = "Date is required."
    if cash_balance in (None, ""):
        field_errors["cash_balance"] = "Cash Balance is required."
    if field_errors:
        return AddRowSimulationResult(
            success=False,
            field_errors=field_errors,
            error_message="Correct the highlighted inputs.",
        )

    try:
        parsed_date = row_date if isinstance(row_date, date) else date.fromisoformat(str(row_date))
        entry = TCPEntry(
            row_date=parsed_date,
            cash_balance=_parse_decimal(cash_balance, label="Cash Balance"),
            cash_transfers=_parse_decimal(cash_transfers or 0, label="Cash Transfers"),
            tranche_count=int(tranche_count),
        )
        proposed = public_row(compute_tcp_row(prior_row, entry))
        return AddRowSimulationResult(
            success=True,
            proposed_row=proposed,
            prior_row=dict(prior_row),
        )
    except (InvalidOperation, ValueError, TypeError) as exc:
        return AddRowSimulationResult(success=False, error_message=map_calculator_error(exc))
    except TCPCalculationError as exc:
        return AddRowSimulationResult(success=False, error_message=map_calculator_error(exc))


def proposed_row_table(proposed_row: Mapping[str, Any], prior_row: Optional[Mapping[str, Any]] = None) -> dbc.Table:
    body = []
    for field_name in LEDGER_TABLE_COLUMNS:
        proposed_value = proposed_row.get(field_name, "")
        delta = ""
        if prior_row is not None and field_name in prior_row:
            try:
                if prior_row.get(field_name) is not None and proposed_value is not None and proposed_value != "":
                    diff = float(proposed_value) - float(prior_row.get(field_name))
                    if diff != 0:
                        delta = f" (Δ {diff:+.3f})"
            except (TypeError, ValueError):
                if prior_row.get(field_name) != proposed_value:
                    delta = " (changed)"
        body.append(html.Tr([html.Td(field_name), html.Td(f"{proposed_value}{delta}")]))
    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Field"), html.Th("Proposed value")])), html.Tbody(body)],
        bordered=True,
        size="sm",
    )


def build_add_row_modal() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader("Add Row — Simulation"),
            dbc.ModalBody(
                [
                    dbc.Label("Date"),
                    dbc.Input(id="admin-add-date", type="date"),
                    dbc.FormText(id="admin-add-date-error", color="danger"),
                    dbc.Label("Cash Balance", className="mt-2"),
                    dbc.Input(id="admin-add-cash-balance", type="number", step="0.01"),
                    dbc.FormText(id="admin-add-cash-balance-error", color="danger"),
                    dbc.Label("Cash Transfers", className="mt-2"),
                    dbc.Input(id="admin-add-cash-transfers", type="number", step="0.01", value=0),
                    dbc.FormText(id="admin-add-transfer-error", color="danger"),
                    dbc.Label("# Tranches", className="mt-2"),
                    dbc.Input(id="admin-add-tranche-count", type="number", min=1, step=1),
                    dbc.FormText(id="admin-add-tranche-error", color="danger"),
                    dbc.Alert(id="admin-add-general-error", color="danger", is_open=False, className="mt-3"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Preview Calculation", id="admin-add-preview-btn", color="primary"),
                    dbc.Button("Cancel", id="admin-add-cancel-btn", color="secondary"),
                ]
            ),
        ],
        id="admin-add-modal",
        is_open=False,
        centered=True,
        size="lg",
        className=ADMIN_MODAL_CLASS,
    )


def build_add_row_preview_modal(*, persistence_enabled: bool = False) -> dbc.Modal:
    footer_buttons = [
        dbc.Button(ADD_ROW_CONFIRM_LABEL, id="admin-add-confirm-btn", color="secondary", outline=True),
        dbc.Button("Close", id="admin-add-preview-close-btn", color="secondary"),
    ]
    if persistence_enabled:
        footer_buttons.insert(
            0,
            dbc.Button(ADD_ROW_SAVE_LABEL, id="admin-add-save-btn", color="success"),
        )
    return dbc.Modal(
        [
            dbc.ModalHeader("Calculation preview"),
            dbc.ModalBody(
                [
                    dbc.Alert(
                        "Simulation only — not saved" if not persistence_enabled else "Review the computed row before saving.",
                        color="info",
                    ),
                    html.Div(id="admin-add-preview-table"),
                    dbc.Alert(id="admin-add-save-result", color="success", is_open=False, className="mt-3"),
                ]
            ),
            dbc.ModalFooter(footer_buttons),
        ],
        id="admin-add-preview-modal",
        is_open=False,
        centered=True,
        size="lg",
        className=ADMIN_MODAL_CLASS,
    )


def build_delete_modal(*, persistence_enabled: bool = False) -> dbc.Modal:
    confirm_label = "Delete Latest Row" if persistence_enabled else "Confirm Simulation"
    return dbc.Modal(
        [
            dbc.ModalHeader("Delete Latest Row"),
            dbc.ModalBody(
                [
                    html.P(
                        "Review the final completed row."
                        if persistence_enabled
                        else "Review the final completed row. No deletion will occur."
                    ),
                    html.Div(id="admin-delete-preview-content"),
                    dbc.Alert(id="admin-delete-result", color="info", is_open=False, className="mt-3"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(confirm_label, id="admin-delete-confirm-btn", color="danger", outline=not persistence_enabled),
                    dbc.Button("Close", id="admin-delete-close-btn", color="secondary"),
                ]
            ),
        ],
        id="admin-delete-modal",
        is_open=False,
        centered=True,
        size="lg",
        className=ADMIN_MODAL_CLASS,
    )


def simulate_delete_last_row(records: Sequence[LedgerRecord]) -> DeleteSimulationResult:
    if not records:
        return DeleteSimulationResult(success=False, error_message="No completed rows are available.")
    deleted = records[-1].fields
    prior = records[-2].fields if len(records) >= 2 else None
    resulting_date = prior.get("Date") if prior else None
    resulting_nav = prior.get("nav-x1") if prior else None
    label_date = None
    if isinstance(resulting_date, date):
        label_date = resulting_date.strftime("%B %d, %Y")
    elif isinstance(resulting_date, datetime):
        label_date = resulting_date.date().strftime("%B %d, %Y")
    return DeleteSimulationResult(
        success=True,
        deleted_row=dict(deleted),
        prior_row=dict(prior) if prior else None,
        resulting_latest_date=resulting_date if isinstance(resulting_date, date) else None,
        resulting_latest_nav=float(resulting_nav) if resulting_nav is not None else None,
        resulting_label_date=label_date,
    )


def delete_preview_content(result: DeleteSimulationResult) -> html.Div:
    if not result.success:
        return html.Div(html.P(result.error_message or "Unable to simulate deletion."))
    children: List[Any] = [
        html.H6("Final row (would be removed in a future active delete)"),
        proposed_row_table(result.deleted_row or {}),
    ]
    if result.prior_row:
        children.extend(
            [
                html.Hr(),
                html.P([html.Strong("Resulting latest date: "), result.resulting_label_date or "—"]),
                html.P(
                    [
                        html.Strong("Resulting latest NAV: "),
                        f"{result.resulting_latest_nav:.3f}" if result.resulting_latest_nav is not None else "—",
                    ]
                ),
                html.P(
                    [
                        html.Strong("Dashboard label would become: "),
                        f"Data current to {result.resulting_label_date} close"
                        if result.resulting_label_date
                        else "—",
                    ],
                    className="mb-0",
                ),
            ]
        )
    return html.Div(children)


def build_admin_editor_layout(
    *,
    rows: List[Dict[str, Any]],
    completed_rows: int,
    latest_date: Optional[str],
    data_source: str,
    state_revision: Optional[int] = None,
    persistence_enabled: bool = False,
    writable: bool = False,
    warning: Optional[str] = None,
) -> html.Div:
    return html.Div(
        [
            build_simulation_banner(persistence_enabled=persistence_enabled and writable),
            build_admin_status_card(
                completed_rows=completed_rows,
                latest_date=latest_date,
                data_source=data_source,
                state_revision=state_revision,
                persistence_enabled=persistence_enabled,
                writable=writable,
                warning=warning,
            ),
            build_column_selector(),
            build_add_row_modal(),
            build_add_row_preview_modal(persistence_enabled=persistence_enabled and writable),
            build_delete_modal(persistence_enabled=persistence_enabled and writable),
        ]
    )


LOGIN_FORM_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TCP v2 Admin Login</title>
  <style>
    body.tcp-admin-login-page {
      font-family: sans-serif;
      max-width: 28rem;
      margin: 2rem auto;
      padding: 0 1rem;
      box-sizing: border-box;
    }
    body.tcp-admin-login-page input,
    body.tcp-admin-login-page button {
      font-size: 16px;
      box-sizing: border-box;
    }
    body.tcp-admin-login-page input {
      width: 100%;
      margin: 0.5rem 0 1rem;
      padding: 0.65rem 0.75rem;
    }
    body.tcp-admin-login-page button {
      width: 100%;
      padding: 0.65rem 1rem;
    }
    body.tcp-admin-login-page p {
      word-wrap: break-word;
      overflow-wrap: anywhere;
    }
  </style>
</head>
<body class="tcp-admin-login-page">
  <h2>TCP v2 Admin Login</h2>
  <p>Server-side authentication is required for the simulation editor.</p>
  {% if error %}<p style="color: #b00020;">{{ error }}</p>{% endif %}
  <form method="post">
    <label for="token">Admin token</label><br>
    <input id="token" name="token" type="password" autocomplete="current-password" required>
    <button type="submit">Sign in</button>
  </form>
  <p><a href="/">Return to public preview</a></p>
</body>
</html>
"""


ADMIN_PORTAL_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body {
      font-family: Arial, Helvetica, sans-serif;
      margin: 0;
      background: #ffffff;
      color: #212529;
    }
    .wrap {
      max-width: 960px;
      margin: 0 auto;
      padding: 24px;
    }
    h1 {
      color: #0D3562;
      font-size: 1.75rem;
      margin-bottom: 0.5rem;
    }
    .muted {
      color: #6c757d;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1.5rem 0;
    }
    th, td {
      border: 1px solid #ccc;
      padding: 8px;
      text-align: left;
    }
    th {
      background: #EBEBEB;
    }
    a {
      color: #0D3562;
    }
    .actions a {
      margin-right: 0.75rem;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Admin Overview</h1>
    <p class="muted">Programs and daily entry access.</p>
    <table id="admin-account-overview">
      <thead>
        <tr>
          <th>Program</th>
          <th>Latest completed date</th>
          <th>Completed rows</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{{ program_name }}</td>
          <td>{{ latest_date }}</td>
          <td>{{ row_count }}</td>
          <td class="actions">
            <a href="{{ daily_entry_href }}">Daily entry</a>
            <a href="/">Public tearsheet</a>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="muted"><a href="/admin/logout">Logout</a> · <a href="/">Back to tearsheet</a></p>
  </div>
</body>
</html>
"""


def render_admin_portal_page(
    *,
    program_name: str,
    latest_date: str = "—",
    row_count: str = "—",
    daily_entry_href: str = "/",
) -> str:
    return render_template_string(
        ADMIN_PORTAL_HTML,
        title=f"{program_name} — Admin",
        program_name=program_name,
        latest_date=latest_date,
        row_count=row_count,
        daily_entry_href=daily_entry_href,
    )
