from __future__ import annotations

from datetime import datetime
from typing import Any

from dash import html

try:
    from services.research.source_registry import build_default_source_registry
except Exception:
    build_default_source_registry = None


def _source_cards() -> list[Any]:
    if build_default_source_registry is None:
        return [
            html.Div(
                "Research services are not available yet.",
                className="newsroom-muted",
            )
        ]

    cards = []
    for source in build_default_source_registry():
        badges = []
        badges.append(html.Span(source.category, className="newsroom-badge"))
        badges.append(html.Span(source.reliability, className="newsroom-badge newsroom-badge-muted"))
        if source.api_url:
            badges.append(html.Span("api", className="newsroom-badge newsroom-badge-api"))
        if source.rss_url:
            badges.append(html.Span("feed", className="newsroom-badge newsroom-badge-feed"))

        cards.append(
            html.Div(
                [
                    html.Div(source.name, className="newsroom-card-title"),
                    html.Div(badges, className="newsroom-badges"),
                    html.Div(source.description, className="newsroom-card-text"),
                    html.Div(source.url, className="newsroom-link-text"),
                ],
                className="newsroom-source-card",
            )
        )
    return cards


def build_newsroom_tab(*args: Any, **kwargs: Any) -> html.Div:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Newsroom", className="newsroom-title"),
                    html.Div(
                        "Trusted macro, filings, policy, and economic-news sources for future AI research briefs.",
                        className="newsroom-subtitle",
                    ),
                ],
                className="newsroom-header",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Research status", className="newsroom-section-title"),
                            html.Div("Read-only framework", className="newsroom-status-pill"),
                            html.Div(f"Generated: {generated}", className="newsroom-muted"),
                        ],
                        className="newsroom-panel",
                    ),
                    html.Div(
                        [
                            html.Div("AI research rule", className="newsroom-section-title"),
                            html.Div(
                                "The AI should only use attached research briefs/context. It should not freely browse or place trades.",
                                className="newsroom-card-text",
                            ),
                            html.Ul(
                                [
                                    html.Li("Official sources first: FRED, BEA, BLS, SEC, Treasury, Federal Reserve."),
                                    html.Li("Institutional sources for global context: IMF, World Bank, World Economic Forum."),
                                    html.Li("News feeds are context only, not trading signals by themselves."),
                                    html.Li("No broker access, order placement, or secret exposure."),
                                ],
                                className="newsroom-list",
                            ),
                        ],
                        className="newsroom-panel",
                    ),
                ],
                className="newsroom-grid-two",
            ),
            html.Div(
                [
                    html.Div("Trusted Sources", className="newsroom-section-title"),
                    html.Div(_source_cards(), className="newsroom-source-grid"),
                ],
                className="newsroom-panel",
            ),
            html.Div(
                [
                    html.Div("Next implementation", className="newsroom-section-title"),
                    html.Div(
                        "Next: add a Refresh News button and callback that fetches feed headlines, then optionally attach a sanitized research brief to the Strategy AI Advisor.",
                        className="newsroom-card-text",
                    ),
                ],
                className="newsroom-panel",
            ),
        ],
        className="newsroom-root",
    )
