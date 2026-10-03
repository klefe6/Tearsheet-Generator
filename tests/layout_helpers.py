"""Shared Dash layout helpers for tests (callable vs static layouts)."""
from __future__ import annotations

from typing import Any


def materialize_layout(layout_or_app: Any) -> Any:
    """Return the concrete layout tree from an app or layout object."""
    layout = getattr(layout_or_app, "layout", layout_or_app)
    return layout() if callable(layout) else layout


def _value_text(value: Any) -> str:
    """Flatten nested prop values (e.g. Plotly figure dicts) into searchable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return "".join(_value_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return "".join(_value_text(item) for item in value)
    if hasattr(value, "to_plotly_json"):
        return _value_text(value.to_plotly_json())
    if hasattr(value, "to_dict"):
        try:
            return _value_text(value.to_dict())
        except TypeError:
            return ""
    return ""


def _component_prefix(node: Any) -> str:
    """Emit layout-relevant scalar props once per component (no nested repr)."""
    parts: list[str] = []

    node_id = getattr(node, "id", None)
    if node_id is not None and node_id != "":
        parts.append(f"id='{node_id}'")

    class_name = getattr(node, "className", None)
    if class_name is not None and class_name != "":
        parts.append(str(class_name))

    available = getattr(node, "available_properties", None)
    if available:
        for prop in available:
            if prop in {"children", "id", "className"}:
                continue
            if prop == "style":
                style = getattr(node, "style", None)
                if style:
                    parts.append(str(style))
                continue
            value = getattr(node, prop, None)
            if value is None:
                continue
            if isinstance(value, dict):
                parts.append(_value_text(value))
                continue
            if isinstance(value, (list, tuple)):
                nested = _value_text(value)
                if nested:
                    parts.append(nested)
                continue
            if isinstance(value, bool):
                parts.append(f"{prop}={value}")
            elif isinstance(value, (str, int, float)):
                parts.append(f"{prop}={value}")
            else:
                nested = _value_text(value)
                if nested:
                    parts.append(nested)

    return "".join(parts)


def component_tree_text(node: Any) -> str:
    """Extract readable text recursively from a Dash component tree."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (int, float, bool)):
        return str(node)
    if isinstance(node, (list, tuple)):
        return "".join(component_tree_text(child) for child in node)

    prefix = _component_prefix(node)
    children = getattr(node, "children", None)
    if children is None:
        return prefix
    if isinstance(children, (list, tuple)):
        return prefix + "".join(component_tree_text(child) for child in children)
    return prefix + component_tree_text(children)


def layout_text(layout_or_app: Any) -> str:
    """Resolve callable layouts once and stringify the resulting component tree."""
    return component_tree_text(materialize_layout(layout_or_app))
