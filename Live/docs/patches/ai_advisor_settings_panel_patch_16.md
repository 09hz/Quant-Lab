# Patch 16 — Settings AI Advisor Panel

## Summary

Adds the first read-only AI integration point inside the Dash app.

The Settings tab now includes an **AI Advisor** panel with:

- prompt text area
- optional read-only context text area
- prompt template selector
- max-output-token control
- Ask Advisor button
- response/status area

## Safety

This patch keeps the AI advisor advisory-only.

It does not:

- place orders
- modify orders
- access broker/account objects
- call external tools
- store API keys in browser storage
- ask the user to paste secrets
- bypass `services.safety.ai_policy`

The callback calls `AIAdvisorService`, which enforces the central AI safety policy.

## Files changed

- `Live/ui/tabs_ui.py`
- `Live/services/ai/advisor_callbacks.py`
- `Live/app.py`
- `Live/assets/zz_settings_tab.css`
- `Live/docs/patches/ai_advisor_settings_panel_patch_16.md`

## Test

```powershell
python -m py_compile .\Live\ui\tabs_ui.py
python -m py_compile .\Live\services\ai\advisor_callbacks.py
python -m py_compile .\Live\app.py
python .\Live\app.py
```

Open Settings and ask a simple advisory question.

For exact-output testing, use:

```powershell
python .\Live\scripts\ask_ai_advisor.py --healthcheck
```

## Notes

This panel is intentionally small. Later patches can add predefined buttons for:

- explain provider status
- summarize backtest
- explain strategy
- debug latest error
