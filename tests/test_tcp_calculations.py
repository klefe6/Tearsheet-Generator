"""Tests for tcp_calculations pure row calculator."""
from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tcp_calculations import (
    CALCULATED_FIELDS,
    CalculationInvariantError,
    InvalidCashBalance,
    InvalidEntryDate,
    InvalidTrancheCount,
    InvalidTransfer,
    MissingEntryField,
    MissingPreviousField,
    NonChronologicalDate,
    TCPInceptionContext,
    TCPRules,
    TCPEntry,
    TrancheRegression,
    UnsupportedWithdrawal,
    build_seed_row,
    compare_field,
    compute_tcp_row,
    public_row,
)
from tcp_config import load_config, resolve_state_paths
from tcp_ledger import load_ledger
from tcp_state import serialize_state, validate_state
from tcp_test_constants import GOLDEN_FIXTURE_PATH
from replay_tcp_ledger import replay_ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGURED_ACTIVE = REPO_ROOT / "tcp_daily_returns_secret_state.json"
CONFIGURED_BACKUP = REPO_ROOT / "tcp_daily_returns_secret_state.backup.json"
CONFIGURED_LOCK = REPO_ROOT / "tcp_daily_returns_secret_state.lock"

GOLDEN_ROWS = {
    3: "first_trading_day",
    4: "profit_and_fee",
    6: "rounding_small_pl",
    7: "loss_carry_initiation",
    8: "hwm_recovery",
    10: "under_hwm_loss_carry",
    16: "deposit_tranche_change",
    17: "post_deposit",
    114: "latest_completed_row",
}


def _workbook_available() -> bool:
    return Path(load_config().workbook_path).is_file()


def _load_golden_fixture() -> dict:
    return json.loads(GOLDEN_FIXTURE_PATH.read_text(encoding="utf-8"))


def _ledger():
    cfg = load_config()
    if not Path(cfg.workbook_path).is_file():
        pytest.skip("TCP workbook not available")
    return load_ledger(cfg.workbook_path, cfg.sheet_name)


def _record_by_excel_row(ledger, excel_row: int):
    for record in ledger.completed_records:
        if record.excel_row_number == excel_row:
            return record
    raise KeyError(excel_row)


def _entry_from_record(record) -> TCPEntry:
    fields = record.fields
    return TCPEntry(
        row_date=fields["Date"],
        cash_balance=Decimal(str(fields["Cash Balance"])),
        cash_transfers=Decimal(str(fields.get("Cash Transfers") or 0)),
        tranche_count=int(fields["#"]),
        trading_days=int(fields["Trading Days"]),
    )


def _compute_through_row(ledger, target_excel_row: int) -> dict:
    records = ledger.completed_records
    first = records[0]
    calculated = build_seed_row(
        _entry_from_record(first),
        TCPInceptionContext(),
    )
    if target_excel_row == first.excel_row_number:
        return calculated
    for record in records[1:]:
        calculated = compute_tcp_row(calculated, _entry_from_record(record))
        if record.excel_row_number == target_excel_row:
            return calculated
    raise KeyError(target_excel_row)


def _prior_workbook_row(ledger, excel_row: int):
    records = ledger.completed_records
    for index, record in enumerate(records):
        if record.excel_row_number == excel_row:
            if index == 0:
                return None
            return records[index - 1]
    raise KeyError(excel_row)


@pytest.fixture
def rules():
    return TCPRules()


@pytest.mark.parametrize("excel_row,scenario", list(GOLDEN_ROWS.items()))
def test_golden_row_matches_workbook(excel_row, scenario):
    ledger = _ledger()
    target = _record_by_excel_row(ledger, excel_row)
    if excel_row == ledger.completed_records[0].excel_row_number:
        entry = _entry_from_record(target)
        calculated = build_seed_row(entry, TCPInceptionContext())
    else:
        prior = _prior_workbook_row(ledger, excel_row)
        prior_calculated = _compute_through_row(ledger, prior.excel_row_number)
        calculated = compute_tcp_row(prior_calculated, _entry_from_record(target))

    max_diff = 0.0
    for field in sorted(CALCULATED_FIELDS):
        observed = target.fields.get(field)
        calc_val = calculated.get(field)
        ok, diff = compare_field(field, calc_val, observed)
        max_diff = max(max_diff, diff)
        assert ok, (
            f"row {excel_row} ({scenario}) field {field!r}: "
            f"calc={calc_val!r} obs={observed!r} diff={diff}"
        )


def test_full_ledger_replay_passes():
    ledger = _ledger()
    report = replay_ledger(ledger)
    assert report.rows_mismatched == 0
    assert report.rows_matched == report.rows_attempted == 112
    assert report.final_nav_difference is not None
    assert report.final_nav_difference < 0.001


def test_seed_row_validation():
    entry = TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 1, 1)
    row = build_seed_row(entry, TCPInceptionContext())
    assert row["Day PnL"] == 0.0
    assert row["nav-x1"] == 50000.0
    assert row["Inc. Fee"] == 0.0


def test_missing_previous_field(rules):
    entry = TCPEntry(date(2026, 1, 21), Decimal("25013.6"), Decimal("0"), 1, 2)
    with pytest.raises(MissingPreviousField):
        compute_tcp_row({"Date": date(2026, 1, 20)}, entry, rules)


def test_missing_entry_field():
    with pytest.raises(MissingEntryField):
        TCPEntry.from_mapping({"Date": "2026-01-21", "Cash Balance": 1})


def test_same_date_entry(rules):
    prior = build_seed_row(
        TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 1, 1),
        TCPInceptionContext(),
    )
    entry = TCPEntry(date(2026, 1, 20), Decimal("25000"), Decimal("0"), 1, 2)
    with pytest.raises(NonChronologicalDate):
        compute_tcp_row(prior, entry, rules)


def test_earlier_date_entry(rules):
    prior = build_seed_row(
        TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 1, 1),
        TCPInceptionContext(),
    )
    entry = TCPEntry(date(2026, 1, 19), Decimal("25000"), Decimal("0"), 1, 2)
    with pytest.raises(NonChronologicalDate):
        compute_tcp_row(prior, entry, rules)


def test_invalid_entry_date():
    with pytest.raises(InvalidEntryDate):
        TCPEntry.from_mapping({"Date": "not-a-date", "Cash Balance": 1, "#": 1})


def test_non_finite_cash_balance():
    with pytest.raises(InvalidCashBalance):
        TCPEntry.from_mapping({"Date": "2026-01-21", "Cash Balance": float("nan"), "#": 1})


def test_invalid_transfer():
    with pytest.raises(InvalidTransfer):
        TCPEntry.from_mapping(
            {"Date": "2026-01-21", "Cash Balance": 1, "#": 1, "Cash Transfers": "bad"}
        )


def test_unsupported_negative_transfer():
    with pytest.raises(UnsupportedWithdrawal):
        TCPEntry.from_mapping(
            {"Date": "2026-01-21", "Cash Balance": 1, "#": 1, "Cash Transfers": -100}
        )


def test_zero_tranche_count(rules):
    prior = build_seed_row(
        TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 1, 1),
        TCPInceptionContext(),
    )
    entry = TCPEntry(date(2026, 1, 21), Decimal("25000"), Decimal("0"), 0, 2)
    with pytest.raises(InvalidTrancheCount):
        compute_tcp_row(prior, entry, rules)


def test_negative_tranche_count(rules):
    prior = build_seed_row(
        TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 1, 1),
        TCPInceptionContext(),
    )
    entry = TCPEntry(date(2026, 1, 21), Decimal("25000"), Decimal("0"), -1, 2)
    with pytest.raises(InvalidTrancheCount):
        compute_tcp_row(prior, entry, rules)


def test_fractional_tranche_count():
    with pytest.raises(InvalidTrancheCount):
        TCPEntry.from_mapping({"Date": "2026-01-21", "Cash Balance": 1, "#": 1.5})


def test_tranche_regression(rules):
    prior = {
        **build_seed_row(
            TCPEntry(date(2026, 1, 20), Decimal("24996.76"), Decimal("0"), 2, 1),
            TCPInceptionContext(),
        ),
        "#": 2,
    }
    entry = TCPEntry(date(2026, 1, 21), Decimal("25000"), Decimal("0"), 1, 2)
    with pytest.raises(TrancheRegression):
        compute_tcp_row(prior, entry, rules)


def test_very_small_positive_pl_matches_workbook(rules):
    ledger = _ledger()
    calculated = _compute_through_row(ledger, 6)
    observed = _record_by_excel_row(ledger, 6).fields
    assert compare_field("$PL", calculated["$PL"], observed["$PL"])[0]
    assert calculated["$PL"] > 0


def test_very_small_loss_matches_workbook():
    ledger = _ledger()
    calculated = _compute_through_row(ledger, 7)
    observed = _record_by_excel_row(ledger, 7).fields
    assert calculated["$PL"] < 0
    assert compare_field("Loss Carry", calculated["Loss Carry"], observed["Loss Carry"])[0]


def test_fee_boundary_at_prior_loss_carry(rules):
    prior = {
        "Date": date(2026, 1, 20),
        "Cash Balance": Decimal("100"),
        "Cash Transfers": Decimal("0"),
        "Trading Days": 1,
        "#": 1,
        "NLV": 100.0,
        "$PL": 0.0,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": 50000.0,
        "Loss Carry": 50.0,
        "%Net": 0.0,
        "S net cummulative %": 0.0,
        "HWM": 50000.0,
        "_running_max_nav": 50000.0,
    }
    entry = TCPEntry(date(2026, 1, 21), Decimal("150"), Decimal("0"), 1, 2)
    row_at = compute_tcp_row(prior, entry, rules)
    assert row_at["Inc. Fee"] == 0.0
    entry2 = TCPEntry(date(2026, 1, 22), Decimal("150.01"), Decimal("0"), 1, 3)
    prior2 = compute_tcp_row(prior, TCPEntry(date(2026, 1, 21), Decimal("150"), Decimal("0"), 1, 2), rules)
    row_above = compute_tcp_row(prior2, entry2, rules)
    assert row_above["Inc. Fee"] > 0.0


def test_pl_just_above_and_below_loss_carry(rules):
    prior = {
        "Date": date(2026, 1, 20),
        "Cash Balance": Decimal("100"),
        "Cash Transfers": Decimal("0"),
        "Trading Days": 1,
        "#": 1,
        "NLV": 100.0,
        "$PL": 0.0,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": 50000.0,
        "Loss Carry": 10.0,
        "%Net": 0.0,
        "S net cummulative %": 0.0,
        "HWM": 50000.0,
        "_running_max_nav": 50000.0,
    }
    below = compute_tcp_row(
        prior,
        TCPEntry(date(2026, 1, 21), Decimal("109.99"), Decimal("0"), 1, 2),
        rules,
    )
    assert below["Inc. Fee"] == 0.0
    above = compute_tcp_row(
        prior,
        TCPEntry(date(2026, 1, 21), Decimal("110.01"), Decimal("0"), 1, 2),
        rules,
    )
    assert above["Inc. Fee"] > 0.0


def test_new_hwm_boundary_matches_workbook():
    ledger = _ledger()
    calculated = _compute_through_row(ledger, 8)
    observed = _record_by_excel_row(ledger, 8).fields
    assert calculated["nav-x1"] > calculated["HWM"] - 0.001 or math.isclose(
        calculated["nav-x1"], calculated["HWM"], abs_tol=0.001
    )
    assert compare_field("HWM", calculated["HWM"], observed["HWM"])[0]


def test_no_fee_under_hwm_row_matches_workbook():
    ledger = _ledger()
    calculated = _compute_through_row(ledger, 10)
    observed = _record_by_excel_row(ledger, 10).fields
    assert calculated["Inc. Fee"] == 0.0
    assert compare_field("Loss Carry", calculated["Loss Carry"], observed["Loss Carry"])[0]


def test_input_dictionaries_remain_unchanged(rules):
    prior = {
        "Date": date(2026, 1, 20),
        "Cash Balance": 24996.76,
        "Cash Transfers": None,
        "Trading Days": 1,
        "#": 1,
        "NLV": 24996.76,
        "$PL": -3.24,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": 50000.0,
        "Loss Carry": 0.0,
        "%Net": -0.0000648,
        "S net cummulative %": -0.0000648,
        "HWM": 50000.0,
        "_running_max_nav": 50000.0,
    }
    entry = {
        "Date": date(2026, 1, 21),
        "Cash Balance": 25013.6,
        "Cash Transfers": 0,
        "#": 1,
        "Trading Days": 2,
    }
    prior_copy = deepcopy(prior)
    entry_copy = deepcopy(entry)
    compute_tcp_row(prior, TCPEntry.from_mapping(entry), rules)
    assert prior == prior_copy
    assert entry == entry_copy


def test_repeated_calls_return_identical_output(rules):
    ledger = _ledger()
    prior = _compute_through_row(ledger, 4)
    entry = _entry_from_record(_record_by_excel_row(ledger, 5))
    first = compute_tcp_row(prior, entry, rules)
    second = compute_tcp_row(prior, entry, rules)
    assert first == second


def test_import_does_not_touch_state_or_workbook():
    if CONFIGURED_ACTIVE.exists():
        active_before = CONFIGURED_ACTIVE.stat().st_mtime
    else:
        active_before = None
    wb_path = Path(load_config().workbook_path)
    wb_before = wb_path.stat().st_mtime if wb_path.is_file() else None

    import tcp_calculations  # noqa: F401

    if active_before is not None:
        assert CONFIGURED_ACTIVE.stat().st_mtime == active_before
    if wb_before is not None:
        assert wb_path.stat().st_mtime == wb_before


def test_import_creates_no_files():
    tmp_dir = REPO_ROOT / "tests" / "_tmp_calc_import"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in tmp_dir.iterdir()}
    import tcp_calculations  # noqa: F401

    after = {p.name for p in tmp_dir.iterdir()}
    assert before == after


def test_no_tkp_module_imported():
    for name, module in list(sys.modules.items()):
        if name.startswith("tkp_") or name == "tkp_ts":
            pytest.fail(f"Unexpected TKP module imported: {name}")
    import tcp_calculations  # noqa: F401


def test_calculated_record_passes_state_validation():
    ledger = _ledger()
    seed = public_row(
        build_seed_row(_entry_from_record(ledger.completed_records[0]), TCPInceptionContext())
    )
    calculated = public_row(_compute_through_row(ledger, 4))
    state = {
        "schema_version": 1,
        "app": "tcp",
        "revision": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "source": "test",
        "records": [seed, calculated],
    }
    validate_state(state)


def test_calculated_record_serializes_in_memory():
    ledger = _ledger()
    seed = public_row(
        build_seed_row(_entry_from_record(ledger.completed_records[0]), TCPInceptionContext())
    )
    row = public_row(_compute_through_row(ledger, 4))
    state = {
        "schema_version": 1,
        "app": "tcp",
        "revision": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "source": "test",
        "records": [seed, row],
    }
    payload = serialize_state(state)
    assert "nav-x1" in payload
    assert "_running_max_nav" not in payload


def test_state_files_not_written_by_calculator():
    active_existed = CONFIGURED_ACTIVE.exists()
    backup_existed = CONFIGURED_BACKUP.exists()
    lock_existed = CONFIGURED_LOCK.exists()

    ledger = _ledger()
    _compute_through_row(ledger, 10)

    if active_existed:
        assert CONFIGURED_ACTIVE.exists()
    else:
        assert not CONFIGURED_ACTIVE.exists()
    if backup_existed:
        assert CONFIGURED_BACKUP.exists()
    else:
        assert not CONFIGURED_BACKUP.exists()
    if lock_existed:
        assert CONFIGURED_LOCK.exists()
    else:
        assert not CONFIGURED_LOCK.exists()


def test_rules_immutability(rules):
    ledger = _ledger()
    prior = _compute_through_row(ledger, 4)
    entry = _entry_from_record(_record_by_excel_row(ledger, 5))
    rules_copy = TCPRules(
        performance_fee_rate=rules.performance_fee_rate,
        base_nav_per_tranche=rules.base_nav_per_tranche,
        currency_quantize=rules.currency_quantize,
        nav_quantize=rules.nav_quantize,
        percent_quantize=rules.percent_quantize,
    )
    compute_tcp_row(prior, entry, rules_copy)
    assert rules_copy == rules
