# Patch 13 — Settings Runtime Diagnostics

## Summary

This patch improves the Settings tab so it shows what the running Dash process actually sees.

It helps diagnose cases where `check_llm_provider.py` is run in one PowerShell window, but `python .\Live\app.py` is launched from another window with different environment variables.

## Files changed

- `Live/ui/tabs_ui.py`
- `Live/assets/zz_settings_tab.css`
- `Live/.env.example`
- `Live/docs/patches/settings_runtime_diagnostics_patch_13.md`

## What the Settings tab now shows

The Settings tab now includes a **Settings Runtime Diagnostics** card with:

- generated timestamp
- Dash process ID
- current working directory
- Python executable
- `MARKET_DATA_PROVIDER`
- `CSV_MARKET_DATA_ROOT`
- `IBKR_HOST`
- `IBKR_PORT`
- `IBKR_CLIENT_ID`
- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_CHAT_TOKEN_PARAM`
- `LLM_SEND_TEMPERATURE`
- masked `OPENAI_API_KEY` configured/missing status

## Security

This patch is read-only.

It does not:

- store API keys in browser storage
- save settings
- edit `.env`
- call OpenAI
- call a local LLM
- call broker APIs
- place trades

Secrets are still shown only as configured/missing.

## Restart behavior

Environment variables are process-scoped. If you set `$env:LLM_PROVIDER` after Dash has already started, the running Dash process will not automatically inherit that new value.

The correct workflow is:

```powershell
$env:AI_FEATURES_ENABLED="true"
$env:LLM_PROVIDER="openai"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-5.4-nano"
$env:OPENAI_API_KEY = Read-Host "OpenAI API key"

python .\Live\app.py
```

Then hard refresh the browser.
