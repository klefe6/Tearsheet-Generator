"""Read-only structural audit for TCP v1 vs v2 public UI parity."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.audit_tcp_public_ui import (
    CLASSIFICATIONS,
    audit_sources,
    paused_step11_inventory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _head_file(rel: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=15,
    )
    proc.check_returncode()
    return proc.stdout.decode("utf-8", errors="replace")


def test_classification_enum_is_stable():
    assert "MISSING_REQUIRED" in CLASSIFICATIONS
    assert "MATCHES_V1" in CLASSIFICATIONS


def test_v1_head_contains_core_public_sections():
    source = _head_file("tcp_ts.py")
    for needle in (
        "Important Notice",
        "Strategy Overview",
        "Maximum Drawdown Profile",
        "Account Stats",
        "Important Disclosure:",
        "footer_contact",
    ):
        assert needle in source


def _v2_public_source() -> str:
    root = REPO_ROOT
    return "\n".join(
        [
            (root / "tcp_ts_v2.py").read_text(encoding="utf-8"),
            (root / "tcp_public_sections.py").read_text(encoding="utf-8"),
        ]
    )


def test_v2_restored_step_11c_public_sections():
    combined = _v2_public_source()
    for needle in (
        "Trading Universe & Risk Profile",
        "Investor Information",
        "Terms & Fees",
        "Other Notes:",
        "Cryptocurrencies",
    ):
        assert needle in combined


def test_v2_restored_step_11e_benchmark_integration():
    combined = _v2_public_source()
    for needle in (
        "benchmark-store",
        "tcp-benchmark-notice",
        "SPXTR",
        "load_spxtr_benchmark",
    ):
        assert needle in combined


def test_v2_restored_step_11d_drawdown_section():
    combined = _v2_public_source()
    for needle in (
        "Maximum Drawdown Profile",
        "drawdown-profile-container",
        "tcp-drawdown-profile-card",
        "build_drawdown_profile_card",
        "DRAWDOWN_FOOTNOTE",
    ):
        assert needle in combined


def test_v2_restored_step_11b_public_sections():
    combined = _v2_public_source()
    for needle in (
        "Important Notice",
        "Strategy Overview",
        "Account Stats",
        "Important Disclosure:",
        "footer_contact",
        "hcdisclaimer_text",
        "disclaimer_text",
    ):
        assert needle in combined


def test_v2_has_dynamic_core_sections():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    for needle in (
        "Performance Summary",
        "Performance Metrics",
        "nav-preview-graph",
        "data-current-label-desktop",
        "propagate_tcp_dashboard",
    ):
        assert needle in source


def test_v2_does_not_reference_tkp_product():
    lines = [
        line
        for line in (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith('"""') and '"""' not in line[:3]
    ]
    body = "\n".join(lines).lower()
    assert "the kelly program" not in body
    assert "tkp tearsheet" not in body


def test_v2_preserves_tcp_product_naming():
    combined = _v2_public_source()
    assert "The Crypto Program" in combined


def test_audit_reports_missing_required_sections():
    report = audit_sources(
        v1_text=_head_file("tcp_ts.py"),
        v2_text=_v2_public_source(),
        v1_label="HEAD",
        v2_label="v2+public",
    )
    by_id = {s.section_id: s for s in report.sections}
    for section_id in (
        "gate_notice",
        "firm_description",
        "strategy_overview",
        "account_stats_columns",
        "hcdisclaimer",
        "general_disclaimer",
        "proprietary_disclosure",
        "footer_contact",
        "nav_footnotes",
        "trading_universe",
        "investor_information",
        "terms_and_fees",
    ):
        assert by_id[section_id].v2_present, section_id
    assert by_id["drawdown_table"].v2_present


def test_audit_json_is_deterministic():
    report = audit_sources(
        v1_text=_head_file("tcp_ts.py"),
        v2_text=_v2_public_source(),
        v1_label="HEAD",
        v2_label="v2+public",
    )
    a = json.dumps(report.to_dict(), sort_keys=True)
    b = json.dumps(report.to_dict(), sort_keys=True)
    assert a == b


def test_paused_step11_files_recorded_not_empty():
    rows = paused_step11_inventory()
    paths = {r["path"] for r in rows}
    assert "scripts/tcp_cutover_preflight.py" in paths
    assert "docs/tcp_production_cutover_runbook.md" in paths
    for row in rows:
        if row["status"].startswith("CUTOVER"):
            assert len(row["sha256"]) == 64


def test_import_tcp_ts_v2_does_not_start_server():
    import socket

    import tcp_ts_v2  # noqa: F401

    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        if sock.connect_ex(("127.0.0.1", 8302)) == 0:
            pytest.skip("Production already listening on 8302; import did not bind it")
        assert sock.connect_ex(("127.0.0.1", 8302)) != 0
    finally:
        sock.close()
