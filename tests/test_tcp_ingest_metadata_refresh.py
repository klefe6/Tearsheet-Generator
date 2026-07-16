"""TCP public metadata must track authoritative JSON state without restart."""
from __future__ import annotations

from datetime import date

from tcp_dashboard import build_tcp_current_data_labels
from tcp_daily_values import build_daily_values_summary


def test_summary_and_label_agree_on_july_15():
    canonical = [
        {"Date": "2026-07-14", "NAV": 47993.334},
        {"Date": "2026-07-15", "NAV": 50007.20},
    ]
    labels = build_tcp_current_data_labels(canonical)
    summary = build_daily_values_summary(
        completed_rows=127,
        latest_date=date(2026, 7, 15),
        data_source="json",
    )
    assert labels.date_line == "July 15, 2026 close"
    summary_text = str(summary.children)
    assert "127" in summary_text
    assert "July 15, 2026" in summary_text


def test_revision_change_would_update_label_from_stale_july_14():
    stale = build_tcp_current_data_labels(
        [{"Date": "2026-07-14", "NAV": 47993.334}]
    )
    fresh = build_tcp_current_data_labels(
        [
            {"Date": "2026-07-14", "NAV": 47993.334},
            {"Date": "2026-07-15", "NAV": 50007.20},
        ]
    )
    assert stale.date_line == "July 14, 2026 close"
    assert fresh.date_line == "July 15, 2026 close"
