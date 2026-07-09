"""First direct test coverage for the Y&Q tearsheet (yq_ts.py, port 8303).

yq_ts reads yq.csv (machine-local, gitignored) at import time and calls
sys.exit(1) if it cannot load — so every test here is skipped with an
explanation when the data file is absent (fresh clones / CI).

yq_ts also attempts benchmark downloads via yfinance at module level, but
each symbol is wrapped in its own try/except and degrades to a warning, so
no network is REQUIRED for these tests (they are merely slower online).

Run from the repo root, per docs/REPO_MAP.md section 6:
    .venv310\\Scripts\\python.exe -m pytest tests/test_yq_smoke.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
YQ_CSV = REPO_ROOT / "yq.csv"

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not YQ_CSV.exists(),
        reason=(
            "yq.csv is machine-local (gitignored); yq_ts.py sys.exit(1)s at "
            "import when it is absent"
        ),
    ),
]


def _import_yq():
    try:
        import yq_ts

        return yq_ts
    except SystemExit as exc:  # yq_ts exits rather than raising on bad data
        pytest.skip(f"yq_ts exited at import (unloadable machine-local data): {exc}")


def test_yq_module_imports_and_exposes_app():
    yq_ts = _import_yq()
    assert yq_ts.app is not None
    assert yq_ts.app.server is not None
    assert "Blue Whale" in yq_ts.app.title


def test_yq_nav_data_loaded():
    yq_ts = _import_yq()
    assert not yq_ts.NAV_df.empty
    assert "nav-x1" in yq_ts.NAV_df.columns
    # NAV values are a compounded equity curve — all positive by construction.
    assert (yq_ts.NAV_df["nav-x1"] > 0).all()


def test_yq_serve_layout_builds():
    yq_ts = _import_yq()
    layout = yq_ts.serve_layout()
    assert layout is not None
    # A real page tree, not an error stub.
    assert len(str(layout)) > 1000
