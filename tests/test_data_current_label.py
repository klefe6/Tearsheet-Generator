"""Data-current-to header label must track the authoritative display dataset."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from tcp_dashboard import build_tcp_current_data_labels, canonical_nav_records_from_ledger
from tearsheet_header import (
    HEADER_DATA_UNAVAILABLE_LABEL,
    build_header_date_label_children_from_date,
    format_data_current_date_line,
    resolve_latest_display_date_from_dataframe,
    resolve_latest_display_date_from_rows,
)


def _tcp_canonical_through(day: int) -> list[dict]:
    return [
        {"Date": f"2026-07-{d:02d}", "NAV": 47000.0 + d}
        for d in range(1, day + 1)
    ]


def test_tcp_label_from_latest_canonical_nav():
    canonical = _tcp_canonical_through(14)
    labels = build_tcp_current_data_labels(canonical)
    assert labels.date_line == "July 14, 2026 close"
    assert labels.source_date == date(2026, 7, 14)


def test_tcp_label_matches_healthz_latest_date_field():
    canonical = _tcp_canonical_through(14)
    labels = build_tcp_current_data_labels(canonical)
    assert labels.source_date.isoformat() == "2026-07-14"


def test_tcp_label_advances_after_simulated_ingest_append():
    before = build_tcp_current_data_labels(_tcp_canonical_through(14))
    after = build_tcp_current_data_labels(_tcp_canonical_through(15))
    assert before.date_line == "July 14, 2026 close"
    assert after.date_line == "July 15, 2026 close"


def test_agm_label_uses_merged_accounting_table():
    csv_only = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-01", "2026-07-06"]),
            "actual_nlv": [44000.0, 44100.0],
            "client_net_value": [43000.0, 43100.0],
        }
    )
    merged = pd.concat(
        [
            csv_only,
            pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2026-07-14"]),
                    "actual_nlv": [44709.5],
                    "client_net_value": [44000.0],
                }
            ),
        ],
        ignore_index=True,
    )
    csv_latest = resolve_latest_display_date_from_dataframe(csv_only)
    merged_latest = resolve_latest_display_date_from_dataframe(merged)
    assert csv_latest == date(2026, 7, 6)
    assert merged_latest == date(2026, 7, 14)
    _, mobile = build_header_date_label_children_from_date(merged_latest)
    assert "July 14, 2026 close" in mobile[1].children  # type: ignore[index]


def test_tkp_label_from_secret_rows():
    rows = [
        {"Date": "2026-07-01", "NAV": 100000},
        {"Date": "2026-07-14", "NAV": 105000},
    ]
    latest = resolve_latest_display_date_from_rows(rows)
    assert format_data_current_date_line(latest) == "July 14, 2026 close"


def test_empty_dataset_shows_unavailable():
    desktop, mobile = build_header_date_label_children_from_date(None)
    assert desktop[0].children == HEADER_DATA_UNAVAILABLE_LABEL  # type: ignore[index]
    assert mobile[0].children == HEADER_DATA_UNAVAILABLE_LABEL  # type: ignore[index]
    assert resolve_latest_display_date_from_rows([]) is None
    assert resolve_latest_display_date_from_dataframe(pd.DataFrame()) is None


def test_canonical_nav_records_from_ledger_aligns_with_label_helper():
    records = [
        {"Date": "2026-07-13", "nav-x1": 47900.0},
        {"Date": "2026-07-14", "nav-x1": 47993.334},
    ]
    canonical = canonical_nav_records_from_ledger(records)
    labels = build_tcp_current_data_labels(canonical)
    assert labels.date_line == "July 14, 2026 close"
