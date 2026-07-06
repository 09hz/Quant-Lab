# Patch 22 — Research-aware AI framework

This patch adds a safe research context layer for the AI Advisor.

## Goals

- Give AI an explicit trusted source manifest.
- Allow optional strategy/backtest context attachment.
- Allow optional economic/news feed context.
- Export context packs as Markdown/JSON for debugging.
- Keep AI advisory-only.

## Files

- `Live/services/research/source_registry.py`
- `Live/services/research/news_feeds.py`
- `Live/services/research/research_brief.py`
- `Live/services/research/research_context.py`
- `Live/services/ai/research_aware_advisor.py`
- `Live/scripts/ask_research_ai_advisor.py`

## Safety

The advisor does not get broker access, order placement, account access, or arbitrary browser/tool access.
It receives only the context that the user explicitly attaches or that the app explicitly builds.

## Example

```powershell
python .\Live\scripts\ask_research_ai_advisor.py --print-sources
python .\Live\scripts\ask_research_ai_advisor.py --dry-run --prompt "Explain the macro sources."
python .\Live\scripts\ask_research_ai_advisor.py --prompt "Explain whether my strategy context is enough for analysis."
```

Optional news fetch:

```powershell
python .\Live\scripts\ask_research_ai_advisor.py --include-news --per-feed 2 --dry-run
```

## Next patch

Wire this framework into the Strategy AI Advisor panel:

- Attach current strategy/backtest context.
- Add research context toggle.
- Add news context toggle.
- Preview attached context before sending.
