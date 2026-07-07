"""Tests for Algominds v2 preview shell."""
from __future__ import annotations

import ast
import socket
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_preview_app as preview_app
from algominds_v2_account_state_paths import save_latest_snapshot_for_account
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot

D = Decimal
REPO_ROOT = Path(__file__).resolve().parent.parent


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


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


def _require_port_8311_free() -> None:
    if _port_listening(8311):
        pytest.skip(
            "port 8311 already in use by another process (e.g. a running preview "
            "server); cannot verify import/bind behaviour"
        )


def test_import_does_not_start_preview_server() -> None:
    _require_port_8311_free()
    import importlib

    importlib.reload(preview_app)
    assert not _port_listening(8311), "Importing preview app must not start the server"


def test_create_app_does_not_bind_port(tmp_path: Path) -> None:
    _require_port_8311_free()
    preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    assert not _port_listening(8311)


def test_admin_layout_includes_account_overview_table(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert 'id="admin-account-overview"' in html_text
    assert "Admin Overview" in html_text


def test_admin_table_includes_investor_accounts(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert "Algominds" in html_text
    assert "Vikram Suman" in html_text
    assert "210TSG51" in html_text
    assert "210WAD38" in html_text
    assert 'href="/algominds"' in html_text
    assert 'href="/vikram-suman"' in html_text


def test_admin_rows_link_to_account_routes(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert 'href="/algominds"' in html_text
    assert 'href="/vikram-suman"' in html_text


def test_admin_table_shows_profile_settings_columns(tmp_path: Path) -> None:
    rows = preview_app.build_admin_account_rows(state_root=tmp_path)
    by_slug = {row.account_slug: row for row in rows}
    assert by_slug["algominds"].number_of_units == 1
    assert by_slug["algominds"].exchange_fee_tier == "non-member"
    assert by_slug["algominds"].benchmark_base == D("30000")
    assert by_slug["vikram-suman"].number_of_units == 2
    assert by_slug["vikram-suman"].exchange_fee_tier == "member"
    assert by_slug["vikram-suman"].benchmark_base == D("60000")


def test_after_fee_nlv_placeholder_when_no_snapshot(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert "No snapshot yet" in html_text


def test_after_fee_nlv_shown_when_snapshot_exists(tmp_path: Path) -> None:
    save_latest_snapshot_for_account("algominds", _algominds_snapshot(), state_root=tmp_path)
    rows = preview_app.build_admin_account_rows(state_root=tmp_path)
    algominds_row = next(row for row in rows if row.account_slug == "algominds")
    assert algominds_row.after_fee_nlv is not None
    assert abs(algominds_row.after_fee_nlv - D("48794.960939")) < D("0.01")


def test_algominds_detail_page_renders(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/algominds")
    assert response.status_code == 200
    assert b"Algominds" in response.data
    assert b"tearsheet-header" in response.data


def test_vikram_suman_detail_page_renders(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/vikram-suman")
    assert response.status_code == 200
    assert b"Vikram Suman" in response.data


def test_unknown_account_slug_returns_404(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/client-unknown")
    assert response.status_code == 404
    assert b"Account not found" in response.data


def test_admin_route_returns_200(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/admin")
    assert response.status_code == 200
    assert b"admin-account-overview" in response.data


def test_account_page_empty_snapshot_state(tmp_path: Path) -> None:
    # With no saved snapshot the page still renders a complete tearsheet,
    # backed by clearly-labelled deterministic preview fixture data.
    html_text = preview_app.render_account_page("algominds", state_root=tmp_path)
    assert "No preview snapshot saved" not in html_text
    assert 'id="preview-fixture-banner"' in html_text
    assert "Compounded NAV Since Inception" in html_text


def test_forbidden_import_scan() -> None:
    source_path = Path(preview_app.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "openpyxl",
        "pandas",
        "tkp_ts",
        "tcp_ts",
        "mp_ts",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots


def test_no_workbook_reader_strings_in_source() -> None:
    source = Path(preview_app.__file__).read_text(encoding="utf-8").lower()
    assert "read_excel" not in source
    assert "openpyxl" not in source
