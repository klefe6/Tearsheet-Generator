#!/usr/bin/env python3
"""TCP v2 three-way parity and resilience acceptance harness (read-only by default)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.tcp_acceptance import (  # noqa: E402
    collect_excel_baseline,
    collect_json_baseline,
    kevin_decision_table,
    run_parity_acceptance,
)


def _default_state_path() -> Path:
    from tcp_config import load_config, resolve_state_paths

    cfg = load_config()
    active, _, _ = resolve_state_paths(cfg, REPO_ROOT)
    return active


def cmd_parity(args: argparse.Namespace) -> int:
    state_path = Path(args.state_path) if args.state_path else _default_state_path()
    report = run_parity_acceptance(
        state_path=state_path,
        v1_source=args.v1_source,
        include_v1=not args.skip_v1,
    )
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    print(f"VERDICT={report.verdict}")
    print(f"ROWS_COMPARED={report.row_summary.get('rows_compared')}")
    print(f"ROWS_MATCHED={report.row_summary.get('rows_matched')}")
    print(f"ROWS_MISMATCHED={report.row_summary.get('rows_mismatched')}")
    print(f"BLOCKERS={len(report.blockers)}")
    for blocker in report.blockers:
        print(f"BLOCKER={blocker}")
    return 0 if report.verdict == "PASS" else 1


def cmd_report(args: argparse.Namespace) -> int:
    state_path = Path(args.state_path) if args.state_path else _default_state_path()
    report = run_parity_acceptance(state_path=state_path, v1_source=args.v1_source)
    excel = collect_excel_baseline()
    v2 = collect_json_baseline(state_path)
    decisions = kevin_decision_table(report)
    output = {
        "parity": report.to_dict(),
        "excel_checksum": excel["workbook_checksum"],
        "v2_checksum": v2["state_checksum"],
        "kevin_decisions": decisions,
    }
    text = json.dumps(output, indent=2)
    if args.json_output:
        Path(args.json_output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.verdict == "PASS" else 1


def cmd_resilience(_args: argparse.Namespace) -> int:
    import pytest

    code = pytest.main(["-q", str(REPO_ROOT / "tests" / "test_tcp_resilience_acceptance.py")])
    return 0 if code == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TCP v2 acceptance harness")
    sub = parser.add_subparsers(dest="command", required=True)

    parity = sub.add_parser("parity", help="Run read-only three-way parity acceptance")
    parity.add_argument("--state-path")
    parity.add_argument("--v1-source", default="head", choices=["head", "working-tree"])
    parity.add_argument("--skip-v1", action="store_true")
    parity.add_argument("--json-output")
    parity.set_defaults(func=cmd_parity)

    report = sub.add_parser("report", help="Full parity report with Kevin decision table")
    report.add_argument("--state-path")
    report.add_argument("--v1-source", default="head", choices=["head", "working-tree"])
    report.add_argument("--json-output")
    report.set_defaults(func=cmd_report)

    resilience = sub.add_parser("resilience", help="Run resilience acceptance tests")
    resilience.set_defaults(func=cmd_resilience)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
