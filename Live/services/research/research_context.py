from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any

from .research_brief import ResearchBrief, ResearchBriefBuilder


_SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(token\s*[:=]\s*)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password\s*[:=]\s*)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED_OPENAI_KEY]"),
]


def redact_secrets(text: str) -> str:
    value = str(text or "")
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


@dataclass
class ResearchContextPack:
    user_prompt: str
    strategy_context: str = ""
    research_brief: ResearchBrief | None = None
    include_news: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [
            "# AI Advisor Context Pack",
            "",
            f"Created at: {self.created_at}",
            "",
            "## User Prompt",
            redact_secrets(self.user_prompt),
            "",
        ]

        if self.strategy_context:
            lines.extend(["## Attached Strategy / Backtest Context", redact_secrets(self.strategy_context), ""])

        if self.research_brief is not None:
            lines.extend(["## Trusted Research Brief", self.research_brief.to_ai_context(), ""])

        lines.extend(
            [
                "## Guardrails",
                "- Advisory only.",
                "- Do not place trades.",
                "- Do not claim certainty.",
                "- Mention when a conclusion needs verification.",
                "- Separate source-backed context from speculation.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def to_ai_messages(self) -> list[dict[str, str]]:
        system = (
            "You are an advisory-only trading research assistant. "
            "You may explain strategy behavior, macro context and risk factors. "
            "You must not place orders, access broker accounts, ask for API keys, or claim guaranteed outcomes. "
            "Use attached trusted research context where relevant. Clearly label uncertainty."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": self.to_markdown()},
        ]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.research_brief is not None:
            data["research_brief"] = self.research_brief.to_dict()
        return data

    def write_exports(self, out_dir: str | Path = "research_context_exports", prefix: str = "research_context") -> dict[str, str]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = out / f"{prefix}_{stamp}.md"
        json_path = out / f"{prefix}_{stamp}.json"
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        return {"markdown": str(md_path), "json": str(json_path)}


class ResearchContextBuilder:
    def __init__(self, brief_builder: ResearchBriefBuilder | None = None) -> None:
        self.brief_builder = brief_builder or ResearchBriefBuilder()

    def build(
        self,
        *,
        user_prompt: str,
        strategy_context: str = "",
        include_research: bool = True,
        include_news: bool = False,
        per_feed: int = 2,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchContextPack:
        brief = None
        if include_research:
            brief = self.brief_builder.build(include_news=include_news, per_feed=per_feed)

        return ResearchContextPack(
            user_prompt=user_prompt,
            strategy_context=strategy_context,
            research_brief=brief,
            include_news=include_news,
            metadata=metadata or {},
        )
