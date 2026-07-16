from __future__ import annotations

from typing import Any
from dash import dcc, html
from ui.structured_evidence_preview_ui import build_structured_evidence_preview_panel
from ui.research_autolab_ui import build_research_autolab_panel


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
            dcc.Store(id="newsroom-results-store", data=[], storage_type="session"),
            dcc.Store(id="newsroom-brief-store", data=[], storage_type="session"),
            dcc.Store(id="newsroom-recommendations-store", data=[], storage_type="session"),
            dcc.Store(id="newsroom-rejected-recommendations-store", data=[], storage_type="session"),
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
                            html.Div(
                                className="newsroom-recommendation-panel",
                                children=[
                                    html.Div("Evidence Recommendation Queue", className="newsroom-panel-subtitle"),
                                    html.Div(
                                        "Generate missing-source candidates from the current brief. Review them, then approve only what you want added.",
                                        className="newsroom-help-text",
                                    ),
                                    html.Div(
                                        [
                                            html.Button("Generate Missing Evidence Recommendations", id="newsroom-generate-recommendations", n_clicks=0, className="newsroom-btn"),
                                            html.Button("Approve Selected Recommendations", id="newsroom-approve-recommendations", n_clicks=0, className="newsroom-btn primary"),
                                            html.Button("Reject Selected", id="newsroom-reject-recommendations", n_clicks=0, className="newsroom-btn danger"),
                                        ],
                                        className="newsroom-button-row",
                                    ),
                                    dcc.Checklist(
                                        id="newsroom-recommendation-selection",
                                        options=[],
                                        value=[],
                                        className="newsroom-result-checklist",
                                        inputClassName="newsroom-check-input",
                                        labelClassName="newsroom-result-label",
                                    ),
                                    html.Div(id="newsroom-recommendation-status", className="newsroom-status"),
                                    html.Pre(id="newsroom-recommendation-preview", className="newsroom-brief-preview"),
                                ],
                            ),
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
                    html.Div(
                        id="research-analyst-panel",
                        className="research-analyst-panel",
                        children=[
                            html.Div("AI Research Analyst", className="research-analyst-title"),
                            html.Div(
                                "Ask questions about the current Newsroom brief. Answers are grounded in the evidence packet and source links.",
                                className="research-analyst-subtitle",
                            ),
                            dcc.Textarea(
                                id="research-analyst-question",
                                value="",
                                placeholder="Example: What are the most important highlights, how valid is the evidence, and what is the likely market/stock impact?",
                                className="research-analyst-question",
                            ),
                            html.Div(
                                className="research-analyst-controls",
                                children=[
                                    html.Div(
                                        className="research-analyst-control",
                                        children=[
                                            html.Label("Output style", className="research-analyst-label"),
                                            dcc.Dropdown(
                                                id="research-analyst-style",
                                                options=[
                                                    {"label": "Concise", "value": "concise"},
                                                    {"label": "Detailed", "value": "detailed"},
                                                    {"label": "Bullet brief", "value": "bullet_brief"},
                                                    {"label": "Validity check", "value": "validity_check"},
                                                ],
                                                value="concise",
                                                clearable=False,
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="research-analyst-control research-analyst-control-max-output",
                                        children=[
                                            html.Label("Max output tokens", className="research-analyst-label"),
                                            dcc.Input(
                                                id="research-analyst-max-output",
                                                type="number",
                                                min=800,
                                                max=8000,
                                                step=100,
                                                value=3000,
                                                className="research-analyst-number",
                                            ),
                                            html.Div(
                                                "Recommended: 3,000-5,000 for market impact, sector, and correlation questions. This is an output-token cap, not a credit estimate.",
                                                className="research-analyst-help",
                                            ),
                                        ],
                                    ),
                                    html.Button(
                                        "Ask Research Analyst",
                                        id="research-analyst-ask",
                                        n_clicks=0,
                                        className="primary-button",
                                    ),
                                ],
                            ),
                            html.Div(id="research-analyst-status", className="research-analyst-status"),
                            html.Div(id="research-analyst-response", className="research-analyst-response"),
                            html.Div(id="research-analyst-sources", className="research-analyst-sources"),
                        ],
                    ),

                    html.Pre(id="newsroom-brief-preview", className="newsroom-brief-preview"),
                ],
            ),
            html.Div(
                className="newsroom-section newsroom-structured-evidence-section",
                children=[build_structured_evidence_preview_panel()],
            ),
            html.Div(
                className="newsroom-panel newsroom-autolab-panel",
                children=[build_research_autolab_panel()],
            ),
            html.Div(className="newsroom-panel", children=[html.Div("Trusted Source Registry", className="newsroom-panel-title"), html.Div(_load_source_cards(), className="newsroom-source-grid")]),
        ],
    )

# --- v23.3 Newsroom Auto Lab Render Removal ---
try:
    def _v23_3_text(value):
        return str(value or "").lower().replace("_", " ").replace("-", " ")

    def _v23_3_is_autolab(component):
        blob = f"{_v23_3_text(getattr(component, 'id', ''))} {_v23_3_text(getattr(component, 'className', ''))}"
        if any(token in blob for token in ["auto lab", "autolab", "research autolab"]):
            return True
        children = getattr(component, "children", None)
        if isinstance(children, str):
            txt = _v23_3_text(children)
            return ("auto lab" in txt and len(txt) < 140)
        return False

    def _v23_3_clean(component):
        if component is None:
            return None
        if isinstance(component, list):
            out = []
            for item in component:
                cleaned = _v23_3_clean(item)
                if cleaned is None:
                    continue
                if isinstance(cleaned, list):
                    out.extend(cleaned)
                else:
                    out.append(cleaned)
            return out
        if isinstance(component, tuple):
            return _v23_3_clean(list(component))
        if _v23_3_is_autolab(component):
            return None
        children = getattr(component, "children", None)
        if isinstance(children, (list, tuple)):
            try:
                component.children = _v23_3_clean(list(children))
            except Exception:
                pass
        elif children is not None and not isinstance(children, str):
            try:
                component.children = _v23_3_clean(children)
            except Exception:
                pass
        return component

    def _v23_3_should_wrap(name, obj):
        if not callable(obj) or str(name).startswith("_"):
            return False
        module_name = str(getattr(obj, "__module__", ""))
        if module_name.startswith("dash") or module_name.startswith("plotly"):
            return False
        lowered = str(name).lower()
        return "newsroom" in lowered or any(token in lowered for token in ["layout", "tab", "page", "build", "render"])

    def _v23_3_wrap(fn):
        if getattr(fn, "_v23_3_newsroom_autolab_removed", False):
            return fn

        def _wrapped(*args, **kwargs):
            return _v23_3_clean(fn(*args, **kwargs))

        _wrapped.__name__ = getattr(fn, "__name__", "wrapped_newsroom_layout")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped._v23_3_newsroom_autolab_removed = True
        return _wrapped

    for _name, _obj in list(globals().items()):
        if _v23_3_should_wrap(_name, _obj):
            globals()[_name] = _v23_3_wrap(_obj)

    for _name, _obj in list(globals().items()):
        if str(_name).startswith("_") or callable(_obj):
            continue
        if hasattr(_obj, "children") or hasattr(_obj, "to_plotly_json"):
            globals()[_name] = _v23_3_clean(_obj)

except Exception as _v23_3_error:
    print(f"v23.3 Newsroom Auto Lab Render Removal failed: {_v23_3_error}")
# --- end v23.3 Newsroom Auto Lab Render Removal ---
