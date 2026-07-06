# Watch chart state newline hotfix patch 34i

This hotfix repairs `Live/services/watch_chart_state.py` after Patch 34h wrote
literal `\n` escape sequences into the Python file instead of real newlines.

It restores a valid module and keeps the intended behavior:

- `1 hour` replay defaults to the latest-session / `1D` style viewport.
- `1 day` replay defaults to `MAX` so daily candles are visible.
- stale manual zoom ranges are cleared when they do not overlap current candles.
