#!/usr/bin/env python3
"""Read-only TCP v2 production cutover preflight CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.tcp_cutover_preflight import DEFAULT_GIT_TIMEOUT_SECONDS, EXIT_ERROR, run_preflight  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TCP v2 production cutover preflight (read-only)")
    parser.add_argument("--check", action="store_true", help="Run preflight checks (default)")
    parser.add_argument("--json-output", type=Path, help="Write redacted JSON report to path")
    parser.add_argument("--expected-branch", default="feature/tcp-v2-migration")
    parser.add_argument("--expected-commit", default="7de8ba1")
    parser.add_argument("--workbook-path", type=Path)
    parser.add_argument("--state-path", type=Path, help="Production state directory (parent of active JSON)")
    parser.add_argument("--production-port", type=int, default=8302)
    parser.add_argument("--preview-port", type=int, default=8312)
    parser.add_argument("--production-ready", action="store_true", help="Require production secrets and json_active")
    parser.add_argument("--skip-parent", action="store_true", help="Skip parent-repository pointer checks")
    parser.add_argument(
        "--git-timeout",
        type=float,
        default=DEFAULT_GIT_TIMEOUT_SECONDS,
        help="Timeout in seconds for git/network subprocess checks (default: 15)",
    )
    args = parser.parse_args(argv)

    report = run_preflight(
        expected_branch=args.expected_branch,
        expected_commit=args.expected_commit,
        workbook_path=args.workbook_path,
        state_base=args.state_path,
        production_port=args.production_port,
        preview_port=args.preview_port,
        production_ready=args.production_ready,
        check_parent=not args.skip_parent,
        git_timeout_seconds=args.git_timeout,
    )

    payload = report.to_dict()
    if args.json_output:
        args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"VERDICT={report.verdict}")
    print(f"EXIT_CODE={report.exit_code}")
    print(f"PASS={len(report.passes)}")
    print(f"WARNING={len(report.warnings)}")
    print(f"BLOCKER={len(report.blockers)}")
    for item in report.blockers:
        print(f"BLOCKER={item}")
    for item in report.warnings:
        print(f"WARNING={item}")

    if report.exit_code == EXIT_ERROR:
        return EXIT_ERROR
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
