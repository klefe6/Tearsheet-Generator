"""Isolated worker: extract v1 dashboard snapshot without starting the server."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    v1_path = Path(sys.argv[1])
    import contextlib
    import io

    # Prevent benchmark network calls
    import types

    mock_utils = types.ModuleType("utils")

    def _empty_returns(_symbol: str) -> pd.Series:
        return pd.Series(dtype=float)

    mock_utils.download_returns = _empty_returns  # type: ignore[attr-defined]
    sys.modules["utils"] = mock_utils

    import importlib.util

    spec = importlib.util.spec_from_file_location("tcp_ts_v1_snapshot", v1_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load v1 module")
    mod = importlib.util.module_from_spec(spec)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        spec.loader.exec_module(mod)

    latest_date = mod.NAV_df.index.max().date().isoformat()
    payload = {
        "nav_chart_points": int(len(mod.NAV_df)),
        "latest_nav": float(mod.NAV_df[mod.NAV_col].iloc[-1]),
        "latest_date": latest_date,
        "label_date_line": f"{pd.Timestamp(latest_date).strftime('%B %d, %Y')} close",
        "monthly_df": mod.monthly_df.to_dict(),
        "daily_df": mod.daily_perf_df.to_dict(),
        "baseline_amount_constant": getattr(mod, "BASELINE_AMOUNT", None),
        "override_months": ["2025-04", "2025-10"],
        "has_daily_returns_table": "Daily Returns" in str(mod.dynamic_layout),
        "percentage_nav_axis": False,
        "product_name": "The Crypto Program",
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
