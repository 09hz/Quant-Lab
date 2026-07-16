# Patch 15b — AI Advisor CLI Env Loader

## Purpose

Make AI advisor command-line scripts load the same local `.env` settings as `Live/app.py`.

This fixes the case where the Dash Settings tab can see:

- `AI_FEATURES_ENABLED=true`
- `LLM_PROVIDER=openai`
- `OPENAI_API_KEY=configured`

but `Live/scripts/ask_ai_advisor.py` still reports:

```text
[BLOCKED] AI features are disabled.
```

## Files changed

- `Live/scripts/ask_ai_advisor.py`
- `Live/scripts/check_ai_advisor.py`
- `Live/docs/patches/ai_advisor_env_loader_patch_15b.md`

## Behavior

The scripts now call:

```python
load_app_env(override=True, verbose=False)
```

before constructing the AI advisor or reading the safety policy.

## Security

This patch does not print API keys, does not store secrets in browser storage, and does not enable broker access or order placement.
