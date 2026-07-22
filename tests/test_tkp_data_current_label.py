"""TKP 'Data current to' label must track authoritative persisted secret rows."""
from __future__ import annotations

from tearsheet_header import HEADER_DATA_CURRENT_LABEL, format_data_current_date_line


def _row(d: str, stonex: str, *, nav: str = "", plus500: str = "") -> dict:
    return {
        "Date": d,
        "NAV": nav,
        "Plus500": plus500,
        "StoneX": stonex,
    }


def _label_date_line(secret_rows) -> str:
    import tkp_ts

    latest = tkp_ts._latest_authoritative_tkp_date_from_rows(secret_rows)
    return format_data_current_date_line(latest)


def test_authoritative_latest_date_july_15_label():
    rows = [
        _row("2026-07-14", "$82,000.00", nav="$192,000.00"),
        _row("2026-07-15", "$82,955.48", plus500="$85,330.46", nav="$192,969.87"),
    ]
    assert _label_date_line(rows) == "July 15, 2026 close"

    import tkp_ts

    layout = str(tkp_ts.serve_layout(records=rows))
    assert HEADER_DATA_CURRENT_LABEL in layout
    assert "July 15, 2026 close" in layout


def test_uploader_only_row_not_in_secret_state_does_not_change_label():
    """Glenn Uploader save without TKP persistence must not move the label."""
    persisted = [_row("2026-07-14", "$82,000.00", nav="$192,000.00")]
    assert _label_date_line(persisted) == "July 14, 2026 close"


def test_durable_ingest_updates_label_without_restart():
    """Fresh records passed to serve_layout must override import-time constants."""
    import tkp_ts

    before = [_row("2026-07-14", "$82,000.00", nav="$192,000.00")]
    after = before + [_row("2026-07-15", "$82,955.48", nav="$192,969.87")]

    stale_constant = "July 06, 2026"
    tkp_ts.DAILY_RETURNS_LATEST_DATE = stale_constant

    before_layout = str(tkp_ts.serve_layout(records=before))
    after_layout = str(tkp_ts.serve_layout(records=after))

    assert "July 14, 2026 close" in before_layout
    assert "July 06, 2026 close" not in before_layout
    assert "July 15, 2026 close" in after_layout
    assert stale_constant not in after_layout


def test_stale_july_06_cutoff_cannot_override_newer_ingested_row():
    import tkp_ts

    rows = [
        _row("2026-07-06", "$80,000.00", nav="$190,000.00"),
        _row("2026-07-15", "$82,955.48", nav="$192,969.87"),
    ]
    tkp_ts.DAILY_RETURNS_LATEST_DATE = "July 06, 2026"

    latest = tkp_ts._latest_authoritative_tkp_date_from_rows(rows)
    layout = str(tkp_ts.serve_layout(records=rows))

    assert latest == "July 15, 2026"
    assert "July 15, 2026 close" in layout
    assert "July 06, 2026 close" not in layout


def test_plus500_only_row_without_stonex_does_not_extend_authoritative_date():
    import tkp_ts

    rows = [
        _row("2026-07-14", "$82,000.00", nav="$192,000.00"),
        {
            "Date": "2026-07-15",
            "NAV": "$192,969.87",
            "Plus500": "$85,330.46",
            "StoneX": "",
        },
    ]
    canonical = tkp_ts._canonical_records_from_secret_rows(rows)
    latest = tkp_ts._latest_authoritative_tkp_date_from_rows(rows)

    assert len(canonical) == 1
    assert canonical[-1]["Date"] == "2026-07-14"
    assert latest == "July 14, 2026"


def test_propagate_dashboard_uses_authoritative_date_not_synthetic_nav():
    import tkp_ts

    secret_rows = [
        _row("2026-07-14", "$82,000.00", nav="$192,000.00"),
        _row("2026-07-15", "$82,955.48", nav="$192,969.87"),
    ]
    canonical = tkp_ts._canonical_records_from_secret_rows(secret_rows)

    monthly, perf, _fig, _dd, desktop, mobile = tkp_ts.propagate_dashboard(canonical, secret_rows)

    assert monthly is not None
    assert "July 15, 2026 close" in str(desktop)
    assert "July 15, 2026 close" in str(mobile)
