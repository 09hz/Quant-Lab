from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any

from .source_registry import build_default_source_registry, source_manifest_text
from .news_feeds import NewsItem, news_items_markdown


@dataclass
class ResearchBrief:
    title: str = "Research Brief"
    topic: str = "market context"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_manifest: list[dict[str, Any]] = field(default_factory=list)
    news_items: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"Topic: {self.topic}",
            f"Generated: {self.generated_at}",
            "",
            "## Safety / Usage Notes",
            "- This brief is advisory context only.",
            "- It does not authorize broker access or order placement.",
            "- Prefer official/institutional sources for macro and filings.",
            "- Treat news/commentary as context, not as a trading signal by itself.",
            "",
            "## Trusted Sources",
        ]

        for source in self.source_manifest:
            lines.append(f"- {source.get('name')} ({source.get('category')}): {source.get('url')}")

        if self.news_items:
            lines.append("")
            lines.append("## News Items")
            for item in self.news_items:
                lines.append(f"- [{item.get('source_name')}] {item.get('title')}")

        if self.notes:
            lines.append("")
            lines.append("## Notes")
            for note in self.notes:
                lines.append(f"- {note}")

        return "\n".join(lines)

    def to_ai_context(self) -> str:
        return self.to_markdown()


def build_research_brief(
    topic: str = "market context",
    news_items: list[NewsItem] | None = None,
    notes: list[str] | None = None,
) -> ResearchBrief:
    sources = [source.to_dict() for source in build_default_source_registry()]
    return ResearchBrief(
        topic=topic,
        source_manifest=sources,
        news_items=[item.to_dict() for item in (news_items or [])],
        notes=list(notes or []),
    )


def source_manifest_markdown() -> str:
    return source_manifest_text()


def combined_research_markdown(news_items: list[NewsItem] | None = None, errors: list[str] | None = None) -> str:
    brief = build_research_brief(news_items=news_items or [])
    parts = [brief.to_markdown()]
    if news_items is not None:
        parts.append("")
        parts.append(news_items_markdown(news_items, errors=errors))
    return "\n".join(parts)
