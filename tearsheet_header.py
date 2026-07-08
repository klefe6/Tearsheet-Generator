"""
Shared tearsheet header — top-right “Data current to” status block.

TCP introduced the polished layout and typography; TKP, TCP, and AGM all
render the same block via this module (tearsheet-header-date-* classes in
assets/styles.css).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional, Union

from dash import html
import dash_bootstrap_components as dbc

HEADER_DATA_CURRENT_LABEL = "Data current to"
HEADER_DATA_UNAVAILABLE_LABEL = "Data unavailable"
HEADER_DATE_CLOSE_SUFFIX = " close"

DateLike = Union[date, datetime, str, None]


def format_data_current_date_line(value: DateLike) -> str:
    """Format a date as ``July 06, 2026 close`` (TCP label style)."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "unavailable":
            return ""
        if text.endswith(HEADER_DATE_CLOSE_SUFFIX):
            return text
        return f"{text}{HEADER_DATE_CLOSE_SUFFIX}"
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.strftime('%B %d, %Y')}{HEADER_DATE_CLOSE_SUFFIX}"


def build_header_date_label_children(
    header: str,
    date_line: str,
) -> tuple[List[Any], List[Any]]:
    """Desktop/mobile label children — matches TCP ``_desktop/_mobile_label_children``."""
    desktop = [
        html.Div(
            header,
            className="tearsheet-header-date-label",
            id="data-current-label-desktop-header",
        ),
        html.Div(
            date_line,
            className="tearsheet-header-date-value",
            id="data-current-label-desktop-date",
        ),
    ]
    mobile = [
        html.Div(
            header,
            className="tearsheet-header-date-label",
            id="data-current-label-mobile-header",
        ),
        html.Div(
            date_line,
            className="tearsheet-header-date-value",
            id="data-current-label-mobile-date",
        ),
    ]
    return desktop, mobile


def build_header_date_label_children_from_date(
    latest: DateLike,
    *,
    header: str = HEADER_DATA_CURRENT_LABEL,
    unavailable_header: str = HEADER_DATA_UNAVAILABLE_LABEL,
) -> tuple[List[Any], List[Any]]:
    """Build label children from a date (or unavailable)."""
    if latest is None or (isinstance(latest, str) and latest.strip().lower() == "unavailable"):
        return build_header_date_label_children(unavailable_header, "")
    return build_header_date_label_children(header, format_data_current_date_line(latest))


def build_tearsheet_header_row(
    *,
    logo_src: Optional[str],
    logo_alt: str,
    firm_name: str,
    product_name: str,
    desktop_label_children: List[Any],
    mobile_label_children: List[Any],
    grey_bg: str = "#EBEBEB",
    header_row_id: Optional[str] = None,
) -> List[Any]:
    """Header row + mobile date row + rule — same structure as TCP ``build_tcp_header``."""
    header_row_kwargs: dict[str, Any] = {
        "align": "center",
        "style": {"backgroundColor": grey_bg, "padding": "10px 0", "pageBreakInside": "avoid"},
        "className": "header-row",
    }
    if header_row_id is not None:
        header_row_kwargs["id"] = header_row_id

    logo_col = (
        html.Img(
            src=logo_src,
            className="img-fluid",
            style={"maxHeight": "100px", "height": "auto", "width": "auto"},
            alt=logo_alt,
        )
        if logo_src
        else html.Div(style={"height": "80px"})
    )

    return [
        dbc.Row(
            [
                dbc.Col(logo_col, width=2),
                dbc.Col(
                    html.Div(
                        [
                            html.H2(firm_name, className="text-center"),
                            html.H5(product_name, className="text-center text-muted"),
                        ],
                        style={"lineHeight": "1.2", "paddingTop": "20px"},
                    ),
                    width=8,
                ),
                dbc.Col(
                    html.Div(
                        desktop_label_children,
                        id="data-current-label-desktop",
                        className="d-none d-md-block tearsheet-header-date-block",
                    ),
                    width=2,
                ),
            ],
            **header_row_kwargs,
        ),
        html.Hr(),
        dbc.Row(
            dbc.Col(
                html.Div(
                    mobile_label_children,
                    id="data-current-label-mobile",
                    className="d-block d-md-none tearsheet-header-date-block",
                ),
                width=12,
            ),
            className="mb-3",
        ),
    ]
