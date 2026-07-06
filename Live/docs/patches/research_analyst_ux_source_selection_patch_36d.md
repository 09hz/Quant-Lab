# Patch 36d - Research Analyst UX and source-selection improvements

## Purpose

Improve the Newsroom Research Analyst workflow after the first UI version.

## Changes

- Moves the Research Analyst max-output / credit control visually to the left.
- Renames the control to `Max output / credits`.
- Strengthens the Research Analyst prompt so answers include:
  - market impact,
  - stock/sector implications,
  - confirmed facts vs interpretation,
  - missing or stale evidence,
  - invalidation risks,
  - source titles/publishers used.
- Allows lower-confidence or context sources to be added to the Research Brief
  when they are visible and have a usable link.
- Labels lower-confidence/context sources with caution text instead of hiding
  them from the selection list.
- Adds brief markdown caution notes for lower-confidence/context sources.

## Safety

The AI still does not browse by itself. It answers from the Newsroom evidence
packet. Lower-confidence sources are allowed into the brief only when the user
selects them, and they are labeled as requiring verification.
