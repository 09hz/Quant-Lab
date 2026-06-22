# Settings Env BOM Patch 13e

## Purpose

Fixes a Windows `.env` parsing edge case where the first key can contain a
hidden UTF-8 BOM character.

Example broken raw key:

```text
\ufeffAI_FEATURES_ENABLED
```

That makes the Settings tab load later LLM values correctly while still showing
`AI_FEATURES_ENABLED` as OFF.

## Changes

- Reads `.env` files with `utf-8-sig`.
- Strips a hidden BOM from parsed keys.
- Keeps local `.env` loading standard-library only.
- Keeps secrets out of logs/browser output.
- Keeps app startup compatible with IDE Run buttons.

## Files

- `Live/services/config/env_loader.py`
- `Live/services/config/__init__.py`
- `Live/docs/patches/settings_env_bom_patch_13e.md`

## Safety

This patch does not enable broker access, order placement, tool calling, or
browser-based secret editing.
