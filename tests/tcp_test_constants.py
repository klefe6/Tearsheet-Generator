"""Constants for TCP v2 tests (no production imports)."""
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_FIXTURE_PATH = FIXTURES_DIR / "tcp_golden_rows.json"
CONTRACT_PATH = TESTS_DIR.parent / "docs" / "tcp_daily_ledger_contract.md"

TEST_AUTH_TOKEN = "test-conftest-runtime-admin-token"
TEST_AUTH_SECRET = "test-conftest-runtime-session-secret"

REQUIRED_LEDGER_FIELDS = [
    "Cash Transfers",
    "Trading Days",
    "Date",
    "Cash Balance",
    "NLV",
    "#",
    "$PL",
    "Inc. Fee",
    "cumm fee",
    "Day PnL",
    "nav-x1",
    "Loss Carry",
    "%Net",
    "S net cummulative %",
    "HWM",
]

REQUIRED_SCENARIOS = {
    "profitable_day",
    "losing_day",
    "fee",
    "loss_carry_start",
    "under_hwm_loss_carry",
    "hwm_recovery",
    "deposit",
    "tranche_change",
    "post_deposit",
    "rounding_small_pl",
    "latest_completed_row",
}
