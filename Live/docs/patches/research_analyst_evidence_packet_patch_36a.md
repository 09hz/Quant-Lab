# Patch 36a — Research Analyst evidence packets

This patch adds the backend foundation for an AI Market Research Analyst mode.

## Added

- `Live/services/research/evidence_packet.py`
- `Live/services/ai/research_analyst.py`
- `Live/scripts/check_research_evidence_packet.py`

## Purpose

The app should not rely on unrestricted AI browsing for current market facts. Instead, the app should collect or receive trusted research items, normalize them into an evidence packet, and ask the AI to answer from that packet.

The evidence packet includes source title, publisher, URL, source type, primary/secondary classification, relevance score, confidence score, validity label, highlights, structured values, and source links.

## AI behavior

Research Analyst prompts instruct the model to use only the provided evidence packet for current facts, avoid inventing dates/prices/events, separate confirmed facts from interpretation, include source links, and flag weak or single-source claims.

## Not included yet

This is backend-only. It does not add a Newsroom UI chat box yet.

Recommended next patches:

- Patch 36b: connect Newsroom brief items to `EvidencePacketBuilder`
- Patch 36c: add Research Analyst UI for source Q&A, validity checks, and source-linked summaries
