from __future__ import annotations

from typing import Any
from dash import dcc, html


def _safe_get(obj: Any, *names: str, default: str = "") -> str:
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None and str(value).strip():
            return str(value)
    return default


def _load_source_cards() -> list[Any]:
    try:
        from services.research.source_registry import build_default_source_registry
        registry = build_default_source_registry()
        sources = registry.all() if hasattr(registry, "all") else list(registry)
    except Exception:
        sources = [
            {"name": "FRED", "category": "macro", "description": "Federal Reserve economic time-series research.", "url": "https://fred.stlouisfed.org/", "authority": "official"},
            {"name": "SEC EDGAR", "category": "filings", "description": "Company filings and disclosure research.", "url": "https://www.sec.gov/edgar", "authority": "official"},
            {"name": "BLS", "category": "labor/inflation", "description": "Labor, CPI, PPI, and employment statistics.", "url": "https://www.bls.gov/data/", "authority": "official"},
            {"name": "BEA", "category": "macro", "description": "GDP, income, spending, and national accounts.", "url": "https://www.bea.gov/data", "authority": "official"},
        ]

    cards = []
    for source in sources:
        name = _safe_get(source, "name", "title", "id", default="Research Source")
        category = _safe_get(source, "category", "source_type", "kind", default="research")
        authority = _safe_get(source, "authority", "trust_level", "quality", "reliability", default="trusted")
        description = _safe_get(source, "description", "summary", "notes", default="")
        url = _safe_get(source, "url", "base_url", "home_url", "docs_url", default="#")
        cards.append(
            html.Div(
                className="newsroom-source-card",
                children=[
                    html.Div([html.Div(name, className="newsroom-source-name"), html.Div([html.Span(category, className="newsroom-badge"), html.Span(authority, className="newsroom-badge newsroom-badge-muted")], className="newsroom-source-badges")], className="newsroom-source-card-top"),
                    html.Div(description, className="newsroom-source-desc"),
                    html.A("Open source", href=url, target="_blank", className="newsroom-source-link"),
                ],
            )
        )
    return cards


def build_newsroom_tab(*args: Any, **kwargs: Any) -> Any:
    source_options = [
        {"label": "FRED", "value": "fred"},
        {"label": "SEC EDGAR", "value": "sec"},
        {"label": "BLS", "value": "bls"},
        {"label": "BEA", "value": "bea"},
        {"label": "Federal Reserve", "value": "fed"},
        {"label": "Treasury", "value": "treasury"},
        {"label": "IMF", "value": "imf"},
        {"label": "World Bank", "value": "worldbank"},
        {"label": "WEF", "value": "wef"},
        {"label": "General Economic News", "value": "news"},
    ]

    return html.Div(
        className="newsroom-page",
        children=[
            dcc.Store(id="newsroom-results-store", data=[]),
            dcc.Store(id="newsroom-brief-store", data=[]),
            dcc.Download(id="newsroom-download-json"),
            dcc.Download(id="newsroom-download-markdown"),
            html.Div(
                className="newsroom-hero",
                children=[
                    html.Div([html.Div("Newsroom", className="newsroom-title"), html.Div("Interactive research workspace for trusted sources, clickable links, research briefs, and future AI research context.", className="newsroom-subtitle")]),
                    html.Div([html.Span("Read-only research", className="newsroom-pill"), html.Span("No broker access", className="newsroom-pill newsroom-pill-safe"), html.Span("User-selected AI context", className="newsroom-pill newsroom-pill-safe")], className="newsroom-pill-row"),
                ],
            ),
            html.Div(
                className="newsroom-grid",
                children=[
                    html.Div(
                        className="newsroom-panel",
                        children=[
                            html.Div("Research Search", className="newsroom-panel-title"),
                            html.Label("Topic, ticker, or question", className="newsroom-label"),
                            dcc.Input(id="newsroom-topic-input", type="text", value="inflation rates Fed market conditions", debounce=True, className="newsroom-input", placeholder="Example: MSFT inflation rates Fed semiconductors"),
                            html.Label("Sources", className="newsroom-label"),
                            dcc.Checklist(id="newsroom-source-filter", options=source_options, value=["fred", "sec", "bls", "bea", "fed", "news"], className="newsroom-checklist", inputClassName="newsroom-check-input", labelClassName="newsroom-check-label"),
                            html.Div([html.Button("Fetch Research", id="newsroom-fetch", n_clicks=0, className="newsroom-btn primary"), html.Button("Add Selected to Brief", id="newsroom-add-selected", n_clicks=0, className="newsroom-btn"), html.Button("Clear Brief", id="newsroom-clear-brief", n_clicks=0, className="newsroom-btn danger")], className="newsroom-button-row"),
                            html.Div(id="newsroom-status", className="newsroom-status"),
                        ],
                    ),
                    html.Div(
                        className="newsroom-panel",
                        children=[
                            html.Div("Results", className="newsroom-panel-title"),
                            html.Div("Select results, open links, then add selected items to the research brief.", className="newsroom-help-text"),
                            dcc.Checklist(id="newsroom-result-selection", options=[], value=[], className="newsroom-result-checklist", inputClassName="newsroom-check-input", labelClassName="newsroom-result-label"),
                            html.Div(id="newsroom-results-list", className="newsroom-results-list"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="newsroom-panel newsroom-brief-panel",
                children=[
                    html.Div([html.Div("Research Brief", className="newsroom-panel-title"), html.Div([html.Button("Export JSON", id="newsroom-export-json", n_clicks=0, className="newsroom-btn"), html.Button("Export Markdown", id="newsroom-export-markdown", n_clicks=0, className="newsroom-btn"), html.Button("Send Brief to Strategy AI", id="newsroom-send-to-ai", n_clicks=0, className="newsroom-btn disabled", disabled=True)], className="newsroom-button-row")], className="newsroom-brief-header"),
                    html.Div("Add selected results to the brief, then send the selected brief to Strategy AI as read-only advisory context.", className="newsroom-help-text"),
                    html.Pre(id="newsroom-brief-preview", className="newsroom-brief-preview"),
                ],
            ),
            html.Div(className="newsroom-panel", children=[html.Div("Trusted Source Registry", className="newsroom-panel-title"), html.Div(_load_source_cards(), className="newsroom-source-grid")]),
        ],
    )
