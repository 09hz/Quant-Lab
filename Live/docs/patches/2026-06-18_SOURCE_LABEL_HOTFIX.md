# Strategy Overlay source_label Hotfix

Fixes:

```text
[STRATEGY OVERLAY ERROR] cannot access local variable 'source_label' where it is not associated with a value
```

Cause: the strategy overlay cache key used `source_label` before the variable was assigned in `render_watch_tab`.

Change: `source_label = "live" if use_live_watch_data else "replay"` is now defined before the strategy overlay block.
