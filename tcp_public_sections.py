"""
TCP v2 public static sections — committed v1 copy and layout helpers.

Safe to import: no server start, no workbook/JSON I/O, no network calls.
Source of truth: git HEAD tcp_ts.py at Step 11B base (b5fce4b).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import dash_bootstrap_components as dbc
from dash import dcc, html

from tcp_dashboard import GREY_BG

HNC_LEGAL_NAME = "Hughes & Company LLC"
TCP_PRODUCT_NAME = "The Crypto Program"

WHITE_BG = "#ffffff"
PRIMARY_COLOR = "#0D3562"
SECONDARY_COLOR = "#CCCCCC"
LEFT_TABLE_GAPS = "20px"
HEADER_ROW_CLASS = "bg-light"

GATE_SCREEN_STYLE: Dict[str, str] = {"padding": "4rem", "textAlign": "center"}
GATE_ACCEPT_TEXT = (
    "By clicking “Accept,” you agree that the performance figures shown are strictly "
    "informational and do not amount to investment advice, a solicitation, or an offer "
    "to invest or participate in this strategy. This material is not intended to solicit funds."
)

STRATEGY_DESCRIPTION = (
    "The Crypto Program (TCP) is a crypto options strategy focused on Bitcoin and Ethereum, "
    "designed to generate long-biased, stable returns through the systematic sale of short-dated "
    "put options at proprietary strike levels. The strategy actively monetizes volatility by "
    "selling puts with the intent to either capture premium or be assigned underlying assets at "
    "attractive prices, after which out-of-the-money call options are written sequentially to "
    "generate additional yield and manage downside risk. TCP is most active during volatile market "
    "conditions and is structured to reduce both drawdown depth and duration while maintaining "
    "long-term exposure to BTC and ETH. The program is built for consistent performance across "
    "market environments, with frequent visibility, disciplined risk management, and liquidity "
    "as core design principles."
)

ACCOUNT_STATISTICS: Tuple[Tuple[str, str, str], ...] = (
    ("Nominal Assets Being Traded in the Program", "$50,000", "0"),
    ("Total Accounts/Tranches Opened", "2", "0"),
    ("Accounts/Tranches Currently Open", "2", "0"),
    ("Accounts/Tranches Closed Profitably", "0", "0"),
    ("Accounts/Tranches Closed Unprofitably", "0", "0"),
    ("Range of Net Returns of Accounts/Tranches Closed", "N/A", "N/A"),
)

HCDISCLAIMER_TEXT = (
    "UNTIL TCP IS OFFICIALLY OPENED TO OUTSIDE INVESTORS BY THE INTRODUCING BROKER, "
    "THE STRATEGY REMAINS PROPRIETARY AND THIS PAGE OR DESCRIPTION IS NOT A SOLICITATION TO INVEST. "
    "NO SUBSCRIPTION DOCUMENTS HAVE BEEN ISSUED, AND TCP WILL ONLY BECOME AVAILABLE ONCE THE IB "
    "PUBLISHES THE APPROPRIATE SUBSCRIPTION MATERIALS AND DECLARES THE PROGRAM OPEN FOR OUTSIDE INVESTMENT."
)

GENERAL_DISCLAIMER_TEXT = (
    "THE RISK OF LOSS IN COMMODITY INTEREST TRADING CAN BE SUBSTANTIAL. YOU SHOULD, THEREFORE, "
    "CAREFULLY CONSIDER WHETHER SUCH TRADING IS SUITABLE FOR YOU IN LIGHT OF YOUR FINANCIAL CONDITION. "
    "THE HIGH DEGREE OF LEVERAGE IN COMMODITY INTEREST TRADING MEANS INVESTMENTS SHOULD BE MADE WITH RISK "
    "CAPITAL ONLY. ALL INFORMATION ABOVE IS COMPILED WITH THE INTENTION OF BEING FULLY CORRECT, THOUGH THERE "
    "IS NO GUARANTEE ALL INFORMATION IS CORRECT AND COULD BE SUBJECT TO UNINTENTIONAL CLERICAL ITEMS. "
    "PAST PERFORMANCE IS NOT NECESSARILY INDICATIVE OF FUTURE RESULTS.\n\n"
    "PLEASE ENSURE THAT YOU ARE FULLY AWARE AND UNDERSTAND ALL RISKS, FEES, AND OTHER CONCERNS RELATED TO YOUR "
    "INVESTMENT BY REQUESTING THE COMPLETE DISCLOSURE DOCUMENT & INVESTMENT MANAGEMENT AGREEMENT MATERIALS BY "
    "REACHING OUT DIRECTLY TO THE ADVISOR."
)

FOOTER_CONTACT = (
    "HUGHES & COMPANY LLC • NFA ID 0423388 • 330 Himmararshee, Ste 110, FTL, FL 33312 • "
    "954-500-0500 • www.hughesandco.ltd"
)

# Committed v1 symbol names retained for parity audit markers.
hcdisclaimer_text = HCDISCLAIMER_TEXT
disclaimer_text = GENERAL_DISCLAIMER_TEXT
footer_contact = FOOTER_CONTACT

NAV_FOOTNOTE_PRIMARY = (
    "This chart visualizes the growth of a $150,000 investment from inception to today. "
    "NAV stands for Net Asset Value; it reflects the non-compounded performance, net of all fees."
)

NAV_FOOTNOTE_SECONDARY = (
    "Please note that all percentages shown are relative to the initial amount invested. "
    "Also note that performance may vary depending on the time of entry due to the fixed-sizing "
    "nature of this strategy."
)

FIRM_INTRO_LEAD = (
    f"{HNC_LEGAL_NAME} is an introducing brokerage firm with expertise in the futures options industry."
)

FIRM_INTRO_META = (
    "Principals: Daniel V. Hughes III | Inception: January 2026 | "
    "Products Traded: Bitcoin & Ethereum Options | Styles: Short Options"
)

DISCLOSURE_PANEL_STYLE = {
    "backgroundColor": "#f8f9fa",
    "borderLeft": "4px solid #6c757d",
    "fontSize": "0.875rem",
}


def required_copy_fragments() -> Dict[str, str]:
    """Normalized inventory of committed v1 copy fragments for provenance tests."""
    return {
        "product": TCP_PRODUCT_NAME,
        "firm": HNC_LEGAL_NAME,
        "strategy_heading": "Strategy Overview",
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum",
        "gate_title": "Important Notice",
        "account_stats_heading": "Account Stats",
        "proprietary_heading": "Proprietary",
        "client_heading": "Client",
        "hcdisclaimer_prefix": "UNTIL TCP IS OFFICIALLY OPENED",
        "footer_nfa": "NFA ID 0423388",
        "nav_footnote_secondary_prefix": "Please note that all percentages",
    }


def _mark(checked: bool, label: str) -> html.Span:
    symbol = "✓" if checked else "✗"
    color = PRIMARY_COLOR if checked else SECONDARY_COLOR
    return html.Span(f"{symbol} {label}", style={"color": color, "marginRight": "0.5rem"})


def build_public_accept_gate() -> html.Div:
    return html.Div(
        id="disclaimer-screen",
        style=GATE_SCREEN_STYLE,
        children=html.Div(
            children=[
                html.H2("Important Notice", className="mb-4", id="tcp-public-gate-title"),
                html.P(GATE_ACCEPT_TEXT, className="lead mb-5", id="tcp-public-gate-copy"),
                dbc.Button("Accept & Continue", id="accept-button", color="primary"),
            ],
        ),
    )


def build_tcp_header(
    logo_src: str,
    desktop_label_children: List[Any],
    mobile_label_children: List[Any],
) -> List[Any]:
    return [
        dbc.Row(
            [
                dbc.Col(
                    html.Img(
                        src=logo_src,
                        className="img-fluid",
                        style={"maxHeight": "100px", "height": "auto", "width": "auto"},
                        alt=f"{HNC_LEGAL_NAME} Logo",
                    ),
                    width=2,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.H2(HNC_LEGAL_NAME, className="text-center"),
                            html.H5(TCP_PRODUCT_NAME, className="text-center text-muted"),
                        ],
                        style={"lineHeight": "1.2", "paddingTop": "20px"},
                    ),
                    width=8,
                ),
                dbc.Col(
                    html.Div(desktop_label_children, id="data-current-label-desktop", className="d-none d-md-block"),
                    width=2,
                ),
            ],
            align="center",
            style={"backgroundColor": GREY_BG, "padding": "10px 0", "pageBreakInside": "avoid"},
            className="header-row",
            id="tcp-public-header-row",
        ),
        html.Hr(),
        dbc.Row(
            dbc.Col(
                html.Div(mobile_label_children, id="data-current-label-mobile", className="d-block d-md-none text-end"),
                width=12,
            ),
            className="mb-3",
        ),
    ]


def build_firm_intro() -> html.Div:
    return html.Div(
        [
            html.P(FIRM_INTRO_LEAD, className="lead text-center", id="tcp-firm-intro-lead"),
            html.P(FIRM_INTRO_META, className="text-center mb-5", id="tcp-firm-intro-meta"),
        ],
        className="description",
        id="tcp-firm-intro",
    )


def _methodology_rows() -> List[Any]:
    """Committed v1 methodology rows (subset of full Strategy Overview table)."""
    rows: List[Any] = []
    rows.append(html.Tr([html.Th("Methodology", colSpan=3, className="bg-light")]))
    rows.append(
        html.Tr(
            [
                html.Td("Trading Style"),
                html.Td(_mark(True, "Mean Reversion")),
                html.Td(_mark(False, "Breakout")),
            ]
        )
    )
    rows.append(
        html.Tr(
            [
                html.Td("Decision Making Style"),
                html.Td(_mark(True, "Systematic")),
                html.Td(_mark(False, "Discretionary")),
            ]
        )
    )
    rows.append(
        html.Tr(
            [
                html.Td("Execution Style"),
                html.Td(_mark(True, "Automated")),
                html.Td(_mark(True, "Manual")),
            ]
        )
    )
    rows.append(html.Tr([html.Td("", colSpan=3, style={"height": LEFT_TABLE_GAPS})]))
    rows.append(html.Tr([html.Th("Activity Profile", colSpan=3, className=HEADER_ROW_CLASS)]))
    rows.append(
        html.Tr(
            [
                html.Td("Trading Frequency"),
                html.Td(_mark(False, "Low (<500 Contracts)")),
                html.Td(_mark(True, "Medium (500-2000 Contracts)")),
            ]
        )
    )
    return rows


def build_strategy_overview() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Strategy Overview", className="mb-0"), className=HEADER_ROW_CLASS),
            dbc.CardBody(
                dbc.Table(
                    [
                        html.Thead(
                            html.Tr([html.Th("Strategy Description", colSpan=3, className=HEADER_ROW_CLASS)]),
                            className="bg-light",
                        ),
                        html.Tbody(
                            [
                                html.Tr(
                                    [
                                        html.Td(
                                            html.P(STRATEGY_DESCRIPTION),
                                            colSpan=3,
                                            style={"whiteSpace": "normal", "fontStyle": "italic"},
                                        )
                                    ]
                                ),
                                html.Tr([html.Td("", colSpan=3, style={"height": LEFT_TABLE_GAPS})]),
                                *_methodology_rows(),
                            ]
                        ),
                    ],
                    striped=False,
                    bordered=True,
                    hover=True,
                    size="sm",
                    className="table-responsive",
                )
            ),
        ],
        outline=True,
        className="mb-4",
        id="tcp-strategy-overview-card",
    )


def build_account_statistics() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Account Statistics", className="mb-0"), id="tcp-account-stats-header"),
            dbc.CardBody(
                dbc.Table(
                    [
                        html.Thead(
                            html.Tr(
                                [
                                    html.Th("Account Stats"),
                                    html.Th("Proprietary"),
                                    html.Th("Client"),
                                ]
                            )
                        ),
                        html.Tbody(
                            [
                                html.Tr([html.Td(label), html.Td(prop), html.Td(client)])
                                for label, prop, client in ACCOUNT_STATISTICS
                            ]
                        ),
                    ],
                    striped=False,
                    bordered=True,
                    hover=True,
                    size="sm",
                    className="mb-0 table-responsive",
                    id="tcp-account-stats-table",
                )
            ),
        ],
        outline=True,
        className="mb-4",
        id="tcp-account-stats-card",
    )


def build_inline_performance_disclaimers() -> List[Any]:
    return [
        dbc.Row(
            dbc.Col(html.P(HCDISCLAIMER_TEXT, className="text-muted small"), width=12),
            className="mb-4",
            id="tcp-hc-disclaimer-row",
        ),
        dbc.Row(
            dbc.Col(html.P(GENERAL_DISCLAIMER_TEXT, className="text-muted small"), width=12),
            className="mb-4",
            id="tcp-general-disclaimer-row",
        ),
    ]


def build_nav_footnotes() -> List[Any]:
    return [
        html.P(
            NAV_FOOTNOTE_PRIMARY,
            className="text-center small",
            style={"marginTop": "4rem"},
            id="tcp-nav-footnote-primary",
        ),
        html.P(
            NAV_FOOTNOTE_SECONDARY,
            className="text-center small",
            style={"marginBottom": "3rem"},
            id="tcp-nav-footnote-secondary",
        ),
    ]


def build_public_disclosure_panel() -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.Strong("Important Disclosure: ", className="text-dark"),
                    "This tear sheet is provided for informational purposes only and should not "
                    "be interpreted as an offer, solicitation, or recommendation to invest. "
                    "Performance information, if shown, may be unaudited and should be reviewed "
                    "together with the applicable offering documents, advisory agreement, and risk "
                    "disclosures. For more information about this strategy, please contact Hughes "
                    "and Company at ",
                    html.A(
                        "info@hughesandco.ltd",
                        href="mailto:info@hughesandco.ltd",
                        id="tcp-disclosure-email-link",
                    ),
                    " or 954 500 0500.",
                ],
                className="p-3 border rounded",
                style=DISCLOSURE_PANEL_STYLE,
                id="tcp-public-disclosure-panel",
            ),
            width=12,
        ),
        className="mb-4",
    )


def build_public_footer() -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            html.P(FOOTER_CONTACT, className="text-center small text-muted", id="tcp-public-footer"),
            width=12,
        ),
        className="mb-2",
        id="tcp-public-footer-row",
    )


def build_two_column_shell_row(
    left: Any,
    right: Optional[Any] = None,
    *,
    row_id: Optional[str] = None,
) -> dbc.Row:
    children = [dbc.Col(left, width=12, lg=6, className="mb-4 mb-lg-0")]
    if right is not None:
        children.append(dbc.Col(right, width=12, lg=6))
    return dbc.Row(children, className="mb-2 tcp-two-column-row", id=row_id)


def resolve_public_gate_styles(n_clicks: Optional[int]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Presentation-only gate reveal styles (not an admin authorization signal)."""
    if n_clicks and n_clicks > 0:
        return {"display": "none"}, {"display": "block"}
    return GATE_SCREEN_STYLE, {"display": "none"}


def build_public_gate_wrapper(main_children: List[Any]) -> html.Div:
    return html.Div(
        [
            dcc.Store(id="disclaimer-accepted", storage_type="session"),
            build_public_accept_gate(),
            html.Div(id="main-app", style={"display": "none"}, children=main_children),
        ],
        id="tcp-public-root",
    )
