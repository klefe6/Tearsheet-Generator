#!/usr/bin/env python3
"""Read-only preflight audit of the live tearsheet fleet and production checkout.

Companion to docs/production_checkout_alignment_runbook.md (PR 0). Run it from
the production root checkout before every planned restart or deployment:

    python scripts\\audit_live_tearsheet_processes.py

Guarantees:
  * inspects processes, ports, and git metadata ONLY;
  * prints no secret values (env files are checked for existence/size only —
    their contents are never read);
  * modifies nothing, kills nothing, restarts nothing, writes nothing.

Exit status:
  0  all blocking checks passed
  1  one or more FAIL conditions:
       - duplicate listeners on a production port
       - production checkout dirty (modified tracked files, or an untracked
         file that collides with origin/main and differs from it)
       - expected production env file missing/empty
       - tearsheet_runtime_mode.py missing (downgrade with
         --allow-missing-runtime-mode for pre-alignment runs)
  2  the audit itself could not run (unexpected environment error)

Windows-only by design (netstat + Get-CimInstance), matching the ops machine.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Production port -> expected app (see docs/REPO_MAP.md section 1).
PRODUCTION_PORTS: dict[int, str] = {
    8301: "TKP (tkp_ts.py)",
    8302: "TCP v2 (tcp_ts_v2.py)",
    8303: "Y&Q (yq_ts.py)",
    8304: "AGM (Momentum Pacer/mp_ts.py)",
    8077: "tsgen (tsgen.py)",
}
# Informational only — not expected to be running; never a FAIL.
INFO_PORTS: dict[int, str] = {8075: "Gold Maker (Gold_Maker_ts.py)"}

# Apps whose production launcher is a .ps1 that sources an env file and uses
# .venv310 — a live PID on these ports NOT running under .venv310 suggests the
# env file was never sourced (see runbook C3/C4).
VENV_EXPECTED_PORTS = (8301, 8302)

ENV_FILES = (".tkp_production.env", ".tcp_production.env")
RUNTIME_MODE_MODULE = "tearsheet_runtime_mode.py"

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a read-only command, capturing text output safely on cp1252 consoles."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def listeners_by_port() -> dict[int, set[int]]:
    """Parse `netstat -ano` for LISTENING TCP sockets on the audited ports."""
    out = run(["netstat", "-ano"])
    found: dict[int, set[int]] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local, state, pid = parts[1], parts[3].upper(), parts[4]
        if state != "LISTENING":
            continue
        try:
            port = int(local.rsplit(":", 1)[1])
            pid_i = int(pid)
        except (ValueError, IndexError):
            continue
        if port in PRODUCTION_PORTS or port in INFO_PORTS:
            found.setdefault(port, set()).add(pid_i)
    return found


def process_details(pids: set[int]) -> dict[int, dict]:
    """Fetch ProcessId/CreationDate/ExecutablePath/CommandLine via CIM.

    Elevated processes show empty ExecutablePath/CommandLine when queried from
    a non-elevated shell — reported as 'elevated?' rather than an error.
    """
    if not pids:
        return {}
    flt = " OR ".join(f"ProcessId={p}" for p in sorted(pids))
    ps = (
        "Get-CimInstance Win32_Process -Filter \"" + flt + "\" | "
        "Select-Object ProcessId, ExecutablePath, CommandLine, "
        "@{n='Created';e={$_.CreationDate.ToString('yyyy-MM-dd HH:mm:ss')}} | "
        "ConvertTo-Json -Compress"
    )
    out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
    if not out.stdout.strip():
        return {}
    data = json.loads(out.stdout)
    if isinstance(data, dict):  # single result is not wrapped in a list
        data = [data]
    return {int(d["ProcessId"]): d for d in data}


def git(repo: Path, *args: str) -> str:
    out = run(["git", *args], cwd=repo)
    return out.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Production checkout to audit (default: this script's repo)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="git fetch origin main first so the behind-count is accurate "
        "(network read; refs only, working tree untouched)",
    )
    parser.add_argument(
        "--allow-missing-runtime-mode",
        action="store_true",
        help="Downgrade a missing tearsheet_runtime_mode.py to WARN "
        "(only for runs BEFORE the checkout is aligned to main)",
    )
    args = parser.parse_args()
    repo: Path = args.repo_root.resolve()

    results: list[tuple[str, str]] = []  # (status, message)

    def record(status: str, message: str) -> None:
        results.append((status, message))
        print(f"[{status}] {message}")

    print(f"Auditing production checkout: {repo}")
    if not (repo / ".git").exists():
        print(f"[{FAIL}] {repo} is not a git checkout")
        return 2

    # --- 1. Live listeners + duplicate detection -------------------------
    ports = listeners_by_port()
    all_pids = set().union(*ports.values()) if ports else set()
    details = process_details(all_pids)

    for port, app in {**PRODUCTION_PORTS, **INFO_PORTS}.items():
        pids = sorted(ports.get(port, ()))
        if not pids:
            status = WARN if port in PRODUCTION_PORTS else PASS
            record(status, f"port {port} ({app}): no listener (service not running)")
            continue
        descs = []
        for pid in pids:
            d = details.get(pid, {})
            exe = d.get("ExecutablePath") or ""
            created = d.get("Created") or "?"
            elevated = "" if exe else " [elevated? - inspect from elevated shell]"
            descs.append(f"pid {pid} started {created} exe {exe or '?'}{elevated}")
        joined = "; ".join(descs)
        if len(pids) > 1 and port in PRODUCTION_PORTS:
            record(FAIL, f"port {port} ({app}): DUPLICATE listeners - {joined}")
        else:
            record(PASS, f"port {port} ({app}): {joined}")
        # Interpreter heuristic (runbook C3/C4): TKP/TCP should run under .venv310.
        if port in VENV_EXPECTED_PORTS:
            for pid in pids:
                exe = (details.get(pid) or {}).get("ExecutablePath") or ""
                if exe and ".venv310" not in exe:
                    record(
                        WARN,
                        f"port {port} pid {pid}: interpreter '{exe}' is not "
                        ".venv310 - production env file was likely NOT sourced "
                        "(see runbook C3)",
                    )

    # --- 2. Checkout truth ------------------------------------------------
    if args.fetch:
        run(["git", "fetch", "origin", "main"], cwd=repo)
    branch = git(repo, "branch", "--show-current") or "(detached)"
    sha = git(repo, "rev-parse", "--short", "HEAD")
    behind = git(repo, "rev-list", "--count", "HEAD..origin/main") or "?"
    note = "" if args.fetch else " (local refs; pass --fetch for accuracy)"
    status = PASS if behind == "0" else WARN
    record(status, f"checkout: branch '{branch}' @ {sha}, {behind} commits behind origin/main{note}")
    if branch != "main":
        record(WARN, "checkout is not on 'main' - production source-of-truth rule not yet in effect")

    porcelain = git(repo, "status", "--porcelain")
    modified = [l for l in porcelain.splitlines() if l and not l.startswith("??")]
    untracked = [l[3:].strip().strip('"') for l in porcelain.splitlines() if l.startswith("??")]
    if modified:
        record(FAIL, f"checkout DIRTY: {len(modified)} modified tracked file(s): "
               + ", ".join(m.split(None, 1)[-1] for m in modified[:10]))
    else:
        record(PASS, "no modified tracked files")

    colliding_diff = 0
    for f in untracked:
        probe = run(["git", "cat-file", "-e", f"origin/main:{f}"], cwd=repo)
        if probe.returncode == 0:
            local_hash = git(repo, "hash-object", f)
            main_hash = git(repo, "rev-parse", f"origin/main:{f}")
            if local_hash != main_hash:
                colliding_diff += 1
                record(FAIL, f"untracked '{f}' collides with origin/main and DIFFERS "
                       "(unmerged local work - stop condition)")
            else:
                record(WARN, f"untracked '{f}' is byte-identical to origin/main "
                       "(safe to delete during alignment)")
    if untracked and colliding_diff == 0:
        record(WARN, f"{len(untracked)} untracked file(s) present (no differing collisions)")

    # --- 3. Env files (existence/size only - contents never read) ---------
    for name in ENV_FILES:
        p = repo / name
        if p.is_file() and p.stat().st_size > 0:
            record(PASS, f"env file {name}: present ({p.stat().st_size} bytes)")
        else:
            record(FAIL, f"env file {name}: MISSING or empty")

    # --- 4. Expected modules from merged PRs ------------------------------
    rm = repo / RUNTIME_MODE_MODULE
    if rm.is_file():
        record(PASS, f"{RUNTIME_MODE_MODULE} present")
    elif args.allow_missing_runtime_mode:
        record(WARN, f"{RUNTIME_MODE_MODULE} MISSING (allowed by flag - checkout predates PR #19; align before restarting)")
    else:
        record(FAIL, f"{RUNTIME_MODE_MODULE} MISSING - checkout predates PR #19; align to main first")
    for extra in ("scripts/smoke_all.py", "pytest.ini"):
        if (repo / extra).is_file():
            record(PASS, f"{extra} present")
        else:
            record(WARN, f"{extra} missing (checkout predates PR #22 - smoke gate unavailable here)")

    # --- Summary -----------------------------------------------------------
    fails = sum(1 for s, _ in results if s == FAIL)
    warns = sum(1 for s, _ in results if s == WARN)
    print()
    print(f"Summary: {fails} FAIL, {warns} WARN, "
          f"{sum(1 for s, _ in results if s == PASS)} PASS")
    if fails:
        print("Result: BLOCKED - do not restart or deploy. "
              "See docs/production_checkout_alignment_runbook.md stop conditions.")
        return 1
    print("Result: CLEAR (address WARNs per the runbook before restarting).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # audit must never mask its own failure as success
        print(f"[{FAIL}] audit error: {exc}")
        sys.exit(2)
