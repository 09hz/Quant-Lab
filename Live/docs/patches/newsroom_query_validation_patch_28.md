# Patch 28 — Newsroom Query Planning and Result Validation

This patch adds a safer research-search layer for the Newsroom.

It separates source homepages, generic search pages, guessed URLs, useful topic-specific search pages, and broken links.

## Added

- `Live/services/research/query_planner.py`
- `Live/services/research/search_links.py`
- `Live/services/research/result_validator.py`
- `Live/scripts/check_newsroom_query_validation.py`

## Checks

```powershell
python .\Live\scripts\check_newsroom_query_validation.py --query "inflation rate"
python .\Live\scripts\check_newsroom_query_validation.py --query "inflation rate" --validate
python .\Live\scripts\check_newsroom_query_validation.py --query "MSFT inflation rates" --json
```

This patch does not give the AI arbitrary browsing or API access. The AI should receive curated research briefs, not unrestricted internet/tool access.
