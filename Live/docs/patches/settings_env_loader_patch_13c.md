# Settings Env Loader Patch 13c

## Purpose

Fixes IDE Run button behavior by loading local `.env` files when the Dash app
starts. This lets the Settings tab see the same AI/LLM/provider settings even
when the app is launched from an IDE instead of the PowerShell session where
environment variables were typed.

## Files

- `Live/services/config/__init__.py`
- `Live/services/config/env_loader.py`
- `Live/app.py`
- `Live/.env.example`
- `.gitignore`

## Supported local env files

The loader checks:

1. repo-root `.env`
2. `Live/.env`
3. current-working-directory `.env`

Existing real environment variables win by default.

## Security

Do not commit real `.env` files.

This patch adds ignore rules for:

- `.env`
- `Live/.env`
- `*.env.local`

The Settings tab should show only whether a key is configured. It must never
render the OpenAI API key value in the browser.

## Recommended local `.env`

```env
AI_FEATURES_ENABLED=true
AI_ADVISORY_ONLY=true
AI_ALLOW_ORDER_PLACEMENT=false
AI_ALLOW_BROKER_ACCESS=false
AI_ALLOW_EXTERNAL_TOOLS=false
AI_REQUIRE_HUMAN_CONFIRMATION=true

LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.4-nano
LLM_CHAT_TOKEN_PARAM=auto
LLM_SEND_TEMPERATURE=auto
OPENAI_API_KEY=replace_with_your_local_key
```

Restart Dash after editing `.env`.
