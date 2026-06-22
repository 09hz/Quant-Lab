# Patch 10 — Settings AI Safety Locks

## Summary

This patch extends the read-only Settings tab with a dedicated **Future AI Safety Locks** section.

It does not enable AI features. It only reserves a safe place in the UI for future AI-related controls and displays the current environment-driven lock state.

## Files changed

- `Live/ui/tabs_ui.py`
- `Live/assets/zz_settings_tab.css`
- `Live/.env.example`
- `Live/docs/patches/settings_ai_locks_patch_10.md`

## Settings shown

The Settings tab now displays:

- `AI_FEATURES_ENABLED`
- `AI_ADVISORY_ONLY`
- `AI_ALLOW_ORDER_PLACEMENT`
- `AI_ALLOW_BROKER_ACCESS`
- `AI_ALLOW_EXTERNAL_TOOLS`
- `AI_REQUIRE_HUMAN_CONFIRMATION`
- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `OPENAI_API_KEY` as masked/configured-only

## Safe defaults

The safe defaults are:

```env
AI_FEATURES_ENABLED=false
AI_ADVISORY_ONLY=true
AI_ALLOW_ORDER_PLACEMENT=false
AI_ALLOW_BROKER_ACCESS=false
AI_ALLOW_EXTERNAL_TOOLS=false
AI_REQUIRE_HUMAN_CONFIRMATION=true
LLM_PROVIDER=none
LLM_BASE_URL=
OPENAI_API_KEY=
```

## Security rules

This patch is read-only.

It does not:

- Store secrets in browser storage.
- Edit `.env`.
- Call LLM APIs.
- Add AI callbacks.
- Connect to external tools.
- Place trades.
- Change broker/provider state.

Future AI code should be routed through a dedicated service layer, not through Dash callbacks directly. AI code must not be allowed to call broker/order functions directly.
