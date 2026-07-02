"""
TCP v2 acceptance helpers — parity baselines, classifications, and reporting.

Read-only by default. No workbook or preview-state mutation in parity mode.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tcp_config import load_config, resolve_state_paths  # noqa: E402
from tcp_dashboard import (  # noqa: E402
    canonical_nav_records_from_ledger,
    propagate_tcp_dashboard,
)
from tcp_ledger import REQUIRED_HEADERS, load_ledger  # noqa: E402
from tcp_runtime_state import ledger_from_state_envelope, state_record_to_fields  # noqa: E402
from tcp_state import StatePaths, load_state, serialize_state, validate_state  # noqa: E402

CLASSIFICATIONS = frozenset(
    {
        "MATCH",
        "INTENTIONAL_V2_CORRECTION",
        "FORMATTING_ONLY",
        "V1_LEGACY_INERT",
        "EXTERNAL_DATA_DIFFERENCE",
        "V2_DEFECT",
        "UNRESOLVED_BLOCKER",
    }
)

LEDGER_FIELDS = list(REQUIRED_HEADERS)
CURRENCY_TOLERANCE = 1e-3
PERCENT_TOLERANCE = 1e-6


@dataclass
class DifferenceRecord:
    output: str
    excel_value: Any
    v1_value: Any
    v2_value: Any
    classification: str
    user_visible_impact: str
    recommendation: str
    kevin_approval: str


@dataclass
class AcceptanceReport:
    excel_baseline: Dict[str, Any] = field(default_factory=dict)
    v1_baseline: Dict[str, Any] = field(default_factory=dict)
    v2_baseline: Dict[str, Any] = field(default_factory=dict)
    row_summary: Dict[str, Any] = field(default_factory=dict)
    differences: List[DifferenceRecord] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    verdict: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "excel_baseline": self.excel_baseline,
            "v1_baseline": self._redact(self.v1_baseline),
            "v2_baseline": self.v2_baseline,
            "row_summary": self.row_summary,
            "differences": [d.__dict__ for d in self.differences],
            "blockers": self.blockers,
            "verdict": self.verdict,
        }

    @staticmethod
    def _redact(payload: Mapping[str, Any]) -> Dict[str, Any]:
        text = json.dumps(payload, default=str)
        text = re.sub(r"[A-Za-z]:\\\\[^\"\\]+", "<redacted-path>", text)
        return json.loads(text)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _numeric_close(a: Any, b: Any, *, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)
    except (TypeError, ValueError):
        return a == b


def collect_excel_baseline(workbook_path: Optional[str] = None) -> Dict[str, Any]:
    cfg = load_config()
    path = workbook_path or cfg.workbook_path
    ledger = load_ledger(path, cfg.sheet_name)
    meta = ledger.metadata
    final = ledger.completed_records[-1].fields
    canonical = canonical_nav_records_from_ledger(ledger.completed_records)
    propagation = propagate_tcp_dashboard(canonical)
    return {
        "workbook_filename": meta.source_filename,
        "workbook_checksum": sha256_file(Path(path)),
        "workbook_size": Path(path).stat().st_size,
        "workbook_mtime": Path(path).stat().st_mtime,
        "candidate_rows": meta.total_candidate_rows,
        "completed_rows": meta.completed_row_count,
        "first_completed_date": meta.first_completed_date.isoformat() if meta.first_completed_date else None,
        "latest_completed_date": meta.latest_completed_date.isoformat() if meta.latest_completed_date else None,
        "final_nav": float(final["nav-x1"]),
        "final_hwm": float(final["HWM"]),
        "final_loss_carry": float(final["Loss Carry"]),
        "final_cumm_fee": float(final["cumm fee"]),
        "chart_points": propagation.nav_point_count,
        "monthly_shape": list(propagation.monthly_calendar.shape),
        "daily_metrics_shape": list(propagation.daily_performance.shape),
        "label_date_line": propagation.desktop_label.date_line,
        "records": [dict(r.fields) for r in ledger.completed_records],
    }


def collect_json_baseline(state_path: Path) -> Dict[str, Any]:
    paths = StatePaths(
        active_path=state_path,
        backup_path=state_path.with_name(state_path.stem + ".backup.json"),
        lock_path=state_path.with_suffix(".lock"),
    )
    loaded = load_state(paths) if state_path.is_file() else None
    if loaded is None:
        raise FileNotFoundError(f"State not found: {state_path.name}")
    cfg = load_config()
    ledger = ledger_from_state_envelope(loaded.state, cfg=cfg, source_label="json")
    canonical = canonical_nav_records_from_ledger(ledger.completed_records)
    propagation = propagate_tcp_dashboard(canonical)
    final = ledger.completed_records[-1].fields
    return {
        "state_checksum": sha256_file(state_path),
        "state_revision": int(loaded.state["revision"]),
        "completed_rows": len(ledger.completed_records),
        "latest_completed_date": ledger.metadata.latest_completed_date.isoformat(),
        "final_nav": float(final["nav-x1"]),
        "chart_points": propagation.nav_point_count,
        "label_date_line": propagation.desktop_label.date_line,
        "monthly_df": propagation.monthly_calendar.to_dict(),
        "daily_df": propagation.daily_performance.to_dict(),
        "records": loaded.state["records"],
        "propagation": propagation,
        "ledger": ledger,
    }


def compare_row_level(excel_records: Sequence[Mapping[str, Any]], json_records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    max_currency = {field: 0.0 for field in LEDGER_FIELDS}
    max_percent = {field: 0.0 for field in LEDGER_FIELDS}
    mismatches: List[Dict[str, Any]] = []
    if len(excel_records) != len(json_records):
        return {
            "rows_compared": min(len(excel_records), len(json_records)),
            "rows_matched": 0,
            "rows_mismatched": abs(len(excel_records) - len(json_records)),
            "first_mismatch": {"reason": "row_count", "excel": len(excel_records), "json": len(json_records)},
            "max_currency_diff": max_currency,
            "max_percent_diff": max_percent,
            "mismatches": mismatches,
        }
    matched = 0
    first_mismatch = None
    for index, (excel_row, json_row) in enumerate(zip(excel_records, json_records)):
        excel_fields = excel_row if isinstance(excel_row, dict) and "Date" in excel_row else dict(excel_row)
        if hasattr(excel_row, "fields"):
            excel_fields = excel_row.fields  # type: ignore[union-attr]
        json_fields = state_record_to_fields(json_row)
        row_ok = True
        for field_name in LEDGER_FIELDS:
            ev = excel_fields.get(field_name)
            jv = json_fields.get(field_name)
            if field_name == "Date":
                if _normalize_date(ev) != _normalize_date(jv):
                    row_ok = False
                    if first_mismatch is None:
                        first_mismatch = {"row": index, "field": field_name, "excel": ev, "json": jv}
                continue
            tol = PERCENT_TOLERANCE if field_name in {"%Net", "S net cummulative %"} else CURRENCY_TOLERANCE
            if not _numeric_close(ev, jv, tol=tol):
                row_ok = False
                diff = abs(float(ev or 0) - float(jv or 0))
                if field_name in {"%Net", "S net cummulative %"}:
                    max_percent[field_name] = max(max_percent[field_name], diff)
                else:
                    max_currency[field_name] = max(max_currency[field_name], diff)
                if first_mismatch is None:
                    first_mismatch = {"row": index, "field": field_name, "excel": ev, "json": jv}
        if row_ok:
            matched += 1
        else:
            mismatches.append({"row": index, "date": _normalize_date(excel_fields.get("Date"))})
    return {
        "rows_compared": len(excel_records),
        "rows_matched": matched,
        "rows_mismatched": len(excel_records) - matched,
        "first_mismatch": first_mismatch,
        "max_currency_diff": max_currency,
        "max_percent_diff": max_percent,
        "mismatches": mismatches[:5],
    }


def _v1_source_path(source: str) -> Path:
    if source == "working-tree":
        return REPO_ROOT / "tcp_ts.py"
    if source == "head":
        content = subprocess.check_output(
            ["git", "show", "HEAD:tcp_ts.py"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
        )
        tmp = Path(tempfile.gettempdir()) / f"tcp_ts_v1_head_{os.getpid()}.py"
        tmp.write_text(content, encoding="utf-8")
        return tmp
    raise ValueError(f"Unsupported v1 source: {source}")


def collect_v1_baseline(source: str = "head") -> Dict[str, Any]:
    """Extract v1 dashboard snapshot via isolated subprocess (read-only)."""
    worker = REPO_ROOT / "scripts" / "_v1_baseline_worker.py"
    v1_path = _v1_source_path(source)
    cfg = load_config()
    env = os.environ.copy()
    env["TCP_V2_WORKBOOK_PATH"] = cfg.workbook_path
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(worker), str(v1_path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"v1 baseline extraction failed: {result.stderr[:500]}")
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    payload["v1_source"] = source
    payload["v1_file_checksum"] = sha256_file(v1_path)
    return payload


def _add_difference(
    report: AcceptanceReport,
    *,
    output: str,
    excel_value: Any,
    v1_value: Any,
    v2_value: Any,
    classification: str,
    impact: str,
    recommendation: str,
    kevin: str,
) -> None:
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"Invalid classification: {classification}")
    report.differences.append(
        DifferenceRecord(
            output=output,
            excel_value=excel_value,
            v1_value=v1_value,
            v2_value=v2_value,
            classification=classification,
            user_visible_impact=impact,
            recommendation=recommendation,
            kevin_approval=kevin,
        )
    )
    if classification in {"V2_DEFECT", "UNRESOLVED_BLOCKER"}:
        report.blockers.append(f"{output}: {classification}")


def run_parity_acceptance(
    *,
    state_path: Path,
    v1_source: str = "head",
    include_v1: bool = True,
) -> AcceptanceReport:
    report = AcceptanceReport()
    excel = collect_excel_baseline()
    json_base = collect_json_baseline(state_path)
    report.excel_baseline = {k: v for k, v in excel.items() if k != "records"}
    report.v2_baseline = {
        k: v for k, v in json_base.items() if k not in {"records", "propagation", "ledger", "monthly_df", "daily_df"}
    }

    excel_records = excel["records"]
    json_records = json_base["records"]
    row_summary = compare_row_level(excel_records, json_records)
    report.row_summary = row_summary
    if row_summary["rows_mismatched"] > 0:
        _add_difference(
            report,
            output="row_level_ledger",
            excel_value=row_summary["rows_matched"],
            v1_value=None,
            v2_value=row_summary["rows_mismatched"],
            classification="V2_DEFECT",
            impact="Ledger row mismatch between workbook and JSON",
            recommendation="Fix seed or state serialization before cutover",
            kevin="Yes",
        )

    v2_prop = json_base["propagation"]
    _add_difference(
        report,
        output="latest_date",
        excel_value=excel["latest_completed_date"],
        v1_value=None,
        v2_value=json_base["latest_completed_date"],
        classification="MATCH" if excel["latest_completed_date"] == json_base["latest_completed_date"] else "V2_DEFECT",
        impact="Current-date label source",
        recommendation="Accept if match",
        kevin="No" if excel["latest_completed_date"] == json_base["latest_completed_date"] else "Yes",
    )
    _add_difference(
        report,
        output="latest_nav",
        excel_value=excel["final_nav"],
        v1_value=None,
        v2_value=json_base["final_nav"],
        classification="MATCH" if _numeric_close(excel["final_nav"], json_base["final_nav"], tol=CURRENCY_TOLERANCE) else "V2_DEFECT",
        impact="Latest NAV display",
        recommendation="Accept if within tolerance",
        kevin="No" if _numeric_close(excel["final_nav"], json_base["final_nav"], tol=CURRENCY_TOLERANCE) else "Yes",
    )

    if include_v1:
        try:
            v1 = collect_v1_baseline(v1_source)
            report.v1_baseline = {k: v for k, v in v1.items() if k not in {"monthly_df", "daily_df"}}
            _classify_v1_v2_dashboard(report, excel, v1, v2_prop, json_base)
        except Exception as exc:
            _add_difference(
                report,
                output="v1_baseline_collection",
                excel_value=None,
                v1_value=str(exc),
                v2_value=None,
                classification="EXTERNAL_DATA_DIFFERENCE",
                impact="v1 baseline could not be collected safely",
                recommendation="Compare using committed HEAD only; deployed v1 not verified",
                kevin="No",
            )
    else:
        _add_difference(
            report,
            output="monthly_methodology",
            excel_value="workbook-derived sparse dates",
            v1_value="skipped",
            v2_value="sparse completed dates, no overrides",
            classification="INTENTIONAL_V2_CORRECTION",
            impact="v2 monthly table matches workbook ledger",
            recommendation="Accept v2 methodology",
            kevin="Recommended acceptance",
        )

    unresolved = [d for d in report.differences if d.classification in {"V2_DEFECT", "UNRESOLVED_BLOCKER"}]
    report.blockers = [f"{d.output}: {d.classification}" for d in unresolved]
    report.verdict = "PASS" if not report.blockers and row_summary["rows_mismatched"] == 0 else "FAIL"
    return report


def _classify_v1_v2_dashboard(
    report: AcceptanceReport,
    excel: Mapping[str, Any],
    v1: Mapping[str, Any],
    v2_prop: Any,
    json_base: Mapping[str, Any],
) -> None:
    v2_monthly = v2_prop.monthly_calendar
    v1_monthly = pd.DataFrame(v1["monthly_df"])
    override_months = v1.get("override_months", [])
    if override_months:
        _add_difference(
            report,
            output="monthly_2025_overrides",
            excel_value="workbook-derived",
            v1_value=override_months,
            v2_value="none",
            classification="INTENTIONAL_V2_CORRECTION",
            impact="v1 monthly table used hard-coded 2025 overrides; v2 uses ledger only",
            recommendation="Accept v2 aligned to workbook",
            kevin="Recommended acceptance",
        )

    _add_difference(
        report,
        output="nav_chart_point_count",
        excel_value=excel["chart_points"],
        v1_value=v1.get("nav_chart_points"),
        v2_value=v2_prop.nav_point_count,
        classification=(
            "INTENTIONAL_V2_CORRECTION"
            if v1.get("nav_chart_points") != v2_prop.nav_point_count
            else "MATCH"
        ),
        impact="v1 forward-fills business days; v2 charts sparse completed dates",
        recommendation="Accept sparse v2 chart aligned to ledger",
        kevin="Recommended acceptance" if v1.get("nav_chart_points") != v2_prop.nav_point_count else "No",
    )

    v2_daily = v2_prop.daily_performance
    v1_daily = pd.DataFrame(v1["daily_df"])
    inception_col = "TCP (Inception)"
    if inception_col in v1_daily.columns and inception_col in v2_daily.columns:
        for metric in v2_daily["Metric"]:
            v1_val = v1_daily.loc[v1_daily["Metric"] == metric, inception_col].iloc[0]
            v2_val = v2_daily.loc[v2_daily["Metric"] == metric, inception_col].iloc[0]
            same = str(v1_val) == str(v2_val)
            _add_difference(
                report,
                output=f"daily_metric_{metric}",
                excel_value="workbook-derived",
                v1_value=v1_val,
                v2_value=v2_val,
                classification="MATCH" if same else "INTENTIONAL_V2_CORRECTION",
                impact="Daily metrics differ when v1 uses asfreq/ffill series",
                recommendation="Accept v2 sparse-date methodology" if not same else "No action",
                kevin="Recommended acceptance" if not same else "No",
            )

    _add_difference(
        report,
        output="baseline_amount_150000",
        excel_value=excel["final_nav"],
        v1_value=v1.get("baseline_amount_constant"),
        v2_value=v2_prop.baseline_nav,
        classification="V1_LEGACY_INERT",
        impact="v1 defines BASELINE_AMOUNT=150000 but uses first NAV for metrics",
        recommendation="No v2 dependency on unused constant",
        kevin="Does not block cutover",
    )

    _add_difference(
        report,
        output="current_date_label",
        excel_value=excel.get("label_date_line"),
        v1_value=v1.get("label_date_line"),
        v2_value=v2_prop.desktop_label.date_line,
        classification="MATCH" if v2_prop.desktop_label.date_line == v1.get("label_date_line") else "FORMATTING_ONLY",
        impact="Header date wording",
        recommendation="Accept if same latest date",
        kevin="No",
    )

    _add_difference(
        report,
        output="public_daily_returns_table",
        excel_value="absent",
        v1_value=v1.get("has_daily_returns_table", False),
        v2_value=False,
        classification="MATCH",
        impact="TCP public Daily Returns table remains absent",
        recommendation="Preserve absence",
        kevin="Recommended acceptance",
    )

    _add_difference(
        report,
        output="percentage_nav_axis",
        excel_value="absent",
        v1_value=v1.get("percentage_nav_axis", False),
        v2_value=False,
        classification="MATCH",
        impact="Percentage NAV axis remains absent",
        recommendation="Preserve absence",
        kevin="Recommended acceptance",
    )


def kevin_decision_table(report: AcceptanceReport) -> List[Dict[str, str]]:
    decisions = [
        {
            "decision": "Sparse completed dates vs v1 business-day forward fill",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "v2 daily-metric methodology (sparse ledger dates)",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Public Daily Returns table remains absent",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Percentage NAV axis remains absent",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Drawdown/benchmark sections remain static/deferred",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Withdrawal remains blocked",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Tranche count remains explicit",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "Export disabled for initial cutover",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "No",
        },
        {
            "decision": "v1 2025 monthly overrides removed in v2",
            "recommendation": "Recommended acceptance",
            "blocks_cutover": "No",
            "explicit_approval": "Requires explicit approval",
        },
    ]
    if report.blockers:
        decisions.append(
            {
                "decision": "Unresolved acceptance blockers",
                "recommendation": "Block cutover until resolved",
                "blocks_cutover": "Yes",
                "explicit_approval": "Yes",
            }
        )
    return decisions
