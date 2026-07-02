#!/usr/bin/env python3
"""
One-time TCP v2 JSON state seed from the validated workbook ledger.

Does not modify Excel, start Dash, or write TKP state.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tcp_config import TKP_STATE_FILENAME, load_config, resolve_state_paths, validate_config  # noqa: E402
from tcp_ledger import TCPLedgerError, load_ledger  # noqa: E402
from tcp_runtime_state import bootstrap_state_from_workbook  # noqa: E402
from tcp_state import StatePaths, save_state, serialize_state, validate_state  # noqa: E402


def _checksum(state: dict) -> str:
    return hashlib.sha256(serialize_state(state).encode("utf-8")).hexdigest()


def _reject_unsafe_output(path: Path, cfg) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if normalized.endswith(".xlsx") or normalized.endswith(".xls"):
        raise SystemExit("Output path must not point at a workbook.")
    if path.name == TKP_STATE_FILENAME:
        raise SystemExit("Output path collides with TKP state.")
    if "_runtime" in normalized and "tests" not in normalized:
        raise SystemExit("Output path must not point into _runtime.")
    workbook_name = Path(cfg.workbook_path).name.lower()
    if path.name.lower() == workbook_name:
        raise SystemExit("Output path must not point at the workbook.")


def _report_dry_run(state: dict, output: Path, cfg) -> None:
    records = state["records"]
    print("DRY RUN — no files written")
    print(f"row_count={len(records)}")
    print(f"first_date={records[0]['Date']}")
    print(f"latest_date={records[-1]['Date']}")
    print(f"latest_nav={records[-1]['nav-x1']}")
    print(f"revision={state['revision']}")
    print(f"output_filename={output.name}")
    print(f"source_workbook={state.get('source_workbook_filename')}")
    print(f"sheet={state.get('source_sheet')}")
    print(f"checksum={_checksum(state)}")


def _validate_expectations(state: dict, args: argparse.Namespace) -> None:
    records = state["records"]
    if args.expected_row_count is not None and len(records) != args.expected_row_count:
        raise SystemExit(
            f"Expected row count {args.expected_row_count}, got {len(records)}"
        )
    if args.expected_latest_date and records[-1]["Date"] != args.expected_latest_date:
        raise SystemExit(
            f"Expected latest date {args.expected_latest_date}, got {records[-1]['Date']}"
        )
    if args.expected_latest_nav is not None:
        actual = float(records[-1]["nav-x1"])
        if abs(actual - float(args.expected_latest_nav)) > 1e-6:
            raise SystemExit(
                f"Expected latest NAV {args.expected_latest_nav}, got {actual}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed TCP v2 JSON state from workbook ledger.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing.")
    parser.add_argument("--seed", action="store_true", help="Perform the seed write.")
    parser.add_argument("--output", type=Path, help="Active state output path.")
    parser.add_argument("--replace-existing", action="store_true", help="Allow replacing existing active state.")
    parser.add_argument("--expected-row-count", type=int)
    parser.add_argument("--expected-latest-date")
    parser.add_argument("--expected-latest-nav", type=float)
    args = parser.parse_args(argv)

    if not args.dry_run and not args.seed:
        parser.error("Specify --dry-run or --seed.")

    cfg = load_config()
    ok, msg = validate_config(cfg)
    if not ok:
        raise SystemExit(f"Invalid config: {msg}")

    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    output = args.output or active
    _reject_unsafe_output(output, cfg)
    if args.output:
        backup = output.with_name(output.stem + ".backup.json")
        lock = output.with_suffix(".lock")
    paths = StatePaths(active_path=output, backup_path=backup, lock_path=lock)

    try:
        ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)
    except TCPLedgerError as exc:
        raise SystemExit(f"Workbook load failed: {exc}") from exc

    state = bootstrap_state_from_workbook(cfg, ledger)
    _validate_expectations(state, args)

    if "workbook_path" in state or cfg.workbook_path in serialize_state(state):
        raise SystemExit("Absolute workbook path must not appear in state.")

    if args.dry_run:
        _report_dry_run(state, output, cfg)
        return 0

    if output.is_file():
        if not args.replace_existing:
            raise SystemExit(f"Refusing to overwrite existing state: {output.name}")
        import shutil

        if paths.backup_path.parent.exists() or True:
            paths.backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, paths.backup_path)
        output.unlink(missing_ok=True)
        if paths.lock_path.exists():
            paths.lock_path.unlink(missing_ok=True)

    save_state(state, paths)
    persisted = output.read_text(encoding="utf-8")
    loaded = __import__("json").loads(persisted)
    validate_state(loaded)
    print(f"seed_complete revision={loaded['revision']} checksum={_checksum(loaded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
