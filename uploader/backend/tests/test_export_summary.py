"""Reconstruct export UI summary from persisted batch + audit."""
from __future__ import annotations

from app.export_summary import reconstruct_downstream_from_audit


def test_reconstruct_partial_failure_from_audit():
    events = [
        {
            "action": "downstream_export_success",
            "program": "TKP",
            "date": "2026-09-15",
            "detail": {"batch_id": 7, "verification": "verified"},
        },
        {
            "action": "downstream_export_failure",
            "program": "TCP",
            "date": "2026-09-15",
            "detail": {
                "batch_id": 7,
                "error_message": "TCP tearsheet ingest unreachable (HTTP 530).",
            },
        },
    ]
    downstream = reconstruct_downstream_from_audit(7, events)
    assert downstream["results"]["TKP"]["status"] == "success"
    assert downstream["results"]["TCP"]["status"] == "failure"
    assert "530" in downstream["results"]["TCP"]["date_results"][0]["reason"]
