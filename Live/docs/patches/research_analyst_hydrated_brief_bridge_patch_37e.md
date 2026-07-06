# Patch 37e — Research Analyst hydrated brief bridge

## Purpose

The Newsroom recommendation queue can now hydrate approved FRED recommendations into confirmed official data cards. However, the Research Analyst could still over-focus on auto-generated macro anchors, supplemental discovery links, or the quant playbook scaffold instead of the user-approved hydrated brief.

This patch makes the user-approved brief the first-class evidence source.

## Changes

- Prioritizes `newsroom-brief-store` items before auto macro anchors, result-store leftovers, and supplemental discovery links.
- Preserves hydrated FRED cards by series id instead of deduping them only by URL.
- Raises Research Analyst evidence limits so a full macro brief is not truncated.
- Prepends a compact hydrated-FRED manifest to the AI context.
- Preserves `kind`, `evidence_role`, `series_id`, and metadata in the Newsroom evidence bridge.
- Adds a checker: `Live/scripts/check_research_analyst_hydrated_brief_bridge.py`.

## Expected result

When the brief contains hydrated FRED cards for CPI, PCE, yields, VIX, SP500, NASDAQ, labor, sentiment, manufacturing, orders, and oil, the Research Analyst should see and audit those cards instead of reporting only one hydrated series.

## Safety

This remains research-only. No broker access, account access, or order placement is added.
