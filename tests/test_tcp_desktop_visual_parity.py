"""Step 11F — structural desktop visual parity contracts (no pixel screenshots)."""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from tcp_public_sections import (
    DAILY_METRICS_TABLE_CLASS,
    DESKTOP_TWO_COLUMN_ROW_CLASS,
    DRAWDOWN_TABLE_CLASS,
    MONTHLY_PERFORMANCE_CLASS,
    NAV_CHART_CONTAINER_CLASS,
    PREVIEW_BANNER_CLASS,
    PUBLIC_CARD_CLASS,
    RUNTIME_DIAGNOSTICS_CARD_ID,
    benchmark_notice_class,
    desktop_visual_contract,
    monthly_performance_cell_class,
    normalized_gate_title_text,
    required_copy_fragments,
    resolve_public_gate_styles,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
V1_BASE_COMMIT = "b5fce4b"


from layout_helpers import layout_text as _layout_text


def _public_source() -> str:
    return "\n".join(
        [
            (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "assets" / "styles.css").read_text(encoding="utf-8"),
        ]
    )


@pytest.fixture(scope="module")
def layout_text():
    from tcp_layout_support import tcp_layout_benchmark_patches
    from tcp_ts_v2 import create_app

    with tcp_layout_benchmark_patches():
        app, *_ = create_app()
        return _layout_text(app)


def test_main_page_shell_exists(layout_text):
    for marker in ("tcp-public-root", "main-app", "page-container"):
        assert marker in layout_text


def test_header_band_contract_exists(layout_text):
    assert "header-row" in layout_text
    assert "tcp-public-header-row" in layout_text
    assert "bg-light" in layout_text or "header-bg" in layout_text


def test_desktop_grid_exists(layout_text):
    assert DESKTOP_TWO_COLUMN_ROW_CLASS in layout_text
    assert "tcp-strategy-row" in layout_text
    assert "tcp-performance-account-row" in layout_text


def test_full_width_and_two_column_sections(layout_text):
    assert "Performance Summary" in layout_text
    assert MONTHLY_PERFORMANCE_CLASS in layout_text
    assert "tcp-strategy-overview-card" in layout_text
    assert "tcp-trading-universe-card" in layout_text


def test_public_cards_share_consistent_classes(layout_text):
    assert PUBLIC_CARD_CLASS in layout_text
    for card_id in (
        "tcp-strategy-overview-card",
        "tcp-trading-universe-card",
        "tcp-performance-metrics-card",
        "tcp-drawdown-profile-card",
        "tcp-investor-information-card",
    ):
        assert card_id in layout_text


def test_monthly_table_styling_contract():
    assert monthly_performance_cell_class("1.2500%") == "tcp-monthly-cell-positive"
    assert monthly_performance_cell_class("-0.5000%") == "tcp-monthly-cell-negative"
    assert monthly_performance_cell_class("") == "tcp-monthly-cell-empty"
    assert MONTHLY_PERFORMANCE_CLASS in _public_source()


def test_daily_metric_grid_styling_contract(layout_text):
    assert DAILY_METRICS_TABLE_CLASS in layout_text
    assert "tcp-performance-metrics-card" in layout_text


def test_nav_chart_presentation_contract(layout_text):
    assert NAV_CHART_CONTAINER_CLASS in layout_text
    assert "nav-preview-graph" in layout_text
    assert "Non-Compounded NAV Since Inception" in layout_text


def test_drawdown_table_styling_contract(layout_text):
    assert DRAWDOWN_TABLE_CLASS in layout_text
    assert "tcp-drawdown-profile-card" in layout_text


def test_benchmark_status_classes():
    assert "tcp-benchmark-notice-ready" in benchmark_notice_class("ready")
    assert "tcp-benchmark-notice-stale" in benchmark_notice_class("stale")
    assert "tcp-benchmark-notice-unavailable" in benchmark_notice_class("unavailable")


def test_account_stat_columns_remain_distinct(layout_text):
    assert "Proprietary" in layout_text
    assert "Client" in layout_text
    assert "tcp-account-stats-table" in layout_text


def test_disclosure_and_footer_classes(layout_text):
    assert "tcp-public-disclosure-panel" in layout_text
    assert "tcp-public-footer-row" in layout_text


def test_preview_banner_is_subordinate(layout_text):
    assert PREVIEW_BANNER_CLASS in layout_text
    assert RUNTIME_DIAGNOSTICS_CARD_ID in layout_text


def test_no_duplicate_dynamic_component_ids(layout_text):
    dynamic_ids = [
        "canonical-nav-store",
        "benchmark-store",
        "nav-preview-graph",
        "monthly-calendar-container",
        "daily-perf-container",
        "drawdown-profile-container",
        "tcp-benchmark-notice",
        "data-current-label-desktop",
        "data-current-label-mobile",
    ]
    for component_id in dynamic_ids:
        matches = re.findall(rf"id=['\"]{re.escape(component_id)}['\"]", layout_text)
        assert len(matches) == 1, component_id


def test_no_public_content_removed(layout_text):
    fragments = required_copy_fragments()
    for key, needle in fragments.items():
        if key == "gate_title":
            assert needle in layout_text
            assert normalized_gate_title_text() == "Important Notice"
            continue
        assert needle in layout_text


def test_public_gate_separate_from_admin(layout_text):
    from tearsheet_gate_auth import GATE_PASSWORD_ROW_ID

    hidden, shown = resolve_public_gate_styles(1)
    assert hidden.get("display") == "none"
    assert shown.get("display") == "block"
    assert GATE_PASSWORD_ROW_ID in layout_text
    assert "accept-button" in layout_text


def test_styling_helpers_write_no_state(tmp_path):
    assert monthly_performance_cell_class("0.0000%") == "tcp-monthly-cell-neutral"
    assert benchmark_notice_class("ready").startswith("py-2")
    contract = desktop_visual_contract()
    assert contract["page_container"] == "page-container"
    assert not any(tmp_path.iterdir())


def test_import_starts_no_server():
    import importlib
    import tcp_public_sections as sections

    importlib.reload(sections)
    source = (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "run":
                if isinstance(func.value, ast.Name) and func.value.id in {"app", "server"}:
                    pytest.fail("tcp_public_sections must not start a server on import")


def test_no_tkp_stonex_plus500_wording_introduced():
    def _without_comments(source: str) -> str:
        return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))

    tcp_source = _without_comments((REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8"))
    tcp_lowered = re.sub(r"tkp_ts\.py", "", tcp_source.lower())
    assert "tkp" not in tcp_lowered
    assert "plus500" not in tcp_lowered

    css_lowered = (REPO_ROOT / "assets/styles.css").read_text(encoding="utf-8").lower()
    assert "plus500" not in css_lowered
    assert "stonex" not in css_lowered


def test_no_financial_formulas_in_presentation_helpers():
    source = (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8")
    forbidden = ("cumprod", "running_max", "download_returns", "reindex(", "diff().div")
    for token in forbidden:
        assert token not in source


def test_v1_stylesheet_is_wired():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "/assets/styles.css" in source


def test_v1_committed_baseline_has_stylesheet():
    proc = subprocess.run(
        ["git", "show", f"{V1_BASE_COMMIT}:tcp_ts.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=20,
        check=True,
    )
    v1 = proc.stdout.decode("utf-8", errors="replace")
    assert "/assets/styles.css" in v1
