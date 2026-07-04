#!/usr/bin/env python3
"""
Read-only TCP v1 vs v2 public UI parity audit.

Parses layout source markers from committed HEAD tcp_ts.py and tcp_ts_v2.py.
Does not modify applications, state, or the workbook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLASSIFICATIONS = frozenset(
    {
        "MATCHES_V1",
        "PRESENT_BUT_VISUALLY_DIFFERENT",
        "PRESENT_BUT_BEHAVIORALLY_DIFFERENT",
        "MISSING_REQUIRED",
        "MISSING_OPTIONAL",
        "INTENTIONAL_V2_IMPROVEMENT",
        "V1_LEGACY_OR_BUG",
        "NEEDS_KEVIN_DECISION",
    }
)

V1_SECTION_MARKERS: Sequence[Tuple[str, str, str]] = (
    ("gate_notice", "Important Notice", "Access gate overlay"),
    ("header_shell", "header-row", "Logo / firm name / last-updated header band"),
    ("firm_description", "Principals: Daniel V. Hughes III", "Lead description block"),
    ("nav_chart", "NAV-graph", "Primary NAV chart"),
    ("nav_footnotes", "Please note that all percentages", "NAV chart footnotes"),
    ("monthly_performance", "Performance Summary", "Monthly calendar table"),
    ("strategy_overview", "Strategy Overview", "BTC/ETH strategy description card"),
    ("trading_universe", "Trading Universe & Risk Profile", "Sector / exchange / risk card"),
    ("daily_metrics", "Performance Metrics", "Daily performance metrics table"),
    ("drawdown_table", "Maximum Drawdown Profile", "Worst drawdown profile table"),
    ("investor_information", "Investor Information", "Terms, fees, account stats"),
    ("account_stats_columns", "Account Stats", "Proprietary vs client columns"),
    ("terms_and_fees", "Terms & Fees", "Investor terms table"),
    ("hcdisclaimer", "hcdisclaimer_text", "H&C disclaimer paragraph"),
    ("general_disclaimer", "disclaimer_text", "General disclaimer paragraph"),
    ("proprietary_disclosure", "Important Disclosure:", "Bottom disclosure panel"),
    ("footer_contact", "footer_contact", "Footer contact line"),
    ("debug_provenance", "Debug / Data Provenance", "Optional debug table"),
)

V2_SECTION_MARKERS: Sequence[Tuple[str, str, str]] = (
    ("preview_banner", "preview_label", "TCP v2 preview warning banner"),
    ("header_shell", "Hughes & Company LLC", "Logo / firm name header"),
    ("current_date_labels", "data-current-label-desktop", "Dynamic current-date labels"),
    ("mode_alert", "JSON state is authoritative", "Runtime mode / recovery alert"),
    ("nav_chart", "nav-preview-graph", "Primary NAV chart"),
    ("nav_footnote", "This chart visualizes the growth", "Single NAV footnote"),
    ("monthly_performance", "Performance Summary", "Monthly calendar table"),
    ("daily_metrics", "Performance Metrics", "Daily performance metrics table"),
    ("runtime_diagnostics", "Runtime diagnostics (preview only)", "Preview-only diagnostics card"),
    ("admin_shell", "admin-editor-container", "Hidden admin editor mount"),
)


@dataclass
class SectionAudit:
    section_id: str
    title: str
    description: str
    v1_present: bool
    v2_present: bool
    classification: str
    severity: str
    cutover_blocker: bool
    effort: str
    v1_behavior: str
    v2_behavior: str
    data_dependency: str
    refresh_after_mutation: str
    recommended_action: str

    def to_dict(self) -> Dict[str, object]:
        return self.__dict__.copy()


@dataclass
class AuditReport:
    v1_source: str
    v2_source: str
    v1_checksum: str
    v2_checksum: str
    sections: List[SectionAudit] = field(default_factory=list)
    verdict: str = "PENDING"

    def finalize(self) -> None:
        blockers = [s for s in self.sections if s.cutover_blocker]
        missing_required = [
            s for s in self.sections if s.classification == "MISSING_REQUIRED"
        ]
        if missing_required:
            self.verdict = "Backend complete but public UI incomplete — not suitable for public cutover"
        elif blockers:
            self.verdict = "Functionally usable but visually incomplete"
        else:
            self.verdict = "Backend complete but public UI incomplete"

    def to_dict(self) -> Dict[str, object]:
        return {
            "verdict": self.verdict,
            "v1_source": self.v1_source,
            "v2_source": self.v2_source,
            "v1_checksum": self.v1_checksum,
            "v2_checksum": self.v2_checksum,
            "sections": [s.to_dict() for s in self.sections],
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_git_file(rel: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"unable to read HEAD:{rel}")
    return proc.stdout.decode("utf-8", errors="replace")


def _read_working_file(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _contains(source: str, needle: str) -> bool:
    return needle in source


def _classify_section(
    section_id: str,
    v1_present: bool,
    v2_present: bool,
) -> Tuple[str, str, bool, str, str, str, str, str]:
    """Return classification, severity, blocker, effort, v1, v2, data_dep, refresh, action."""
    common_dynamic = {
        "monthly_performance",
        "daily_metrics",
        "nav_chart",
        "current_date_labels",
    }
    if section_id in common_dynamic and v1_present and v2_present:
        if section_id == "current_date_labels":
            return (
                "PRESENT_BUT_BEHAVIORALLY_DIFFERENT",
                "medium",
                False,
                "S",
                "Static 'Last Updated' at startup from workbook",
                "Dynamic 'Data current to … close' from canonical NAV",
                "Canonical NAV / ledger",
                "Yes — already dynamic in v2",
                "Align label wording with product preference",
            )
        if section_id == "nav_chart":
            return (
                "PRESENT_BUT_BEHAVIORALLY_DIFFERENT",
                "medium",
                False,
                "M",
                "Startup-static NAV line chart; business-day index",
                "Dynamic sparse ledger NAV chart",
                "Canonical NAV",
                "Yes",
                "Restore v1 chart title/styling; keep sparse point policy",
            )
        return (
            "PRESENT_BUT_BEHAVIORALLY_DIFFERENT",
            "medium",
            False,
            "S",
            "Startup-static tables from workbook at process start",
            "Dynamic recompute from canonical NAV / JSON",
            "Canonical NAV",
            "Yes",
            "Verify numeric parity; restore surrounding layout",
        )

    mapping = {
        "gate_notice": (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Proprietary accept gate hides main content until click",
            "Absent — main content visible immediately",
            "tearsheet_disclosure + session store",
            "No",
            "Port proprietary gate from v1 using shared disclosure module",
        ),
        "firm_description": (
            "MISSING_REQUIRED",
            "high",
            True,
            "S",
            "Lead + principals/inception/products paragraph block",
            "Absent",
            "Static copy",
            "No",
            "Restore description block under header",
        ),
        "nav_footnotes": (
            "MISSING_REQUIRED",
            "medium",
            True,
            "S",
            "Two centered footnotes under NAV chart",
            "Single footnote only",
            "Static copy",
            "No",
            "Restore second percentage / entry-timing footnote",
        ),
        "strategy_overview": (
            "MISSING_REQUIRED",
            "high",
            True,
            "L",
            "Full BTC/ETH strategy narrative + methodology tables",
            "Absent",
            "Static copy + layout",
            "No",
            "Restore Strategy Overview card",
        ),
        "trading_universe": (
            "MISSING_REQUIRED",
            "high",
            True,
            "L",
            "Trading universe, exchanges, fees, risk profile tables",
            "Absent",
            "Static copy",
            "No",
            "Restore Trading Universe & Risk Profile card",
        ),
        "drawdown_table": (
            "MISSING_REQUIRED",
            "high",
            True,
            "L",
            "Maximum Drawdown Profile table incl. SPXTR column",
            "Absent (deferred in Step 7)",
            "NAV + SPXTR benchmark downloads",
            "Future — product decision",
            "Implement drawdown table; decide dynamic vs restart-static",
        ),
        "investor_information": (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Investor Information card with narrative",
            "Absent",
            "Static copy",
            "No",
            "Restore Investor Information card",
        ),
        "account_stats_columns": (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Proprietary vs client Account Stats columns",
            "Absent",
            "Hard-coded ACCOUNT_STATS",
            "No",
            "Restore proprietary/client account statistics table",
        ),
        "terms_and_fees": (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Terms & Fees rows in investor card",
            "Absent",
            "Hard-coded grouped_info",
            "No",
            "Restore Terms & Fees table",
        ),
        "hcdisclaimer": (
            "MISSING_REQUIRED",
            "medium",
            True,
            "S",
            "H&C disclaimer paragraph above footer module",
            "Absent",
            "Static copy",
            "No",
            "Restore inline disclaimer paragraphs",
        ),
        "general_disclaimer": (
            "MISSING_REQUIRED",
            "medium",
            True,
            "S",
            "General disclaimer paragraph",
            "Absent",
            "Static copy",
            "No",
            "Restore general disclaimer paragraph",
        ),
        "proprietary_disclosure": (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Bottom Important Disclosure panel (HEAD uses inline copy; working tree may use tearsheet_disclosure)",
            "Absent",
            "Static copy / shared module",
            "No",
            "Restore disclosure panel (prefer shared tearsheet_disclosure module)",
        ),
        "footer_contact": (
            "MISSING_REQUIRED",
            "medium",
            True,
            "S",
            "Footer contact line",
            "Absent",
            "Static copy",
            "No",
            "Restore footer contact row",
        ),
        "debug_provenance": (
            "MISSING_OPTIONAL",
            "low",
            False,
            "S",
            "Debug provenance table when DEBUG_PROVENANCE",
            "Preview runtime diagnostics card (different purpose)",
            "Config flag",
            "No",
            "Keep v2 diagnostics preview-only; do not copy debug table to production",
        ),
        "preview_banner": (
            "INTENTIONAL_V2_IMPROVEMENT",
            "low",
            False,
            "S",
            "N/A",
            "Preview warning banner",
            "Config",
            "No",
            "Hide/remove banner for production cutover",
        ),
        "mode_alert": (
            "INTENTIONAL_V2_IMPROVEMENT",
            "low",
            False,
            "S",
            "N/A",
            "JSON/workbook mode alert",
            "Runtime snapshot",
            "No",
            "Replace with production-appropriate notice or remove",
        ),
        "runtime_diagnostics": (
            "INTENTIONAL_V2_IMPROVEMENT",
            "low",
            False,
            "S",
            "N/A",
            "Preview diagnostics card",
            "Runtime snapshot",
            "No",
            "Remove before public cutover",
        ),
        "admin_shell": (
            "INTENTIONAL_V2_IMPROVEMENT",
            "medium",
            False,
            "M",
            "N/A",
            "Hidden admin editor (authenticated)",
            "JSON state",
            "Yes",
            "Keep admin hidden from public; no v1 equivalent",
        ),
    }

    if section_id in mapping:
        return mapping[section_id]

    if v1_present and v2_present:
        return (
            "MATCHES_V1",
            "low",
            False,
            "S",
            "Present in v1 layout",
            "Present in v2 layout",
            "Varies",
            "Varies",
            "Verify styling parity",
        )
    if v1_present and not v2_present:
        return (
            "MISSING_REQUIRED",
            "high",
            True,
            "M",
            "Present in v1",
            "Absent in v2",
            "Unknown",
            "TBD",
            "Restore section",
        )
    return (
        "MISSING_OPTIONAL",
        "low",
        False,
        "S",
        "Not in v1",
        "Present in v2 only",
        "N/A",
        "No",
        "Review for production",
    )


def audit_sources(
    *,
    v1_text: str,
    v2_text: str,
    v1_label: str,
    v2_label: str,
) -> AuditReport:
    report = AuditReport(
        v1_source=v1_label,
        v2_source=v2_label,
        v1_checksum=sha256_text(v1_text),
        v2_checksum=sha256_text(v2_text),
    )

    seen: set[str] = set()
    for section_id, needle, desc in V1_SECTION_MARKERS:
        seen.add(section_id)
        v1_present = _contains(v1_text, needle)
        v2_present = _contains(v2_text, needle)
        if section_id == "gate_notice":
            v2_present = v2_present or _contains(v2_text, "Important Notic") or _contains(
                v2_text, "disclaimer-screen"
            )
        (
            classification,
            severity,
            blocker,
            effort,
            v1_behavior,
            v2_behavior,
            data_dep,
            refresh,
            action,
        ) = _classify_section(section_id, v1_present, v2_present)
        report.sections.append(
            SectionAudit(
                section_id=section_id,
                title=needle,
                description=desc,
                v1_present=v1_present,
                v2_present=v2_present,
                classification=classification,
                severity=severity,
                cutover_blocker=blocker,
                effort=effort,
                v1_behavior=v1_behavior,
                v2_behavior=v2_behavior,
                data_dependency=data_dep,
                refresh_after_mutation=refresh,
                recommended_action=action,
            )
        )

    for section_id, needle, desc in V2_SECTION_MARKERS:
        if section_id in seen:
            continue
        v2_present = _contains(v2_text, needle)
        if not v2_present:
            continue
        (
            classification,
            severity,
            blocker,
            effort,
            v1_behavior,
            v2_behavior,
            data_dep,
            refresh,
            action,
        ) = _classify_section(section_id, False, True)
        report.sections.append(
            SectionAudit(
                section_id=section_id,
                title=needle,
                description=desc,
                v1_present=False,
                v2_present=True,
                classification=classification,
                severity=severity,
                cutover_blocker=blocker,
                effort=effort,
                v1_behavior=v1_behavior,
                v2_behavior=v2_behavior,
                data_dependency=data_dep,
                refresh_after_mutation=refresh,
                recommended_action=action,
            )
        )

    # Derived checks
    v1_has_drawdown_fig = "def build_drawdown_figure" in v1_text
    v1_renders_drawdown_fig = "build_drawdown_figure()" in v1_text and "dcc.Graph" in v1_text
    report.sections.append(
        SectionAudit(
            section_id="drawdown_chart",
            title="Drawdown chart",
            description="Plotly drawdown figure",
            v1_present=v1_renders_drawdown_fig,
            v2_present=False,
            classification="MISSING_OPTIONAL" if not v1_renders_drawdown_fig else "MISSING_REQUIRED",
            severity="low" if not v1_renders_drawdown_fig else "medium",
            cutover_blocker=False,
            effort="M",
            v1_behavior="Helper exists but is not mounted in public layout" if not v1_renders_drawdown_fig else "Rendered chart",
            v2_behavior="Absent",
            data_dependency="NAV + benchmarks",
            refresh_after_mutation="TBD",
            recommended_action="Confirm with Kevin whether drawdown chart is required; v1 code exists but layout omits graph",
        )
    )

    report.sections.append(
        SectionAudit(
            section_id="benchmark_nav_trace",
            title="Benchmark traces on NAV chart",
            description="SPXTR / benchmark overlay on NAV figure",
            v1_present=False,
            v2_present=False,
            classification="V1_LEGACY_OR_BUG",
            severity="low",
            cutover_blocker=False,
            effort="M",
            v1_behavior="Benchmarks computed for drawdown table, not NAV chart trace",
            v2_behavior="Explicitly omitted by v2 chart policy",
            data_dependency="yfinance / external",
            refresh_after_mutation="No",
            recommended_action="NEEDS_KEVIN_DECISION on benchmark presentation",
        )
    )

    report.sections.append(
        SectionAudit(
            section_id="public_daily_returns_table",
            title="Public Daily Returns table",
            description="Collapsible daily returns grid",
            v1_present="Daily Returns" in v1_text and "collapse" in v1_text.lower(),
            v2_present=False,
            classification="MATCHES_V1",
            severity="low",
            cutover_blocker=False,
            effort="S",
            v1_behavior="Absent from public layout (confirmed Step 10)",
            v2_behavior="Absent",
            data_dependency="N/A",
            refresh_after_mutation="No",
            recommended_action="No action unless product requests table",
        )
    )

    report.sections.append(
        SectionAudit(
            section_id="header_visual_styling",
            title="Header band styling",
            description="Grey header band and spacing",
            v1_present="header-row" in v1_text and "GREY_BG" in v1_text,
            v2_present="header-row" not in v2_text,
            classification="PRESENT_BUT_VISUALLY_DIFFERENT",
            severity="medium",
            cutover_blocker=True,
            effort="M",
            v1_behavior="Grey header row, larger logo, centered title block",
            v2_behavior="Minimal header without grey band",
            data_dependency="CSS / layout",
            refresh_after_mutation="No",
            recommended_action="Restore v1 header shell styling",
        )
    )

    report.finalize()
    return report


def paused_step11_inventory() -> List[Dict[str, str]]:
    paths = [
        "scripts/tcp_cutover_preflight.py",
        "scripts/preflight_tcp_cutover.py",
        "tests/test_tcp_cutover_preflight.py",
        "docs/tcp_production_cutover_runbook.md",
        "docs/tcp_production_rollback_runbook.md",
        "docs/tcp_release_checklist.md",
        "tcp_config.py",
        "tcp_ts_v2.py",
        ".gitignore",
    ]
    rows = []
    for rel in paths:
        path = REPO_ROOT / rel
        if path.is_file():
            rows.append(
                {
                    "path": rel,
                    "status": "CUTOVER WORK — PAUSED UNTIL UI PARITY",
                    "sha256": sha256_text(path.read_text(encoding="utf-8")),
                }
            )
        else:
            rows.append({"path": rel, "status": "missing", "sha256": ""})
    return rows


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit TCP public UI parity (read-only)")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--v1-source",
        choices=("head", "working-tree"),
        default="head",
        help="tcp_ts.py version to treat as v1 reference",
    )
    args = parser.parse_args(argv)

    if args.v1_source == "head":
        v1_text = _read_git_file("tcp_ts.py")
        v1_label = "git HEAD:tcp_ts.py"
    else:
        v1_text = _read_working_file("tcp_ts.py")
        v1_label = "local working-tree tcp_ts.py"

    v2_text = _read_working_file("tcp_ts_v2.py")
    report = audit_sources(
        v1_text=v1_text,
        v2_text=v2_text,
        v1_label=v1_label,
        v2_label=f"working tree tcp_ts_v2.py @ {subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO_ROOT, text=True).strip()}",
    )

    payload = report.to_dict()
    payload["paused_step11_files"] = paused_step11_inventory()

    if args.json_output:
        args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"VERDICT={report.verdict}")
    missing = [s.section_id for s in report.sections if s.classification == "MISSING_REQUIRED"]
    print(f"MISSING_REQUIRED={len(missing)}")
    print(f"BLOCKERS={sum(1 for s in report.sections if s.cutover_blocker)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
