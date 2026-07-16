from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from .source_registry import TrustedSourceRegistry, build_default_source_registry
from .news_feeds import fetch_default_news


@dataclass
class ResearchBrief:
    title: str
    generated_at: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"Generated at: {self.generated_at}",
            "",
            "## Safety Notes",
        ]

        for note in self.notes:
            lines.append(f"- {note}")

        lines.extend(["", "## Trusted Sources"])
        for source in self.sources:
            lines.append(f"- **{source.get('name', source.get('key'))}** ({source.get('category')}): {source.get('ai_use')}")

        if self.news:
            lines.extend(["", "## Recent News Feed Items"])
            for item in self.news:
                title = item.get("title", "")
                source = item.get("source", "")
                published = item.get("published", "")
                url = item.get("url", "")
                lines.append(f"- **{title}** — {source} {published}".strip())
                if url:
                    lines.append(f"  - URL: {url}")

        return "\n".join(lines).strip() + "\n"

    def to_ai_context(self, max_chars: int = 12000) -> str:
        text = self.to_markdown()
        if len(text) > max_chars:
            return text[: max_chars - 200] + "\n\n[Research brief truncated for token safety.]\n"
        return text


class ResearchBriefBuilder:
    def __init__(self, registry: TrustedSourceRegistry | None = None) -> None:
        self.registry = registry or build_default_source_registry()

    def build(
        self,
        *,
        include_news: bool = False,
        per_feed: int = 2,
        title: str = "Research Context Brief",
    ) -> ResearchBrief:
        news: list[dict[str, Any]] = []
        if include_news:
            news = [item.to_dict() for item in fetch_default_news(per_feed=per_feed)]

        return ResearchBrief(
            title=title,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            sources=self.registry.to_manifest(enabled_only=True),
            news=news,
            notes=[
                "Research context is advisory only and is not a trading signal.",
                "The AI must not place orders or access broker/account tools.",
                "Prefer primary/official sources for macro, filings and policy context.",
                "News items can be incomplete or delayed; verify material facts before acting.",
            ],
        )
