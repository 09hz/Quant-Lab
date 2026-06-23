# Patch 20b — Combined Research Services + Newsroom Compatibility

## Purpose

Combines the missing research framework and the Quotes-to-Newsroom UI work.

It also fixes:

```text
ImportError: cannot import name 'build_charts_tab' from 'ui.tabs_ui'
```

by adding compatibility aliases in `Live/ui/tabs_ui.py`.

## Added

- `Live/services/research/__init__.py`
- `Live/services/research/source_registry.py`
- `Live/services/research/news_feeds.py`
- `Live/services/research/research_brief.py`
- `Live/scripts/check_research_sources.py`
- `Live/ui/newsroom_ui.py`
- `Live/assets/zz_newsroom_tab.css`

## Safety

Read-only. No broker access, order placement, AI tool calling, or autonomous browsing.
