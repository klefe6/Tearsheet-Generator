"""Tests for tcp_state versioned JSON persistence layer."""
from __future__ import annotations

import json
import math
import shutil
import threading
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from tcp_config import load_config, resolve_state_paths
from tcp_ledger import LedgerLoadResult, LedgerMetadata, LedgerRecord, REQUIRED_HEADERS
from tcp_state import (
    DuplicateStateDate,
    InvalidRevision,
    InvalidStateApp,
    InvalidStateRecord,
    InvalidStateTimestamp,
    LoadResult,
    RevisionConflictError,
    StateLoadError,
    StateMetadataMismatch,
    StateNotFound,
    StatePaths,
    StateValidationError,
    StateWriteError,
    UnsupportedSchemaVersion,
    UnsupportedStateSource,
    build_state_from_ledger,
    load_state,
    save_state,
    serialize_state,
    validate_state,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_STATE_DIR = REPO_ROOT / "tests" / "_tmp_state"
CONFIGURED_ACTIVE = REPO_ROOT / "tcp_daily_returns_secret_state.json"
CONFIGURED_BACKUP = REPO_ROOT / "tcp_daily_returns_secret_state.backup.json"
CONFIGURED_LOCK = REPO_ROOT / "tcp_daily_returns_secret_state.lock"


@pytest.fixture
def state_tmp(request):
    TMP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    path = TMP_STATE_DIR / safe_name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture
def state_paths(state_tmp):
    return StatePaths(
        active_path=state_tmp / "tcp_test_state.json",
        backup_path=state_tmp / "tcp_test_state.backup.json",
        lock_path=state_tmp / "tcp_test_state.lock",
    )


def _sample_record(row_date: str = "2026-01-20", nav: float = 50000.0) -> dict:
    return {
        "Cash Transfers": None,
        "Trading Days": 1,
        "Date": row_date,
        "Cash Balance": 24996.76,
        "NLV": 24996.76,
        "#": 1,
        "$PL": -3.24,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": nav,
        "Loss Carry": 0.0,
        "%Net": -6.48e-05,
        "S net cummulative %": -6.48e-05,
        "HWM": 50000.0,
    }


def _sample_state(**overrides) -> dict:
    records = overrides.pop("records", [_sample_record()])
    state = {
        "schema_version": 1,
        "app": "tcp",
        "revision": 1,
        "updated_at": "2026-07-02T12:00:00+00:00",
        "source": "test",
        "records": records,
        "record_count": len(records),
        "first_completed_date": records[0]["Date"],
        "latest_completed_date": records[-1]["Date"],
    }
    state.update(overrides)
    return state


def _bump_state(state: dict, revision: int) -> dict:
    new_state = deepcopy(state)
    new_state["revision"] = revision
    new_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return new_state


def test_valid_bootstrap_state():
    validate_state(_sample_state(source="excel_bootstrap"))


def test_unsupported_schema_version():
    state = _sample_state(schema_version=99)
    with pytest.raises(UnsupportedSchemaVersion):
        validate_state(state)


def test_wrong_application_name():
    with pytest.raises(InvalidStateApp):
        validate_state(_sample_state(app="tkp"))


def test_invalid_revision():
    with pytest.raises(InvalidRevision):
        validate_state(_sample_state(revision=0))


def test_invalid_timestamp():
    with pytest.raises(InvalidStateTimestamp):
        validate_state(_sample_state(updated_at="not-a-timestamp"))


def test_unsupported_source():
    with pytest.raises(UnsupportedStateSource):
        validate_state(_sample_state(source="manual_import"))


def test_missing_records_envelope_field():
    state = _sample_state()
    del state["records"]
    with pytest.raises(StateValidationError):
        validate_state(state)


def test_metadata_mismatch():
    with pytest.raises(StateMetadataMismatch):
        validate_state(_sample_state(record_count=99))


def test_missing_required_record_field():
    record = _sample_record()
    del record["nav-x1"]
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=[record]))


def test_invalid_record_date():
    record = _sample_record(row_date="bad-date")
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=[record]))


def test_duplicate_date():
    records = [_sample_record("2026-01-20"), _sample_record("2026-01-20", nav=50100.0)]
    with pytest.raises(DuplicateStateDate):
        validate_state(_sample_state(records=records))


def test_out_of_order_dates():
    records = [_sample_record("2026-01-21"), _sample_record("2026-01-20", nav=50100.0)]
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=records))


def test_non_finite_numeric_value():
    record = _sample_record()
    record["nav-x1"] = float("nan")
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=[record]))


def test_invalid_tranche_count():
    record = _sample_record()
    record["#"] = 0
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=[record]))


def test_missing_completed_nav():
    record = _sample_record()
    record["nav-x1"] = None
    with pytest.raises(InvalidStateRecord):
        validate_state(_sample_state(records=[record]))


def test_build_state_does_not_mutate_adapter_records():
    original_fields = {
        header: 1.0 if header not in {"Date", "Cash Transfers"} else None
        for header in REQUIRED_HEADERS
    }
    original_fields["Date"] = date(2026, 1, 20)
    original_fields["nav-x1"] = 50000.0
    original_fields["#"] = 1
    original_fields["Trading Days"] = 1
    before = deepcopy(original_fields)
    record = LedgerRecord(excel_row_number=3, fields=original_fields)
    ledger = LedgerLoadResult(
        candidate_records=(record,),
        completed_records=(record,),
        metadata=LedgerMetadata(
            source_filename="tcp_alex.xlsx",
            sheet_name="NAV",
            header_mapping={"C": "Date", "L": "nav-x1"},
            total_candidate_rows=1,
            completed_row_count=1,
            first_completed_date=date(2026, 1, 20),
            latest_completed_date=date(2026, 1, 20),
            latest_completed_excel_row=3,
        ),
    )
    build_state_from_ledger(ledger)
    assert original_fields == before


def test_deterministic_json_output():
    state = _sample_state()
    first = serialize_state(state)
    second = serialize_state(state)
    assert first == second
    assert first.endswith("\n")


def test_utf8_serialization():
    payload = serialize_state(_sample_state())
    assert "tcp" in payload
    assert payload.encode("utf-8")


def test_nan_infinity_rejection_on_serialize():
    state = _sample_state()
    state["records"][0]["$PL"] = float("inf")
    with pytest.raises((InvalidStateRecord, StateValidationError)):
        serialize_state(state)


def test_datelike_numeric_values_serialize_correctly():
    state = build_state_from_ledger(_ledger_from_records([_ledger_record()]))
    payload = json.loads(serialize_state(state))
    assert payload["records"][0]["Date"] == "2026-01-20"
    assert payload["records"][0]["nav-x1"] == 50000.0


def _ledger_record(row_date: date = date(2026, 1, 20), nav: float = 50000.0) -> LedgerRecord:
    fields = {
        "Cash Transfers": None,
        "Trading Days": 1,
        "Date": row_date,
        "Cash Balance": 24996.76,
        "NLV": 24996.76,
        "#": 1,
        "$PL": -3.24,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": nav,
        "Loss Carry": 0.0,
        "%Net": -6.48e-05,
        "S net cummulative %": -6.48e-05,
        "HWM": 50000.0,
    }
    return LedgerRecord(excel_row_number=3, fields=fields)


def _ledger_from_records(records: list[LedgerRecord]) -> LedgerLoadResult:
    return LedgerLoadResult(
        candidate_records=tuple(records),
        completed_records=tuple(records),
        metadata=LedgerMetadata(
            source_filename="tcp_alex.xlsx",
            sheet_name="NAV",
            header_mapping={"C": "Date", "L": "nav-x1"},
            total_candidate_rows=len(records),
            completed_row_count=len(records),
            first_completed_date=records[0].fields["Date"],
            latest_completed_date=records[-1].fields["Date"],
            latest_completed_excel_row=3,
        ),
    )


def test_first_write_succeeds(state_paths):
    state = _sample_state(source="excel_bootstrap")
    result = save_state(state, state_paths)
    assert result.revision == 1
    assert state_paths.active_path.is_file()
    loaded = load_state(state_paths)
    assert loaded.loaded_from == "active"
    assert loaded.state["revision"] == 1


def test_subsequent_write_creates_valid_backup(state_paths):
    first = _sample_state(source="excel_bootstrap")
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    backup = json.loads(state_paths.backup_path.read_text(encoding="utf-8"))
    assert backup["revision"] == 1
    active = json.loads(state_paths.active_path.read_text(encoding="utf-8"))
    assert active["revision"] == 2


def test_active_state_is_always_valid_json(state_paths):
    save_state(_sample_state(), state_paths)
    json.loads(state_paths.active_path.read_text(encoding="utf-8"))


def test_temp_file_cleaned_after_success(state_paths):
    save_state(_sample_state(), state_paths)
    leftovers = list(state_paths.active_path.parent.glob(f".{state_paths.active_path.name}.*.tmp"))
    assert leftovers == []


def test_temp_file_cleaned_after_simulated_failure(state_paths):
    state = _sample_state()
    with patch("tcp_state.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(StateWriteError):
            save_state(state, state_paths)
    leftovers = list(state_paths.active_path.parent.glob(f".{state_paths.active_path.name}.*.tmp"))
    assert leftovers == []
    assert not state_paths.active_path.exists()


def test_failed_write_preserves_prior_active_state(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    with patch("tcp_state.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(StateWriteError):
            save_state(second, state_paths, expected_revision=1)
    active = json.loads(state_paths.active_path.read_text(encoding="utf-8"))
    assert active["revision"] == 1


def test_failed_write_preserves_prior_valid_backup(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    third = _bump_state(second, revision=3)
    with patch("tcp_state.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(StateWriteError):
            save_state(third, state_paths, expected_revision=2)
    backup = json.loads(state_paths.backup_path.read_text(encoding="utf-8"))
    assert backup["revision"] == 1


def test_successful_changed_state_save_increments_revision_once(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    active = load_state(state_paths).state
    assert active["revision"] == 2


def test_stale_expected_revision_rejected(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    stale = _bump_state(first, revision=2)
    with pytest.raises(RevisionConflictError):
        save_state(stale, state_paths, expected_revision=1)


def test_failed_save_does_not_increment_revision(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    with patch("tcp_state.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(StateWriteError):
            save_state(second, state_paths, expected_revision=1)
    assert load_state(state_paths).state["revision"] == 1


def test_two_competing_writes_from_same_revision(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    barrier = threading.Barrier(2)
    results: list = []

    def worker():
        barrier.wait()
        try:
            save_state(_bump_state(first, revision=2), state_paths, expected_revision=1)
            results.append("ok")
        except RevisionConflictError:
            results.append("conflict")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("ok") == 1
    assert results.count("conflict") == 1
    assert load_state(state_paths).state["revision"] == 2


def test_valid_active_state_loads(state_paths):
    save_state(_sample_state(), state_paths)
    loaded = load_state(state_paths)
    assert loaded.loaded_from == "active"
    assert loaded.recovery is None


def test_missing_active_state_is_explicit(state_paths):
    with pytest.raises(StateNotFound):
        load_state(state_paths)


def test_corrupt_active_valid_backup_recovers(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    state_paths.active_path.write_text("{not json", encoding="utf-8")
    loaded = load_state(state_paths)
    assert loaded.loaded_from == "backup"
    assert loaded.recovery == "backup_recovery"
    assert loaded.state["revision"] == 1


def test_invalid_active_and_invalid_backup_fail_clearly(state_paths):
    state_paths.active_path.write_text("{bad", encoding="utf-8")
    state_paths.backup_path.write_text("{also bad", encoding="utf-8")
    with pytest.raises(StateLoadError) as excinfo:
        load_state(state_paths)
    message = str(excinfo.value)
    assert "Active state invalid" in message
    assert "backup unavailable or invalid" in message


def test_recovery_does_not_overwrite_active_automatically(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    state_paths.active_path.write_text("{bad", encoding="utf-8")
    load_state(state_paths)
    assert state_paths.active_path.read_text(encoding="utf-8") == "{bad"


def test_backup_recovery_labeled_in_metadata(state_paths):
    first = _sample_state()
    save_state(first, state_paths)
    second = _bump_state(first, revision=2)
    save_state(second, state_paths, expected_revision=1)
    state_paths.active_path.write_text("{bad", encoding="utf-8")
    loaded = load_state(state_paths)
    assert loaded.public_dict()["recovery"] == "backup_recovery"


def test_tcp_state_paths_do_not_collide_with_tkp():
    cfg = load_config()
    assert cfg.state_filename != "daily_returns_secret_state.json"
    assert cfg.state_backup_filename != "daily_returns_secret_state.json"
    assert cfg.lock_filename != "daily_returns_secret_state.json"


def test_tests_never_touch_configured_active_state(state_paths):
    assert state_paths.active_path.resolve() != CONFIGURED_ACTIVE.resolve()
    assert state_paths.backup_path.resolve() != CONFIGURED_BACKUP.resolve()
    assert state_paths.lock_path.resolve() != CONFIGURED_LOCK.resolve()


def test_import_tcp_state_creates_no_files():
    import tcp_state  # noqa: F401

    assert not CONFIGURED_ACTIVE.exists()


def test_no_workbook_modified_by_state_layer(golden_fixture, state_tmp):
    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")
    before = wb_path.stat()
    noop = state_tmp / "noop"
    noop.mkdir(exist_ok=True)
    save_state(
        _sample_state(),
        StatePaths(
            active_path=noop / "state.json",
            backup_path=noop / "backup.json",
            lock_path=noop / "state.lock",
        ),
    )
    after = wb_path.stat()
    assert before.st_size == after.st_size


def test_no_production_module_imports_in_tcp_state_source():
    source = (REPO_ROOT / "tcp_state.py").read_text(encoding="utf-8")
    assert "import tcp_ts" not in source
    assert "import tkp_ts" not in source


@pytest.mark.local_workbook
def test_local_workbook_builds_valid_bootstrap_state(golden_fixture):
    from tcp_ledger import load_ledger

    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")
    ledger = load_ledger(str(wb_path))
    state = build_state_from_ledger(ledger)
    validate_state(state)
    assert state["record_count"] == 112
    assert state["latest_completed_date"] == "2026-06-24"
    assert "workbook_path" not in json.dumps(state)


def test_state_metadata_matches_adapter_metadata(golden_fixture):
    from tcp_ledger import load_ledger

    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")
    ledger = load_ledger(str(wb_path))
    state = build_state_from_ledger(ledger)
    assert state["record_count"] == ledger.metadata.completed_row_count
    assert state["first_completed_date"] == ledger.metadata.first_completed_date.isoformat()
    assert state["latest_completed_date"] == ledger.metadata.latest_completed_date.isoformat()
    assert state["source_workbook_filename"] == ledger.metadata.source_filename
    assert state["source_sheet"] == ledger.metadata.sheet_name


def test_golden_fixture_ledger_builds_valid_state(golden_fixture):
    records = []
    for row in golden_fixture["rows"]:
        fields = {
            name: evidence["observed_value"]
            for name, evidence in row["columns"].items()
        }
        fields["Date"] = date.fromisoformat(row["date"])
        records.append(LedgerRecord(excel_row_number=row["excel_row_number"], fields=fields))
    ledger = _ledger_from_records(records)
    state = build_state_from_ledger(ledger)
    validate_state(state)
    assert state["revision"] == 1
    assert state["source"] == "excel_bootstrap"


def test_state_canary_end_to_end(state_tmp):
    """Disposable directory canary from Step 5 validation spec."""
    from tcp_ledger import load_ledger

    canary_dir = state_tmp / "canary"
    canary_dir.mkdir(exist_ok=True)
    paths = StatePaths(
        active_path=canary_dir / "state.json",
        backup_path=canary_dir / "state.backup.json",
        lock_path=canary_dir / "state.lock",
    )
    cfg = load_config()
    wb_path = Path(cfg.workbook_path)
    if not wb_path.is_file():
        ledger = _ledger_from_records([_ledger_record(), _ledger_record(date(2026, 1, 21), 50100.0)])
    else:
        ledger = load_ledger(str(wb_path))

    bootstrap = build_state_from_ledger(ledger)
    save_state(bootstrap, paths)
    loaded_one = load_state(paths)
    assert loaded_one.state["revision"] == 1

    changed = deepcopy(loaded_one.state)
    changed["revision"] = 2
    changed["updated_at"] = datetime.now(timezone.utc).isoformat()
    changed["source"] = "test"
    save_state(changed, paths, expected_revision=1)
    active_two = load_state(paths).state
    assert active_two["revision"] == 2
    backup = json.loads(paths.backup_path.read_text(encoding="utf-8"))
    assert backup["revision"] == 1

    stale = deepcopy(changed)
    stale["revision"] = 3
    with pytest.raises(RevisionConflictError):
        save_state(stale, paths, expected_revision=1)

    paths.active_path.write_text("{corrupt", encoding="utf-8")
    recovered = load_state(paths)
    assert recovered.loaded_from == "backup"
    assert recovered.state["revision"] == 1

    for child in canary_dir.iterdir():
        child.unlink()
    canary_dir.rmdir()
    assert not CONFIGURED_ACTIVE.exists()
