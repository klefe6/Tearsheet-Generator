"""Regression coverage for callable Dash layouts and TCP/Y&Q footnote date semantics."""
from __future__ import annotations

from pathlib import Path

import pytest

from layout_helpers import component_tree_text, layout_text, materialize_layout


class _FakeApp:
    def __init__(self, layout):
        self.layout = layout


class _Node:
    def __init__(self, children):
        self.children = children


def test_materialize_layout_calls_callable():
    app = _FakeApp(lambda: {"ok": True})
    assert materialize_layout(app) == {"ok": True}


def test_materialize_layout_passes_through_static():
    app = _FakeApp({"static": 1})
    assert materialize_layout(app) == {"static": 1}


def test_materialize_layout_accepts_layout_directly():
    assert materialize_layout(lambda: "direct") == "direct"


def test_layout_text_stringifies_callable_result():
    app = _FakeApp(lambda: ["drawdown", "$50,000 fixed nominal"])
    text = layout_text(app)
    assert "$50,000 fixed nominal" in text


def test_component_tree_text_handles_nested_children_and_none():
    tree = _Node(
        [
            "Maximum Drawdown Profile",
            None,
            _Node(["$50,000 fixed nominal", 42]),
        ]
    )
    text = component_tree_text(tree)
    assert "Maximum Drawdown Profile" in text
    assert "$50,000 fixed nominal" in text
    assert "42" in text


def test_component_tree_text_emits_dash_id_once_per_component():
    try:
        from dash import html
    except ImportError:
        pytest.skip("dash not installed")

    tree = html.Div(
        id="monthly-calendar-container",
        children=[html.P("Performance Summary")],
    )
    text = component_tree_text(tree)
    assert text.count("id='monthly-calendar-container'") == 1
    assert "Performance Summary" in text


def test_tcp_drawdown_footnote_rejects_obsolete_150k_wording():
    from tcp_drawdown import DRAWDOWN_FOOTNOTE

    assert "$50,000 fixed nominal" in DRAWDOWN_FOOTNOTE
    assert "$150,000" not in DRAWDOWN_FOOTNOTE
    assert "use the same $50,000 fixed nominal" not in DRAWDOWN_FOOTNOTE


def test_yq_source_module_has_no_first_monday_heuristic():
    source = Path(__file__).resolve().parents[1] / "yq_data_current.py"
    text = source.read_text(encoding="utf-8")
    assert "first_monday" not in text
    assert "Data current through" in (
        Path(__file__).resolve().parents[1] / "yq_ts.py"
    ).read_text(encoding="utf-8")
