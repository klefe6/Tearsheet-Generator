"""Upsert idempotency, last-N retrieval, and delete-last behavior."""

from __future__ import annotations


def test_upsert_by_program_and_date_does_not_duplicate(sandbox_client):
    first = sandbox_client.post(
        "/api/rows/TKP",
        json={"date": "2026-07-01", "stonex_nlv": 100, "plus500_nlv": 50},
    )
    assert first.status_code == 200
    assert first.json()["created"] is True

    # Same date, new values -> update, not a second row.
    second = sandbox_client.post(
        "/api/rows/TKP",
        json={"date": "2026-07-01", "stonex_nlv": 200, "plus500_nlv": 75},
    )
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["row"]["stonex_nlv"] == 200

    rows = sandbox_client.get("/api/rows/TKP?limit=50").json()["rows"]
    same_date = [r for r in rows if r["date"] == "2026-07-01"]
    assert len(same_date) == 1
    assert same_date[0]["stonex_nlv"] == 200


def test_get_last_rows_limit_and_order(sandbox_client):
    for day in range(1, 11):
        sandbox_client.post(
            "/api/rows/YQ",
            json={"date": f"2026-07-{day:02d}", "stonex_nlv": 1000 + day},
        )
    body = sandbox_client.get("/api/rows/YQ?limit=7").json()
    assert body["count"] == 7
    dates = [r["date"] for r in body["rows"]]
    # Newest first, exactly the last 7 calendar days entered.
    assert dates == [f"2026-07-{d:02d}" for d in range(10, 3, -1)]


def test_delete_last_removes_newest(sandbox_client):
    for day in (1, 2, 3):
        sandbox_client.post(
            "/api/rows/AGM",
            json={"date": f"2026-07-0{day}", "tradestation_nlv": 30000 + day},
        )
    r = sandbox_client.delete("/api/rows/AGM/last")
    assert r.status_code == 200
    assert r.json()["deleted"]["date"] == "2026-07-03"

    remaining = [row["date"] for row in sandbox_client.get("/api/rows/AGM").json()["rows"]]
    assert "2026-07-03" not in remaining
    assert remaining[0] == "2026-07-02"


def test_delete_last_on_empty_returns_404(sandbox_client):
    r = sandbox_client.delete("/api/rows/TCP/last")
    assert r.status_code == 404
