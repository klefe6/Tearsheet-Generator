"""Step 11C — Trading Universe, Investor Information, and Terms & Fees tests."""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tcp_admin import SESSION_KEY, AdminAuthManager, SIMULATION_BANNER_TEXT
from tcp_config import AdminAuthSettings, load_config, resolve_state_paths
from tcp_public_sections import (
    ACCOUNT_STATISTICS,
    INVESTOR_OTHER_NOTES,
    TERMS_AND_FEES,
    TRANSACTION_FEE_FOOTNOTE,
    resolve_public_gate_styles,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-admin-token-public-content"
TEST_SECRET = "test-session-secret-public-content"


def _layout_text(app) -> str:
    return str(app.layout)


def _public_source_text() -> str:
    return "\n".join(
        [
            (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8"),
            (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8"),
        ]
    )


def _trading_universe_section_text(layout_text: str) -> str:
    start = layout_text.find("Trading Universe & Risk Profile")
    end = layout_text.find("Investor Information", start)
    assert start >= 0
    return layout_text[start:end if end > start else len(layout_text)]


def _trading_universe_pre_fee_footnote(layout_text: str) -> str:
    section = _trading_universe_section_text(layout_text)
    return section.split("* Give up fee")[0]


@pytest.fixture(scope="module")
def _app_bundle_module():
    import os

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = TEST_TOKEN
    os.environ["TCP_V2_SESSION_SECRET"] = TEST_SECRET
    settings = AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET)
    from tcp_ts_v2 import create_app

    bundle = create_app(auth_settings=settings)
    yield bundle
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def app_bundle(_app_bundle_module):
    return _app_bundle_module


@pytest.fixture
def layout_text(app_bundle):
    app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    return _layout_text(app)


@pytest.fixture
def client(app_bundle):
    return app_bundle[0].server.test_client()


@pytest.fixture
def auth_manager():
    return AdminAuthManager(AdminAuthSettings(admin_token=TEST_TOKEN, session_secret=TEST_SECRET))


# --- Trading Universe ---


def test_trading_universe_heading(layout_text):
    assert "Trading Universe & Risk Profile" in layout_text
    assert "tcp-trading-universe-card" in layout_text


def test_trading_universe_btc_context(layout_text):
    assert "Cryptocurrencies" in _trading_universe_section_text(layout_text)
    assert "Bitcoin" in layout_text


def test_trading_universe_eth_context(layout_text):
    assert "Ethereum" in layout_text


def test_trading_universe_risk_labels(layout_text):
    section = _trading_universe_section_text(layout_text)
    for needle in (
        "Risk Management",
        "Average Margin Usage",
        "Exchange Margin Ratios",
        "Risk Controls",
        "Transaction Fees (per Contract)",
        "CME Group / MGX",
    ):
        assert needle in section


def test_no_tkp_instrument_wording():
    lowered = _public_source_text().lower()
    assert "the kinetics program" not in lowered
    assert "tkp tearsheet" not in lowered


def test_trading_universe_no_stonex_in_exchange_or_product_sections(layout_text):
    pre_footnote = _trading_universe_pre_fee_footnote(layout_text)
    assert "StoneX" not in pre_footnote


def test_no_plus500_wording(layout_text):
    assert "Plus500" not in layout_text


# --- Investor Information ---


def test_investor_information_heading(layout_text):
    assert "Investor Information" in layout_text
    assert "tcp-investor-information-card" in layout_text


@pytest.mark.parametrize("label, _value", TERMS_AND_FEES)
def test_investor_terms_labels(layout_text, label, _value):
    assert label in layout_text


def test_minimum_investment_values_from_committed_v1(layout_text):
    assert "$150,000 per tranche" in layout_text
    assert "$300,000 Nominal" in layout_text


def test_proprietary_client_distinctions(layout_text):
    assert "Proprietary" in layout_text
    assert "Client" in layout_text
    assert "Account Stats" in layout_text


def test_investor_other_notes_footnote(layout_text):
    assert "Other Notes:" in layout_text
    assert INVESTOR_OTHER_NOTES[:60] in layout_text


# --- Terms & Fees ---


def test_terms_and_fees_heading(layout_text):
    assert "Terms & Fees" in layout_text


@pytest.mark.parametrize("label, value", TERMS_AND_FEES)
def test_terms_and_fees_values(layout_text, label, value):
    assert label in layout_text
    assert value in layout_text


def test_fee_wording_matches_v1():
    fees = dict(TERMS_AND_FEES)
    assert fees["Fee Structure"] == "0% Annual / 20% Performance"


def test_hwm_wording_matches_v1():
    fees = dict(TERMS_AND_FEES)
    assert fees["High Water Mark"] == "Yes"


def test_terms_not_sourced_from_calculator_module():
    public = (REPO_ROOT / "tcp_public_sections.py").read_text(encoding="utf-8")
    runtime = (REPO_ROOT / "tcp_runtime_state.py").read_text(encoding="utf-8")
    assert "TERMS_AND_FEES" in public
    assert "TERMS_AND_FEES" not in runtime
    assert "0% Annual / 20% Performance" in public


def test_transaction_fee_footnote(layout_text):
    assert TRANSACTION_FEE_FOOTNOTE in layout_text


# --- Layout ---


def test_section_stable_ids(layout_text):
    for section_id in (
        "tcp-trading-universe-card",
        "tcp-investor-information-card",
        "tcp-terms-and-fees-table",
    ):
        assert section_id in layout_text


def test_public_content_hierarchy(layout_text):
    strategy = layout_text.find("tcp-strategy-row")
    performance = layout_text.find("tcp-performance-account-row")
    disclaimers = layout_text.find("tcp-hc-disclaimer-row")
    assert strategy < performance < disclaimers


def test_sections_behind_public_gate(layout_text):
    for marker in ("disclaimer-screen", "main-app", "tcp-trading-universe-card"):
        assert marker in layout_text
    assert '"display": "none"' in layout_text or "'display': 'none'" in layout_text
    gate_style, main_style = resolve_public_gate_styles(0)
    assert main_style == {"display": "none"}


def test_mobile_stacking_classes(layout_text):
    assert "mb-lg-0" in layout_text
    assert "tcp-two-column-row" in layout_text


def test_desktop_grouping_structure(layout_text):
    assert "tcp-strategy-row" in layout_text
    assert "tcp-performance-account-row" in layout_text


def test_footer_after_new_sections(layout_text):
    investor = layout_text.find("tcp-investor-information-card")
    footer = layout_text.find("tcp-public-footer")
    assert investor < footer


# --- Regression ---


def test_step_11b_shell_present(layout_text):
    for needle in (
        "Important Notic",
        "Strategy Overview",
        "Performance Summary",
        "Important Disclosure:",
    ):
        assert needle in layout_text


def test_monthly_container(layout_text):
    assert "monthly-calendar-container" in layout_text


def test_daily_container(layout_text):
    assert "daily-perf-container" in layout_text


def test_nav_graph(layout_text):
    assert "nav-preview-graph" in layout_text


def test_date_labels(layout_text):
    assert "data-current-label-desktop" in layout_text
    assert "data-current-label-mobile" in layout_text


def test_canonical_store(layout_text):
    assert "canonical-nav-store" in layout_text


def test_admin_login_logout(client, auth_manager):
    login = client.post("/admin/login", data={"token": TEST_TOKEN}, follow_redirects=False)
    assert login.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert auth_manager.is_authenticated(sess)
    logout = client.get("/admin/logout", follow_redirects=False)
    assert logout.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert not auth_manager.is_authenticated(sess)


def test_public_gate_does_not_authenticate_admin(auth_manager):
    session = {}
    resolve_public_gate_styles(1)
    assert not auth_manager.is_authenticated(session)
    assert SESSION_KEY not in session


def test_layout_construction_no_state_files():
    active, backup, lock = resolve_state_paths(load_config(), REPO_ROOT)
    before = {p: p.stat().st_mtime if p.exists() else None for p in (active, backup, lock)}
    import tcp_public_sections as tps

    tps.build_trading_universe()
    tps.build_investor_information()
    after = {p: p.stat().st_mtime if p.exists() else None for p in (active, backup, lock)}
    assert before == after


def test_import_starts_no_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        assert sock.connect_ex(("127.0.0.1", 8312)) != 0
    import tcp_public_sections  # noqa: F401

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        assert sock.connect_ex(("127.0.0.1", 8312)) != 0


def test_unauthenticated_no_admin_ledger(client, app_bundle):
    _app, _cfg, state, _auth, _holder = app_bundle
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    body = client.get("/").get_data(as_text=True)
    assert "admin-ledger-table" not in body
    assert SIMULATION_BANNER_TEXT not in body
