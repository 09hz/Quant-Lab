# Watch chart state repair hotfix 34f

This hotfix repairs malformed indentation introduced while patching higher-timeframe Watch chart state.

## Fixes

- Rebuilds the Patch 34 replay range safety block in `Live/callbacks.py`.
- Moves `normalize_watch_chart_state_for_render` to a safe top-level guarded import.
- Adds a callable guard around the Watch chart state normalizer.
- Repairs `check_watch_chart_state.py` imports so it runs from the repo root.

No backup files are created. Use Git for rollback.
