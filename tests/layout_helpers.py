"""Shared Dash layout helpers for tests (callable vs static layouts)."""
from __future__ import annotations

from typing import Any


def materialize_layout(app: Any) -> Any:
    """Return the concrete layout tree, calling ``app.layout`` when it is callable."""
    layout = app.layout
    return layout() if callable(layout) else layout


def layout_text(app: Any) -> str:
    """Stringify a materialized Dash layout for content assertions."""
    return str(materialize_layout(app))
