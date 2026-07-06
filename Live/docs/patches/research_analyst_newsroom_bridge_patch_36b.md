# Patch 36b - Newsroom evidence bridge

This patch adds a backend bridge between existing Newsroom result/brief data and
the Research Analyst evidence-packet flow from Patch 36a.

## Added

- `Live/services/research/newsroom_evidence_bridge.py`
- `Live/scripts/check_newsroom_evidence_bridge.py`
- `Live/docs/patches/research_analyst_newsroom_bridge_patch_36b.md`

## Purpose

The bridge accepts tolerant Newsroom payload shapes such as:

- `brief_items`
- `selected_items`
- `research_items`
- `items`
- `results`
- `sources`
- nested `payload`, `data`, or `research_brief`

It normalizes them into evidence items with:

- title
- summary
- source
- URL
- domain
- source type
- validity label
- relevance
- confidence
- published/updated date

Then it can produce a compact markdown context block for a future AI Research
Analyst UI.

## Design rule

The AI should not silently browse. It should answer from an evidence packet built
from visible Newsroom sources and show the source links used.
