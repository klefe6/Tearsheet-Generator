"""Y&Q data-current helpers — source-derived labels, no first-Monday heuristic."""
from datetime import date
from pathlib import Path

import pandas as pd

from yq_data_current import (
    DEFAULT_REPO_ROOT_CSV,
    expected_latest_closed_month,
    format_yq_data_current_label,
    format_yq_statistics_range,
    max_valid_period,
    resolve_yq_csv_path,
    yq_source_is_stale,
    yq_stale_warning_text,
)


def test_resolve_yq_csv_path_env_override(tmp_path):
    csv = tmp_path / "custom.csv"
    csv.write_text("x", encoding="utf-8")
    resolved = resolve_yq_csv_path(env={"YQ_CSV_PATH": str(csv)}, module_dir=tmp_path)
    assert resolved == csv.resolve()


def test_resolve_yq_csv_path_sibling_then_repo_root(tmp_path):
    sibling = tmp_path / "yq.csv"
    sibling.write_text("x", encoding="utf-8")
    assert resolve_yq_csv_path(env={}, module_dir=tmp_path) == sibling.resolve()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert resolve_yq_csv_path(env={}, module_dir=empty) == DEFAULT_REPO_ROOT_CSV.resolve()


def test_format_label_from_source_period():
    assert format_yq_data_current_label("2026-05-01") == "Data current through May 2026"


def test_statistics_range_uses_actual_bounds():
    text = format_yq_statistics_range("2011-04-01", "2026-05-01")
    assert "April 2011" in text
    assert "May 2026" in text
    assert "April 2026" not in text


def test_stale_when_older_than_prior_month():
    assert yq_source_is_stale("2026-05-01", as_of=date(2026, 7, 30)) is True
    assert yq_source_is_stale("2026-06-01", as_of=date(2026, 7, 30)) is False
    assert yq_source_is_stale("2026-07-01", as_of=date(2026, 7, 30)) is False


def test_expected_latest_closed_month():
    assert expected_latest_closed_month(date(2026, 7, 30)) == pd.Timestamp("2026-06-01")


def test_stale_warning_mentions_source_month():
    text = yq_stale_warning_text("2026-05-01")
    assert "May 2026" in text
    assert "monthly" in text.lower()


def test_max_valid_period():
    idx = pd.to_datetime(["2011-04-01", "2026-05-01"])
    assert max_valid_period(idx) == pd.Timestamp("2026-05-01")


def test_no_first_monday_helpers_in_module_source():
    source = Path(__file__).resolve().parents[1] / "yq_data_current.py"
    text = source.read_text(encoding="utf-8")
    assert "first_monday" not in text
    assert "weekday" not in text
