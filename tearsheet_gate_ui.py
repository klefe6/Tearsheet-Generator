"""
Shared Important Notice gate layout for H&C sibling tearsheets (TCP, TKP, Algominds).

Presentation only — no auth, server binding, or persistence.
"""
from __future__ import annotations

import html as html_module
from typing import Any, Optional, Sequence

import dash_bootstrap_components as dbc
from dash import html

from tearsheet_disclosure import (
    GATE_SCREEN_STYLE,
    PROPRIETARY_GATE_ACCEPT_TEXT,
    proprietary_participation_text,
)

GATE_TITLE_NORMALIZED = "Important Notice"
GATE_TITLE_PREFIX = "Important Notic"
GATE_NOTICE_E_ID = "secret-notice-e"

GATE_SCREEN_ID = "disclaimer-screen"
GATE_INNER_CARD_CLASS = "tearsheet-gate-inner"
GATE_TITLE_HEADING_CLASS = "mb-4 tearsheet-gate-title tcp-public-gate-title"
GATE_TITLE_INLINE_CLASS = "tearsheet-gate-title-inline tcp-gate-title-inline"
GATE_SECRET_E_CLASS = "tearsheet-gate-secret-e tcp-gate-secret-e"
GATE_COPY_LEAD_CLASS = "lead mb-4 tearsheet-gate-copy-lead"
GATE_COPY_MUTED_CLASS = "text-muted mb-5 tearsheet-gate-copy-muted"
GATE_ACCEPT_BUTTON_CLASS = "tearsheet-gate-accept-btn"
GATE_ACCEPT_BUTTON_LABEL = "Accept & Continue"

# Backward-compatible aliases used by tcp_public_sections contract tests.
TCP_GATE_TITLE_HEADING_CLASS = GATE_TITLE_HEADING_CLASS
TCP_GATE_TITLE_INLINE_CLASS = GATE_TITLE_INLINE_CLASS
TCP_GATE_SECRET_E_CLASS = GATE_SECRET_E_CLASS

TEARSHEET_GATE_STATIC_CSS = """
#disclaimer-screen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.3);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
#disclaimer-screen > .tearsheet-gate-inner,
#disclaimer-screen > div {
  background-color: #EBEBEB;
  padding: 1rem;
  border-radius: 1rem;
  width: 90vw;
  max-width: 40rem;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.1);
  text-align: center;
}
#disclaimer-screen h2,
#disclaimer-screen .tearsheet-gate-title {
  font-size: 1.75rem;
  font-weight: 500;
  line-height: 1.2;
  margin: 0 0 1.5rem;
}
#disclaimer-screen p.lead,
#disclaimer-screen .tearsheet-gate-copy-lead {
  max-width: 30rem;
  margin: 0 auto 1rem;
  font-size: 0.95rem;
  line-height: 1.55;
}
#disclaimer-screen .tearsheet-gate-copy-muted {
  max-width: 30rem;
  margin: 0 auto 2rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #6c757d;
}
#disclaimer-screen button,
#disclaimer-screen .tearsheet-gate-accept-btn {
  background-color: #0D3562;
  border-color: #0D3562;
  color: #fff;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  min-width: 10rem;
  border-radius: 0.375rem;
  border: 1px solid transparent;
  cursor: pointer;
}
#disclaimer-screen .tearsheet-gate-secret-e {
  cursor: pointer;
  user-select: none;
}
#main-app.tearsheet-gate-hidden {
  display: none;
}
"""


def normalized_gate_title_text() -> str:
    return GATE_TITLE_NORMALIZED


def build_gate_title_h2(
    *,
    title_id: Optional[str] = None,
    secret_e_id: str = GATE_NOTICE_E_ID,
) -> html.H2:
    kwargs: dict[str, Any] = {
        "children": [
            html.Span(GATE_TITLE_PREFIX, className=GATE_TITLE_INLINE_CLASS),
            html.Span("e", id=secret_e_id, n_clicks=0, className=GATE_SECRET_E_CLASS),
        ],
        "className": GATE_TITLE_HEADING_CLASS,
    }
    if title_id is not None:
        kwargs["id"] = title_id
    return html.H2(**kwargs)


def build_sibling_accept_gate(
    program_code: str,
    *,
    accept_text: Optional[str] = None,
    include_participation_line: bool = True,
    extra_children: Optional[Sequence[Any]] = None,
    title_id: Optional[str] = None,
    copy_lead_id: Optional[str] = None,
    gate_screen_id: str = GATE_SCREEN_ID,
) -> html.Div:
    """Centered proprietary-tier accept gate shared by TCP, TKP, and Algominds preview."""
    children: list[Any] = [
        build_gate_title_h2(title_id=title_id),
    ]
    lead_kwargs: dict[str, Any] = {
        "children": accept_text or PROPRIETARY_GATE_ACCEPT_TEXT,
        "className": GATE_COPY_LEAD_CLASS,
    }
    if copy_lead_id is not None:
        lead_kwargs["id"] = copy_lead_id
    children.append(html.P(**lead_kwargs))
    if include_participation_line:
        children.append(
            html.P(
                proprietary_participation_text(program_code),
                className=GATE_COPY_MUTED_CLASS,
            )
        )
    children.append(
        dbc.Button(
            GATE_ACCEPT_BUTTON_LABEL,
            id="accept-button",
            color="primary",
            className=GATE_ACCEPT_BUTTON_CLASS,
        )
    )
    if extra_children:
        children.extend(extra_children)
    return html.Div(
        id=gate_screen_id,
        style=GATE_SCREEN_STYLE,
        children=html.Div(children=children, className=GATE_INNER_CARD_CLASS),
    )


def render_static_gate_markup(
    program_code: str,
    *,
    accept_text: Optional[str] = None,
    include_participation_line: bool = True,
    include_secret_e: bool = False,
) -> str:
    """HTML fragment for static tearsheet pages (Algominds v2 preview)."""
    lead = html_module.escape(accept_text or PROPRIETARY_GATE_ACCEPT_TEXT)
    if include_secret_e:
        title = (
            f'<h2 class="{GATE_TITLE_HEADING_CLASS}">'
            f'<span class="{GATE_TITLE_INLINE_CLASS}">{GATE_TITLE_PREFIX}</span>'
            f'<span id="{GATE_NOTICE_E_ID}" class="{GATE_SECRET_E_CLASS}">e</span>'
            f"</h2>"
        )
    else:
        title = f'<h2 class="{GATE_TITLE_HEADING_CLASS}">{GATE_TITLE_NORMALIZED}</h2>'
    parts = [
        f'<div id="{GATE_SCREEN_ID}">',
        f'<div class="{GATE_INNER_CARD_CLASS}">',
        title,
        f'<p class="{GATE_COPY_LEAD_CLASS}">{lead}</p>',
    ]
    if include_participation_line:
        muted = html_module.escape(proprietary_participation_text(program_code))
        parts.append(f'<p class="{GATE_COPY_MUTED_CLASS}">{muted}</p>')
    parts.extend(
        [
            f'<button type="button" id="accept-button" class="{GATE_ACCEPT_BUTTON_CLASS}">'
            f"{GATE_ACCEPT_BUTTON_LABEL}</button>",
            "</div>",
            "</div>",
        ]
    )
    return "\n".join(parts)


def static_gate_script() -> str:
    return """
<script>
(function () {
  var gate = document.getElementById("disclaimer-screen");
  var main = document.getElementById("main-app");
  var btn = document.getElementById("accept-button");
  if (!gate || !main || !btn) return;
  main.classList.add("tearsheet-gate-hidden");
  btn.addEventListener("click", function () {
    gate.style.display = "none";
    main.classList.remove("tearsheet-gate-hidden");
  });
})();
</script>
"""
