# Settings Env Override Patch 13d

## Purpose

Fixes an IDE-run mismatch where `.env` values such as `LLM_PROVIDER=openai`
load correctly, but `AI_FEATURES_ENABLED=true` still displays as OFF because the
IDE process already supplied an older value such as `AI_FEATURES_ENABLED=false`.

Patch 13d makes the app startup loader call:

```python
load_app_env(override=True, verbose=True)
```

This means the local `.env` file wins for the Dash app process. Because `.env`
is ignored by Git, this is the intended local-development behavior for IDE Run
button launches.

## Files changed

- `Live/app.py`
- `Live/services/config/env_loader.py`
- `Live/docs/patches/settings_env_override_patch_13d.md`

## Security

- Does not expose secrets in the browser.
- Does not commit `.env`.
- Does not enable broker access.
- Does not enable order placement.
- Keeps AI controlled by the existing safety flags.
