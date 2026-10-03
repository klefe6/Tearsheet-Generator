"""Guardrails for deterministic TCP layout tests."""
from __future__ import annotations

import pytest

from layout_helpers import layout_text
from tcp_layout_support import tcp_layout_benchmark_patches


def test_tcp_layout_fixture_skips_live_benchmark_download(monkeypatch):
    calls: list[str] = []

    def _track_fetch(*_args, **_kwargs):
        calls.append("fetch")
        raise AssertionError("live benchmark download attempted")

    monkeypatch.setattr("tcp_benchmarks._fetch_returns_with_timeout", _track_fetch)

    with tcp_layout_benchmark_patches():
        from tcp_ts_v2 import create_app

        app, _cfg, state, *_ = create_app()
        if state.snapshot is None:
            pytest.skip("runtime unavailable")
        text = layout_text(app)

    assert calls == []
    assert "tcp-public-root" in text or "Maximum Drawdown Profile" in text
