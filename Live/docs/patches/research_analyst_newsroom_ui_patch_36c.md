# Patch 36c - Newsroom Research Analyst UI

This patch connects the Research Analyst backend to the Newsroom tab.

## Added

- `Live/services/ai/research_analyst_callbacks.py`
- `Live/scripts/check_research_analyst_newsroom_ui.py`
- `Live/assets/zz_research_analyst.css`

## Updated

- `Live/ui/newsroom_ui.py`
- `Live/app.py`

## Behavior

The Newsroom tab now has an AI Research Analyst panel.

The analyst answers questions from the current Newsroom evidence packet:

1. Prefer selected/curated Newsroom brief items.
2. Fall back to Newsroom results when no brief items are selected.
3. Build a source-linked evidence packet.
4. Ask the AI to answer using only that packet for current facts.
5. Display source links used for validation.

## Safety

The Research Analyst does not browse independently. Current facts must come from the Newsroom evidence packet. If evidence is weak or missing, the AI is instructed to say what is missing.
