#!/usr/bin/env python3
"""Subprocess-isolated import smoke for every tearsheet app.

Each app is imported in its OWN Python subprocess so that:

- import-time side effects (workbook/CSV reads, yfinance fetches) stay isolated;
- the sys.modules purity constraints in the pytest suite are never violated
  (this script imports tkp_ts/tcp-adjacent modules only in child processes);
- one broken app cannot mask another.

No servers are started (every app guards ``app.run`` under ``__main__``),
nothing is written to production state, and missing machine-local data is
reported as SKIP rather than FAIL so the harness is meaningful on fresh
clones as well as on the ops machine.

Usage (from the repo root):

    .venv310\\Scripts\\python.exe scripts\\smoke_all.py
    .venv310\\Scripts\\python.exe scripts\\smoke_all.py --only yq_ts,tsgen

Exit code 0 = no FAIL results (SKIPs are allowed); 1 = at least one FAIL.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# stderr fragments that mean "machine-local data is absent", not "app broken".
SKIP_SIGNATURES = (
    "FileNotFoundError",
    "No such file or directory",
    "Failed to load CSV data",  # yq_ts prints this then sys.exit(1)s
)

# stderr fragments that usually mean a transient network problem (yfinance).
NETWORK_SIGNATURES = (
    "ConnectionError",
    "Max retries exceeded",
    "curl: (28)",
    "Read timed out",
    "KeyError: 'SPXTR'",  # tkp_ts symptom when the ^SP500TR fetch fails
)


@dataclass
class SmokeCheck:
    name: str
    code: str
    timeout: int = 180
    retries: int = 0  # extra attempts for network-flaky imports
    note: str = ""


CHECKS = [
    SmokeCheck(
        name="tcp_ts_v2",
        code=(
            "import tcp_ts_v2; "
            "assert callable(tcp_ts_v2.create_app); "
            "print('OK tcp_ts_v2')"
        ),
        note="side-effect-free import (enforced by test_tcp_v2_shell)",
    ),
    SmokeCheck(
        name="tkp_ts",
        code=(
            "import tkp_ts; "
            "assert tkp_ts.app is not None; "
            "assert tkp_ts.app.server is not None; "
            "print('OK tkp_ts')"
        ),
        timeout=300,
        retries=1,
        note="reads NAV workbook + live ^SP500TR fetch at import; retried once",
    ),
    SmokeCheck(
        name="mp_ts (AGM)",
        code=(
            "import sys; sys.path.insert(0, 'Momentum Pacer'); "
            "import mp_ts; "
            "assert mp_ts.app is not None; "
            "assert mp_ts.serve_layout() is not None; "
            "print('OK mp_ts')"
        ),
        timeout=300,
        note="AGM_BENCHMARK_CACHE_ONLY=1 forces offline benchmark cache",
    ),
    SmokeCheck(
        name="yq_ts",
        code=(
            "import yq_ts; "
            "assert yq_ts.app is not None; "
            "assert not yq_ts.NAV_df.empty; "
            "print('OK yq_ts')"
        ),
        timeout=300,
        note="needs machine-local yq.csv; benchmark fetches degrade offline",
    ),
    SmokeCheck(
        name="tsgen",
        code=(
            "import tsgen; "
            "assert tsgen.app is not None; "
            "assert len(tsgen.rets) > 0; "
            "print('OK tsgen')"
        ),
        note="needs Trade_Results.csv at its hardcoded absolute path",
    ),
    SmokeCheck(
        name="Gold_Maker_ts",
        code=(
            "import Gold_Maker_ts; "
            "assert Gold_Maker_ts.app is not None; "
            "print('OK Gold_Maker_ts')"
        ),
        timeout=300,
        note="needs machine-local GLD_Maker_VADI.csv (absolute path)",
    ),
]


def run_check(check: SmokeCheck) -> tuple[str, str]:
    """Return (status, detail) where status is PASS / SKIP / FAIL."""
    env = dict(os.environ)
    env.setdefault("AGM_BENCHMARK_CACHE_ONLY", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    attempts = check.retries + 1
    detail = ""
    for attempt in range(1, attempts + 1):
        try:
            # Children emit UTF-8 (PYTHONIOENCODING above); decode explicitly so
            # a cp1252 parent console never throws in the reader thread.
            proc = subprocess.run(
                [sys.executable, "-c", check.code],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=check.timeout,
            )
        except subprocess.TimeoutExpired:
            detail = f"timed out after {check.timeout}s (attempt {attempt}/{attempts})"
            continue

        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            return "PASS", f"attempt {attempt}/{attempts}"
        if any(sig in output for sig in SKIP_SIGNATURES):
            last_lines = [l for l in output.strip().splitlines() if l.strip()][-2:]
            return "SKIP", "missing machine-local data: " + " | ".join(last_lines)
        if any(sig in output for sig in NETWORK_SIGNATURES) and attempt < attempts:
            detail = "transient network failure, retrying"
            continue
        last_lines = [l for l in output.strip().splitlines() if l.strip()][-3:]
        detail = " | ".join(last_lines) or f"exit code {proc.returncode}"
    return "FAIL", detail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tearsheet app import smoke")
    parser.add_argument(
        "--only",
        help="comma-separated subset of check names (substring match), e.g. yq_ts,tsgen",
    )
    args = parser.parse_args(argv)

    checks = CHECKS
    if args.only:
        wanted = [w.strip().lower() for w in args.only.split(",") if w.strip()]
        checks = [c for c in CHECKS if any(w in c.name.lower() for w in wanted)]
        if not checks:
            print(f"No checks match --only {args.only!r}")
            return 1

    # ASCII-only output: the ops console is often cp1252.
    print(f"Tearsheet smoke harness - {len(checks)} app import checks, repo {REPO_ROOT}")
    failures = 0
    for check in checks:
        status, detail = run_check(check)
        if status == "FAIL":
            failures += 1
        line = f"[{status:4}] {check.name}"
        if detail:
            line += f" - {detail}"
        if check.note and status != "PASS":
            line += f" (note: {check.note})"
        print(line.encode("ascii", "replace").decode("ascii"))

    print(f"Result: {'FAIL' if failures else 'OK'} ({failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
