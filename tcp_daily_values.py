"""
TCP v2 Daily Values presentation — shared public/admin table from canonical runtime snapshot.

Safe to import: no server start, no workbook/JSON writes, no secrets.
"""
from __future__ import annotations

from datetime import date
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
    ADMIN_TOOLBAR_CLASS,
)

DAILY_VALUES_SECTION_ID = "tcp-daily-values-section"
DAILY_VALUES_TABLE_ID = "tcp-daily-values-table"
DAILY_VALUES_TOOLBAR_ID = "tcp-daily-values-admin-toolbar"
DAILY_VALUES_SUMMARY_ID = "tcp-daily-values-summary"
PUBLIC_GATE_ACCEPTED_STORE_ID = "public-gate-accepted-store"
GATE_NOTICE_E_ID = "secret-notice-e"

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
    display_rows = project_public_daily_rows(rows)
    return dash_table.DataTable(
        id=DAILY_VALUES_TABLE_ID,
        columns=public_daily_column_defs(visible_columns),
        data=display_rows,
        page_action="native",
        page_size=DEFAULT_PAGE_SIZE,
        sort_action="native",
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
        style_data_conditional=ledger_table_style_conditional(list(rows)),
    )


def build_daily_values_admin_toolbar() -> html.Div:
    return html.Div(
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
        className=f"mb-3 {ADMIN_TOOLBAR_CLASS}",
    )


def resolve_access_visibility(
    *,
    accept_clicks: Optional[int],
    admin_authenticated: bool,
    public_accepted: Optional[bool],
) -> tuple[Dict[str, str], Dict[str, str], Dict[str, str], bool]:
    """Presentation-only access gate (not an admin authorization signal)."""
    if admin_authenticated:
        return {"display": "none"}, {"display": "block"}, {"display": "block"}, True
    if accept_clicks and accept_clicks > 0:
        return {"display": "none"}, {"display": "block"}, {"display": "block"}, True
    if public_accepted:
        return {"display": "none"}, {"display": "block"}, {"display": "block"}, True
    from tcp_public_sections import resolve_public_gate_styles

    gate_style, main_style = resolve_public_gate_styles(None)
    return gate_style, main_style, {"display": "none"}, False


def resolve_daily_values_toolbar_style(*, admin_authenticated: bool) -> Dict[str, str]:
    if admin_authenticated:
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
                dbc.CardHeader(html.H6("Daily Values", className="mb-0"), className=HEADER_ROW_CLASS),
                dbc.CardBody(
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
            ],
            className=PUBLIC_CARD_CLASS,
            id="tcp-daily-values-card",
        ),
        id=DAILY_VALUES_SECTION_ID,
        style={"display": "none"},
    )
