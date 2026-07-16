# Patch 17 — Move AI Advisor to Strategy Tab

## Summary

Moves the read-only AI Advisor out of Settings and into the Strategy Lab area.

The Strategy Lab is reorganized into inner tabs:

- Editor
- Backtest
- AI Advisor
- Help

This reduces clutter in the Strategy section while keeping the AI assistant close to strategy scripts and backtest workflows.

## Safety

The AI Advisor remains advisory-only.

It does not:

- place orders
- modify orders
- access broker/account objects
- call external tools
- store API keys in browser storage
- expose secrets
- bypass `services.safety.ai_policy`

## Files changed

- `Live/ui/tabs_ui.py`
- `Live/services/ai/advisor_callbacks.py`
- `Live/assets/zz_strategy_ai_advisor.css`
- `Live/docs/patches/ai_advisor_strategy_panel_patch_17.md`

## Test

```powershell
python -m py_compile .\Live\ui\tabs_ui.py
python -m py_compile .\Live\services\ai\advisor_callbacks.py
python -m py_compile .\Live\app.py
python .\Live\app.py
```

Open the Strategy Lab area and confirm the inner tabs show:

- Editor
- Backtest
- AI Advisor
- Help

The Settings tab should no longer show the AI Advisor prompt panel.
