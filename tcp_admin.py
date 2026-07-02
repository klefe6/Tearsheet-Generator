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
from dash import dash_table, dcc, html

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
from tcp_config import AdminAuthSettings
from tcp_ledger import CURRENCY_HEADERS, INTEGER_HEADERS, PERCENTAGE_HEADERS, REQUIRED_HEADERS, LedgerRecord

SESSION_KEY = "tcp_v2_admin_authenticated"
SIMULATION_BANNER_TEXT = "TCP v2 Admin — Simulation Only"
SIMULATION_WARNING = "No changes will be saved"
ADD_ROW_CONFIRM_LABEL = "Calculation Verified"
DELETE_CONFIRM_MESSAGE = "Deletion simulation complete — no data was changed"
EXPORT_DISABLED_LABEL = "Export will be enabled after state activation"

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

    def __init__(self, settings: AdminAuthSettings):
        self._settings = settings

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
            session[SESSION_KEY] = True
            if hasattr(session, "permanent"):
                session.permanent = True
            return True, ""
        return False, "Invalid credentials."

    def logout(self, session: Any) -> None:
        session.pop(SESSION_KEY, None)

    def is_authenticated(self, session: Mapping[str, Any]) -> bool:
        return self.is_configured and bool(session.get(SESSION_KEY))


def configure_flask_session_secret(server: Any, settings: AdminAuthSettings) -> None:
    if settings.session_secret:
        server.secret_key = settings.session_secret


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


def build_simulation_banner() -> dbc.Alert:
    return dbc.Alert(
        [html.Strong(SIMULATION_BANNER_TEXT), html.Br(), SIMULATION_WARNING],
        color="warning",
        className="text-center fw-bold",
    )


def build_admin_status_card(*, completed_rows: int, latest_date: Optional[str], data_source: str) -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader("Simulation status"),
            dbc.CardBody(
                [
                    html.P([html.Strong("Mode: "), "admin_simulation"], className="mb-1"),
                    html.P([html.Strong("Completed rows: "), str(completed_rows)], className="mb-1"),
                    html.P([html.Strong("Latest completed date: "), latest_date or "—"], className="mb-1"),
                    html.P([html.Strong("Data source: "), data_source], className="mb-1"),
                    html.P([html.Strong("Persistence: "), "disabled"], className="mb-0"),
                ]
            ),
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
    )


def build_add_row_preview_modal() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader("Calculation preview — simulation only"),
            dbc.ModalBody(
                [
                    dbc.Alert("Simulation only — not saved", color="info"),
                    html.Div(id="admin-add-preview-table"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(ADD_ROW_CONFIRM_LABEL, id="admin-add-confirm-btn", color="success"),
                    dbc.Button("Close", id="admin-add-preview-close-btn", color="secondary"),
                ]
            ),
        ],
        id="admin-add-preview-modal",
        is_open=False,
        centered=True,
        size="lg",
    )


def build_delete_modal() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader("Delete Last Row — Simulation"),
            dbc.ModalBody(
                [
                    html.P("Review the final completed row. No deletion will occur."),
                    html.Div(id="admin-delete-preview-content"),
                    dbc.Alert(id="admin-delete-result", color="info", is_open=False, className="mt-3"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Confirm Simulation", id="admin-delete-confirm-btn", color="danger", outline=True),
                    dbc.Button("Close", id="admin-delete-close-btn", color="secondary"),
                ]
            ),
        ],
        id="admin-delete-modal",
        is_open=False,
        centered=True,
        size="lg",
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
) -> html.Div:
    table = build_ledger_datatable(rows, LEDGER_TABLE_COLUMNS)
    table.style_data_conditional = ledger_table_style_conditional(rows)
    return html.Div(
        [
            build_simulation_banner(),
            build_admin_status_card(
                completed_rows=completed_rows,
                latest_date=latest_date,
                data_source="workbook",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Button("Add Row", id="admin-open-add-modal", color="success", size="sm", className="me-2"),
                            dbc.Button(
                                "Delete Last Row",
                                id="admin-open-delete-modal",
                                color="danger",
                                size="sm",
                                outline=True,
                                className="me-2",
                            ),
                            build_export_disabled_control(),
                            html.A("Logout", href="/admin/logout", className="btn btn-link btn-sm"),
                        ],
                        width=12,
                    )
                ],
                className="mb-3",
            ),
            build_column_selector(),
            html.Div(table, id="admin-ledger-table-container"),
            build_add_row_modal(),
            build_add_row_preview_modal(),
            build_delete_modal(),
            dcc.Store(id="admin-proposed-row-store", storage_type="memory", data=None),
        ]
    )


LOGIN_FORM_HTML = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>TCP v2 Admin Login</title></head>
<body style="font-family: sans-serif; max-width: 420px; margin: 40px auto;">
  <h2>TCP v2 Admin Login</h2>
  <p>Server-side authentication is required for the simulation editor.</p>
  {% if error %}<p style="color: #b00020;">{{ error }}</p>{% endif %}
  <form method="post">
    <label for="token">Admin token</label><br>
    <input id="token" name="token" type="password" style="width: 100%; margin: 8px 0;" autocomplete="current-password" required>
    <button type="submit">Sign in</button>
  </form>
  <p><a href="/">Return to public preview</a></p>
</body>
</html>
"""
