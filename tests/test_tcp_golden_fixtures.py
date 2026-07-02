"""Golden-row fixture schema and evidence integrity tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from tcp_test_constants import GOLDEN_FIXTURE_PATH, REQUIRED_LEDGER_FIELDS

REQUIRED_ROW_KEYS = {
    "excel_row_number",
    "dataframe_index",
    "prior_excel_row_number",
    "date",
    "scenarios",
    "columns",
    "notes",
}

REQUIRED_COLUMN_EVIDENCE_KEYS = {
    "excel_column",
    "observed_value",
    "excel_formula",
    "number_format",
    "confidence",
}

EXPECTED_GOLDEN_ROWS = [3, 4, 6, 7, 8, 10, 16, 17, 114]


def test_fixture_contains_all_audited_golden_rows(golden_fixture: dict):
    excel_rows = [r["excel_row_number"] for r in golden_fixture["rows"]]
    assert excel_rows == EXPECTED_GOLDEN_ROWS


def test_row_schema(golden_fixture: dict):
    for row in golden_fixture["rows"]:
        missing = REQUIRED_ROW_KEYS - row.keys()
        assert not missing, f"Row {row.get('excel_row_number')} missing keys: {missing}"
        assert row["date"]
        assert row["scenarios"]
        assert isinstance(row["columns"], dict)


def test_column_schema_and_required_ledger_fields(golden_fixture: dict):
    for row in golden_fixture["rows"]:
        cols = row["columns"]
        missing_fields = set(REQUIRED_LEDGER_FIELDS) - set(cols.keys())
        assert not missing_fields, (
            f"Row {row['excel_row_number']} missing ledger fields: {missing_fields}"
        )
        for name, evidence in cols.items():
            missing_evidence = REQUIRED_COLUMN_EVIDENCE_KEYS - evidence.keys()
            assert not missing_evidence, (
                f"Row {row['excel_row_number']} col {name} missing: {missing_evidence}"
            )


def test_formula_evidence_captured_for_calculated_columns(golden_fixture: dict):
    """Formula-driven cells should record excel_formula on representative rows."""
    row4 = next(r for r in golden_fixture["rows"] if r["excel_row_number"] == 4)
    assert row4["columns"]["$PL"]["excel_formula"] is not None
    assert row4["columns"]["nav-x1"]["excel_formula"] is not None
    assert row4["columns"]["Inc. Fee"]["excel_formula"] is not None


def test_dataframe_index_matches_excel_row(golden_fixture: dict):
    for row in golden_fixture["rows"]:
        assert row["dataframe_index"] == row["excel_row_number"] - 2


def test_tranche_change_row_documents_unit_count(golden_fixture: dict):
    row16 = next(r for r in golden_fixture["rows"] if r["excel_row_number"] == 16)
    assert row16["columns"]["#"]["observed_value"] == 2
    assert row16["columns"]["Cash Transfers"]["observed_value"] == 25000
    row4 = next(r for r in golden_fixture["rows"] if r["excel_row_number"] == 4)
    assert row4["columns"]["#"]["observed_value"] == 1


def test_no_speculative_python_expected_values(golden_fixture: dict):
    """Fixtures must not embed Python-computed expected_* fields."""
    raw = GOLDEN_FIXTURE_PATH.read_text(encoding="utf-8")
    assert "expected_value" not in raw
    assert "python_formula" not in raw


@pytest.mark.local_workbook
def test_optional_formula_strings_match_workbook(golden_fixture: dict):
    wb_path = Path(golden_fixture["metadata"]["workbook_path"])
    if not wb_path.is_file():
        pytest.skip(f"Local workbook not available: {wb_path}")

    import openpyxl

    wb = openpyxl.load_workbook(wb_path, data_only=False, read_only=True)
    try:
        ws = wb["NAV"]
        for row in golden_fixture["rows"]:
            excel_row = row["excel_row_number"]
            for _name, col_data in row["columns"].items():
                fixture_formula = col_data["excel_formula"]
                if fixture_formula is None:
                    continue
                letter = col_data["excel_column"]
                current = ws[f"{letter}{excel_row}"].value
                assert current == fixture_formula, (
                    f"Row {excel_row} {letter}: formula drift"
                )
    finally:
        wb.close()
