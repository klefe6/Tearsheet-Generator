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
from typing import List, Optional, Tuple

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import dcc, html
from flask import jsonify

from tcp_config import TCPConfig, load_config, resolve_state_paths, validate_config
from tcp_ledger import LedgerLoadResult, TCPLedgerError, load_ledger
from tcp_state import StatePaths, state_layer_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tcp_ts_v2")

PRIMARY_COLOR = "#0D3562"
GREY_BG = "#EBEBEB"
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
        logger.info(
            "TCP v2 adapter loaded %s completed rows (%s candidates); latest %s",
            ledger.metadata.completed_row_count,
            ledger.metadata.total_candidate_rows,
            ledger.metadata.latest_completed_date,
        )
        return PreviewState(ledger=ledger, state_diagnostics=diagnostics)
    except TCPLedgerError as exc:
        logger.error("TCP v2 adapter failed for %s: %s", cfg.workbook_path, exc)
        return PreviewState(
            error=str(exc),
            error_type=type(exc).__name__,
            state_diagnostics=diagnostics,
        )


def build_nav_figure(ledger: LedgerLoadResult) -> go.Figure:
    dates: List[date] = []
    nav_values: List[float] = []
    for record in ledger.completed_records:
        row_date = record.fields["Date"]
        nav = record.fields["nav-x1"]
        if row_date is not None and nav is not None:
            dates.append(row_date)
            nav_values.append(float(nav))

    fig = go.Figure(
        go.Scatter(
            x=dates,
            y=nav_values,
            mode="lines",
            line={"color": PRIMARY_COLOR},
            name="NAV",
        )
    )
    fig.update_layout(
        title={
            "text": "<u>Non-Compounded NAV Since Inception</u>",
            "x": 0.5,
            "xanchor": "center",
        },
        template="ggplot2",
        plot_bgcolor=GREY_BG,
        paper_bgcolor=WHITE_BG,
        xaxis_title="Date",
        yaxis_title="NAV",
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
    )
    return fig


def _format_date(d: Optional[date]) -> str:
    if d is None:
        return "—"
    return d.strftime("%B %d, %Y")


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
    last_updated = _format_date(meta.latest_completed_date)
    first_completed = _format_date(meta.first_completed_date)
    state_diag = state.state_diagnostics or {}

    return html.Div(
        [
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
                                [
                                    html.H6("Data current to", className="text-end text-secondary"),
                                    html.H5(last_updated, className="text-end text-primary"),
                                ],
                                width=2,
                            ),
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
                        figure=build_nav_figure(ledger),
                        config={"displayModeBar": False, "responsive": True},
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
                                            last_updated,
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
            )
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
