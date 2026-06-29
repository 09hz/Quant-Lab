from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from services.research.evidence_packet import EvidencePacket, EvidencePacketBuilder


RESEARCH_ANALYST_SYSTEM_PROMPT = """You are the Research Analyst inside a market research and strategy application.

Your job:
- answer market, macro, company, filing, and news questions from the provided evidence packet
- summarize what matters most
- explain validity and confidence
- link conclusions to sources
- clearly separate confirmed evidence from interpretation

Hard rules:
- Use only the supplied evidence packet for current facts.
- Do not claim you browsed, checked live news, or verified a source unless the packet says so.
- Do not invent prices, dates, article claims, filings, or macro values.
- If evidence is weak or missing, say what is missing.
- Keep trading language advisory and educational, not an instruction to buy or sell.
"""


@dataclass
class ResearchAnalystPrompt:
    system_prompt: str
    user_prompt: str
    context: str
    packet: EvidencePacket

    def as_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "context": self.context,
            "packet": self.packet.as_dict(),
        }


class ResearchAnalystService:
    """Build AI-ready research prompts from controlled evidence packets."""

    def __init__(self, packet_builder: EvidencePacketBuilder | None = None):
        self.packet_builder = packet_builder or EvidencePacketBuilder()

    def build_packet(
        self,
        question: str,
        raw_items: Sequence[Any],
        symbol: str = "",
        topic: str = "",
        max_items: int = 12,
    ) -> EvidencePacket:
        return self.packet_builder.build(
            question=question,
            raw_items=raw_items,
            symbol=symbol,
            topic=topic,
            max_items=max_items,
        )

    def build_prompt(
        self,
        question: str,
        raw_items: Sequence[Any],
        symbol: str = "",
        topic: str = "",
        max_items: int = 12,
        output_style: str = "concise",
    ) -> ResearchAnalystPrompt:
        packet = self.build_packet(question, raw_items, symbol=symbol, topic=topic, max_items=max_items)
        style = str(output_style or "concise").strip().lower()
        if style not in {"concise", "detailed", "bullet_brief", "validity_check"}:
            style = "concise"
        return ResearchAnalystPrompt(
            system_prompt=RESEARCH_ANALYST_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(question, style),
            context=packet.to_markdown(),
            packet=packet,
        )

    def _build_user_prompt(self, question: str, output_style: str) -> str:
        if output_style == "validity_check":
            return (
                f"Question: {question}\n\n"
                "Assess the validity of the provided research evidence. Return:\n"
                "1. What is confirmed\n"
                "2. What is weak or single-source\n"
                "3. Missing evidence\n"
                "4. Most important source links\n"
            )
        if output_style == "detailed":
            return (
                f"Question: {question}\n\n"
                "Return a detailed research answer with these sections:\n"
                "1. Executive summary\n"
                "2. Most important evidence\n"
                "3. Validity and confidence\n"
                "4. Market/strategy implications\n"
                "5. Sources used\n"
            )
        if output_style == "bullet_brief":
            return f"Question: {question}\n\nReturn a compact bullet brief: top 5 highlights, confidence, and source links."
        return f"Question: {question}\n\nReturn a concise answer with: summary, top highlights, validity/confidence, and sources."


def build_research_analyst_prompt(
    question: str,
    raw_items: Sequence[Any],
    symbol: str = "",
    topic: str = "",
    max_items: int = 12,
    output_style: str = "concise",
) -> ResearchAnalystPrompt:
    return ResearchAnalystService().build_prompt(
        question=question,
        raw_items=raw_items,
        symbol=symbol,
        topic=topic,
        max_items=max_items,
        output_style=output_style,
    )
