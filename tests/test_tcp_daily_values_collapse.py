"""TCP public Daily Values collapse behavior."""
from __future__ import annotations

from layout_helpers import layout_text as render_layout_text

from datetime import date

from tcp_daily_values import (
    DAILY_VALUES_SECTION_ID,
    PUBLIC_DAILY_COLLAPSE_ID,
    PUBLIC_DAILY_TOGGLE_BTN_ID,
    PUBLIC_DAILY_TOGGLE_LABEL_SHOW,
    build_daily_values_section,
)
from tcp_ledger import LedgerMetadata, LedgerRecord
from tcp_ts_v2 import create_app


def test_daily_values_section_is_collapsed_by_default():
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
    section = build_daily_values_section(records, metadata, data_source="json")
    layout_text = str(section)
    assert PUBLIC_DAILY_COLLAPSE_ID in layout_text
    assert PUBLIC_DAILY_TOGGLE_BTN_ID in layout_text
    assert PUBLIC_DAILY_TOGGLE_LABEL_SHOW in layout_text
    assert "is_open=False" in layout_text


def test_layout_includes_daily_values_collapse_ids():
    app, *_ = create_app()
    layout_text = render_layout_text(app)
    assert DAILY_VALUES_SECTION_ID in layout_text
    assert PUBLIC_DAILY_COLLAPSE_ID in layout_text
    assert PUBLIC_DAILY_TOGGLE_BTN_ID in layout_text
