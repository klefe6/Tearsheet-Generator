"""Tests for the Algominds v2 tearsheet view model and v1-style layout."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_preview_app as preview_app
import algominds_v2_tearsheet as tearsheet
import algominds_v2_tearsheet_layout as layout
from algominds_v2_account_registry import get_account_profile
from algominds_v2_account_state_paths import save_latest_snapshot_for_account
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot

D = Decimal

TEARSHEET_SECTION_MARKERS = (
    'id="tearsheet-header"',
    'id="tearsheet-intro"',
    'id="nav-chart"',
    'id="performance-summary"',
    'id="strategy-overview"',
    'id="fee-structure"',
    'id="performance-metrics"',
    'id="performance-stats"',
    'id="investor-information"',
    'id="drawdown-chart"',
    "Compounded NAV Since Inception",
    "Drawdown from Peak",
    "Performance Summary",
    "Last Updated",
    "Algominds Financial LLC",
    "Momentum Pacer Program",
)


def _algominds_snapshot() -> AlgomindsV2FeeSnapshot:
    return AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        account_slug="algominds",
    )


# ── Full report sections ─────────────────────────────────────────────────────


def test_algominds_renders_full_v1_style_report_sections(tmp_path: Path) -> None:
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    for marker in TEARSHEET_SECTION_MARKERS:
        assert marker in html_text, f"missing tearsheet section marker: {marker}"
    assert "Algominds" in html_text


def test_vikram_suman_renders_full_report_with_account_profile(tmp_path: Path) -> None:
    html_text = preview_app.render_account_page("vikram-suman", state_root=tmp_path)
    for marker in TEARSHEET_SECTION_MARKERS:
        assert marker in html_text, f"missing tearsheet section marker: {marker}"
    assert "Vikram Suman" in html_text
    assert "$60,000" in html_text


def test_account_labels_are_route_specific(tmp_path: Path) -> None:
    algominds_html = preview_app.render_account_page("algominds", state_root=tmp_path)
    acct_html = preview_app.render_account_page("vikram-suman", state_root=tmp_path)
    assert 'class="account-label">Algominds</p>' in algominds_html
    assert 'class="account-label">Vikram Suman</p>' in acct_html
    assert 'class="account-label">Vikram Suman</p>' not in algominds_html
    assert 'class="account-label">Algominds</p>' not in acct_html
    assert "$30,000" in algominds_html
    assert "$60,000" in acct_html


def test_debug_bullet_shell_is_gone(tmp_path: Path) -> None:
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    assert "No preview snapshot saved" not in html_text
    assert "state path:" not in html_text
    assert "account_slug:" not in html_text


def test_routes_serve_full_tearsheet(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    client = app.server.test_client()
    for route, label in (("/algominds", b"Algominds"), ("/vikram-suman", b"Vikram Suman")):
        response = client.get(route)
        assert response.status_code == 200
        assert label in response.data
        assert b"tearsheet-header" in response.data
        assert b"drawdown-chart" in response.data


# ── Preview fixture data behaviour ───────────────────────────────────────────


def test_fixture_mode_is_labelled_when_no_snapshot(tmp_path: Path) -> None:
    vm = tearsheet.build_tearsheet_view_model(
        get_account_profile("algominds"), state_root=tmp_path
    )
    assert vm.is_preview_fixture
    assert vm.data_notice is not None
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    assert 'id="preview-fixture-banner"' in html_text
    assert "Preview fixture data" in html_text


def test_view_model_is_deterministic(tmp_path: Path) -> None:
    profile = get_account_profile("algominds")
    first = tearsheet.build_tearsheet_view_model(profile, state_root=tmp_path)
    second = tearsheet.build_tearsheet_view_model(profile, state_root=tmp_path)
    assert first == second
    assert (
        preview_app.render_account_page("algominds", state_root=tmp_path)
        == preview_app.render_account_page("algominds", state_root=tmp_path)
    )


def test_fixture_months_are_deterministic_per_account() -> None:
    algominds = get_account_profile("algominds")
    acct = get_account_profile("vikram-suman")
    assert tearsheet.build_preview_fixture_months(algominds) == tearsheet.build_preview_fixture_months(algominds)
    algominds_months = tearsheet.build_preview_fixture_months(algominds)
    acct_months = tearsheet.build_preview_fixture_months(acct)
    assert algominds_months[0].account_start == D("30000")
    assert acct_months[0].account_start == D("60000")
    assert algominds_months[0].month_start == date(2025, 11, 1)
    assert acct_months[0].month_start == date(2026, 1, 1)


def test_view_model_never_writes_state(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    tearsheet.build_tearsheet_view_model(
        get_account_profile("algominds"), state_root=state_root
    )
    preview_app.render_account_page("algominds", state_root=state_root)
    assert not state_root.exists() or not any(state_root.iterdir())


def test_snapshot_data_preferred_over_fixture(tmp_path: Path) -> None:
    save_latest_snapshot_for_account("algominds", _algominds_snapshot(), state_root=tmp_path)
    vm = tearsheet.build_tearsheet_view_model(
        get_account_profile("algominds"), state_root=tmp_path
    )
    assert vm.data_mode == tearsheet.DATA_MODE_SNAPSHOT
    assert not vm.is_preview_fixture
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    assert 'id="preview-fixture-banner"' not in html_text
    # after-fee NLV from the real snapshot appears in the report
    assert "$48,794.96" in html_text


def test_snapshot_mode_still_renders_all_sections(tmp_path: Path) -> None:
    save_latest_snapshot_for_account("algominds", _algominds_snapshot(), state_root=tmp_path)
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    for marker in TEARSHEET_SECTION_MARKERS:
        assert marker in html_text, f"missing tearsheet section marker: {marker}"


# ── Separation of concerns ───────────────────────────────────────────────────


def _import_roots(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_layout_module_has_no_fee_or_state_imports() -> None:
    roots = _import_roots(Path(layout.__file__))
    forbidden = {
        "algominds_v2",  # fee engine package
        "algominds_v2_account_registry",
        "algominds_v2_account_state_paths",
        "algominds_v2_snapshot_state",
        "algominds_v2_snapshots",
        "algominds_v2_state",
        "algominds_v2_config",
        "algominds_v2_daily_source",
    }
    assert not (roots & forbidden), f"layout must stay presentation-only, found {roots & forbidden}"


def test_view_model_module_has_no_layout_imports() -> None:
    roots = _import_roots(Path(tearsheet.__file__))
    assert "algominds_v2_tearsheet_layout" not in roots
    source = Path(tearsheet.__file__).read_text(encoding="utf-8")
    assert "<div" not in source and "<table" not in source, (
        "view model module must not build HTML"
    )


def test_new_modules_avoid_workbook_and_v1_imports() -> None:
    forbidden_roots = {"openpyxl", "pandas", "plotly", "tkp_ts", "tcp_ts", "mp_ts"}
    for module in (tearsheet, layout):
        roots = _import_roots(Path(module.__file__))
        assert not (roots & forbidden_roots), f"{module.__name__}: {roots & forbidden_roots}"


def test_fee_slab_rows_come_from_fee_engine() -> None:
    from algominds_v2.fee_engine import SLAB_RATES

    rows = tearsheet.fee_structure_rows()
    assert len(rows) == len(SLAB_RATES)
    assert [row.rate for row in rows] == [f"{rate * 100:.0f}%" for rate in SLAB_RATES]
    assert tearsheet.negative_benchmark_rate_label() == "50%"
