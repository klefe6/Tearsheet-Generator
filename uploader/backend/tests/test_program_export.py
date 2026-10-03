"""Single-program export. Export All stays the fan-out; /api/export/{program}
touches only that program. Downstream HTTP is a local mock, never production.
"""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

from tests.conftest import VALID_ROWS
from tests.test_downstream_export import _downstream_client
from tests.test_downstream_push import TOKEN, _MockIngest


def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIngest)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/api/uploader/ingest-daily-row"
    return server, url


def _seed_all(client) -> None:
    for code, row in VALID_ROWS.items():
        created = client.post(f"/api/rows/{code}", json=row)
        assert created.status_code == 200, created.text


def _programs_called(server) -> set[str]:
    return {req["body"].get("program") for req in server.requests}


def test_pending_counts_are_read_only(sandbox_client):
    _seed_all(sandbox_client)
    before = sandbox_client.get("/api/export/status").json()["pending_by_program"]
    assert before == {"TKP": 1, "TCP": 1, "AGM": 1, "YQ": 1}
    again = sandbox_client.get("/api/export/status").json()["pending_by_program"]
    assert again == before
    for code in ("TKP", "TCP", "AGM", "YQ"):
        row = sandbox_client.get(f"/api/rows/{code}").json()["rows"][0]
        assert row["exported"] is False


def test_export_tcp_calls_tcp_only():
    server, url = _server()
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tkp_ingest_url=url,
        tcp_ingest_url=url,
        agm_ingest_url=url,
    )
    try:
        _seed_all(client)
        response = client.post("/api/export/tcp")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["programs_selected"] == ["TCP"]
        assert set(body["downstream"]["results"]) == {"TCP"}
        assert _programs_called(server) == {"TCP"}
        assert len(server.requests) == 1
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is True
        for code in ("TKP", "AGM", "YQ"):
            assert client.get(f"/api/rows/{code}").json()["rows"][0]["exported"] is False
    finally:
        client.close()
        server.shutdown()


def test_export_all_still_fans_out():
    server, url = _server()
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tkp_ingest_url=url,
        tcp_ingest_url=url,
        agm_ingest_url=url,
    )
    try:
        _seed_all(client)
        response = client.post("/api/export/all")
        assert response.status_code == 200, response.text
        body = response.json()
        assert "programs_selected" not in body
        assert set(body["downstream"]["results"]) == {"TKP", "TCP", "AGM", "YQ"}
        assert body["downstream"]["results"]["YQ"]["status"] == "skipped"
        assert _programs_called(server) == {"TKP", "TCP", "AGM"}
    finally:
        client.close()
        server.shutdown()


def test_unknown_program_is_rejected():
    client = _downstream_client()
    try:
        response = client.post("/api/export/not-a-program")
        assert response.status_code == 404
    finally:
        client.close()


def test_downstream_error_does_not_mark_tcp_exported():
    class _Reject(_MockIngest):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            self.server.requests.append({"body": body})
            payload = {"accepted": False, "message": "ingest is disabled"}
            raw = json.dumps(payload).encode()
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Reject)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/api/uploader/ingest-daily-row"
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tcp_ingest_url=url,
        tkp_ingest_url=url,
        agm_ingest_url=url,
    )
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        response = client.post("/api/export/tcp")
        assert response.status_code == 200
        assert response.json()["downstream"]["results"]["TCP"]["status"] == "failure"
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is False
        assert _programs_called(server) == {"TCP"}
    finally:
        client.close()
        server.shutdown()


def test_tcp_dry_run_query_does_not_mark_exported_or_call_siblings():
    server, url = _server()
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tkp_ingest_url=url,
        tcp_ingest_url=url,
        agm_ingest_url=url,
    )
    try:
        _seed_all(client)
        response = client.post("/api/export/tcp?dry_run=true")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["dry_run"] is True
        assert body["downstream"]["results"]["TCP"]["status"] == "dry_run"
        assert server.requests[0]["body"]["dry_run"] is True
        assert _programs_called(server) == {"TCP"}
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is False
        pending = client.get("/api/export/status").json()["pending_by_program"]
        assert pending["TCP"] == 1
        assert pending["TKP"] == 1
    finally:
        client.close()
        server.shutdown()


def test_dry_run_false_cannot_force_a_live_write():
    client = _downstream_client(export_dry_run=True, export_target_env="production")
    try:
        response = client.post("/api/export/tcp?dry_run=false")
        assert response.status_code == 400
    finally:
        client.close()


def test_second_tcp_export_is_idempotent_at_uploader_level():
    server, url = _server()
    client = _downstream_client(
        export_target_env="production",
        export_dry_run=False,
        downstream_ingest_token=TOKEN,
        tcp_ingest_url=url,
    )
    try:
        client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
        first = client.post("/api/export/tcp")
        assert first.json()["downstream"]["results"]["TCP"]["status"] == "success"
        second = client.post("/api/export/tcp")
        assert second.json()["downstream"]["results"]["TCP"]["status"] == "no_rows"
        assert len(server.requests) == 1
        assert client.get("/api/rows/TCP").json()["rows"][0]["exported"] is True
    finally:
        client.close()
        server.shutdown()
