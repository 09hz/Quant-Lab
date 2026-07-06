from __future__ import annotations

from dash import html


def _disabled_preview(*args, **kwargs):
    return html.Div(id='official-evidence-preview-disabled', style={'display': 'none'})


def build_structured_evidence_preview_panel(*args, **kwargs):
    return _disabled_preview(*args, **kwargs)
