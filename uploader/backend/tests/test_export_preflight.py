"""Export preflight blocks live production writes when ingest is unreachable."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.test_downstream_export import _downstream_client


class _Always530(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        self.send_response(530)
        self.end_headers()

    def log_message(self, *args):
        pass


def _start_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_live_export_preflight_blocks_before_row_push():
    server = _start_server(_Always530)
    url = f"http://127.0.0.1:{server.server_address[1]}/ingest"
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token="tok",
        tkp_ingest_url=url,
        tcp_ingest_url=url,
        agm_ingest_url=url,
    )
    client.post("/api/rows/TKP", json={"date": "2026-09-15", "stonex_nlv": 1, "plus500_nlv": 2})
    r = client.post("/api/export/all")
    body = r.json()
    assert body["external_calls_made"] == 0
    assert body["downstream"]["results"]["TKP"]["status"] == "failure"
    reason = body["downstream"]["results"]["TKP"]["date_results"][0]["reason"]
    assert "Preflight blocked" in reason
    rows = client.get("/api/rows/TKP").json()["rows"]
    assert rows[0]["exported"] is False
    latest = client.get("/api/export/latest").json()["batch"]
    assert latest["batch_id"] == body["batch_id"]
    assert latest["downstream"]["results"]["TKP"]["status"] == "failure"
    server.shutdown()


def test_http_530_row_error_is_actionable():
    """When preflight passes but a row push gets 530, message names the ops fix."""
    calls = {"n": 0}

    class _ProbeThen530(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            calls["n"] += 1
            if body.get("dry_run"):
                payload = {
                    "accepted": True,
                    "dry_run": True,
                    "program": body.get("program"),
                    "date": body.get("date"),
                    "action": "unchanged",
                }
                raw = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self.send_response(530)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = _start_server(_ProbeThen530)
    url = f"http://127.0.0.1:{server.server_address[1]}/ingest"
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token="tok",
        tkp_ingest_url=url,
        tcp_ingest_url=url,
        agm_ingest_url=url,
    )
    client.post("/api/rows/TKP", json={"date": "2026-09-15", "stonex_nlv": 1, "plus500_nlv": 2})
    r = client.post("/api/export/all")
    body = r.json()
    assert calls["n"] >= 4  # 3 preflight probes + 1 real row push
    reason = body["downstream"]["results"]["TKP"]["date_results"][0]["reason"]
    assert "HTTP 530" in reason
    assert "tunnel" in reason.lower() or "Cloudflare" in reason
    server.shutdown()
