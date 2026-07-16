# Patch 36e2 - Research Analyst gap-fill hotfix

## Purpose

Patch 36e expected the old Newsroom selection block and failed after Patch 36d had already changed that area. This hotfix is idempotent and accepts either the Patch 36d source-selection logic or the Patch 36e fallback logic.

## Changes

- Keeps lower-confidence/context source selection from Patch 36d when it already exists.
- Adds supplemental Research Analyst source candidates through the approved Newsroom source pipeline.
- Combines selected brief items, current Newsroom results, and supplemental candidates into one evidence packet.
- Requires Research Analyst answers to include market impact, sector impact, correlation/transmission path, bullish/bearish/mixed quarter read, invalidation conditions, source support, and remaining gaps.
- Raises the UI and server-side output range to 800-6,000 with a 2,000 default.

## Safety

This does not enable unrestricted AI browsing. Supplemental sources are generated through the existing Newsroom source builders. The AI still has to label missing evidence and cannot invent current facts not in the evidence packet.
