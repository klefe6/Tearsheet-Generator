"""TCP v2 visual parity with TKP — shared gate design system, TKP-style header
status block, and TKP-pattern Daily Values table controls.

Presentation-only contract: none of these tests touch TCP calculations, data
values, persistence, or auth behavior.
"""
from __future__ import annotations

from layout_helpers import layout_text

from datetime import date
from pathlib import Path

from tearsheet_header import format_data_current_date_line

from tcp_ledger import LedgerMetadata, LedgerRecord

REPO_ROOT = Path(__file__).resolve().parent.parent


def _sample_daily_values_section_str() -> str:
    from tcp_daily_values import build_daily_values_section

    metadata = LedgerMetadata(
        source_filename="tcp_alex.xlsx",
        sheet_name="NAV",
        header_mapping={},
        total_candidate_rows=1,
        completed_row_count=1,
        first_completed_date=date(2026, 1, 20),
        latest_completed_date=date(2026, 1, 20),
        latest_completed_excel_row=2,
    )
    records = (
        LedgerRecord(
            excel_row_number=2,
            fields={"#": 1, "Date": date(2026, 1, 20), "nav-x1": 50000.0},
        ),
    )
    return str(build_daily_values_section(records, metadata, data_source="json"))


# ── Gate: same shared design system as TKP ───────────────────────────────────

def test_tcp_gate_uses_shared_sibling_gate_builder():
    from tcp_public_sections import build_public_accept_gate
    from tearsheet_gate_ui import (
        GATE_ACCEPT_BUTTON_CLASS,
        GATE_ACCEPT_BUTTON_LABEL,
        GATE_INNER_CARD_CLASS,
        GATE_SCREEN_ID,
        GATE_SECRET_E_CLASS,
        GATE_TITLE_HEADING_CLASS,
    )

    gate_str = str(build_public_accept_gate())
    assert GATE_SCREEN_ID in gate_str
    assert GATE_INNER_CARD_CLASS in gate_str
    assert GATE_TITLE_HEADING_CLASS in gate_str
    assert GATE_ACCEPT_BUTTON_CLASS in gate_str
    assert GATE_ACCEPT_BUTTON_LABEL in gate_str
    # Hidden admin reveal ("e" in Important Notic·e) preserved.
    assert "secret-notice-e" in gate_str
    assert GATE_SECRET_E_CLASS in gate_str


def test_tcp_gate_refresh_behavior_not_regressed():
    """Full refresh / Ctrl+Shift+R must always show the Important Notice gate
    again — stale browser ui-mode hints are ignored."""
    from tcp_daily_values import resolve_gate_bootstrap_state

    assert resolve_gate_bootstrap_state(ui_mode=None) == (None, True)
    assert resolve_gate_bootstrap_state(ui_mode="public") == (None, True)
    assert resolve_gate_bootstrap_state(ui_mode="admin") == (None, True)


# ── Header: TKP-style date/status block ──────────────────────────────────────

def test_tcp_header_status_block_matches_tkp_pattern():
    from tearsheet_header import build_header_date_label_children

    desktop, mobile = build_header_date_label_children("Data current to:", "June 24, 2026 close")
    for rendered in (str(desktop), str(mobile)):
        assert "tearsheet-header-date-label" in rendered
        assert "tearsheet-header-date-value" in rendered

    from tcp_public_sections import build_tcp_header

    header_str = str(build_tcp_header("", [], []))
    assert "tearsheet-header-date-block" in header_str
    assert "header-row" in header_str
    assert "data-current-label-mobile" in header_str


def test_tkp_header_uses_shared_tcp_layout():
    import tkp_ts

    layout_str = str(tkp_ts.serve_layout())
    assert "Data current to" in layout_str
    assert "tearsheet-header-date-block" in layout_str
    assert "data-current-label-desktop" in layout_str
    assert "data-current-label-mobile" in layout_str
    assert "Last Updated" not in layout_str


def test_agm_header_uses_shared_tcp_layout():
    import importlib.util
    from pathlib import Path

    mp_path = REPO_ROOT / "Momentum Pacer" / "mp_ts.py"
    spec = importlib.util.spec_from_file_location("mp_ts", mp_path)
    mp_ts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp_ts)

    layout_str = str(mp_ts.serve_layout())
    assert "Data current to" in layout_str
    assert "tearsheet-header-date-block" in layout_str
    assert "data-current-label-desktop" in layout_str
    assert "data-current-label-mobile" in layout_str
    assert "Last Updated" not in layout_str
    if mp_ts.daily_balances_df is not None and not mp_ts.daily_balances_df.empty:
        latest = mp_ts._agm_authoritative_latest_date()
        assert latest is not None
        assert format_data_current_date_line(latest) in layout_str


def test_format_data_current_date_line():
    from tearsheet_header import format_data_current_date_line

    assert format_data_current_date_line(date(2026, 6, 24)) == "June 24, 2026 close"
    assert format_data_current_date_line("July 06, 2026") == "July 06, 2026 close"
    assert format_data_current_date_line("July 06, 2026 close") == "July 06, 2026 close"


def test_shared_header_date_css_serves_tkp_and_tcp():
    css = (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    # TKP selectors untouched (TKP not degraded)...
    assert ".tkp-header-date-block" in css
    assert ".tkp-header-date-label" in css
    assert ".tkp-header-date-value" in css
    # ...and shared aliases exist for the sibling tearsheets.
    assert ".tearsheet-header-date-block" in css
    assert ".tearsheet-header-date-label" in css
    assert ".tearsheet-header-date-value" in css


# ── Daily Values: TKP Daily Returns control pattern ──────────────────────────

def test_tcp_daily_values_card_has_tkp_pattern_controls():
    from tcp_daily_values import (
        PUBLIC_DAILY_COLLAPSE_ID,
        PUBLIC_DAILY_EXPORT_BTN_ID,
        PUBLIC_DAILY_EXPORT_DOWNLOAD_ID,
        PUBLIC_DAILY_PAGE_SIZE_ID,
        PUBLIC_DAILY_TOGGLE_BTN_ID,
    )

    section_str = _sample_daily_values_section_str()
    # Show/Hide (collapsed by default).
    assert PUBLIC_DAILY_COLLAPSE_ID in section_str
    assert PUBLIC_DAILY_TOGGLE_BTN_ID in section_str
    assert "is_open=False" in section_str
    # View per page selector.
    assert PUBLIC_DAILY_PAGE_SIZE_ID in section_str
    assert "View per page" in section_str
    # Export Excel.
    assert PUBLIC_DAILY_EXPORT_BTN_ID in section_str
    assert PUBLIC_DAILY_EXPORT_DOWNLOAD_ID in section_str
    assert "Export Excel" in section_str
    # Admin toolbar (hidden by default) with Visible Columns + Add/Delete.
    assert "Visible Columns" in section_str
    assert "admin-column-selector" in section_str
    assert "Add Row" in section_str
    assert "Delete Last Row" in section_str
    assert "Delete Latest Row" not in section_str


def test_tcp_daily_values_admin_toolbar_hidden_without_admin_auth():
    from tcp_daily_values import (
        UI_MODE_ADMIN,
        UI_MODE_PUBLIC,
        resolve_daily_values_toolbar_style,
    )

    assert resolve_daily_values_toolbar_style(
        ui_mode=None, admin_authenticated=False
    ) == {"display": "none"}
    assert resolve_daily_values_toolbar_style(
        ui_mode=UI_MODE_PUBLIC, admin_authenticated=False
    ) == {"display": "none"}
    # An admin-mode hint without a real server-side session is not enough.
    assert resolve_daily_values_toolbar_style(
        ui_mode=UI_MODE_ADMIN, admin_authenticated=False
    ) == {"display": "none"}
    assert resolve_daily_values_toolbar_style(
        ui_mode=UI_MODE_ADMIN, admin_authenticated=True
    ) == {"display": "block"}


def test_tcp_page_size_and_export_callbacks_registered():
    import tcp_ts_v2
    from tcp_daily_values import (
        PUBLIC_DAILY_EXPORT_BTN_ID,
        PUBLIC_DAILY_PAGE_SIZE_ID,
    )

    all_inputs = str([cb.get("inputs") for cb in tcp_ts_v2.app.callback_map.values()])
    assert PUBLIC_DAILY_PAGE_SIZE_ID in all_inputs
    assert PUBLIC_DAILY_EXPORT_BTN_ID in all_inputs


def test_tcp_column_selector_not_duplicated():
    """The Visible Columns control moved into the Daily Values admin toolbar;
    the admin editor must not build a second component with the same id."""
    from tcp_admin import build_admin_editor_layout

    editor_str = str(
        build_admin_editor_layout(
            rows=[],
            completed_rows=0,
            latest_date=None,
            data_source="json",
        )
    )
    assert "admin-column-selector" not in editor_str

    import tcp_ts_v2

    layout_str = layout_text(tcp_ts_v2.app)
    assert layout_str.count("'admin-column-selector'") == 1


def test_tcp_export_config_filename_unchanged():
    from tcp_config import TCPConfig

    assert TCPConfig().export_filename == "tcp_daily_returns_export.xlsx"
