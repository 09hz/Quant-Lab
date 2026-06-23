from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from dash import Input, Output, State, dcc, html

try:
    from services.research.search_links import build_source_search_links
except Exception:
    build_source_search_links = None

try:
    from services.research.fred_newsroom_adapter import extend_results_with_fred
except Exception:
    extend_results_with_fred = None

def _topic_text(topic: str | None) -> str:
    topic = str(topic or "").strip()
    return topic or "market conditions"

def _build_results(topic: str, sources: list[str] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    if build_source_search_links is not None:
        links = build_source_search_links(topic, sources or None, include_skipped=True)
        for idx, link in enumerate(links, start=1):
            metadata = dict(getattr(link, "metadata", {}) or {})
            kind = getattr(link, "result_type", "research_link")
            selectable = bool(metadata.get("selectable", kind != "skipped" and bool(getattr(link, "url", ""))))
            results.append({
                "id": f"research-{idx}",
                "title": getattr(link, "title", "Untitled"),
                "source": getattr(link, "source", "Source"),
                "url": getattr(link, "url", ""),
                "summary": getattr(link, "summary", ""),
                "topic": topic,
                "kind": kind,
                "confidence": getattr(link, "confidence", "manual-search"),
                "needs_manual_search": bool(getattr(link, "needs_manual_search", False)),
                "selectable": selectable,
                "metadata": metadata,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            })

    if extend_results_with_fred is not None:
        try:
            results = extend_results_with_fred(topic, sources or None, results)
        except Exception as exc:
            results.insert(0, {
                "id": "fred-ui-extension-error",
                "title": "FRED structured data unavailable",
                "source": "FRED",
                "url": "https://fred.stlouisfed.org/",
                "summary": f"FRED UI integration could not build structured cards: {exc}",
                "topic": topic,
                "kind": "fred-data-warning",
                "confidence": "low",
                "needs_manual_search": True,
                "selectable": False,
                "metadata": {"connector": "fred", "error": str(exc)},
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            })

    return results

def _render_result_cards(results: list[dict[str, Any]]) -> list[Any]:
    if not results:
        return [html.Div("No research links yet. Enter a topic and click Fetch Research Links.", className="newsroom-empty")]
    cards: list[Any] = []
    for item in results:
        url = item.get("url", "")
        selectable = bool(item.get("selectable", True))
        kind = item.get("kind", "research_link")
        confidence = item.get("confidence", "manual-search")
        manual = "manual search may be needed" if item.get("needs_manual_search") else "direct/openable result"
        title_node = html.A(item.get("title", "Untitled"), href=url, target="_blank", className="newsroom-result-title") if url else html.Div(item.get("title", "Untitled"), className="newsroom-result-title newsroom-result-title-disabled")
        cards.append(html.Div(
            className=f"newsroom-result-card newsroom-result-{kind}",
            children=[
                html.Div(item.get("source", "Source"), className="newsroom-result-source"),
                title_node,
                html.Div(item.get("summary", ""), className="newsroom-result-summary"),
                html.Div(f"Type: {kind} | Confidence: {confidence} | {manual}", className="newsroom-result-kind"),
                html.Div("Selectable for brief" if selectable else "Not added to brief", className="newsroom-result-selectable"),
                html.Div(url, className="newsroom-result-url") if url else html.Div("No link shown because this source was not relevant for the query.", className="newsroom-result-url"),
            ],
        ))
    return cards

def _brief_markdown(brief: list[dict[str, Any]]) -> str:
    lines = ["# Research Brief", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", "## Selected Research Links", ""]
    if not brief:
        lines.append("_No items selected yet._")
    for idx, item in enumerate(brief, start=1):
        lines += [
            f"### {idx}. {item.get('title', 'Untitled')}",
            f"- Source: {item.get('source', 'Unknown')}",
            f"- Type: {item.get('kind', 'research_link')}",
            f"- Confidence: {item.get('confidence', 'unknown')}",
            f"- URL: {item.get('url', '')}",
            f"- Summary: {item.get('summary', '')}",
            "",
        ]
    lines += ["## AI Use Notes", "", "Use this brief as user-selected research context only.", "These entries may be direct official pages, search links, or data pages.", "Separate facts from assumptions.", "Do not infer broker/account data from this brief."]
    return "\n".join(lines)

def register_newsroom_callbacks(app: Any) -> None:
    @app.callback(
        Output("newsroom-results-store", "data"),
        Output("newsroom-result-selection", "options"),
        Output("newsroom-result-selection", "value"),
        Output("newsroom-results-list", "children"),
        Output("newsroom-status", "children"),
        Input("newsroom-fetch", "n_clicks"),
        State("newsroom-topic-input", "value"),
        State("newsroom-source-filter", "value"),
        prevent_initial_call=True,
    )
    def fetch_research(n_clicks: int, topic: str, sources: list[str]):
        topic_clean = _topic_text(topic)
        results = _build_results(topic_clean, sources)
        selectable = [item for item in results if item.get("selectable")]
        skipped = [item for item in results if not item.get("selectable")]
        options = [{"label": f"{item.get('source')} - {item.get('title')}", "value": item["id"]} for item in selectable]
        status = f"Loaded {len(selectable)} relevant links"
        if skipped:
            status += f"; skipped/flagged {len(skipped)} low-relevance source(s)"
        status += f" for: {topic_clean}"
        return results, options, [], _render_result_cards(results), status

    @app.callback(
        Output("newsroom-brief-store", "data"),
        Output("newsroom-brief-preview", "children"),
        Input("newsroom-add-selected", "n_clicks"),
        Input("newsroom-clear-brief", "n_clicks"),
        State("newsroom-result-selection", "value"),
        State("newsroom-results-store", "data"),
        State("newsroom-brief-store", "data"),
        prevent_initial_call=True,
    )
    def update_brief(add_clicks: int, clear_clicks: int, selected_ids: list[str], results: list[dict[str, Any]], brief: list[dict[str, Any]]):
        from dash import callback_context
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        if triggered == "newsroom-clear-brief":
            return [], _brief_markdown([])
        current = list(brief or [])
        selected = set(selected_ids or [])
        existing = {item.get("id") for item in current}
        for item in results or []:
            if item.get("id") in selected and item.get("id") not in existing and item.get("selectable"):
                current.append(item)
        return current, _brief_markdown(current)

    @app.callback(Output("newsroom-download-json", "data"), Input("newsroom-export-json", "n_clicks"), State("newsroom-brief-store", "data"), prevent_initial_call=True)
    def export_json(n_clicks: int, brief: list[dict[str, Any]]):
        payload = {"kind": "research_brief", "schema_version": "1.2", "generated_at": datetime.now().isoformat(timespec="seconds"), "items": brief or [], "notes": ["JSON is for structured reloads, audit trails, and future app-to-AI attachment.", "Markdown is usually better for direct manual upload to an AI chat."]}
        return dcc.send_string(json.dumps(payload, indent=2), filename="research_brief.json")

    @app.callback(Output("newsroom-download-markdown", "data"), Input("newsroom-export-markdown", "n_clicks"), State("newsroom-brief-store", "data"), prevent_initial_call=True)
    def export_markdown(n_clicks: int, brief: list[dict[str, Any]]):
        return dcc.send_string(_brief_markdown(brief or []), filename="research_brief.md")
