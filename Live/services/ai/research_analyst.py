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

Authoritative evidence rule:
- If an Approved Hydrated FRED Official Data manifest is provided, treat it as authoritative.
- Count every listed hydrated FRED series before judging evidence gaps.
- Do not collapse multiple hydrated FRED cards into a single macro anchor.
- Do not answer 1 when the hydrated FRED manifest lists multiple approved series.
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
        authoritative_hydrated_manifest: str = "",
        authoritative_hydrated_fred_count: int = 0,
        authoritative_hydrated_fred_series_ids: Sequence[str] | None = None,
    ) -> ResearchAnalystPrompt:
        packet = self.build_packet(
            question,
            raw_items,
            symbol=symbol,
            topic=topic,
            max_items=max_items,
        )

        style = str(output_style or "concise").strip().lower()
        if style not in {"concise", "detailed", "bullet_brief", "validity_check"}:
            style = "concise"

        authoritative_hydrated_fred_series_ids = list(authoritative_hydrated_fred_series_ids or [])

        manifest_block = ""
        if authoritative_hydrated_manifest.strip():
            manifest_block = "\n".join(
                [
                    "## Approved Hydrated FRED Official Data Manifest",
                    f"- Approved hydrated FRED card count: {int(authoritative_hydrated_fred_count or 0)}",
                    f"- Approved hydrated FRED series IDs: {', '.join(authoritative_hydrated_fred_series_ids) if authoritative_hydrated_fred_series_ids else 'not listed'}",
                    "- Treat this manifest as authoritative over competing macro-anchor summaries.",
                    "- Count each listed series as a distinct approved hydrated FRED card.",
                    "",
                    authoritative_hydrated_manifest.strip(),
                ]
            ).strip()

        context = packet.to_markdown()
        if manifest_block:
            context = manifest_block + "\n\n" + context

        return ResearchAnalystPrompt(
            system_prompt=RESEARCH_ANALYST_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(
                question=question,
                output_style=style,
                authoritative_hydrated_fred_count=int(authoritative_hydrated_fred_count or 0),
                authoritative_hydrated_fred_series_ids=authoritative_hydrated_fred_series_ids,
                has_manifest=bool(manifest_block),
            ),
            context=context,
            packet=packet,
        )

    def _build_user_prompt(
        self,
        question: str,
        output_style: str,
        authoritative_hydrated_fred_count: int = 0,
        authoritative_hydrated_fred_series_ids: Sequence[str] | None = None,
        has_manifest: bool = False,
    ) -> str:
        authoritative_hydrated_fred_series_ids = list(authoritative_hydrated_fred_series_ids or [])

        preface = []
        if has_manifest:
            preface.extend(
                [
                    "Before answering, read the Approved Hydrated FRED Official Data Manifest first.",
                    f"The approved hydrated FRED card count is {authoritative_hydrated_fred_count}.",
                    (
                        "Approved hydrated FRED series IDs: "
                        + ", ".join(authoritative_hydrated_fred_series_ids)
                        if authoritative_hydrated_fred_series_ids
                        else "Approved hydrated FRED series IDs were not separately listed."
                    ),
                    "Do not reduce the hydrated FRED count to a single macro anchor.",
                    "",
                ]
            )

        if output_style == "validity_check":
            body = (
                f"Question: {question}\n\n"
                "Assess the validity of the provided research evidence. Return:\n"
                "1. What is confirmed\n"
                "2. What is weak or single-source\n"
                "3. Missing evidence\n"
                "4. Most important source links\n"
            )
        elif output_style == "detailed":
            body = (
                f"Question: {question}\n\n"
                "Return a detailed research answer with these sections:\n"
                "1. Executive summary\n"
                "2. Most important evidence\n"
                "3. Validity and confidence\n"
                "4. Market/strategy implications\n"
                "5. Sources used\n"
            )
        elif output_style == "bullet_brief":
            body = (
                f"Question: {question}\n\n"
                "Return a compact bullet brief: top 5 highlights, confidence, and source links."
            )
        else:
            body = (
                f"Question: {question}\n\n"
                "Return a concise answer with: summary, top highlights, validity/confidence, and sources."
            )

        return "\n".join(preface + [body]).strip()


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