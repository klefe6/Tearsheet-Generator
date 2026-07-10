"""Extract historical daily rows from the tearsheet apps' stores — READ-ONLY.

Produces the JSON payload consumed by the uploader's sandbox-only
``POST /api/backfill/import`` (see ``app/backfill.py`` and
``docs/historical_backfill.md``). Run this on the machine that hosts the
tearsheet state files (they are not present on the deployed sandbox host).

Safety contract (enforced by construction, tested in tests/test_backfill.py):
  * Every tearsheet file is opened for READ only. This script never writes,
    creates, renames, or deletes anything outside ``--out``.
  * It never imports any tearsheet module (tkp_ts / tcp_ts_v2 / mp_ts / yq_ts)
    — some of those trigger network fetches or state writes at import time.
    The AGM fee-payment-evidence module is parsed textually for the same
    reason (it imports pandas).
  * It never touches the TCP ``.lock`` / ``.backup`` files (TCP reads are
    lock-free and safe against the app's atomic writes).
  * TKP's state is written non-atomically by its admin UI, so the read is
    retried on JSONDecodeError.

Sources (per the 2026-07-10 field-level audit):
  * TKP  — <repo>/daily_returns_secret_state.json (list of row dicts;
           $-string money; columns Date / StoneX / Plus500 / Deposit).
  * TCP  — the LIVE state file resolved from TCP_V2_STATE_PATH in
           <repo>/.tcp_production.env (dict envelope with ``records``;
           NLV / Cash Transfers / Date). The repo-root file of the same name
           is a stale bootstrap seed and is deliberately NOT a default.
  * AGM  — newest <repo>/Momentum Pacer/data/daily_balances/
           balances_210TGG51_*.csv (TradeStation Historical Balances Report;
           ``Net Worth`` = raw account NLV / actual_nlv — NOT the client-net
           value shown on the tearsheet). AGM ``fee`` is deliberately NOT
           extracted: the uploader's fee-vs-NLV relationship is an open,
           documented question and performance excludes fee anyway.
  * Y&Q  — NO daily source exists (yq.csv is monthly, at real-fund scale,
           while the tearsheet renders a normalized ROR curve). Y&Q is
           always skipped, with the reason in the audit output.

Usage:
  python scripts/extract_tearsheet_history.py --dry-run
  python scripts/extract_tearsheet_history.py --out backfill_payload.json
  python scripts/extract_tearsheet_history.py --push https://<sandbox>/api/backfill/import
  # --push posts with dry_run=true unless --commit is also given.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_PROGRAMS = ["TKP", "TCP", "AGM", "YQ"]

SOURCE_LABELS = {
    "TKP": "tkp_state_json",
    "TCP": "tcp_state_json",
    "AGM": "agm_daily_balances_csv",
}

YQ_SKIP_REASON = (
    "Y&Q has no daily historical source: yq.csv is monthly (2011-04 onward) at "
    "real-fund scale, and the tearsheet renders a $100k-normalized ROR curve. "
    "Skipped — Y&Q stays uploader-entries-only."
)


def _repo_root() -> Path:
    # scripts/ -> backend/ -> uploader/ -> repo root
    return Path(__file__).resolve().parents[3]


def parse_money(raw) -> Optional[float]:
    """Parse tearsheet money cells: '$1,234.56 ', '($50.00)', '', None, floats."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace("\xa0", " ").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace("$", "").replace(",", "").replace("*", "").strip()
    if not text:
        return None
    value = float(text)  # raises ValueError on junk — caller reports the row
    return -value if negative else value


def _iso_date(raw: str) -> str:
    """Validate/normalize a date cell to ISO YYYY-MM-DD."""
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unparseable date {raw!r}")


class SourceResult:
    def __init__(self, program: str, path: Optional[Path]):
        self.program = program
        self.path = path
        self.rows: list[dict] = []
        self.warnings: list[str] = []
        self.skipped_reason: Optional[str] = None

    @property
    def date_range(self) -> str:
        if not self.rows:
            return "-"
        dates = sorted(r["date"] for r in self.rows)
        return f"{dates[0]} .. {dates[-1]}"


# --- TKP ---------------------------------------------------------------------

def extract_tkp(state_path: Path) -> SourceResult:
    res = SourceResult("TKP", state_path)
    raw_rows = _read_json_with_retry(state_path)
    if not isinstance(raw_rows, list):
        raise ValueError(f"{state_path}: expected a JSON list of rows")

    by_date: dict[str, dict] = {}
    for i, raw in enumerate(raw_rows):
        try:
            date = _iso_date(raw["Date"])
            stonex = parse_money(raw.get("StoneX"))
            plus500 = parse_money(raw.get("Plus500"))
            deposit = parse_money(raw.get("Deposit"))
        except (KeyError, ValueError) as exc:
            res.warnings.append(f"row {i}: skipped ({exc})")
            continue
        if stonex is None:
            res.warnings.append(f"row {i} ({date}): blank StoneX — skipped")
            continue
        if date in by_date:
            res.warnings.append(f"duplicate date {date}: later row wins")
        by_date[date] = {
            "program": "TKP",
            "date": date,
            "stonex_nlv": stonex,
            # Blank Plus500 = the second account did not exist yet -> 0.0.
            "plus500_nlv": plus500 if plus500 is not None else 0.0,
            "cash_transfer": deposit if deposit is not None else 0.0,
            "source": SOURCE_LABELS["TKP"],
            "source_detail": state_path.name,
        }
    res.rows = [by_date[d] for d in sorted(by_date)]
    _synthesize_unrecorded_plus500_transfers(res)
    return res


def _synthesize_unrecorded_plus500_transfers(res: SourceResult) -> None:
    """Neutralize Plus500 open/close funding the Deposit column never recorded.

    Verified against the real store (2026-07-10): on 2025-03-11 Plus500 went
    from blank to $100,000.00 with a blank Deposit cell — without a matching
    cash_transfer the uploader's return formula would show that funding as a
    fake +82.6% day. Narrow, deterministic rule: on the day Plus500 transitions
    0 -> V (or V -> 0) with NO recorded deposit, treat the transition amount as
    the day's cash transfer, and say so loudly in the audit output. Days where
    the Deposit column DID record the movement are left exactly as recorded.
    """
    prev = None
    for row in res.rows:
        if prev is not None and row["cash_transfer"] == 0.0:
            opened = prev["plus500_nlv"] == 0.0 and row["plus500_nlv"] > 0.0
            closed = prev["plus500_nlv"] > 0.0 and row["plus500_nlv"] == 0.0
            if opened or closed:
                amount = row["plus500_nlv"] if opened else -prev["plus500_nlv"]
                row["cash_transfer"] = amount
                res.warnings.append(
                    f"{row['date']}: Plus500 {'funding' if opened else 'defunding'} of "
                    f"${abs(amount):,.2f} not recorded in the Deposit column — "
                    "synthesized cash_transfer so the day is not counted as "
                    "performance (verify against broker records)"
                )
        prev = row


def _read_json_with_retry(path: Path, attempts: int = 3):
    """TKP's admin UI writes its state non-atomically; retry a torn read."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:  # torn read during an admin save
            last_exc = exc
            time.sleep(0.5 * (attempt + 1))
    raise last_exc


# --- TCP ---------------------------------------------------------------------

def resolve_tcp_state_path(repo_root: Path) -> Path:
    """Resolve the LIVE TCP state path from .tcp_production.env.

    Reads ONLY the TCP_V2_STATE_PATH key (never prints other keys — the file
    also holds secrets). The repo-root tcp_daily_returns_secret_state.json is
    a stale bootstrap seed and is deliberately never used as a fallback; pass
    --tcp-state explicitly if you really mean to read a different file.
    """
    env_file = repo_root / ".tcp_production.env"
    if not env_file.exists():
        raise FileNotFoundError(
            f"{env_file} not found — cannot resolve the live TCP state path. "
            "Pass --tcp-state explicitly."
        )
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        # The real file uses batch syntax: set "TCP_V2_STATE_PATH=C:\...".
        # Accept that, plain KEY=value, and quoted variants.
        m = re.match(r'\s*(?:set\s+)?"?TCP_V2_STATE_PATH\s*=\s*(.+?)\s*$', line)
        if m:
            return Path(m.group(1).strip().strip('"').strip("'"))
    raise ValueError(
        f"TCP_V2_STATE_PATH not set in {env_file} — pass --tcp-state explicitly."
    )


def extract_tcp(state_path: Path) -> SourceResult:
    res = SourceResult("TCP", state_path)
    with open(state_path, "r", encoding="utf-8") as fh:
        envelope = json.load(fh)
    if not isinstance(envelope, dict) or "records" not in envelope:
        raise ValueError(f"{state_path}: expected the TCP state envelope with 'records'")

    revision = envelope.get("revision")
    detail = f"{state_path.name} (revision {revision})"
    by_date: dict[str, dict] = {}
    for i, rec in enumerate(envelope["records"]):
        try:
            date = _iso_date(rec["Date"])
        except (KeyError, ValueError) as exc:
            res.warnings.append(f"record {i}: skipped ({exc})")
            continue
        nlv = rec.get("NLV")
        if nlv is None:
            res.warnings.append(f"record {i} ({date}): null NLV — skipped")
            continue
        cash = rec.get("Cash Transfers")
        if date in by_date:
            res.warnings.append(f"duplicate date {date}: later record wins")
        by_date[date] = {
            "program": "TCP",
            "date": date,
            "stonex_nlv": float(nlv),
            "cash_transfer": float(cash) if cash is not None else 0.0,
            "source": SOURCE_LABELS["TCP"],
            "source_detail": detail,
        }
    res.rows = [by_date[d] for d in sorted(by_date)]
    return res


# --- AGM ---------------------------------------------------------------------

def resolve_agm_balances_path(repo_root: Path) -> Path:
    """Newest TradeStation balances CSV by last data date (filenames are
    date-stamped and the app's hardcoded constant changes with each export)."""
    folder = repo_root / "Momentum Pacer" / "data" / "daily_balances"
    candidates = sorted(folder.glob("balances_210TGG51_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"no balances_210TGG51_*.csv under {folder}")
    best, best_last = None, ""
    for path in candidates:
        rows = _read_agm_csv_rows(path)
        if not rows:
            continue
        last = max(r["date"] for r in rows)
        if last > best_last:
            best, best_last = path, last
    if best is None:
        raise ValueError(f"no parseable balances CSV under {folder}")
    return best


def _read_agm_csv_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header: Optional[list[str]] = None
        date_idx = worth_idx = None
        for cells in reader:
            if header is None:
                stripped = [c.strip() for c in cells]
                if "Date" in stripped and "Net Worth" in stripped:
                    header = stripped
                    date_idx = header.index("Date")
                    worth_idx = header.index("Net Worth")
                continue
            if len(cells) <= max(date_idx, worth_idx):
                continue
            try:
                date = _iso_date(cells[date_idx])
                worth = parse_money(cells[worth_idx])
            except ValueError:
                continue
            if worth is None:
                continue
            rows.append({"date": date, "net_worth": worth})
    return rows


def parse_agm_fee_payment_evidence(repo_root: Path) -> dict[str, float]:
    """{date: total fee paid} from algominds_fee_payment_evidence.py.

    Parsed TEXTUALLY, never imported — the evidence module pulls in pandas and
    the extractor must stay import-clean of tearsheet code. These are the
    hand-confirmed TradeStation incentive-fee withdrawals; without them the
    uploader's return formula would count each withdrawal day as a fake loss.
    """
    path = repo_root / "algominds_fee_payment_evidence.py"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, float] = {}
    pattern = (
        r'FeePaymentEvidence\(\s*date=pd\.Timestamp\("(\d{4}-\d{2}-\d{2})"\),'
        r'\s*description=.*?,\s*amount=([0-9_]+(?:\.[0-9]+)?),'
    )
    for m in re.finditer(pattern, text, re.S):
        out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(2))
    return out


def extract_agm(balances_path: Path, fee_payments: Optional[dict[str, float]] = None) -> SourceResult:
    res = SourceResult("AGM", balances_path)
    fee_payments = fee_payments or {}
    by_date: dict[str, dict] = {}
    for rec in _read_agm_csv_rows(balances_path):
        if rec["date"] in by_date:
            res.warnings.append(f"duplicate date {rec['date']}: later row wins")
        # Evidenced incentive-fee withdrawals are the only per-date cash
        # transactions AGM has a confirmed record of; stored positive in the
        # evidence module, they are cash LEAVING the account here.
        paid = fee_payments.get(rec["date"], 0.0)
        by_date[rec["date"]] = {
            "program": "AGM",
            "date": rec["date"],
            # Raw TradeStation Net Worth == actual_nlv. Deliberately NOT the
            # client_net_value (net of accrued fees) the tearsheet displays.
            "tradestation_nlv": rec["net_worth"],
            "cash_transfer": -paid,
            # `fee` is deliberately omitted: AGM fee-vs-NLV treatment is a
            # documented open question and performance excludes fee anyway.
            "source": SOURCE_LABELS["AGM"],
            "source_detail": balances_path.name,
        }
        if paid:
            res.warnings.append(
                f"{rec['date']}: evidenced incentive-fee withdrawal of "
                f"${paid:,.2f} applied as a negative cash transfer "
                "(from algominds_fee_payment_evidence.py)"
            )
    if not by_date:
        raise ValueError(f"{balances_path}: no data rows parsed")
    unmatched = sorted(d for d in fee_payments if d not in by_date)
    if unmatched:
        res.warnings.append(
            f"evidenced fee payments on dates missing from the balances CSV "
            f"(NOT applied): {', '.join(unmatched)}"
        )
    res.warnings.append(
        "AGM general deposits/withdrawals have no per-date source in the "
        "balances CSV (0 except evidenced fee withdrawals); fee column "
        "deliberately not backfilled (documented open question)."
    )
    res.rows = [by_date[d] for d in sorted(by_date)]
    return res


# --- orchestration -------------------------------------------------------------

def extract_all(
    repo_root: Path,
    programs: list[str],
    tkp_state: Optional[Path] = None,
    tcp_state: Optional[Path] = None,
    agm_balances: Optional[Path] = None,
) -> list[SourceResult]:
    results: list[SourceResult] = []
    for program in programs:
        if program == "TKP":
            path = tkp_state or (repo_root / "daily_returns_secret_state.json")
            results.append(extract_tkp(path))
        elif program == "TCP":
            path = tcp_state or resolve_tcp_state_path(repo_root)
            results.append(extract_tcp(path))
        elif program == "AGM":
            path = agm_balances or resolve_agm_balances_path(repo_root)
            results.append(extract_agm(path, parse_agm_fee_payment_evidence(repo_root)))
        elif program == "YQ":
            res = SourceResult("YQ", None)
            res.skipped_reason = YQ_SKIP_REASON
            results.append(res)
        else:
            raise ValueError(f"unknown program {program!r}")
    return results


def build_payload(results: list[SourceResult], dry_run: bool) -> dict:
    rows = [row for res in results for row in res.rows]
    return {
        "generated_by": "extract_tearsheet_history.py",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "sources": {
            res.program: {
                "path": str(res.path) if res.path else None,
                "row_count": len(res.rows),
                "date_range": res.date_range,
                "skipped_reason": res.skipped_reason,
                "warnings": res.warnings,
            }
            for res in results
        },
        "rows": rows,
    }


def print_audit(results: list[SourceResult]) -> None:
    print("\nBackfill extraction audit (read-only; nothing was modified):")
    print(f"{'program':<8} {'rows':>6}  {'date range':<26} source")
    for res in results:
        if res.skipped_reason:
            print(f"{res.program:<8} {0:>6}  {'-':<26} SKIPPED")
            print(f"         reason: {res.skipped_reason}")
            continue
        print(f"{res.program:<8} {len(res.rows):>6}  {res.date_range:<26} {res.path}")
        for w in res.warnings[:10]:
            print(f"         warning: {w}")
        extra = len(res.warnings) - 10
        if extra > 0:
            print(f"         ... and {extra} more warnings")
    print()


def push_payload(url: str, payload: dict, token: Optional[str], commit: bool) -> dict:
    body = dict(payload)
    body["dry_run"] = not commit
    data = json.dumps({"dry_run": body["dry_run"], "rows": body["rows"]}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument(
        "--programs",
        default=",".join(DEFAULT_PROGRAMS),
        help="comma-separated subset of TKP,TCP,AGM,YQ",
    )
    parser.add_argument("--tkp-state", type=Path, default=None)
    parser.add_argument(
        "--tcp-state",
        type=Path,
        default=None,
        help="override the live TCP state path (default: TCP_V2_STATE_PATH from "
        ".tcp_production.env; the repo-root copy is a stale seed — do not use it)",
    )
    parser.add_argument("--agm-balances", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write payload JSON here")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the audit only; write nothing"
    )
    parser.add_argument(
        "--push", default=None, metavar="URL",
        help="POST the payload to a sandbox /api/backfill/import URL",
    )
    parser.add_argument("--token", default=None, help="bearer token for --push")
    parser.add_argument(
        "--commit", action="store_true",
        help="with --push: import for real (default posts dry_run=true)",
    )
    args = parser.parse_args(argv)

    programs = [p.strip().upper() for p in args.programs.split(",") if p.strip()]
    results = extract_all(
        args.repo_root,
        programs,
        tkp_state=args.tkp_state,
        tcp_state=args.tcp_state,
        agm_balances=args.agm_balances,
    )
    print_audit(results)
    payload = build_payload(results, dry_run=args.dry_run)

    if args.dry_run:
        print("--dry-run: no file written, nothing pushed.")
        return 0

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
        print(f"wrote {len(payload['rows'])} rows to {args.out}")

    if args.push:
        response = push_payload(args.push, payload, args.token, args.commit)
        mode = "COMMIT" if args.commit else "server-side dry-run"
        print(f"pushed to {args.push} ({mode}); server response:")
        print(json.dumps(response, indent=1))

    if not args.out and not args.push:
        print("no --out/--push given; audit only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
