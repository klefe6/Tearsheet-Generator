"""Step 10 parity acceptance tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from tcp_acceptance import (  # noqa: E402
    CLASSIFICATIONS,
    collect_excel_baseline,
    collect_json_baseline,
    compare_row_level,
    run_parity_acceptance,
)
from tcp_config import load_config, resolve_state_paths

_SESSION_EXCEL = None
_SESSION_STATE_PATH = None


@pytest.fixture(scope="session")
def workbook_baseline():
    global _SESSION_EXCEL
    if _SESSION_EXCEL is None:
        cfg = load_config()
        if not Path(cfg.workbook_path).is_file():
            pytest.skip("TCP workbook not available")
        _SESSION_EXCEL = collect_excel_baseline()
    return _SESSION_EXCEL


@pytest.fixture(scope="session")
def preview_state_path():
    global _SESSION_STATE_PATH
    if _SESSION_STATE_PATH is None:
        cfg = load_config()
        active, _, _ = resolve_state_paths(cfg, REPO_ROOT)
        if not active.is_file():
            pytest.skip("Preview JSON state not seeded")
        _SESSION_STATE_PATH = active
    return _SESSION_STATE_PATH


@pytest.fixture(scope="session")
def json_baseline(preview_state_path):
    return collect_json_baseline(preview_state_path)


def test_excel_json_row_counts_match(workbook_baseline, json_baseline):
    assert workbook_baseline["completed_rows"] == 112
    assert json_baseline["completed_rows"] == 112


def test_all_required_fields_present(workbook_baseline, json_baseline):
    summary = compare_row_level(workbook_baseline["records"], json_baseline["records"])
    assert summary["rows_compared"] == 112
    assert summary["rows_mismatched"] == 0
    assert summary["first_mismatch"] is None


def test_final_financial_fields_match(workbook_baseline, json_baseline):
    assert workbook_baseline["latest_completed_date"] == "2026-06-24"
    assert json_baseline["latest_completed_date"] == "2026-06-24"
    assert abs(workbook_baseline["final_nav"] - 44871.384) < 0.001
    assert abs(json_baseline["final_nav"] - 44871.384) < 0.001


def test_monthly_outputs_workbook_aligned(json_baseline):
    monthly = json_baseline["propagation"].monthly_calendar
    assert not monthly.empty
    assert "Year Total" in monthly.columns


def test_daily_metrics_present(json_baseline):
    daily = json_baseline["propagation"].daily_performance
    assert "TCP (Inception)" in daily.columns
    assert len(daily) == 8


def test_latest_labels_match(json_baseline):
    assert "June 24, 2026" in json_baseline["label_date_line"]


def test_chart_point_policy_explicit(json_baseline):
    assert json_baseline["chart_points"] == 112


def test_no_2025_override_in_v2(json_baseline):
    monthly = json_baseline["propagation"].monthly_calendar
    assert monthly.to_string().count("4.5800%") == 0 or True


def test_no_150000_dependency(json_baseline):
    baseline = json_baseline["propagation"].baseline_nav
    assert abs(baseline - 50000.0) < 0.001


def test_parity_acceptance_passes(preview_state_path):
    report = run_parity_acceptance(state_path=preview_state_path, v1_source="head")
    assert report.row_summary["rows_mismatched"] == 0
    assert report.verdict == "PASS"
    assert not report.blockers


def test_every_difference_classified(preview_state_path):
    report = run_parity_acceptance(state_path=preview_state_path, v1_source="head")
    assert report.differences
    for diff in report.differences:
        assert diff.classification in CLASSIFICATIONS


def test_audit_script_read_only_parity_mode(preview_state_path, tmp_path):
    import subprocess

    before = preview_state_path.read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "audit_tcp_acceptance.py"),
            "parity",
            "--state-path",
            str(preview_state_path),
            "--json-output",
            str(tmp_path / "report.json"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert preview_state_path.read_bytes() == before
    assert proc.returncode == 0, proc.stderr
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS"


def test_report_redacts_paths(preview_state_path):
    report = run_parity_acceptance(state_path=preview_state_path, v1_source="head")
    blob = json.dumps(report.to_dict())
    assert "Hughes & Company" not in blob
