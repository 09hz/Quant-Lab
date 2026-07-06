# Patch 26 - Strategy AI Context Attach + Export UI

This patch adds Strategy Lab controls that let a user explicitly attach the current Strategy context to the AI Advisor and export that context as JSON or Markdown.

## Added

- `Live/services/ai/strategy_context_callbacks.py`
- Strategy AI context buttons in `Live/ui/tabs_ui.py`
- callback registration in `Live/app.py`
- CSS additions in `Live/assets/zz_strategy_ai_advisor.css`

## New UI controls

- Attach Current Strategy Context
- Clear Context
- Export Context JSON
- Export Context Markdown

## Context collected

- Current strategy editor text
- Symbol
- Timeframe
- Replay/backtest start and end dates
- Initial cash
- Quantity
- Visible backtest result text
- Chart state summaries when available

## Safety

The AI still receives only user-approved context through the Strategy AI Advisor. This patch does not add broker access, order placement, external tools, Tradier wiring, or autonomous research.
