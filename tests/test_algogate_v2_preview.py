"""Algominds v2 preview Important Notice gate tests."""
from __future__ import annotations

from pathlib import Path

import algominds_v2_preview_app as preview_app
from tearsheet_disclosure import proprietary_participation_text
from tearsheet_gate_ui import (
    GATE_INNER_CARD_CLASS,
    TEARSHEET_GATE_STATIC_CSS,
    render_static_gate_markup,
)


def test_algogate_static_markup_has_sibling_classes(tmp_path: Path) -> None:
    markup = render_static_gate_markup("Momentum Pacer")
    assert GATE_INNER_CARD_CLASS in markup
    assert proprietary_participation_text("Momentum Pacer") in markup
    assert 'id="main-app"' not in markup


def test_admin_page_includes_gate_and_hidden_main(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert 'id="disclaimer-screen"' in html_text
    assert 'id="main-app"' in html_text
    assert "tearsheet-gate-hidden" in html_text
    assert TEARSHEET_GATE_STATIC_CSS.strip()[:40] in html_text
    assert "Algominds v2 Preview" not in html_text


def test_account_page_includes_gate(tmp_path: Path) -> None:
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    assert 'id="disclaimer-screen"' in html_text
    assert 'id="main-app"' in html_text
    assert proprietary_participation_text("Momentum Pacer") in html_text
