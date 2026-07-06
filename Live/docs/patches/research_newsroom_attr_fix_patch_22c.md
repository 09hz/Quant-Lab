# Patch 22c — Fix Newsroom Research Source Attribute Compatibility

This patch fixes a startup crash in the Newsroom tab:

```text
AttributeError: 'ResearchSource' object has no attribute 'reliability'
```

The Newsroom UI was expecting older source fields such as `reliability`, while the newer
research framework may expose different field names.

## Changes

- Replaces `Live/ui/newsroom_ui.py` with a defensive renderer.
- Supports source registries returned as:
  - iterable registries
  - objects with `.all()`
  - lists
- Reads source fields with safe fallbacks:
  - `name` / `title` / `id`
  - `category` / `source_type` / `kind`
  - `reliability` / `trust_level` / `quality` / `authority`
  - `description` / `summary` / `notes`
  - `url` / `base_url` / `home_url` / `docs_url`
- Leaves broker logic, order routing, AI policy, IBKR, CSV provider, and Strategy logic untouched.

## Test

```powershell
python -m py_compile .\Live\ui\newsroom_ui.py
python -m py_compile .\Live\app.py
python .\Live\app.py
```
