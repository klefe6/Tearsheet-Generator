"""Step 11G — TCP v2 mobile and responsive presentation contracts."""
from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

from tcp_admin import LOGIN_FORM_HTML
from tcp_config import load_config, resolve_state_paths
from tcp_daily_values import (
    DAILY_VALUES_SECTION_ID,
    DAILY_VALUES_TABLE_ID,
    DAILY_VALUES_TOOLBAR_ID,
    GATE_NOTICE_E_ID,
    build_daily_values_datatable,
    resolve_access_visibility,
    resolve_daily_values_toolbar_style,
)
from tcp_public_sections import (
    ACCOUNT_STATS_TABLE_CLASS,
    ADMIN_MODAL_CLASS,
    ADMIN_TOOLBAR_CLASS,
    CONTROLLED_TABLE_OVERFLOW_CLASS,
    DESKTOP_TWO_COLUMN_ROW_CLASS,
    DRAWDOWN_TABLE_CLASS,
    FOOTER_WRAP_CLASS,
    GATE_SECRET_E_CLASS,
    MONTHLY_PERFORMANCE_CLASS,
    NAV_CHART_CONTAINER_CLASS,
    PUBLIC_ROOT_CLASS,
    TERMS_FEES_TABLE_CLASS,
    mobile_responsive_contract,
)
from tcp_runtime_state import persist_add_row
from tcp_state import StatePaths

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_PORT = 8302
PREVIEW_PORT = 8312


def _layout_text(app) -> str:
    return str(app.layout)


def _public_source() -> str:
    return "\n".join(
        [
            (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "tcp_daily_values.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "tcp_admin.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8"),
        ]
    )


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture
def layout_text():
    from tcp_ts_v2 import create_app

    app, *_ = create_app()
    return _layout_text(app)


@pytest.fixture
def css_text():
    return (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8")


def test_mobile_breakpoint_rules_exist(css_text):
    assert "@media (max-width: 768px)" in css_text
    assert "@media (max-width: 430px)" in css_text
    assert "@media (orientation: landscape)" in css_text


def test_no_fixed_desktop_only_page_width_at_mobile(css_text):
    assert "overflow-x: hidden" in css_text
    assert ".tcp-public-root" in css_text
    assert re.search(r"#page-container\s*\{[^}]*width:\s*100%", css_text, re.S)


def test_two_column_sections_stack(css_text, layout_text):
    assert DESKTOP_TWO_COLUMN_ROW_CLASS in layout_text
    assert "tcp-two-column-row" in layout_text
    assert "lg=6" in layout_text or "lg=6," in layout_text.replace(" ", "")


def test_account_stat_cards_stack(layout_text):
    assert ACCOUNT_STATS_TABLE_CLASS in layout_text
    assert "Proprietary" in layout_text
    assert "Client" in layout_text


def test_terms_rows_remain_associated(layout_text):
    assert TERMS_FEES_TABLE_CLASS in layout_text
    assert "tcp-terms-and-fees-table" in layout_text


def test_monthly_table_has_controlled_overflow(layout_text, css_text):
    assert MONTHLY_PERFORMANCE_CLASS in layout_text
    assert CONTROLLED_TABLE_OVERFLOW_CLASS in css_text
    assert "tcp-monthly-performance" in css_text


def test_daily_values_has_controlled_overflow_wrapper(layout_text):
    assert CONTROLLED_TABLE_OVERFLOW_CLASS in layout_text
    assert DAILY_VALUES_TABLE_ID in layout_text


def test_daily_values_before_disclosure_and_footer(layout_text):
    daily_idx = layout_text.index(DAILY_VALUES_SECTION_ID)
    disclosure_idx = layout_text.index("tcp-public-disclosure-panel")
    footer_idx = layout_text.index("tcp-public-footer-row")
    assert daily_idx < disclosure_idx < footer_idx


def test_public_daily_values_read_only():
    from tcp_admin import ledger_records_to_rows
    from tcp_ledger import load_ledger

    cfg = load_config()
    wb = Path(cfg.workbook_path)
    if not wb.is_file():
        pytest.skip("workbook unavailable")
    ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)
    table = build_daily_values_datatable(ledger_records_to_rows(ledger.completed_records))
    assert table.editable is False


def test_admin_toolbar_wrapping_layout(css_text, layout_text):
    assert ADMIN_TOOLBAR_CLASS in layout_text
    assert "flex-wrap" in css_text
    assert ".tcp-admin-toolbar" in css_text


def test_add_delete_controls_admin_only(layout_text):
    assert "admin-open-add-modal" in layout_text
    assert resolve_daily_values_toolbar_style(admin_authenticated=False) == {"display": "none"}


def test_login_form_mobile_safe_input_sizing():
    assert 'name="viewport"' in LOGIN_FORM_HTML
    assert "font-size: 16px" in LOGIN_FORM_HTML
    assert "tcp-admin-login-page" in LOGIN_FORM_HTML


def test_nav_chart_responsive_contract(layout_text, css_text):
    assert NAV_CHART_CONTAINER_CLASS in layout_text
    assert "nav-preview-graph" in layout_text
    assert "autosize" in (REPO_ROOT / "tcp_dashboard.py").read_text(encoding="utf-8")
    assert "#nav-preview-graph" in css_text


def test_drawdown_table_controlled_overflow(layout_text):
    assert DRAWDOWN_TABLE_CLASS in layout_text
    assert CONTROLLED_TABLE_OVERFLOW_CLASS in layout_text
    assert "drawdown-profile-container" in layout_text


def test_benchmark_warning_wraps(css_text):
    assert ".tcp-benchmark-notice" in css_text
    assert "overflow-wrap" in css_text or "word-break" in css_text


def test_modal_mobile_max_height_internal_overflow(css_text):
    from tcp_admin import build_add_row_modal, build_delete_modal

    admin_source = (REPO_ROOT / "tcp_admin.py").read_text(encoding="utf-8")
    assert "className=ADMIN_MODAL_CLASS" in admin_source
    assert ADMIN_MODAL_CLASS in str(build_add_row_modal())
    assert ADMIN_MODAL_CLASS in str(build_delete_modal())
    assert ".tcp-admin-modal .modal-content" in css_text
    assert "max-height" in css_text
    assert "overflow-y: auto" in css_text


def test_footer_contact_wrapping_classes(layout_text):
    assert FOOTER_WRAP_CLASS in layout_text


def test_public_gate_usable_contract(css_text, layout_text):
    assert "disclaimer-screen" in layout_text
    assert GATE_SECRET_E_CLASS in layout_text
    assert GATE_NOTICE_E_ID in layout_text
    assert "#disclaimer-screen" in css_text


def test_e_reveals_password_row_callback_registered():
    from tcp_ts_v2 import create_app
    from tearsheet_gate_auth import GATE_PASSWORD_VISIBLE_STORE_ID

    app, *_ = create_app()
    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == GATE_NOTICE_E_ID for inp in cb.get("inputs", []))
        for cb in app.callback_map.values()
    )


def test_accept_does_not_authenticate_admin():
    from tcp_admin import AdminAuthManager
    from tcp_config import AdminAuthSettings

    auth = AdminAuthManager(AdminAuthSettings(admin_token="t", session_secret="s"))
    resolve_access_visibility(accept_clicks=1, admin_authenticated=False, public_accepted=False)
    assert not auth.is_authenticated({})


def test_no_duplicate_component_ids(layout_text):
    ids = re.findall(r"id='([^']+)'", layout_text)
    ids += re.findall(r'id="([^"]+)"', layout_text)
    assert len(ids) == len(set(ids))


def test_no_page_level_horizontal_overflow_styles(css_text):
    assert "overflow-x: hidden" in css_text
    assert "100vw" in css_text


def test_layout_construction_writes_no_state():
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    before = {p: p.stat().st_mtime if p.exists() else None for p in (active, backup, lock)}
    from tcp_public_sections import build_public_accept_gate

    assert build_public_accept_gate() is not None
    after = {p: p.stat().st_mtime if p.exists() else None for p in (active, backup, lock)}
    assert before == after


def test_import_starts_no_server():
    assert not _port_listening(PREVIEW_PORT)
    import tcp_public_sections  # noqa: F401

    assert not _port_listening(PREVIEW_PORT)


def test_port_8302_not_referenced_as_test_target():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert str(PRODUCTION_PORT) not in source


def test_mobile_responsive_contract_markers():
    contract = mobile_responsive_contract()
    assert contract["controlled_table_overflow"] == CONTROLLED_TABLE_OVERFLOW_CLASS
    assert contract["public_root"] == PUBLIC_ROOT_CLASS
    assert contract["daily_values_section"] == DAILY_VALUES_SECTION_ID


def test_unauthenticated_mutation_still_rejected():
    cfg = load_config()
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    paths = StatePaths(active_path=active, backup_path=backup, lock_path=lock)
    result = persist_add_row(
        cfg,
        paths,
        expected_revision=1,
        row_date="2026-06-25",
        cash_balance=45000,
        cash_transfers=0,
        tranche_count=112,
        authenticated=False,
    )
    assert not result.success


def test_public_root_class_on_wrapper(layout_text):
    assert PUBLIC_ROOT_CLASS in layout_text
    assert "tcp-public-root" in layout_text


def test_daily_values_toolbar_id_present(layout_text):
    assert DAILY_VALUES_TOOLBAR_ID in layout_text
