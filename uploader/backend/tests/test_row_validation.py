"""Per-program field acceptance and rejection rules."""

from __future__ import annotations

from tests.conftest import VALID_ROWS


# --- Acceptance -----------------------------------------------------------
def test_tkp_accepts_stonex_and_plus500(sandbox_client):
    r = sandbox_client.post("/api/rows/TKP", json=VALID_ROWS["TKP"])
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    assert row["stonex_nlv"] == 105000
    assert row["plus500_nlv"] == 20000


def test_tcp_accepts_stonex_only(sandbox_client):
    r = sandbox_client.post("/api/rows/TCP", json=VALID_ROWS["TCP"])
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    assert row["stonex_nlv"] == 98000
    assert "plus500_nlv" not in row
    assert "fee" not in row


def test_agm_accepts_tradestation_and_fee(sandbox_client):
    r = sandbox_client.post("/api/rows/AGM", json=VALID_ROWS["AGM"])
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    assert row["tradestation_nlv"] == 30000
    assert row["fee"] == 125.50


def test_yq_accepts_stonex_only(sandbox_client):
    r = sandbox_client.post("/api/rows/YQ", json=VALID_ROWS["YQ"])
    assert r.status_code == 200, r.text
    row = r.json()["row"]
    assert row["stonex_nlv"] == 60000
    assert "fee" not in row
    assert "plus500_nlv" not in row


def test_cash_transfer_defaults_to_zero_when_blank(sandbox_client):
    r = sandbox_client.post(
        "/api/rows/TCP", json={"date": "2026-07-02", "stonex_nlv": 100}
    )
    assert r.status_code == 200, r.text
    assert r.json()["row"]["cash_transfer"] == 0.0


# --- Rejections -----------------------------------------------------------
def test_fee_rejected_for_non_agm(sandbox_client):
    for code in ["TKP", "TCP", "YQ"]:
        payload = dict(VALID_ROWS[code], fee=10)
        r = sandbox_client.post(f"/api/rows/{code}", json=payload)
        assert r.status_code == 422, f"{code}: {r.text}"
        assert "fee" in r.json()["errors"]


def test_plus500_rejected_for_non_tkp(sandbox_client):
    for code in ["TCP", "AGM", "YQ"]:
        payload = dict(VALID_ROWS[code], plus500_nlv=1000)
        r = sandbox_client.post(f"/api/rows/{code}", json=payload)
        assert r.status_code == 422, f"{code}: {r.text}"
        assert "plus500_nlv" in r.json()["errors"]


def test_tradestation_rejected_for_non_agm(sandbox_client):
    for code in ["TKP", "TCP", "YQ"]:
        payload = dict(VALID_ROWS[code], tradestation_nlv=5000)
        r = sandbox_client.post(f"/api/rows/{code}", json=payload)
        assert r.status_code == 422, f"{code}: {r.text}"
        assert "tradestation_nlv" in r.json()["errors"]


def test_required_nlv_missing_rejected(sandbox_client):
    r = sandbox_client.post("/api/rows/TKP", json={"date": "2026-07-01", "plus500_nlv": 1})
    assert r.status_code == 422
    assert "stonex_nlv" in r.json()["errors"]


def test_bad_date_rejected(sandbox_client):
    r = sandbox_client.post(
        "/api/rows/TCP", json={"date": "07/01/2026", "stonex_nlv": 1}
    )
    assert r.status_code == 422
    assert "date" in r.json()["errors"]


def test_non_numeric_nlv_rejected(sandbox_client):
    r = sandbox_client.post(
        "/api/rows/TCP", json={"date": "2026-07-01", "stonex_nlv": "abc"}
    )
    assert r.status_code == 422
    assert "stonex_nlv" in r.json()["errors"]


def test_unknown_program_404(sandbox_client):
    r = sandbox_client.post("/api/rows/XXX", json={"date": "2026-07-01"})
    assert r.status_code == 404
