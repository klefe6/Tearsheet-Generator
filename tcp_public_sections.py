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
from tearsheet_gate_auth import GATE_PASSWORD_VISIBLE_STORE_ID, build_gate_password_row
from tearsheet_disclosure import TCP_GATE_ACCEPT_TEXT
from tearsheet_gate_ui import (
    GATE_SECRET_E_CLASS,
    GATE_TITLE_HEADING_CLASS,
    GATE_TITLE_INLINE_CLASS,
    GATE_TITLE_NORMALIZED,
    build_sibling_accept_gate,
    normalized_gate_title_text,
)
from tcp_drawdown import DRAWDOWN_FOOTNOTE

HNC_LEGAL_NAME = "Hughes & Company LLC"
TCP_PRODUCT_NAME = "The Crypto Program"

WHITE_BG = "#ffffff"
PRIMARY_COLOR = "#0D3562"
SECONDARY_COLOR = "#CCCCCC"
LEFT_TABLE_GAPS = "20px"
HEADER_ROW_CLASS = "bg-light"

# Step 11G mobile/responsive contract markers (presentation only).
PUBLIC_ROOT_CLASS = "tcp-public-root"
CONTROLLED_TABLE_OVERFLOW_CLASS = "tcp-table-scroll"
ADMIN_TOOLBAR_CLASS = "tcp-admin-toolbar"
ADMIN_MODAL_CLASS = "tcp-admin-modal"
LEGAL_NOTICE_CLASS = "tcp-legal-notice-block"
PUBLIC_SECTION_CLASS = "tcp-public-section"
POST_ACCOUNT_DISCLAIMERS_CLASS = "tcp-post-account-disclaimers"
PERFORMANCE_DRAWDOWN_COLUMN_CLASS = "tcp-performance-drawdown-column"
ACCOUNT_STATS_TABLE_CLASS = "tcp-account-stats-table"
TERMS_FEES_TABLE_CLASS = "tcp-terms-fees-table"
FOOTER_WRAP_CLASS = "tcp-public-footer-wrap"

# Step 11F desktop visual contract markers (presentation only).
PUBLIC_CARD_CLASS = "mb-4 tcp-public-card"
DESKTOP_TWO_COLUMN_ROW_CLASS = "mb-2 tcp-two-column-row"
MONTHLY_PERFORMANCE_CLASS = "table-responsive tcp-monthly-performance"
NAV_CHART_CONTAINER_CLASS = "tcp-nav-chart-container"
PREVIEW_BANNER_CLASS = "text-center fw-bold tcp-preview-banner"
MODE_ALERT_CLASS = "tcp-mode-alert"
DAILY_METRICS_TABLE_CLASS = "fixed-cols tcp-daily-metrics-table"
DRAWDOWN_TABLE_CLASS = "tcp-drawdown-table"
DRAWDOWN_SECTION_CLASS = "tcp-drawdown-section"
RUNTIME_DIAGNOSTICS_CARD_ID = "tcp-runtime-diagnostics-card"

GATE_SCREEN_STYLE: Dict[str, str] = {"padding": "4rem", "textAlign": "center"}
GATE_ACCEPT_TEXT = TCP_GATE_ACCEPT_TEXT

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

RIGHT_TABLE_GAPS = "30px"

TERMS_AND_FEES: Tuple[Tuple[str, str], ...] = (
    ("Investment Type", "Managed Account"),
    ("Fee Structure", "0% Annual / 20% Performance"),
    ("High Water Mark", "Yes"),
    ("Lockup Period", "None"),
    ("Liquidity", "Daily"),
    ("Notional Funding", "Yes"),
    ("Execution FCM", "StoneX Financial"),
)

INVESTOR_OTHER_NOTES = (
    "TCP allows for efficient, opportunistic deployments of capital in and out of the program in fixed "
    "nominal trading levels of $150,000 per tranche. The program will remain perpetually funded with permanent "
    "capital of the Introducing Broker in the form of a minimum of two tranches ($300,000 Nominal). The IB "
    "itself also has historically allocated more tranches, and closed tranches profitably, and plans on "
    "continuing in doing so, in what it considers opportunities for additional capital deployment based on "
    "drawdowns of the program itself, with expected recoveries. This capability is allowed for investors as "
    "well, with the announcement of any tranche opening or closure by/of the IB shared for complete disclosure "
    "and additional visibility for the benefit of all potential participants."
)

TRANSACTION_FEE_FOOTNOTE = (
    "* Give up fee is waived if account is traded at StoneX Financial."
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


def monthly_performance_cell_class(value: str) -> str:
    """Map monthly percentage display strings to presentation classes (no calculation)."""
    if value is None or str(value).strip() == "":
        return "tcp-monthly-cell-empty"
    try:
        numeric = float(str(value).replace("%", "").strip())
    except ValueError:
        return "tcp-monthly-cell-neutral"
    if numeric > 0:
        return "tcp-monthly-cell-positive"
    if numeric < 0:
        return "tcp-monthly-cell-negative"
    return "tcp-monthly-cell-neutral"


def benchmark_notice_class(status: str) -> str:
    """CSS class for benchmark ready/stale/unavailable notices."""
    mapping = {
        "ready": "tcp-benchmark-notice-ready",
        "stale": "tcp-benchmark-notice-stale",
        "unavailable": "tcp-benchmark-notice-unavailable",
    }
    return f"py-2 mb-2 small tcp-benchmark-notice {mapping.get(status, 'tcp-benchmark-notice-stale')}"


def mobile_responsive_contract() -> Dict[str, str]:
    """Stable mobile/responsive presentation markers for structural tests."""
    return {
        "public_root": PUBLIC_ROOT_CLASS,
        "controlled_table_overflow": CONTROLLED_TABLE_OVERFLOW_CLASS,
        "admin_toolbar": ADMIN_TOOLBAR_CLASS,
        "admin_modal": ADMIN_MODAL_CLASS,
        "gate_secret_e": GATE_SECRET_E_CLASS,
        "gate_title_heading": GATE_TITLE_HEADING_CLASS,
        "gate_title_inline": GATE_TITLE_INLINE_CLASS,
        "legal_notice": LEGAL_NOTICE_CLASS,
        "public_section": PUBLIC_SECTION_CLASS,
        "post_account_disclaimers": POST_ACCOUNT_DISCLAIMERS_CLASS,
        "account_stats_table": ACCOUNT_STATS_TABLE_CLASS,
        "terms_fees_table": TERMS_FEES_TABLE_CLASS,
        "footer_wrap": FOOTER_WRAP_CLASS,
        "monthly_performance": MONTHLY_PERFORMANCE_CLASS,
        "drawdown_table": DRAWDOWN_TABLE_CLASS,
        "drawdown_section": DRAWDOWN_SECTION_CLASS,
        "nav_chart_container": NAV_CHART_CONTAINER_CLASS,
        "two_column_row": DESKTOP_TWO_COLUMN_ROW_CLASS,
        "disclosure_panel": "tcp-public-disclosure-panel",
        "daily_values_section": "tcp-daily-values-section",
    }


def layout_overlap_contract() -> Dict[str, str]:
    """Stable layout-flow markers for overlap regression tests."""
    return {
        "gate_title_normalized": GATE_TITLE_NORMALIZED,
        "gate_secret_e_id": "secret-notice-e",
        "gate_secret_e": GATE_SECRET_E_CLASS,
        "gate_title_heading": GATE_TITLE_HEADING_CLASS,
        "performance_drawdown_column": PERFORMANCE_DRAWDOWN_COLUMN_CLASS,
        "drawdown_card": "tcp-drawdown-profile-card",
        "proprietary_notice_row": "tcp-hc-disclaimer-row",
        "general_disclaimer_row": "tcp-general-disclaimer-row",
        "post_account_disclaimers": POST_ACCOUNT_DISCLAIMERS_CLASS,
        "legal_notice": LEGAL_NOTICE_CLASS,
        "public_section": PUBLIC_SECTION_CLASS,
        "controlled_table_overflow": CONTROLLED_TABLE_OVERFLOW_CLASS,
        "daily_values_section": "tcp-daily-values-section",
        "disclosure_panel": "tcp-public-disclosure-panel",
        "footer_row": "tcp-public-footer-row",
        "runtime_diagnostics": RUNTIME_DIAGNOSTICS_CARD_ID,
    }


def desktop_visual_contract() -> Dict[str, str]:
    """Stable presentation contract markers for structural tests."""
    return {
        "page_container": "page-container",
        "header_row": "header-row",
        "two_column_row": DESKTOP_TWO_COLUMN_ROW_CLASS,
        "public_card": PUBLIC_CARD_CLASS,
        "monthly_performance": MONTHLY_PERFORMANCE_CLASS,
        "nav_chart_container": NAV_CHART_CONTAINER_CLASS,
        "preview_banner": PREVIEW_BANNER_CLASS,
        "daily_metrics_table": DAILY_METRICS_TABLE_CLASS,
        "drawdown_table": DRAWDOWN_TABLE_CLASS,
        "drawdown_section": DRAWDOWN_SECTION_CLASS,
        "benchmark_notice_prefix": "tcp-benchmark-notice",
        "disclosure_panel": "tcp-public-disclosure-panel",
        "footer_row": "tcp-public-footer-row",
        "runtime_diagnostics": RUNTIME_DIAGNOSTICS_CARD_ID,
    }


def required_copy_fragments() -> Dict[str, str]:
    """Normalized inventory of committed v1 copy fragments for provenance tests."""
    return {
        "product": TCP_PRODUCT_NAME,
        "firm": HNC_LEGAL_NAME,
        "strategy_heading": "Strategy Overview",
        "bitcoin": "Bitcoin",
        "ethereum": "Ethereum",
        "gate_title": "Important Notic",
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
    return build_sibling_accept_gate(
        "TCP",
        accept_text=GATE_ACCEPT_TEXT,
        title_id="tcp-public-gate-title",
        copy_lead_id="tcp-public-gate-copy",
        extra_children=[build_gate_password_row()],
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
                html.Div(
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
                        className="mb-0",
                    ),
                    className="table-responsive tcp-table-scroll",
                )
            ),
        ],
        outline=True,
        className=PUBLIC_CARD_CLASS,
        id="tcp-strategy-overview-card",
    )


def _blank_row(colspan: int = 3, *, gap: str = LEFT_TABLE_GAPS) -> html.Tr:
    return html.Tr([html.Td("", colSpan=colspan, style={"height": gap})])


def _checked_items(items: Sequence[Tuple[bool, str]]) -> List[Any]:
    return [html.Tr([html.Td(_mark(checked, label))]) for checked, label in items]


def _terms_and_fees_table() -> dbc.Table:
    return dbc.Table(
        [
            html.Thead(html.Tr([html.Th("Terms & Fees"), html.Th("Details")])),
            html.Tbody([html.Tr([html.Td(label), html.Td(value)]) for label, value in TERMS_AND_FEES]),
        ],
        striped=False,
        bordered=True,
        hover=True,
        size="sm",
        className=f"mb-3 table-responsive tcp-table-scroll {TERMS_FEES_TABLE_CLASS}",
        id="tcp-terms-and-fees-table",
    )


def _account_stats_table() -> dbc.Table:
    return dbc.Table(
        [
            html.Thead(
                html.Tr([html.Th("Account Stats"), html.Th("Proprietary"), html.Th("Client")])
            ),
            html.Tbody(
                [html.Tr([html.Td(label), html.Td(prop), html.Td(client)]) for label, prop, client in ACCOUNT_STATISTICS]
            ),
        ],
        striped=False,
        bordered=True,
        hover=True,
        size="sm",
        className=f"mb-3 table-responsive tcp-table-scroll {ACCOUNT_STATS_TABLE_CLASS}",
        id="tcp-account-stats-table",
    )


def build_terms_and_fees() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Terms & Fees", className="mb-0")),
            dbc.CardBody(_terms_and_fees_table()),
        ],
        outline=True,
        className=f"{PUBLIC_CARD_CLASS} d-none",
        id="tcp-terms-and-fees-card",
    )


def build_investor_information() -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Investor Information", className="mb-0"), id="tcp-investor-information-header"),
            dbc.CardBody(
                html.Div(
                    [
                        _terms_and_fees_table(),
                        _account_stats_table(),
                        html.P("Other Notes:", className="small fw-bold mb-1 mt-2", id="tcp-investor-other-notes-heading"),
                        html.P(
                            INVESTOR_OTHER_NOTES,
                            className="mt-2",
                            style={"fontSize": "0.9rem"},
                            id="tcp-investor-other-notes",
                        ),
                    ],
                    id="tcp-investor-information-body",
                )
            ),
        ],
        outline=True,
        className=PUBLIC_CARD_CLASS,
        id="tcp-investor-information-card",
    )


def build_trading_universe() -> dbc.Card:
    na_exchanges = [
        (True, "CME Group / MGX"),
        (False, "ICE US"),
        (False, "CFE"),
        (False, "LME"),
        (False, "NODAL"),
    ]
    europe_exchanges = [
        (False, "ICE UK / Financial"),
        (False, "Eurex"),
        (False, "Euronext"),
        (False, "DGCX"),
    ]
    asia_exchanges = [
        (False, "SGX"),
        (False, "HKFE"),
        (False, "OSE / TOCOM"),
        (False, "SAFEX"),
        (False, "Bursa Malaysia"),
    ]
    financial_products = [
        (False, "Equity Indices"),
        (False, "Volatility Indices"),
        (False, "Interest Rates"),
        (False, "Currencies"),
    ]
    ag_products = [
        (False, "Grains / Oilseeds"),
        (False, "Softs"),
        (False, "Dairy"),
        (False, "Meats / Livestock"),
    ]
    other_products = [
        (False, "Metals"),
        (False, "Renewable Fuels"),
        (True, "Cryptocurrencies"),
    ]
    ratio_rows = [
        (True, "0-10 %", "94.8 %"),
        (True, "10-25 %", "5.2 %"),
        (False, "25-50 %", "-- %"),
        (False, "50 %+", "-- %"),
    ]
    fee_rows = [
        ("Commission", "$0.20"),
        ("Exchange Fee", "$0.10"),
        ("NFA Fee", "$0.00"),
        ("Give Up Fee", "$0.00"),
    ]

    ratio_grid_children: List[Any] = [
        html.Div("Ranges", className="ratio-header"),
        html.Div("% time in range (daily)", className="ratio-header"),
    ]
    for checked, range_label, pct in ratio_rows:
        color = PRIMARY_COLOR if checked else SECONDARY_COLOR
        symbol = "✓" if checked else "✗"
        ratio_grid_children.extend(
            [
                html.Div(html.Span(f"{symbol} {range_label}", style={"color": color, "marginRight": "0.5rem"}), className="ratio-cell"),
                html.Div(html.Span(pct, style={"color": color, "marginRight": "0.5rem"}), className="ratio-cell"),
            ]
        )

    tbody_rows: List[Any] = [
        html.Tr([html.Th("Product Exchanges", colSpan=3, className=HEADER_ROW_CLASS)]),
        html.Tr([html.Td("North America"), html.Td("Europe"), html.Td("Asia/Pacific")]),
        html.Tr(
            [
                html.Td(_checked_items(na_exchanges)),
                html.Td(_checked_items(europe_exchanges)),
                html.Td(_checked_items(asia_exchanges)),
            ]
        ),
        _blank_row(gap=RIGHT_TABLE_GAPS),
        html.Tr([html.Th("Futures Products Traded", colSpan=3, className=HEADER_ROW_CLASS)]),
        html.Tr([html.Td("Financial Instruments"), html.Td("Agricultural Commodities"), html.Td("Other Asset Classes")]),
        html.Tr(
            [
                html.Td(_checked_items(financial_products)),
                html.Td(_checked_items(ag_products)),
                html.Td(_checked_items(other_products)),
            ]
        ),
        _blank_row(gap=RIGHT_TABLE_GAPS),
        html.Tr([html.Th("Risk Management", colSpan=3, className=HEADER_ROW_CLASS)]),
        html.Tr([html.Td("Average Margin Usage"), html.Td("5.00 %"), html.Td()]),
        html.Tr(
            [
                html.Td(
                    [
                        html.Div("Exchange Margin Ratios"),
                        html.Small(
                            "This is not cost-bearing, but is a measure of the exchange-required minimum funds "
                            "to be in the account versus the Nominal Trade Size (150 k)",
                            style={
                                "fontSize": "0.75rem",
                                "color": "#6c757d",
                                "marginTop": "0.25rem",
                                "display": "block",
                            },
                        ),
                    ]
                ),
                html.Td(html.Div(ratio_grid_children, className="ratio-grid"), colSpan=2),
            ]
        ),
        html.Tr(
            [
                html.Td("Risk Controls", id="risk-controls"),
                html.Td(
                    [
                        html.Tr([html.Td(_mark(False, "Stop Losses"), id="stop-losses")]),
                        html.Tr([html.Td(_mark(True, "VaR Considerations"), id="var-considerations")]),
                    ]
                ),
                html.Td(
                    [
                        html.Tr([html.Td(_mark(False, "Position Reductions"), id="position-reductions")]),
                        html.Tr([html.Td(_mark(True, "Position Offsets (Hedges)"), id="position-hedges")]),
                    ]
                ),
            ]
        ),
        dbc.Tooltip("Mechanisms to limit potential losses in volatile markets.", target="risk-controls", placement="top"),
        dbc.Tooltip(
            "Orders that close a position at a predefined price to cap losses.",
            target="stop-losses",
            placement="top",
        ),
        dbc.Tooltip(
            "Statistical estimate of potential loss over a given period at a chosen confidence level.",
            target="var-considerations",
            placement="top",
        ),
        dbc.Tooltip(
            "Gradual decrease in position size to reduce exposure as risk increases.",
            target="position-reductions",
            placement="top",
        ),
        dbc.Tooltip(
            "Taking opposite or correlated positions to hedge against adverse moves.",
            target="position-hedges",
            placement="top",
        ),
        _blank_row(gap=RIGHT_TABLE_GAPS),
        html.Tr([html.Th("Transaction Fees (per Contract)", colSpan=3, className=HEADER_ROW_CLASS)]),
        *[html.Tr([html.Td(label), html.Td(value), html.Td()]) for label, value in fee_rows],
        html.Tr([html.Td(html.Strong("Total All-In Fees")), html.Td(html.Strong("$0.30")), html.Td()]),
        html.Tr(
            [
                html.Td(
                    html.Small(TRANSACTION_FEE_FOOTNOTE, style={"fontStyle": "italic", "color": "#6c757d"}),
                    colSpan=3,
                )
            ]
        ),
    ]

    return dbc.Card(
        [
            dbc.CardHeader(
                html.H6("Trading Universe & Risk Profile", className="mb-0"),
                className=HEADER_ROW_CLASS,
            ),
            dbc.CardBody(
                html.Div(
                    dbc.Table(
                        [html.Tbody(tbody_rows)],
                        striped=False,
                        bordered=True,
                        hover=True,
                        size="sm",
                        className="mb-0",
                        id="tcp-trading-universe-table",
                    ),
                    className="table-responsive tcp-table-scroll",
                )
            ),
        ],
        outline=True,
        className=PUBLIC_CARD_CLASS,
        id="tcp-trading-universe-card",
    )


def build_drawdown_profile_card(
    table_children: Any,
    *,
    benchmark_notice: Optional[Any] = None,
) -> dbc.Card:
    body_children: List[Any] = []
    if benchmark_notice is not None:
        body_children.append(html.Div(benchmark_notice, id="tcp-benchmark-notice"))
    else:
        body_children.append(html.Div(id="tcp-benchmark-notice"))
    body_children.append(
        html.Div(table_children, id="drawdown-profile-container", className="table-responsive tcp-table-scroll"),
    )
    return dbc.Card(
        [
            dbc.CardHeader(html.H6("Maximum Drawdown Profile", className="mb-0"), className=HEADER_ROW_CLASS),
            dbc.CardBody(body_children),
            dbc.CardFooter(
                html.Small(DRAWDOWN_FOOTNOTE, className="text-muted fst-italic", id="tcp-drawdown-footnote"),
            ),
        ],
        outline=True,
        className=PUBLIC_CARD_CLASS,
        id="tcp-drawdown-profile-card",
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
                    className=f"mb-0 table-responsive tcp-table-scroll {ACCOUNT_STATS_TABLE_CLASS}",
                    id="tcp-account-stats-table",
                )
            ),
        ],
        outline=True,
        className=PUBLIC_CARD_CLASS,
        id="tcp-account-stats-card",
    )


def build_inline_performance_disclaimers() -> List[Any]:
    return [
        dbc.Row(
            dbc.Col(
                html.P(HCDISCLAIMER_TEXT, className=f"text-muted small {LEGAL_NOTICE_CLASS}"),
                width=12,
            ),
            className=f"mb-4 {PUBLIC_SECTION_CLASS}",
            id="tcp-hc-disclaimer-row",
        ),
        dbc.Row(
            dbc.Col(
                html.P(GENERAL_DISCLAIMER_TEXT, className=f"text-muted small {LEGAL_NOTICE_CLASS}"),
                width=12,
            ),
            className=f"mb-4 {PUBLIC_SECTION_CLASS}",
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
                className=f"p-3 border rounded {LEGAL_NOTICE_CLASS}",
                style=DISCLOSURE_PANEL_STYLE,
                id="tcp-public-disclosure-panel",
            ),
            width=12,
        ),
        className=f"mb-4 {PUBLIC_SECTION_CLASS}",
    )


def build_public_footer() -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            html.P(FOOTER_CONTACT, className=f"text-center small text-muted {FOOTER_WRAP_CLASS}", id="tcp-public-footer"),
            width=12,
        ),
        className=f"mb-2 {PUBLIC_SECTION_CLASS}",
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
    return dbc.Row(children, className=DESKTOP_TWO_COLUMN_ROW_CLASS, id=row_id)


def resolve_public_gate_styles(n_clicks: Optional[int]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Presentation-only gate reveal styles (not an admin authorization signal)."""
    if n_clicks and n_clicks > 0:
        return {"display": "none"}, {"display": "block"}
    return GATE_SCREEN_STYLE, {"display": "none"}


def build_public_gate_wrapper(main_children: List[Any]) -> html.Div:
    from tcp_daily_values import PUBLIC_GATE_ACCEPTED_STORE_ID, TCP_UI_MODE_STORE_ID

    return html.Div(
        [
            dcc.Store(id="disclaimer-accepted", storage_type="memory"),
            dcc.Store(id=PUBLIC_GATE_ACCEPTED_STORE_ID, storage_type="memory", data=False),
            dcc.Store(id=TCP_UI_MODE_STORE_ID, storage_type="memory", data=None),
            dcc.Store(id=GATE_PASSWORD_VISIBLE_STORE_ID, storage_type="memory", data=False),
            build_public_accept_gate(),
            html.Div(id="main-app", style={"display": "none"}, children=main_children),
        ],
        id="tcp-public-root",
        className=PUBLIC_ROOT_CLASS,
    )
