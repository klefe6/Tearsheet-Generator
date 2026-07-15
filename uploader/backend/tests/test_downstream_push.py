"""Real downstream transport (target_env=production) against a local mock
tearsheet ingest server: dry-run passthrough, real push + mark-exported,
auth header, per-program aggregation, uploader-level idempotency, and
failure handling. The mock speaks the tearsheet_uploader_ingest response
contract ({accepted, action, ...})."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.conftest import VALID_ROWS
from tests.test_downstream_export import _downstream_client

TOKEN = "push-test-token"


def _mock_after_state(body: dict) -> dict:
    """Authoritative after-state matching tearsheet ingest contracts."""
    program = body.get("program")
    date = body.get("date")
    if program == "TCP":
        return {
            "date": date,
            "cash_balance": body["stonex_nlv"],
            "cash_transfers": body.get("cash_transfer", 0),
            "nav_x1": body["stonex_nlv"],
        }
    if program == "AGM":
        return {
            "date": date,
            "tradestation_nlv": body["tradestation_nlv"],
            "cash_transfer": body.get("cash_transfer", 0),
            "fee": body.get("fee", 0),
        }
    if program == "TKP":
        return {
            "date": date,
            "stonex_nlv": body["stonex_nlv"],
            "plus500_nlv": body["plus500_nlv"],
            "cash_transfer": body.get("cash_transfer", 0),
        }
    return dict(body)


class _MockIngest(BaseHTTPRequestHandler):
    server_version = "MockIngest/1.0"

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(
            {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        )
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            payload = {"accepted": False, "action": "rejected", "message": "bad token"}
            code = 401
        else:
            after = _mock_after_state(body)
            dry = bool(body.get("dry_run"))
            payload = {
                "accepted": True,
                "dry_run": dry,
                "program": body.get("program"),
                "date": body.get("date"),
                "action": "created",
                "message": "ok",
                "before": None,
                "after": after,
                "persisted": not dry,
                "authoritative_record_date": body.get("date"),
                "storage_target": "/mock/state.json",
                "display_refreshed": body.get("_display_refreshed", True),
            }
            code = 200
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):  # keep pytest output clean
        pass


@pytest.fixture
def mock_ingest():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIngest)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}/api/uploader/ingest-daily-row"
    finally:
        server.shutdown()


def _push_client(url, dry_run, **overrides):
    kwargs = {
        "export_target_env": "production",
        "export_dry_run": dry_run,
        "downstream_ingest_token": TOKEN,
        "tkp_ingest_url": url,
        "tcp_ingest_url": url,
        "agm_ingest_url": url,
    }
    kwargs.update(overrides)
    return _downstream_client(**kwargs)


def test_dry_run_posts_dry_run_true_and_marks_nothing(mock_ingest):
    server, url = mock_ingest
    client = _push_client(url, dry_run=True)
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        r = client.post("/api/export/all")
        body = r.json()
        assert body["external_calls_made"] == 1
        assert body["transport_implemented"] is True
        assert body["downstream"]["results"]["TKP"]["status"] == "dry_run"
        sent = server.requests[0]["body"]
        assert sent["dry_run"] is True
        assert sent["source"] == "glenn_uploader"
        assert sent["stonex_nlv"] == VALID_ROWS["TKP"]["stonex_nlv"]
        assert sent["plus500_nlv"] == VALID_ROWS["TKP"]["plus500_nlv"]
        # Dry-run never marks exported — the row stays in the next batch.
        assert client.get("/api/rows/TKP").json()["rows"][0]["exported"] is False
    finally:
        client.close()


def test_real_push_marks_exported_and_is_idempotent_at_uploader_level(mock_ingest):
    server, url = mock_ingest
    client = _push_client(url, dry_run=False)
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])
        r = client.post("/api/export/all")
        body = r.json()
        assert body["external_calls_made"] == 2
        assert body["downstream"]["results"]["TKP"]["status"] == "success"
        assert body["downstream"]["results"]["AGM"]["status"] == "success"
        assert all(req["auth"] == f"Bearer {TOKEN}" for req in server.requests)
        assert client.get("/api/rows/TKP").json()["rows"][0]["exported"] is True

        # Second Export All: nothing unexported -> no rows sent, no calls.
        r2 = client.post("/api/export/all")
        body2 = r2.json()
        assert body2["external_calls_made"] == 0
        assert body2["downstream"]["results"]["TKP"]["status"] == "no_rows"
        assert len(server.requests) == 2  # no new HTTP traffic
    finally:
        client.close()


def test_fee_goes_only_to_agm_payload(mock_ingest):
    server, url = mock_ingest
    client = _push_client(url, dry_run=False)
    try:
        client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
        client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])
        client.post("/api/export/all")
        by_program = {req["body"]["program"]: req["body"] for req in server.requests}
        assert "fee" in by_program["AGM"]
        assert "fee" not in by_program["TKP"]
        assert "tradestation_nlv" in by_program["AGM"]
        assert "plus500_nlv" not in by_program["AGM"]
    finally:
        client.close()


def test_yq_skipped_with_explicit_message(mock_ingest):
    server, url = mock_ingest
    client = _push_client(url, dry_run=False)
    try:
        client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
        r = client.post("/api/export/all")
        result = r.json()["downstream"]["results"]["YQ"]
        assert result["status"] == "skipped"
        assert result["date_results"][0]["reason"] == "Y&Q downstream export not implemented yet."
        assert all(req["body"]["program"] != "YQ" for req in server.requests)
    finally:
        client.close()


def test_downstream_rejection_is_a_failure_not_marked_exported(mock_ingest):
    server, url = mock_ingest
    client = _push_client(url, dry_run=False, downstream_ingest_token="wrong-token")
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        r = client.post("/api/export/all")
        body = r.json()
        result = body["downstream"]["results"]["TCP"]
        assert result["status"] == "failure"
        assert body["external_calls_made"] == 1  # call made, rejected downstream
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is False
    finally:
        client.close()


def test_historical_rows_never_pushed(mock_ingest):
    """Backfilled historical rows are invisible to Export All — only manual
    daily_rows become downstream payloads."""
    server, url = mock_ingest
    client = _push_client(url, dry_run=False, backfill_enabled=True)
    try:
        client.post(
            "/api/backfill/import",
            json={
                "dry_run": False,
                "rows": [
                    {"program": "TKP", "date": "2026-06-30", "stonex_nlv": 150000.0,
                     "plus500_nlv": 0.0, "cash_transfer": 0.0, "source": "tkp_state_json"}
                ],
            },
        )
        r = client.post("/api/export/all")
        body = r.json()
        assert body["total_rows"] == 0
        assert body["external_calls_made"] == 0
        assert server.requests == []
    finally:
        client.close()


class _MockIngestNoPersist(_MockIngest):
    """Returns accepted=true but omits durable-write proof."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(
            {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        )
        payload = {
            "accepted": True,
            "dry_run": False,
            "program": body.get("program"),
            "date": body.get("date"),
            "action": "created",
            "message": "ok",
            "before": None,
            "after": _mock_after_state(body),
        }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def mock_ingest_no_persist():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIngestNoPersist)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}/api/uploader/ingest-daily-row"
    finally:
        server.shutdown()


def test_http_200_without_persisted_does_not_mark_exported(mock_ingest_no_persist):
    _server, url = mock_ingest_no_persist
    client = _push_client(url, dry_run=False)
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        r = client.post("/api/export/all")
        result = r.json()["downstream"]["results"]["TCP"]
        assert result["status"] == "failure"
        date = result["date_results"][0]
        assert date["status"] == "not_confirmed"
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is False
    finally:
        client.close()
