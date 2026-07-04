"""TCP v2 layout overlap and gate-title alignment regression tests."""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tcp_admin import AdminAuthManager, ledger_records_to_rows
from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_ledger import load_ledger
from tcp_daily_values import (
    DAILY_VALUES_SECTION_ID,
    DAILY_VALUES_TABLE_ID,
    GATE_NOTICE_E_ID,
    PUBLIC_GATE_ACCEPTED_STORE_ID,
    UI_MODE_PUBLIC,
    build_daily_values_datatable,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
)
from tcp_public_sections import (
    CONTROLLED_TABLE_OVERFLOW_CLASS,
    GATE_SECRET_E_CLASS,
    GATE_TITLE_INLINE_CLASS,
    GATE_TITLE_NORMALIZED,
    HCDISCLAIMER_TEXT,
    LEGAL_NOTICE_CLASS,
    POST_ACCOUNT_DISCLAIMERS_CLASS,
    PUBLIC_SECTION_CLASS,
    RUNTIME_DIAGNOSTICS_CARD_ID,
    build_inline_performance_disclaimers,
    build_public_accept_gate,
    layout_overlap_contract,
    normalized_gate_title_text,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_PORT = 8312


def _layout_text(app) -> str:
    return str(app.layout)


def _css_text() -> str:
    return (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def layout_text():
    from tcp_ts_v2 import create_app

    app, *_ = create_app()
    return _layout_text(app)


@pytest.fixture(scope="session")
def ledger():
    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("TCP workbook not available")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


@pytest.fixture
def css_text():
    return _css_text()


def test_normalized_gate_title_text_equals_important_notice():
    assert normalized_gate_title_text() == GATE_TITLE_NORMALIZED == "Important Notice"


def test_exactly_one_clickable_final_e_control(layout_text):
    assert layout_text.count(f"id='{GATE_NOTICE_E_ID}'") == 1
    assert layout_text.count('id="secret-notice-e"') == 0


def test_clickable_e_inside_gate_title_structure():
    gate = build_public_accept_gate()
    h2 = gate.children.children[0]
    assert h2.id == "tcp-public-gate-title"
    child_ids = [getattr(child, "id", None) for child in h2.children]
    assert child_ids.count(GATE_NOTICE_E_ID) == 1


def test_gate_e_uses_inline_baseline_class(layout_text, css_text):
    assert GATE_SECRET_E_CLASS in layout_text
    assert GATE_TITLE_INLINE_CLASS in layout_text
    assert "display: inline" in css_text
    assert ".tcp-gate-secret-e" in css_text
    assert "vertical-align: baseline" in css_text


def test_gate_e_does_not_use_visible_absolute_positioning(css_text):
    block = css_text.split(".tcp-gate-secret-e {", 1)[1].split("}", 1)[0]
    assert "position: absolute" not in block
    assert "position: fixed" not in block


def test_gate_e_reveals_password_row_callback():
    from tcp_ts_v2 import create_app
    from tearsheet_gate_auth import GATE_PASSWORD_VISIBLE_STORE_ID

    app, *_ = create_app()
    assert any(
        inp.get("id") == GATE_NOTICE_E_ID
        for cb in app.callback_map.values()
        for inp in cb.get("inputs", [])
    )
    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == GATE_NOTICE_E_ID for inp in cb.get("inputs", []))
        for cb in app.callback_map.values()
    )


def test_accept_remains_public_only():
    resolve_access_visibility(ui_mode=UI_MODE_PUBLIC)
    auth = AdminAuthManager(AdminAuthSettings(admin_token="t", session_secret="s"))
    assert not auth.is_authenticated({})


def test_legal_notices_use_normal_flow_classes(layout_text):
    assert LEGAL_NOTICE_CLASS in layout_text
    assert POST_ACCOUNT_DISCLAIMERS_CLASS in layout_text
    assert "tcp-hc-disclaimer-row" in layout_text
    assert "tcp-general-disclaimer-row" in layout_text


def test_notice_blocks_have_wrapping_contract(css_text):
    block = css_text.split(".tcp-legal-notice-block {", 1)[1].split("}", 1)[0]
    assert "max-width: 100%" in block
    assert "overflow-wrap" in block
    assert "position: static" in block


def test_legal_blocks_have_no_negative_margin_class(css_text):
    assert "margin: -" not in css_text.split(".tcp-legal-notice-block {", 1)[1].split("}", 1)[0]


def test_proprietary_notices_follow_performance_row(layout_text):
    drawdown = layout_text.find("tcp-drawdown-profile-card")
    proprietary = layout_text.find("tcp-hc-disclaimer-row")
    general = layout_text.find("tcp-general-disclaimer-row")
    assert drawdown != -1 and proprietary != -1 and general != -1
    assert drawdown < proprietary < general


def test_daily_values_after_complete_drawdown_section(layout_text):
    drawdown = layout_text.find("tcp-drawdown-footnote")
    daily = layout_text.find(DAILY_VALUES_SECTION_ID)
    disclaimers = layout_text.find("tcp-post-account-disclaimers")
    assert drawdown != -1 and daily != -1 and disclaimers != -1
    assert disclaimers < daily
    assert drawdown < disclaimers


def test_disclosure_footer_after_daily_values(layout_text):
    daily = layout_text.find(DAILY_VALUES_SECTION_ID)
    disclosure = layout_text.find("tcp-public-disclosure-panel")
    footer = layout_text.find("tcp-public-footer-row")
    runtime = layout_text.find(RUNTIME_DIAGNOSTICS_CARD_ID)
    assert daily < disclosure < footer < runtime


def test_runtime_diagnostics_after_public_footer(layout_text):
    footer = layout_text.find("tcp-public-footer-row")
    runtime = layout_text.find(RUNTIME_DIAGNOSTICS_CARD_ID)
    assert footer != -1 and runtime != -1
    assert footer < runtime


def test_major_tables_use_contained_overflow_wrappers(layout_text):
    for marker in (
        "drawdown-profile-container",
        "monthly-calendar-container",
        "tcp-terms-and-fees-table",
        "tcp-account-stats-table",
        DAILY_VALUES_TABLE_ID,
    ):
        assert marker in layout_text
    assert CONTROLLED_TABLE_OVERFLOW_CLASS in layout_text
    assert layout_text.count(CONTROLLED_TABLE_OVERFLOW_CLASS) >= 4


def test_no_duplicate_daily_values_component(layout_text):
    assert layout_text.count(DAILY_VALUES_TABLE_ID) == 1
    assert layout_text.count(DAILY_VALUES_SECTION_ID) == 1


def test_public_daily_values_remains_read_only(ledger):
    rows = ledger_records_to_rows(ledger.completed_records)
    table = build_daily_values_datatable(rows)
    assert table.editable is False


def test_admin_toolbar_remains_session_protected():
    assert resolve_daily_values_toolbar_style(ui_mode=None, admin_authenticated=False) == {"display": "none"}
    auth = AdminAuthManager(AdminAuthSettings(admin_token="t", session_secret="s"))
    fake = {PUBLIC_GATE_ACCEPTED_STORE_ID: True, "disclaimer-accepted": True}
    assert not auth.is_authenticated(fake)


def test_layout_construction_writes_no_state():
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    before = {p: p.exists() for p in (active, backup, lock)}
    assert build_public_accept_gate() is not None
    assert build_inline_performance_disclaimers()
    after = {p: p.exists() for p in (active, backup, lock)}
    assert before == after


def test_import_starts_no_server():
    assert not _port_listening(PREVIEW_PORT)
    import tcp_public_sections  # noqa: F401

    assert not _port_listening(PREVIEW_PORT)


def test_layout_overlap_contract_markers():
    contract = layout_overlap_contract()
    assert contract["gate_title_normalized"] == "Important Notice"
    assert contract["gate_secret_e_id"] == GATE_NOTICE_E_ID
    assert contract["legal_notice"] == LEGAL_NOTICE_CLASS
    assert contract["public_section"] == PUBLIC_SECTION_CLASS


def test_gate_title_prefix_present_in_dom(layout_text):
    assert "Important Notic" in layout_text
    assert HCDISCLAIMER_TEXT[:40] in layout_text


def test_public_sections_use_section_gap_class(layout_text):
    assert PUBLIC_SECTION_CLASS in layout_text
    assert layout_text.count(PUBLIC_SECTION_CLASS) >= 4
