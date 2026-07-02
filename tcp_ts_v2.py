"""
TCP v2 read-only preview shell (port 8312).

Does not import tcp_ts.py or tkp_ts.py. Does not write JSON or Excel.
Server starts only under if __name__ == "__main__".
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objs as go
from dash import dcc, html
from flask import jsonify

from tcp_config import TCPConfig, load_config, validate_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tcp_ts_v2")

PRIMARY_COLOR = "#0D3562"
GREY_BG = "#EBEBEB"
WHITE_BG = "#ffffff"

LOGO_PATH = (
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"
    r"\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png"
)


@dataclass
class NavPreviewData:
    dates: pd.DatetimeIndex
    nav_values: pd.Series
    last_completed_date: pd.Timestamp
    row_count: int


class NavPreviewLoadError(Exception):
    """Raised when the TCP workbook cannot be read for preview."""


def _logo_src() -> str:
    import base64

    try:
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except OSError:
        return ""


def load_nav_preview_data(cfg: TCPConfig) -> NavPreviewData:
    """
    Read-only load of Date (C) and nav-x1 (L) from worksheet NAV.
    Last completed row = last date with non-empty nav-x1 (matches production TCP rule).
    """
    path = cfg.workbook_path
    if not os.path.exists(path):
        raise NavPreviewLoadError(f"Workbook not found: {path}")
    if not os.access(path, os.R_OK):
        raise NavPreviewLoadError(
            f"Workbook not readable (may be open in Excel): {path}"
        )

    try:
        nav_df = pd.read_excel(
            path,
            sheet_name=cfg.sheet_name,
            usecols="C,L",
            header=0,
            engine="openpyxl",
        )
    except PermissionError as exc:
        raise NavPreviewLoadError(
            f"Permission denied reading workbook: {path}"
        ) from exc
    except Exception as exc:
        raise NavPreviewLoadError(f"Failed to read workbook: {exc}") from exc

    if nav_df.empty or len(nav_df.columns) < 2:
        raise NavPreviewLoadError("NAV sheet missing Date or nav-x1 columns")

    nav_df.rename(columns={nav_df.columns[0]: cfg.date_column}, inplace=True)
    nav_col_name = nav_df.columns[1]

    if nav_df[cfg.date_column].dtype == "object":
        nav_df[cfg.date_column] = pd.to_datetime(nav_df[cfg.date_column], errors="coerce")
    nav_df = nav_df.dropna(subset=[cfg.date_column])
    nav_df = nav_df.set_index(cfg.date_column)

    nav_col = nav_df[nav_col_name]
    has_nav = nav_col.notna()
    if nav_col.dtype == object:
        has_nav &= (
            nav_col.astype(str).str.strip().ne("")
            & nav_col.astype(str).str.strip().str.lower().ne("nan")
        )
    if not has_nav.any():
        raise NavPreviewLoadError("No rows with nav-x1 values in column L")

    nav_df = nav_df.loc[has_nav]
    last_date = nav_df.index.max()
    series = nav_df[nav_col_name].astype(float)

    return NavPreviewData(
        dates=nav_df.index,
        nav_values=series,
        last_completed_date=last_date,
        row_count=len(nav_df),
    )


def build_nav_figure(data: NavPreviewData) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=data.dates,
            y=data.nav_values,
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


def build_error_layout(cfg: TCPConfig, message: str) -> html.Div:
    return html.Div(
        [
            dbc.Alert(
                [
                    html.H4(cfg.preview_label, className="alert-heading"),
                    html.P("Read-only preview could not load workbook data."),
                    html.Hr(),
                    html.P(message, className="mb-0"),
                    html.P(
                        f"Configured workbook filename: {cfg.workbook_filename}",
                        className="small text-muted mt-2",
                    ),
                ],
                color="danger",
            ),
        ],
        className="p-4",
    )


def build_preview_layout(cfg: TCPConfig, data: NavPreviewData) -> html.Div:
    last_updated = data.last_completed_date.strftime("%B %d, %Y")
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
                        "Daily entry, JSON persistence, and full ledger loading are not yet available.",
                        color="info",
                    ),
                    dcc.Graph(
                        id="nav-preview-graph",
                        figure=build_nav_figure(data),
                        config={"displayModeBar": False, "responsive": True},
                    ),
                    html.P(
                        f"Loaded {data.row_count} NAV rows from {cfg.workbook_filename} "
                        f"({cfg.sheet_name} sheet). Preview port {cfg.preview_port}.",
                        className="text-center small text-muted mt-3",
                    ),
                ],
            )
        ]
    )


def create_app(cfg: Optional[TCPConfig] = None) -> Tuple[dash.Dash, TCPConfig]:
    """Construct Dash app and attach health route. Does not start the server."""
    cfg = cfg or load_config()
    ok, msg = validate_config(cfg)
    if not ok:
        raise ValueError(f"Invalid TCP v2 config: {msg}")

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
        title="H&C – TCP v2 Preview",
    )

    try:
        data = load_nav_preview_data(cfg)
        app.layout = build_preview_layout(cfg, data)
        logger.info(
            "TCP v2 preview loaded %s rows; last date %s",
            data.row_count,
            data.last_completed_date.date(),
        )
    except NavPreviewLoadError as exc:
        logger.error("TCP v2 preview load failed: %s", exc)
        app.layout = build_error_layout(cfg, str(exc))

    @app.server.route("/healthz")
    def healthz():
        return jsonify(
            {
                "app": "tcp-v2",
                "mode": "read-only",
                "port": cfg.preview_port,
                "debug": cfg.debug,
                "workbook": cfg.workbook_filename,
                "sheet": cfg.sheet_name,
            }
        )

    return app, cfg


# Module-level app for tests; server not started until __main__.
app, _CONFIG = create_app()


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
