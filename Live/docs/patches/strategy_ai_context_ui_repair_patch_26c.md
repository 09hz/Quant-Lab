# Patch 26c - Repair Strategy AI Advisor context UI

This corrective patch repairs the Strategy AI Advisor panel after Patch 26 inserted context/export controls into the layout in a way that caused Dash to raise:

```text
TypeError: Div.__init__() got multiple values for argument 'id'
```

## Changes

- Replaces `_strategy_build_ai_advisor_panel()` with a clean Dash layout that uses explicit `children=...`.
- Keeps existing AI Advisor IDs.
- Keeps Patch 26 context/export IDs.
- Repairs `app.py` callback registration so AI Advisor callbacks and Strategy context callbacks are registered in separate `try/except` blocks.

## Safety

No broker access, order placement, Tradier wiring, Newsroom changes, or autonomous AI actions are added.
