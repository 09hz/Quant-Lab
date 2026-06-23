from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.ai.advisor import AIAdvisorService
from services.research.research_context import ResearchContextBuilder, ResearchContextPack


@dataclass
class ResearchAwareAdvisorResult:
    ok: bool
    response_text: str
    context_preview: str
    error: str = ""


class ResearchAwareAdvisor:
    """Advisory-only AI helper that can attach sanitized research/strategy context."""

    def __init__(
        self,
        advisor: AIAdvisorService | None = None,
        context_builder: ResearchContextBuilder | None = None,
    ) -> None:
        self.advisor = advisor or AIAdvisorService()
        self.context_builder = context_builder or ResearchContextBuilder()

    def build_context(
        self,
        *,
        prompt: str,
        strategy_context: str = "",
        include_research: bool = True,
        include_news: bool = False,
        per_feed: int = 2,
    ) -> ResearchContextPack:
        return self.context_builder.build(
            user_prompt=prompt,
            strategy_context=strategy_context,
            include_research=include_research,
            include_news=include_news,
            per_feed=per_feed,
        )

    def ask(
        self,
        *,
        prompt: str,
        strategy_context: str = "",
        strategy_context_file: str | None = None,
        include_research: bool = True,
        include_news: bool = False,
        per_feed: int = 2,
        max_output_tokens: int = 600,
        export_context: bool = False,
    ) -> ResearchAwareAdvisorResult:
        if strategy_context_file:
            strategy_context = Path(strategy_context_file).read_text(encoding="utf-8")

        pack = self.build_context(
            prompt=prompt,
            strategy_context=strategy_context,
            include_research=include_research,
            include_news=include_news,
            per_feed=per_feed,
        )

        if export_context:
            pack.write_exports()

        preview = self._preview(pack)

        try:
            if hasattr(self.advisor, "ask"):
                response = self.advisor.ask(
                    prompt=pack.to_markdown(),
                    max_output_tokens=max_output_tokens,
                )
            else:
                response = self.advisor.generate(
                    pack.to_ai_messages(),
                    max_output_tokens=max_output_tokens,
                )
            return ResearchAwareAdvisorResult(ok=True, response_text=str(response), context_preview=preview)
        except Exception as exc:
            return ResearchAwareAdvisorResult(ok=False, response_text="", context_preview=preview, error=str(exc))

    def _preview(self, pack: ResearchContextPack) -> str:
        source_count = len(pack.research_brief.sources) if pack.research_brief else 0
        news_count = len(pack.research_brief.news) if pack.research_brief else 0
        strategy_chars = len(pack.strategy_context or "")
        return (
            f"research_sources={source_count}; "
            f"news_items={news_count}; "
            f"strategy_context_chars={strategy_chars}; "
            f"include_news={pack.include_news}"
        )
