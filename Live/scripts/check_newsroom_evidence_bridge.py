from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "Live"
if str(LIVE) not in sys.path:
    sys.path.insert(0, str(LIVE))


from services.research.newsroom_evidence_bridge import (  # noqa: E402
    build_newsroom_evidence_packet,
    build_research_analyst_context_from_newsroom,
    extract_newsroom_evidence_items,
)


def main() -> int:
    sample_payload = {
        "brief_items": [
            {
                "title": "Consumer Price Index",
                "summary": "CPI rose in the latest release.",
                "source": "BLS",
                "url": "https://www.bls.gov/cpi/",
                "published_at": "2026-06-01",
                "confidence": "high",
                "relevance": "high",
            },
            {
                "title": "NVDA 10-Q",
                "summary": "Company filing describes demand and supply-chain risks.",
                "source": "SEC EDGAR",
                "url": "https://www.sec.gov/",
                "published_at": "2026-05-15",
            },
        ]
    }

    items = extract_newsroom_evidence_items(sample_payload)
    assert len(items) == 2, items
    assert items[0]["source_type"] == "official", items[0]
    assert items[1]["source_type"] == "filing", items[1]

    packet = build_newsroom_evidence_packet(
        sample_payload,
        question="What matters for NVDA?",
        symbol="NVDA",
        topic="macro and company risk",
    )

    assert packet["packet_type"] == "newsroom_research_evidence", packet
    assert packet["item_count"] == 2, packet
    assert packet["source_counts"]["official"] >= 1, packet
    assert packet["source_counts"]["filing"] >= 1, packet
    assert len(packet["source_links"]) == 2, packet

    markdown = build_research_analyst_context_from_newsroom(
        sample_payload,
        question="What matters for NVDA?",
        symbol="NVDA",
    )

    assert "# Research Analyst Evidence Packet" in markdown, markdown
    assert "Consumer Price Index" in markdown, markdown
    assert "NVDA 10-Q" in markdown, markdown
    assert "Use only the evidence items" in markdown, markdown

    print("items=", len(items))
    print("packet_items=", packet["item_count"])
    print("official=", packet["source_counts"]["official"])
    print("filing=", packet["source_counts"]["filing"])
    print("markdown_chars=", len(markdown))
    print("OK: Newsroom evidence bridge converts brief/results into Research Analyst context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
