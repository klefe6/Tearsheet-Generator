"""Durable-write verification for downstream export success semantics."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from app.downstream_export import (
    downstream_proves_persistence,
    export_verification_status,
)
from tests.conftest import VALID_ROWS
from tests.test_downstream_export import _downstream_client
from tests.test_downstream_push import (
    TOKEN,
    _MockIngest,
    _mock_after_state,
)


class _MockIngestPendingRefresh(_MockIngest):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(
            {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        )
        after = _mock_after_state(body)
        payload = {
            "accepted": True,
            "dry_run": False,
            "program": body.get("program"),
            "date": body.get("date"),
            "action": "created",
            "after": after,
            "persisted": True,
            "display_refreshed": False,
        }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def mock_ingest_pending_refresh():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIngestPendingRefresh)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}/api/uploader/ingest-daily-row"
    finally:
        server.shutdown()


def test_downstream_proves_persistence_requires_persisted_flag():
    fields = {"stonex_nlv": 98000, "cash_transfer": 500}
    after = {"date": "2026-07-01", "cash_balance": 98000, "cash_transfers": 500}
    assert not downstream_proves_persistence("TCP", fields, {"accepted": True, "after": after})
    assert downstream_proves_persistence(
        "TCP", fields, {"persisted": True, "after": after}
    )


def test_dry_run_response_never_proves_persistence():
    fields = {"stonex_nlv": 98000, "cash_transfer": 500}
    after = {"date": "2026-07-01", "cash_balance": 98000}
    assert not downstream_proves_persistence(
        "TCP", fields, {"persisted": True, "dry_run": True, "after": after}
    )


def test_unchanged_requires_matching_authoritative_after():
    fields = {"tradestation_nlv": 30000, "cash_transfer": 0, "fee": 125.50}
    wrong_after = {"tradestation_nlv": 29999, "cash_transfer": 0, "fee": 125.50}
    right_after = {"tradestation_nlv": 30000, "cash_transfer": 0, "fee": 125.50}
    assert not downstream_proves_persistence(
        "AGM",
        fields,
        {"persisted": True, "action": "unchanged", "after": wrong_after},
    )
    assert downstream_proves_persistence(
        "AGM",
        fields,
        {"persisted": True, "action": "unchanged", "after": right_after},
    )


def test_export_verification_status_pending_refresh():
    fields = {"stonex_nlv": 98000, "cash_transfer": 500}
    after = {"cash_balance": 98000, "cash_transfers": 500}
    resp = {"persisted": True, "after": after, "display_refreshed": False}
    assert export_verification_status("TCP", fields, resp) == "pending_refresh"


def test_tkp_path_unchanged_with_persisted_proof():
    fields = {"stonex_nlv": 105000, "plus500_nlv": 20000, "cash_transfer": 0}
    after = {"stonex_nlv": 105000, "plus500_nlv": 20000, "cash_transfer": 0}
    assert export_verification_status(
        "TKP", fields, {"persisted": True, "after": after, "display_refreshed": True}
    ) == "verified"


def test_pending_refresh_marks_exported_but_surfaces_status(mock_ingest_pending_refresh):
    _server, url = mock_ingest_pending_refresh
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tcp_ingest_url=url,
    )
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        r = client.post("/api/export/all")
        result = r.json()["downstream"]["results"]["TCP"]
        assert result["status"] == "pending_refresh"
        date = result["date_results"][0]
        assert date["status"] == "pending_refresh"
        assert date["verification"] == "pending_refresh"
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is True
    finally:
        client.close()
