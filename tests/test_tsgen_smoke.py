"""First direct test coverage for tsgen.py (generic tearsheet app, port 8077).

tsgen reads Trade_Results.csv through a HARDCODED absolute path at import
time (the same coupling documented for run_tsgen.bat in docs/REPO_MAP.md
section 2), so every test here skips with an explanation when that file is
absent. Benchmark downloads live only inside callbacks — importing tsgen
does not require network access.

Run from the repo root, per docs/REPO_MAP.md section 6:
    .venv310\\Scripts\\python.exe -m pytest tests/test_tsgen_smoke.py -q
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def _import_tsgen():
    try:
        import tsgen

        return tsgen
    except FileNotFoundError as exc:
        pytest.skip(f"tsgen requires machine-local data at a hardcoded path: {exc}")


def test_tsgen_module_imports_and_exposes_app():
    tsgen = _import_tsgen()
    assert tsgen.app is not None
    assert tsgen.app.server is not None
    assert tsgen.app.layout is not None


def test_tsgen_returns_series_loaded():
    tsgen = _import_tsgen()
    assert len(tsgen.rets) > 0
    assert tsgen.MIN_DATE < tsgen.MAX_DATE


def test_tsgen_strategy_map_consistent():
    tsgen = _import_tsgen()
    assert tsgen.strategy_map, "strategy_map should list the built-in programs"
    # Every preset fee schedule must point at a known strategy path.
    for path in tsgen.preset_fees:
        assert path in tsgen.strategy_map.values()
