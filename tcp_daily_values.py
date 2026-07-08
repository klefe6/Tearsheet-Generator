"""
TCP v2 Daily Values presentation — shared public/admin table from canonical runtime snapshot.

Safe to import: no server start, no workbook/JSON writes, no secrets.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

import dash_bootstrap_components as dbc
from dash import dash_table, html

from tcp_admin import (
    DEFAULT_PAGE_SIZE,
    build_export_disabled_control,
    datatable_column_defs,
    ledger_records_to_rows,
    ledger_table_style_conditional,
)
from tcp_ledger import LedgerMetadata, LedgerRecord
from tcp_public_sections import (
    CONTROLLED_TABLE_OVERFLOW_CLASS,
    HEADER_ROW_CLASS,
    PUBLIC_CARD_CLASS,
    PUBLIC_SECTION_CLASS,
    ADMIN_TOOLBAR_CLASS,
)

DAILY_VALUES_SECTION_ID = "tcp-daily-values-section"
DAILY_VALUES_TABLE_ID = "tcp-daily-values-table"
DAILY_VALUES_TOOLBAR_ID = "tcp-daily-values-admin-toolbar"
DAILY_VALUES_SUMMARY_ID = "tcp-daily-values-summary"
PUBLIC_DAILY_COLLAPSE_ID = "tcp-public-daily-collapse"
PUBLIC_DAILY_TOGGLE_BTN_ID = "tcp-public-daily-toggle-btn"
PUBLIC_DAILY_TOGGLE_LABEL_SHOW = "Show ▾"
PUBLIC_DAILY_TOGGLE_LABEL_HIDE = "Hide ▴"
PUBLIC_GATE_ACCEPTED_STORE_ID = "public-gate-accepted-store"
TCP_UI_MODE_STORE_ID = "tcp-ui-mode-store"
UI_MODE_PUBLIC = "public"
UI_MODE_ADMIN = "admin"
GATE_NOTICE_E_ID = "secret-notice-e"
TCP_GATE_STORAGE_PURGE_STORE_ID = "tcp-gate-storage-purge-store"
TCP_GATE_SESSION_STORAGE_PREFIXES = (
    "tcp-ui-mode-store",
    "public-gate-accepted-store",
    "disclaimer-accepted",
)


def resolve_gate_bootstrap_state(*, ui_mode: Optional[str] = None) -> tuple[None, bool]:
    """Force Important Notice on every page load/refresh.

    Ignores any stale browser-side ui_mode hint (memory/session/local storage).
    """
    _ = ui_mode
    return None, True


def resolve_public_accept_ui_mode(*, accept_clicks: Optional[int]) -> tuple[Optional[str], bool]:
    """Grant public mode only after an explicit Accept click in the current page session."""
    if accept_clicks is not None and int(accept_clicks) > 0:
        return UI_MODE_PUBLIC, True
    return None, True


def resolve_public_access_ui_mode(
    *,
    triggered_id: Optional[str],
    accept_clicks: Optional[int],
    ui_mode: Optional[str],
) -> tuple[Optional[str], bool]:
    """Backward-compatible wrapper — prefer resolve_gate_bootstrap_state / resolve_public_accept_ui_mode."""
    if triggered_id == "accept-button":
        return resolve_public_accept_ui_mode(accept_clicks=accept_clicks)
    return resolve_gate_bootstrap_state(ui_mode=ui_mode)


DAILY_VALUES_DEFAULT_SORT: List[Dict[str, str]] = [
    {"column_id": "Date", "direction": "desc"},
    {"column_id": "#", "direction": "desc"},
]

# TCP public column contract (TKP PUBLIC_DAILY_COLUMNS analog).
PUBLIC_DAILY_COLUMN_MAP: Sequence[tuple[str, str]] = (
    ("#", "#Day"),
    ("Date", "Date"),
    ("nav-x1", "NAV"),
    ("%Net", "Perc. Net"),
    ("$PL", "$PL"),
    ("HWM", "HWM"),
    ("Inc. Fee", "Fee"),
)
PUBLIC_DAILY_COLUMN_IDS: tuple[str, ...] = tuple(col_id for col_id, _ in PUBLIC_DAILY_COLUMN_MAP)


def public_daily_column_defs(visible_columns: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Column definitions with public display labels."""
    selected = list(visible_columns or PUBLIC_DAILY_COLUMN_IDS)
    label_by_id = {col_id: label for col_id, label in PUBLIC_DAILY_COLUMN_MAP}
    defs = datatable_column_defs(selected)
    for col_def in defs:
        col_def["name"] = label_by_id.get(col_def["id"], col_def["name"])
    return defs


def _row_date_ordinal(row: Mapping[str, Any]) -> int:
    date_val = row.get("Date")
    if isinstance(date_val, date):
        return date_val.toordinal()
    if isinstance(date_val, datetime):
        return date_val.date().toordinal()
    if isinstance(date_val, str) and date_val:
        try:
            return datetime.fromisoformat(date_val[:10]).date().toordinal()
        except ValueError:
            return 0
    return 0


def _row_sequence_number(row: Mapping[str, Any]) -> int:
    seq = row.get("#")
    try:
        return int(seq) if seq not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def sort_rows_for_display(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Presentation-only newest-first ordering; canonical storage order is unchanged."""
    materialized = [dict(row) for row in rows]
    return sorted(
        materialized,
        key=lambda row: (_row_date_ordinal(row), _row_sequence_number(row)),
        reverse=True,
    )


def project_public_daily_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Reduce ledger rows to the public Daily Values column contract."""
    projected: List[Dict[str, Any]] = []
    for row in rows:
        projected.append({col_id: row.get(col_id, "") for col_id in PUBLIC_DAILY_COLUMN_IDS})
    return projected


def rows_from_records(records: Sequence[LedgerRecord]) -> List[Dict[str, Any]]:
    return ledger_records_to_rows(records)


def build_daily_values_summary(
    *,
    completed_rows: int,
    latest_date: Optional[date],
    data_source: str,
) -> html.Div:
    latest_label = latest_date.strftime("%B %d, %Y") if latest_date else "—"
    return html.Div(
        [
            html.P(
                [
                    html.Strong("Rows: "),
                    str(completed_rows),
                    " · ",
                    html.Strong("Latest date: "),
                    latest_label,
                    " · ",
                    html.Strong("Source: "),
                    data_source,
                ],
                className="small text-muted mb-2",
            ),
        ],
        id=DAILY_VALUES_SUMMARY_ID,
        className="tcp-daily-values-summary",
    )


def build_daily_values_datatable(
    rows: Sequence[Mapping[str, Any]],
    *,
    visible_columns: Optional[Sequence[str]] = None,
) -> dash_table.DataTable:
    sorted_rows = sort_rows_for_display(rows)
    display_rows = project_public_daily_rows(sorted_rows)
    return dash_table.DataTable(
        id=DAILY_VALUES_TABLE_ID,
        columns=public_daily_column_defs(visible_columns),
        data=display_rows,
        page_action="native",
        page_size=DEFAULT_PAGE_SIZE,
        sort_action="native",
        sort_by=DAILY_VALUES_DEFAULT_SORT,
        editable=False,
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "right",
            "padding": "4px 8px",
            "fontSize": "12px",
            "fontFamily": "monospace",
            "whiteSpace": "nowrap",
        },
        style_cell_conditional=[
            {"if": {"column_id": "Date"}, "textAlign": "left"},
            {"if": {"column_id": "#"}, "textAlign": "center"},
        ],
        style_header={
            "backgroundColor": "#1a2a3a",
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "11px",
            "textAlign": "center",
        },
        style_data_conditional=ledger_table_style_conditional(sorted_rows),
    )


def build_daily_values_admin_toolbar() -> html.Div:
    return html.Div(
        [
            dbc.Button("Add Row", id="admin-open-add-modal", color="success", size="sm", className="me-2"),
            dbc.Button(
                "Delete Latest Row",
                id="admin-open-delete-modal",
                color="danger",
                size="sm",
                outline=True,
                className="me-2",
            ),
            build_export_disabled_control(),
            html.A("Logout", href="/admin/logout", className="btn btn-link btn-sm"),
        ],
        className=f"mb-3 {ADMIN_TOOLBAR_CLASS}",
    )


def resolve_access_visibility(
    *,
    ui_mode: Optional[str],
) -> tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Presentation-only access gate driven by explicit per-visit UI mode selection."""
    if ui_mode in (UI_MODE_PUBLIC, UI_MODE_ADMIN):
        return {"display": "none"}, {"display": "block"}, {"display": "block"}
    from tcp_public_sections import resolve_public_gate_styles

    gate_style, main_style = resolve_public_gate_styles(None)
    return gate_style, main_style, {"display": "none"}


def resolve_daily_values_toolbar_style(
    *,
    ui_mode: Optional[str],
    admin_authenticated: bool,
) -> Dict[str, str]:
    if ui_mode == UI_MODE_ADMIN and admin_authenticated:
        return {"display": "block"}
    return {"display": "none"}


def build_daily_values_section(
    records: Sequence[LedgerRecord],
    metadata: LedgerMetadata,
    *,
    data_source: str,
) -> html.Div:
    rows = rows_from_records(records)
    return html.Div(
        dbc.Card(
            [
                dbc.CardHeader(
                    html.Div(
                        [
                            html.H6("Daily Values", className="mb-0"),
                            dbc.Button(
                                PUBLIC_DAILY_TOGGLE_LABEL_SHOW,
                                id=PUBLIC_DAILY_TOGGLE_BTN_ID,
                                color="link",
                                size="sm",
                                className="tcp-daily-values-toggle p-0 text-decoration-none fw-bold",
                                n_clicks=0,
                            ),
                        ],
                        className="d-flex align-items-center justify-content-between",
                    ),
                    className=HEADER_ROW_CLASS,
                ),
                dbc.Collapse(
                    id=PUBLIC_DAILY_COLLAPSE_ID,
                    is_open=False,
                    children=dbc.CardBody(
                        [
                            build_daily_values_summary(
                                completed_rows=metadata.completed_row_count,
                                latest_date=metadata.latest_completed_date,
                                data_source=data_source,
                            ),
                            html.Div(
                                build_daily_values_admin_toolbar(),
                                id=DAILY_VALUES_TOOLBAR_ID,
                                style={"display": "none"},
                            ),
                            html.Div(
                                build_daily_values_datatable(rows),
                                className=CONTROLLED_TABLE_OVERFLOW_CLASS,
                            ),
                        ]
                    ),
                ),
            ],
            className=PUBLIC_CARD_CLASS,
            id="tcp-daily-values-card",
        ),
        id=DAILY_VALUES_SECTION_ID,
        className=PUBLIC_SECTION_CLASS,
        style={"display": "none"},
    )
