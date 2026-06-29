from __future__ import annotations

from pathlib import Path
import sys


LIVE_DIR = Path(__file__).resolve().parents[1]
if str(LIVE_DIR) not in sys.path:
    sys.path.insert(0, str(LIVE_DIR))


from services.ai.research_analyst import ResearchAnalystService
from services.research.evidence_packet import EvidencePacketBuilder, build_evidence_packet


SAMPLE_ITEMS = [
    {
        "title": "Consumer Price Index for All Urban Consumers",
        "publisher": "FRED",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "summary": "Official CPI time series used to monitor inflation pressure.",
        "published_at": "2026-06-12",
        "source_type": "official",
        "values": {"series_id": "CPIAUCSL", "latest_value": "sample"},
        "topics": ["inflation", "macro"],
    },
    {
        "title": "NVDA quarterly report",
        "publisher": "SEC EDGAR",
        "url": "https://www.sec.gov/edgar/browse/?CIK=1045810",
        "summary": "Company filing source for revenue, risk factors, and operating commentary.",
        "published_at": "2026-05-30",
        "source_type": "filing",
        "tickers": ["NVDA"],
        "topics": ["filing", "earnings"],
    },
    {
        "title": "Semiconductor shares move on AI demand expectations",
        "publisher": "Reuters",
        "url": "https://www.reuters.com/",
        "summary": "Market news article discussing investor expectations for AI-related chip demand.",
        "published_at": "2026-06-20",
        "source_type": "major_news",
        "tickers": ["NVDA"],
        "topics": ["news", "semiconductors"],
    },
]


def main() -> int:
    packet = EvidencePacketBuilder().build(
        question="What matters most for NVDA and inflation risk?",
        raw_items=SAMPLE_ITEMS,
        symbol="NVDA",
        topic="stock and macro research",
        max_items=5,
    )

    assert packet.items, "Expected evidence items"
    assert packet.items[0].confidence > 0, "Expected confidence score"
    assert any(item.source.primary for item in packet.items), "Expected at least one primary source"
    assert any(item.source.url for item in packet.items), "Expected source links"

    markdown = packet.to_markdown()
    assert "Research Analyst Evidence Packet" in markdown
    assert "Source Links" in markdown
    assert "Use only the evidence items" in markdown

    packet2 = build_evidence_packet(
        question="Summarize NVDA evidence",
        raw_items=SAMPLE_ITEMS,
        symbol="NVDA",
    )
    assert packet2.symbol == "NVDA"

    prompt = ResearchAnalystService().build_prompt(
        question="Why does this evidence matter for NVDA?",
        raw_items=SAMPLE_ITEMS,
        symbol="NVDA",
        output_style="validity_check",
    )
    assert "Use only the supplied evidence packet" in prompt.system_prompt
    assert "Assess the validity" in prompt.user_prompt
    assert prompt.packet.items

    print(f"items={len(packet.items)} warnings={len(packet.warnings)} links={len(packet.source_links())}")
    print(f"top_item={packet.items[0].title}")
    print("OK: research evidence packets and Research Analyst prompts build correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
