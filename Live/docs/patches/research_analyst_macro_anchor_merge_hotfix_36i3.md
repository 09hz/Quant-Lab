# Patch 36i3 - Research Analyst macro anchor merge hotfix

## Purpose

Patch 36i added mandatory macro anchors, but the callback only stored anchor coverage metadata under
`packet["mandatory_macro_anchors"]`. The AI prompt is primarily built from the evidence packet items rendered by
`evidence_packet_to_markdown(packet)`, so macro anchors could be present in status metadata without being visible as
actual evidence.

## Changes

- Merges `macro_anchor_items` into `combined_payload` before brief, result, and supplemental items.
- Expands the evidence packet item cap from 28 to 40 for Research Analyst market-impact questions.
- Raises the Research Analyst prompt builder item cap from 16 to 32.
- Adds `Live/scripts/check_research_analyst_macro_anchor_merge.py`.

## Safety

- No broker access.
- No order placement.
- No unrestricted browsing.
- FRED and Newsroom evidence remains read-only advisory context.
