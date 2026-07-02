"""Tests for TCP v2 state seed script."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.seed_tcp_state import main as seed_main
from tcp_config import load_config
from tcp_state import StatePaths, validate_state

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT / ".venv310" / "Scripts" / "python.exe"
TMP_DIR = REPO_ROOT / "tests" / "_tmp_state"


@pytest.fixture
def seed_tmp(request):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.node.name)
    path = TMP_DIR / f"seed_{safe}"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(scope="session")
def workbook_available():
    cfg = load_config()
    if not Path(cfg.workbook_path).is_file():
        pytest.skip("TCP workbook not available")
    return cfg


def _output(seed_tmp: Path) -> Path:
    return seed_tmp / "seeded_state.json"


def test_dry_run_writes_nothing(seed_tmp, workbook_available, capsys):
    code = seed_main(
        [
            "--dry-run",
            "--output",
            str(_output(seed_tmp)),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    assert code == 0
    assert not _output(seed_tmp).exists()
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "row_count=112" in out


def test_seed_produces_revision_one(seed_tmp, workbook_available):
    output = _output(seed_tmp)
    code = seed_main(
        [
            "--seed",
            "--output",
            str(output),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    assert code == 0
    state = json.loads(output.read_text(encoding="utf-8"))
    validate_state(state)
    assert state["revision"] == 1
    assert len(state["records"]) == 112
    assert state["records"][-1]["Date"] == "2026-06-24"
    assert abs(float(state["records"][-1]["nav-x1"]) - 44871.384) < 1e-3
    assert load_config().workbook_path not in output.read_text(encoding="utf-8")


def test_wrong_row_count_aborts(seed_tmp, workbook_available):
    with pytest.raises(SystemExit):
        seed_main(
            [
                "--dry-run",
                "--output",
                str(_output(seed_tmp)),
                "--expected-row-count",
                "99",
            ]
        )


def test_existing_output_refuses_overwrite(seed_tmp, workbook_available):
    output = _output(seed_tmp)
    code = seed_main(
        [
            "--seed",
            "--output",
            str(output),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    assert code == 0
    with pytest.raises(SystemExit):
        seed_main(
            [
                "--seed",
                "--output",
                str(output),
                "--expected-row-count",
                "112",
                "--expected-latest-date",
                "2026-06-24",
                "--expected-latest-nav",
                "44871.384",
            ]
        )


def test_replace_existing_creates_backup(seed_tmp, workbook_available):
    output = _output(seed_tmp)
    backup = output.with_name(output.stem + ".backup.json")
    seed_main(
        [
            "--seed",
            "--output",
            str(output),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    code = seed_main(
        [
            "--seed",
            "--replace-existing",
            "--output",
            str(output),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    assert code == 0
    assert backup.is_file()
    backup_state = json.loads(backup.read_text(encoding="utf-8"))
    assert backup_state["revision"] == 1
    active_state = json.loads(output.read_text(encoding="utf-8"))
    assert active_state["revision"] == 1


@pytest.mark.local_workbook
def test_workbook_unchanged_by_seed(seed_tmp, workbook_available):
    cfg = workbook_available
    wb = Path(cfg.workbook_path)
    before = hashlib.sha256(wb.read_bytes()).hexdigest()
    seed_main(
        [
            "--seed",
            "--output",
            str(_output(seed_tmp)),
            "--expected-row-count",
            "112",
            "--expected-latest-date",
            "2026-06-24",
            "--expected-latest-nav",
            "44871.384",
        ]
    )
    after = hashlib.sha256(wb.read_bytes()).hexdigest()
    assert before == after
