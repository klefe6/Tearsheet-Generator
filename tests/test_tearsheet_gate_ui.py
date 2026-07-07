"""Shared Important Notice gate UI tests for TCP, TKP, and Algominds preview."""
from __future__ import annotations

from pathlib import Path

from tcp_public_sections import GATE_ACCEPT_TEXT, build_public_accept_gate
from tearsheet_disclosure import proprietary_participation_text
from tearsheet_gate_ui import (
    GATE_ACCEPT_BUTTON_LABEL,
    GATE_COPY_LEAD_CLASS,
    GATE_COPY_MUTED_CLASS,
    GATE_INNER_CARD_CLASS,
    GATE_NOTICE_E_ID,
    GATE_SECRET_E_CLASS,
    GATE_TITLE_HEADING_CLASS,
    build_sibling_accept_gate,
    normalized_gate_title_text,
    render_static_gate_markup,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_normalized_gate_title():
    assert normalized_gate_title_text() == "Important Notice"


def test_tcp_gate_uses_shared_structure():
    gate = build_public_accept_gate()
    layout = str(gate)
    assert "disclaimer-screen" in layout
    assert GATE_INNER_CARD_CLASS in layout
    assert GATE_TITLE_HEADING_CLASS in layout
    assert GATE_SECRET_E_CLASS in layout
    assert GATE_COPY_LEAD_CLASS in layout
    assert GATE_COPY_MUTED_CLASS in layout
    assert GATE_ACCEPT_BUTTON_LABEL in layout
    assert GATE_ACCEPT_TEXT in layout
    assert proprietary_participation_text("TCP") in layout


def test_tkp_gate_uses_shared_structure():
    gate = build_sibling_accept_gate("TKP")
    layout = str(gate)
    assert proprietary_participation_text("TKP") in layout
    assert GATE_INNER_CARD_CLASS in layout
    assert f"id='{GATE_NOTICE_E_ID}'" in layout or f'id="{GATE_NOTICE_E_ID}"' in layout


def test_tcp_gate_preserves_hidden_admin_trigger():
    gate = build_public_accept_gate()
    h2 = gate.children.children[0]
    child_ids = [getattr(child, "id", None) for child in h2.children]
    assert child_ids.count(GATE_NOTICE_E_ID) == 1


def test_static_algominds_gate_markup():
    markup = render_static_gate_markup("Momentum Pacer")
    assert 'id="disclaimer-screen"' in markup
    assert GATE_INNER_CARD_CLASS in markup
    assert "Important Notice" in markup
    assert proprietary_participation_text("Momentum Pacer") in markup
    assert GATE_ACCEPT_BUTTON_LABEL in markup


def test_shared_gate_css_present_in_assets():
    css = (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    assert "#disclaimer-screen" in css
    assert ".tearsheet-gate-title" in css
    assert ".tearsheet-gate-copy-lead" in css
    assert ".tearsheet-gate-accept-btn" in css
    assert "line-height: 1.55" in css


def test_tkp_layout_renders_tkp_participation_line():
    import tkp_ts

    layout = str(tkp_ts.disclaimer_screen)
    assert proprietary_participation_text("TKP") in layout
