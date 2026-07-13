"""Non-production Y&Q import validation using temporary fixture CSV.

yq_ts.py loads ``yq.csv`` at import time and calls ``sys.exit(1)`` when the
file is missing or invalid. Clean clones (including the reorg prep worktree)
therefore cannot import the module without machine-local data.

This test redirects ``pandas.read_csv`` to a minimal synthetic CSV in a
pytest-owned ``tmp_path`` directory. No production file is created or modified.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_YQ_CSV = REPO_ROOT / "yq.csv"
YQ_MODULE_PATH = REPO_ROOT / "yq_ts.py"

MINIMAL_YQ_CSV = """Year(yyyy),Month(mm),Actual ROR (%)
2024,1,1.0
2024,2,0.5
2024,3,-0.25
"""


@pytest.fixture
def yq_fixture_csv(tmp_path: Path) -> Path:
    path = tmp_path / "yq.csv"
    path.write_text(MINIMAL_YQ_CSV, encoding="latin-1")
    return path


def test_yq_imports_with_temporary_fixture_csv(yq_fixture_csv: Path, monkeypatch) -> None:
    """Prove yq_ts initializes from synthetic data without live yq.csv."""
    if EXPECTED_YQ_CSV.exists():
        pytest.skip(
            "live yq.csv present in worktree; fixture redirect targets clean clones"
        )

    real_read_csv = pd.read_csv

    def redirect_read_csv(filepath_or_buffer, *args, **kwargs):
        path = Path(str(filepath_or_buffer))
        if path.name == "yq.csv":
            return real_read_csv(yq_fixture_csv, *args, **kwargs)
        return real_read_csv(filepath_or_buffer, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", redirect_read_csv)
    sys.modules.pop("yq_ts", None)

    yq_ts = importlib.import_module("yq_ts")

    assert yq_ts.app is not None
    assert yq_ts.app.server is not None
    assert not yq_ts.NAV_df.empty
    assert "nav-x1" in yq_ts.NAV_df.columns
    assert (yq_ts.NAV_df["nav-x1"] > 0).all()
    layout = yq_ts.serve_layout()
    assert layout is not None
    assert len(str(layout)) > 500


def test_yq_production_port_remains_8303() -> None:
    """Contract check: Y&Q bind port is still hardcoded at 8303."""
    source = YQ_MODULE_PATH.read_text(encoding="utf-8")
    assert "app.run(debug=True, port=8303)" in source
