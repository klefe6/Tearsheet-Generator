"""

TCP v2 read-only preview shell (port 8312).



Does not import tcp_ts.py or tkp_ts.py. Does not write JSON or Excel.

Server starts only under if __name__ == "__main__".

"""

from __future__ import annotations



import logging

import sys

from dataclasses import dataclass

from datetime import date

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple



import dash

import dash_bootstrap_components as dbc

import pandas as pd

from dash import Input, Output, dcc, html

from flask import jsonify



from tcp_config import TCPConfig, load_config, resolve_state_paths, validate_config

from tcp_dashboard import (

    GREY_BG,

    PRIMARY_COLOR,

    canonical_nav_records_from_ledger,

    propagate_tcp_dashboard,

)

from tcp_ledger import LedgerLoadResult, TCPLedgerError, load_ledger

from tcp_state import StatePaths, state_layer_status



logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("tcp_ts_v2")



WHITE_BG = "#ffffff"

REPO_ROOT = Path(__file__).resolve().parent



LOGO_PATH = (

    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"

    r"\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png"

)





@dataclass

class PreviewState:

    ledger: Optional[LedgerLoadResult] = None

    error: Optional[str] = None

    error_type: Optional[str] = None

    state_diagnostics: Optional[dict] = None

    canonical_nav: Optional[List[Dict[str, Any]]] = None





def _configured_state_paths(cfg: TCPConfig) -> StatePaths:

    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)

    return StatePaths(active_path=active, backup_path=backup, lock_path=lock)





def _logo_src() -> str:

    import base64



    try:

        with open(LOGO_PATH, "rb") as f:

            b64 = base64.b64encode(f.read()).decode("utf-8")

        return f"data:image/png;base64,{b64}"

    except OSError:

        return ""





def load_preview_ledger(cfg: TCPConfig) -> PreviewState:

    state_paths = _configured_state_paths(cfg)

    diagnostics = state_layer_status(state_paths)

    try:

        ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)

        canonical_nav = canonical_nav_records_from_ledger(ledger.completed_records)

        logger.info(

            "TCP v2 adapter loaded %s completed rows (%s candidates); latest %s",

            ledger.metadata.completed_row_count,

            ledger.metadata.total_candidate_rows,

            ledger.metadata.latest_completed_date,

        )

        return PreviewState(

            ledger=ledger,

            state_diagnostics=diagnostics,

            canonical_nav=canonical_nav,

        )

    except TCPLedgerError as exc:

        logger.error("TCP v2 adapter failed for %s: %s", cfg.workbook_path, exc)

        return PreviewState(

            error=str(exc),

            error_type=type(exc).__name__,

            state_diagnostics=diagnostics,

        )





def _monthly_table_component(monthly_df: pd.DataFrame) -> html.Div:

    if monthly_df.empty:

        return html.P("No monthly performance data available.", className="text-muted text-center")

    return dbc.Table(

        [

            html.Thead(

                html.Tr(

                    [

                        html.Th(col, style={"backgroundColor": GREY_BG, "color": "#000"})

                        for col in monthly_df.columns

                    ]

                )

            ),

            html.Tbody(

                [

                    html.Tr([html.Td(monthly_df.iloc[i][col]) for col in monthly_df.columns])

                    for i in range(len(monthly_df))

                ]

            ),

        ],

        bordered=True,

        hover=True,

        size="sm",

        className="table-responsive mb-5",

        style={"width": "95%", "margin": "0 auto", "pageBreakInside": "avoid"},

    )





def _daily_perf_table_component(daily_df: pd.DataFrame) -> html.Div:

    if daily_df.empty:

        return html.P("No daily performance metrics available.", className="text-muted")

    return dbc.Table.from_dataframe(

        daily_df,

        striped=False,

        bordered=True,

        hover=True,

        size="sm",

        className="fixed-cols",

    )





def _desktop_label_children(header: str, date_line: str) -> List[Any]:

    return [

        html.H6(header, className="text-end text-secondary mb-1", id="data-current-label-desktop-header"),

        html.H5(date_line, className="text-end text-primary", id="data-current-label-desktop-date"),

    ]





def _mobile_label_children(header: str, date_line: str) -> List[Any]:

    return [

        html.Small(header, className="d-block text-end text-primary mb-1", id="data-current-label-mobile-header"),

        html.Small(date_line, className="d-block text-end text-primary", id="data-current-label-mobile-date"),

    ]





def build_error_layout(cfg: TCPConfig, state: PreviewState) -> html.Div:

    message = state.error or "Unknown adapter error"

    return html.Div(

        [

            dbc.Alert(cfg.preview_label, color="warning", className="text-center fw-bold"),

            dbc.Container(

                fluid=True,

                className="py-4",

                children=[

                    dbc.Alert(

                        [

                            html.H4("Read-only preview error", className="alert-heading"),

                            html.P(message, className="mb-0"),

                            html.P(

                                f"Adapter status: {state.error_type or 'error'}",

                                className="small text-muted mt-2",

                            ),

                            html.P(

                                f"Workbook: {cfg.workbook_filename} · Sheet: {cfg.sheet_name}",

                                className="small text-muted",

                            ),

                        ],

                        color="danger",

                    ),

                ],

            ),

        ]

    )





def build_preview_layout(cfg: TCPConfig, state: PreviewState) -> html.Div:

    ledger = state.ledger

    assert ledger is not None

    meta = ledger.metadata

    first_completed = meta.first_completed_date.strftime("%B %d, %Y") if meta.first_completed_date else "—"

    state_diag = state.state_diagnostics or {}

    canonical_nav = state.canonical_nav or []

    propagation = propagate_tcp_dashboard(canonical_nav)



    return html.Div(

        [

            dcc.Store(id="canonical-nav-store", storage_type="memory", data=canonical_nav),

            dbc.Container(

                fluid=True,

                className="py-4",

                children=[

                    dbc.Alert(

                        cfg.preview_label,

                        color="warning",

                        className="text-center fw-bold",

                    ),

                    dbc.Row(

                        [

                            dbc.Col(

                                html.Img(

                                    src=_logo_src(),

                                    style={"maxHeight": "80px"},

                                    alt="Hughes & Company Logo",

                                ),

                                width=2,

                            ),

                            dbc.Col(

                                [

                                    html.H2("Hughes & Company LLC", className="text-center"),

                                    html.H5(

                                        "The Crypto Program",

                                        className="text-center text-muted",

                                    ),

                                ],

                                width=8,

                            ),

                            dbc.Col(

                                html.Div(

                                    _desktop_label_children(

                                        propagation.desktop_label.header,

                                        propagation.desktop_label.date_line,

                                    ),

                                    id="data-current-label-desktop",

                                    className="d-none d-md-block",

                                ),

                                width=2,

                            ),

                        ],

                        className="mb-1",

                    ),

                    dbc.Row(

                        [

                            dbc.Col(

                                html.Div(

                                    _mobile_label_children(

                                        propagation.mobile_label.header,

                                        propagation.mobile_label.date_line,

                                    ),

                                    id="data-current-label-mobile",

                                    className="d-block d-md-none text-end",

                                ),

                                width=12,

                            )

                        ],

                        className="mb-3",

                    ),

                    dbc.Alert(

                        "Editing is disabled in this read-only preview. "

                        "JSON persistence and website row entry are not yet available.",

                        color="info",

                    ),

                    dcc.Graph(

                        id="nav-preview-graph",

                        figure=propagation.nav_figure,

                        config={"displayModeBar": False, "responsive": True},

                        style={

                            "width": "100%",

                            "maxWidth": "100%",

                            "maxHeight": "400px",

                            "pageBreakInside": "avoid",

                        },

                    ),

                    html.P(

                        "This chart visualizes the growth of a $50,000 investment from inception to today. "

                        "NAV stands for Net Asset Value; it reflects the non-compounded performance, net of all fees.",

                        className="text-center small",

                        style={"marginTop": "2rem"},

                    ),

                    html.H5("Performance Summary", className="text-center mb-2"),

                    html.Div(

                        _monthly_table_component(propagation.monthly_calendar),

                        id="monthly-calendar-container",

                    ),

                    dbc.Card(

                        [

                            dbc.CardHeader(html.H6("Performance Metrics", className="mb-0")),

                            dbc.CardBody(

                                html.Div(

                                    _daily_perf_table_component(propagation.daily_performance),

                                    id="daily-perf-container",

                                )

                            ),

                        ],

                        outline=True,

                        className="mb-4",

                    ),

                    dbc.Card(

                        [

                            dbc.CardHeader("Adapter diagnostics (preview only)"),

                            dbc.CardBody(

                                [

                                    html.P(

                                        [html.Strong("Data source: "), "workbook adapter"],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [html.Strong("Adapter status: "), "ok"],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [html.Strong("Read-only mode: "), "enabled"],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("State layer: "),

                                            state_diag.get("state_layer", "available"),

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("Active state: "),

                                            state_diag.get("active_state", "not_initialized"),

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("Completed ledger rows: "),

                                            str(meta.completed_row_count),

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("Candidate rows: "),

                                            str(meta.total_candidate_rows),

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("First completed date: "),

                                            first_completed,

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("Latest completed date: "),

                                            propagation.desktop_label.date_line,

                                        ],

                                        className="mb-1",

                                    ),

                                    html.P(

                                        [

                                            html.Strong("Workbook: "),

                                            cfg.workbook_filename,

                                            " · Sheet: ",

                                            cfg.sheet_name,

                                        ],

                                        className="mb-0 small text-muted",

                                    ),

                                ]

                            ),

                        ],

                        className="mt-3",

                    ),

                ],

            ),

        ]

    )





def _health_payload(cfg: TCPConfig, state: PreviewState) -> dict:

    base = {

        "app": "tcp-v2",

        "mode": "read-only",

        "port": cfg.preview_port,

        "debug": cfg.debug,

        "workbook": cfg.workbook_filename,

        "sheet": cfg.sheet_name,

        "data_source": "workbook",

        "active_state": "not_initialized",

        "dashboard_propagation": "ready",

        "monthly_performance": "dynamic",

        "daily_metrics": "dynamic",

        "nav_chart": "dynamic",

        "current_date_labels": "dynamic",

    }

    if state.state_diagnostics:

        base.update(

            {

                "state_layer": state.state_diagnostics.get("state_layer", "available"),

                "active_state": state.state_diagnostics.get("active_state", "not_initialized"),

            }

        )

    if state.ledger is not None:

        meta = state.ledger.metadata

        base.update(

            {

                "adapter_status": "ok",

                "completed_rows": meta.completed_row_count,

                "latest_completed_date": (

                    meta.latest_completed_date.isoformat()

                    if meta.latest_completed_date

                    else None

                ),

                "first_completed_date": (

                    meta.first_completed_date.isoformat()

                    if meta.first_completed_date

                    else None

                ),

                "candidate_rows": meta.total_candidate_rows,

            }

        )

    else:

        base.update(

            {

                "adapter_status": "error",

                "error_type": state.error_type,

                "message": state.error,

            }

        )

    return base





def _register_dashboard_callback(app: dash.Dash) -> None:

    @app.callback(

        Output("nav-preview-graph", "figure"),

        Output("monthly-calendar-container", "children"),

        Output("daily-perf-container", "children"),

        Output("data-current-label-desktop", "children"),

        Output("data-current-label-mobile", "children"),

        Input("canonical-nav-store", "data"),

    )

    def _propagate_dashboard_outputs(canonical_data):

        records = canonical_data or []

        propagation = propagate_tcp_dashboard(records)

        return (

            propagation.nav_figure,

            _monthly_table_component(propagation.monthly_calendar),

            _daily_perf_table_component(propagation.daily_performance),

            _desktop_label_children(

                propagation.desktop_label.header,

                propagation.desktop_label.date_line,

            ),

            _mobile_label_children(

                propagation.mobile_label.header,

                propagation.mobile_label.date_line,

            ),

        )





def create_app(cfg: Optional[TCPConfig] = None) -> Tuple[dash.Dash, TCPConfig, PreviewState]:

    """Construct Dash app and attach health route. Does not start the server."""

    cfg = cfg or load_config()

    ok, msg = validate_config(cfg)

    if not ok:

        raise ValueError(f"Invalid TCP v2 config: {msg}")



    state = load_preview_ledger(cfg)



    app = dash.Dash(

        __name__,

        external_stylesheets=[dbc.themes.BOOTSTRAP],

        suppress_callback_exceptions=True,

        title="H&C – TCP v2 Preview",

    )



    if state.ledger is not None:

        app.layout = build_preview_layout(cfg, state)

        _register_dashboard_callback(app)

    else:

        app.layout = build_error_layout(cfg, state)



    @app.server.route("/healthz")

    def healthz():

        payload = _health_payload(cfg, state)

        status = 200 if state.ledger is not None else 503

        return jsonify(payload), status



    return app, cfg, state





app, _CONFIG, _PREVIEW_STATE = create_app()





def main() -> None:

    cfg = _CONFIG

    ok, msg = validate_config(cfg)

    if not ok:

        logger.error("Config validation failed: %s", msg)

        sys.exit(1)

    logger.info("Starting %s on port %s (debug=%s)", cfg.preview_label, cfg.preview_port, cfg.debug)

    app.run(debug=cfg.debug, port=cfg.preview_port)





if __name__ == "__main__":

    main()


