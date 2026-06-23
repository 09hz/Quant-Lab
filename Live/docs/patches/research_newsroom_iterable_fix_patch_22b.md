
# Patch 22b — Fix Newsroom Research Registry Iteration

## Problem

The Newsroom UI expected `build_default_source_registry()` to return an iterable list.
Patch 22 returns a `TrustedSourceRegistry` object instead.

That caused:

```text
TypeError: 'TrustedSourceRegistry' object is not iterable
```

## Fix

This patch makes the registry compatible in both directions:

- `TrustedSourceRegistry` now supports iteration.
- `newsroom_ui.py` now uses `_registry_sources()` and calls `.all()` when available.

## Scope

UI/research compatibility only.

No broker changes.
No Tradier changes.
No order routing.
No AI trading changes.
