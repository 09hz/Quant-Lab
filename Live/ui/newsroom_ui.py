from __future__ import annotations

from datetime import datetime
from typing import Any

from dash import dcc, html

try:
    from services.research.source_registry import build_default_source_registry
except Exception:
    build_default_source_registry = None

try:
    from services.research.research_brief import build_research_brief
except Exception:
    build_research_brief = None


def _source_value(source: Any, *names: str, default: str = "") -> str:
    for name in names:
        if hasattr(source, name):
            value = getattr(source, name)
            if value is not None and str(value).strip():
                return str(value)
        if isinstance(source, dict) and source.get(name):
            return str(source.get(name))
    return default


def _source_list() -> list[Any]:
    if build_default_source_registry is None:
        return []

    registry = build_default_source_registry()

    if registry is None:
        return []

    if hasattr(registry, "all") and callable(getattr(registry, "all")):
        try:
            return list(registry.all())
        except Exception:
            pass

    try:
        return list(registry)
    except Exception:
        return []


def _source_cards():
    sources = _source_list()

    if not sources:
        return [
            html.Div(
                [
                    html.H4("Research sources unavailable"),
                    html.P(
                        "The research source registry could not be loaded. "
                        "Check Live/services/research/source_registry.py.",
                    ),
                ],
                className="newsroom-card newsroom-card-warning",
            )
        ]

    cards = []

    for source in sources:
        name = _source_value(source, "name", "title", "id", default="Unnamed source")
        category = _source_value(source, "category", "source_type", "kind", default="research")
        reliability = _source_value(
            source,
            "reliability",
            "trust_level",
            "quality",
            "authority",
            default="trusted source",
        )
        description = _source_value(
            source,
            "description",
            "summary",
            "notes",
            default="Trusted research/economic context source.",
        )
        url = _source_value(source, "url", "base_url", "home_url", "docs_url", default="")
        api_required = _source_value(source, "api_key_required", "requires_api_key", default="")
        cadence = _source_value(source, "cadence", "update_frequency", "frequency", default="")

        badges = [
            html.Span(category, className="newsroom-badge"),
            html.Span(reliability, className="newsroom-badge newsroom-badge-muted"),
        ]

        if api_required:
            badges.append(
                html.Span(
                    f"API key: {api_required}",
                    className="newsroom-badge newsroom-badge-muted",
                )
            )

        if cadence:
            badges.append(
                html.Span(
                    cadence,
                    className="newsroom-badge newsroom-badge-muted",
                )
            )

        children = [
            html.Div(badges, className="newsroom-badge-row"),
            html.H4(name),
            html.P(description),
        ]

        if url:
            children.append(
                html.Div(
                    url,
                    className="newsroom-source-url",
                    title=url,
                )
            )

        cards.append(html.Div(children, className="newsroom-card"))

    return cards


def _research_brief_preview():
    if build_research_brief is None:
        return "Research brief builder unavailable."

    try:
        brief = build_research_brief(include_news=False)
    except TypeError:
        try:
            brief = build_research_brief()
        except Exception as exc:
            return f"Research brief unavailable: {exc}"
    except Exception as exc:
        return f"Research brief unavailable: {exc}"

    if hasattr(brief, "to_markdown") and callable(getattr(brief, "to_markdown")):
        try:
            return brief.to_markdown()
        except Exception:
            pass

    return str(brief)


def build_newsroom_tab(*args, **kwargs):
    # Accept legacy Quotes-tab args such as symbol_options/default_symbol.
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Newsroom"),
                            html.P(
                                "Read-only market context, research sources, and future AI research inputs.",
                                className="newsroom-subtitle",
                            ),
                        ],
                    ),
                    html.Div(
                        [
                            html.Span("read-only", className="newsroom-status-pill"),
                            html.Span(f"generated {generated_at}", className="newsroom-status-muted"),
                        ],
                        className="newsroom-status-row",
                    ),
                ],
                className="newsroom-header",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Trusted Research Sources"),
                            html.P(
                                "These sources are the approved context pool for future research-aware AI features. "
                                "The AI should receive a controlled research brief, not unrestricted browsing.",
                                className="newsroom-section-note",
                            ),
                            html.Div(_source_cards(), className="newsroom-source-grid"),
                        ],
                        className="newsroom-section",
                    ),
                    html.Div(
                        [
                            html.H3("Research Brief Preview"),
                            html.P(
                                "This preview is intentionally read-only. Later, Strategy AI can attach a sanitized "
                                "brief when the user chooses to include research context.",
                                className="newsroom-section-note",
                            ),
                            dcc.Textarea(
                                id="newsroom-research-brief-preview",
                                value=_research_brief_preview(),
                                readOnly=True,
                                className="newsroom-brief-textarea",
                            ),
                        ],
                        className="newsroom-section",
                    ),
                    html.Div(
                        [
                            html.H3("Future workflow"),
                            html.Ul(
                                [
                                    html.Li("Fetch curated economic/news items."),
                                    html.Li("Build a sanitized research context pack."),
                                    html.Li("Attach that pack to Strategy AI only when the user chooses it."),
                                    html.Li("Keep broker access and order placement blocked."),
                                ]
                            ),
                        ],
                        className="newsroom-section",
                    ),
                ],
                className="newsroom-body",
            ),
        ],
        className="newsroom-tab",
    )
