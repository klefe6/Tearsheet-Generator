"""
Shared tear sheet disclosure copy and panel styles.

Two disclosure tiers (wording/layout only):

  PROPRIETARY — tkp_ts.py (TKP), tcp_ts.py (TCP)
    No Hughes & Company LLC strategy-inquiry contact on gate or bottom panel.
    Program-not-available-for-participation wording.

  MANAGER — yq_ts.py, Gold_Maker_ts.py, Momentum Pacer/mp_ts.py (Algominds, port 8304),
            tsgen.py
    Proprietary-trading gate notice + Hughes & Company LLC Program/Manager contact.
"""
from dash import html

# Legal entity name — use in all user-facing tear sheet copy (not Windows folder paths).
HNC_LEGAL_NAME = "Hughes & Company LLC"

# Important Disclosure section — bottom panel styling
DISCLOSURE_PANEL_CLASS = "p-3 border rounded"
DISCLOSURE_PANEL_STYLE = {
    "backgroundColor": "#f8f9fa",
    "borderLeft": "4px solid #6c757d",
    "fontSize": "0.875rem",
}

# Accept gate — centered overlay when gate is visible
GATE_SCREEN_STYLE = {"padding": "4rem", "textAlign": "center"}

GATE_INNER_CARD_STYLE = {
    "backgroundColor": "#f8f9fa",
    "padding": "4rem",
    "borderRadius": "1rem",
    "width": "90vw",
    "maxWidth": "600px",
    "margin": "10vh auto",
    "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
}

# ---------------------------------------------------------------------------
# PROPRIETARY tier (TKP, TCP)
# ---------------------------------------------------------------------------

PROPRIETARY_GATE_ACCEPT_TEXT = (
    "By clicking “Accept,” you agree that the performance figures shown are strictly "
    "informational and do not amount to investment advice, a solicitation, or an offer "
    "to invest. This material is not intended to solicit funds."
)


def proprietary_participation_text(program_code: str) -> str:
    """Gate/bottom line — program not open to outside investors."""
    return (
        f"The {program_code} program is not currently available for investor participation."
    )


def proprietary_gate_children(program_code: str = "TKP"):
    """Accept gate — proprietary tier (no H&C contact)."""
    return [
        html.P(PROPRIETARY_GATE_ACCEPT_TEXT, className="lead mb-4"),
        html.P(
            proprietary_participation_text(program_code),
            className="text-muted mb-5",
        ),
    ]


def proprietary_bottom_disclosure_children(program_code: str = "TKP"):
    """Important Disclosure section — bottom panel (proprietary tier)."""
    return [
        html.Strong("Important Disclosure: ", className="text-dark"),
        "This tear sheet is provided for informational purposes only. "
        f"The {program_code} program is not currently available for investor participation. "
        "Performance information, if shown, is presented for informational and "
        "reporting purposes only and should not be interpreted as an offer, "
        "solicitation, or recommendation to invest.",
    ]


# Backward-compatible aliases (TKP)
TKP_GATE_ACCEPT_TEXT = PROPRIETARY_GATE_ACCEPT_TEXT
TKP_GATE_PARTICIPATION_TEXT = proprietary_participation_text("TKP")


def bottom_disclosure_tkp_children():
    return proprietary_bottom_disclosure_children("TKP")


# ---------------------------------------------------------------------------
# MANAGER tier (Y&Q, Gold Maker, Momentum Pacer / Algominds, Compare)
# ---------------------------------------------------------------------------

MANAGER_GATE_PROPRIETARY_MUTED = (
    "Past performance is not necessarily indicative of future results. "
    "The risk of loss in commodity trading can be substantial. "
    "This information does not constitute investment advice."
)


def hnc_program_manager_contact_children():
    """Accept gate disclosure contact line — Hughes & Company LLC (manager tier)."""
    return [
        "For more information about this Program and Manager, please contact "
        f"{HNC_LEGAL_NAME} at ",
        html.A("info@hughesandco.ltd", href="mailto:info@hughesandco.ltd"),
        " or 954-500-0500 *",
    ]


def gate_contact_children():
    """Accept gate disclosure contact line (manager tier)."""
    return hnc_program_manager_contact_children()


def manager_gate_proprietary_bold_text(program_name=None):
    """Bold proprietary notice on Accept gate (manager tier)."""
    if program_name:
        label = program_name.strip().upper()
        if not label.endswith("PROGRAM"):
            label = f"{label} PROGRAM"
        return (
            f"THE {label} IS A PROPRIETARY TRADING STRATEGY. "
            "THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS "
            "NOT A SOLICITATION TO INVEST. PAST PERFORMANCE IS NOT INDICATIVE "
            "OF FUTURE RESULTS."
        )
    return (
        "THIS PROGRAM IS A PROPRIETARY TRADING STRATEGY. "
        "THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS "
        "NOT A SOLICITATION TO INVEST. PAST PERFORMANCE IS NOT INDICATIVE "
        "OF FUTURE RESULTS."
    )


def manager_gate_notice_children(program_name=None):
    """
    Accept gate — Important Notice through contact line (manager tier).

    program_name: e.g. \"Momentum Pacer\" for Algominds Momentum Pacer (port 8304).
    """
    return [
        html.H2("Important Notice", className="mb-4"),
        html.Hr(),
        html.P(
            manager_gate_proprietary_bold_text(program_name),
            className="mb-2",
            style={"fontWeight": "bold"},
        ),
        html.P(MANAGER_GATE_PROPRIETARY_MUTED, className="text-muted mb-4"),
        html.P(gate_contact_children(), className="mb-4"),
    ]


def manager_bottom_disclosure_children():
    """Important Disclosure section — bottom panel (manager tier)."""
    return [
        html.Strong("Important Disclosure: ", className="text-dark"),
        "This tear sheet is provided for informational purposes only and should not "
        "be interpreted as an offer, solicitation, or recommendation to invest. "
        "Performance information, if shown, may be unaudited and should be reviewed "
        "together with the applicable offering documents, advisory agreement, and risk "
        "disclosures. ",
        *hnc_program_manager_contact_children(),
    ]


# Backward-compatible aliases (manager / former non-TKP)
NON_TKP_GATE_PROPRIETARY_MUTED = MANAGER_GATE_PROPRIETARY_MUTED


def non_tkp_gate_proprietary_bold_text(program_name=None):
    return manager_gate_proprietary_bold_text(program_name)


def non_tkp_gate_notice_children(program_name=None):
    return manager_gate_notice_children(program_name)


def bottom_disclosure_non_tkp_children():
    return manager_bottom_disclosure_children()
