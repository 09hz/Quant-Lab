# Watch chart state return contract hotfix patch 34m

This hotfix repairs the warning:

```text
[WATCH CHART STATE NORMALIZE WARNING] too many values to unpack (expected 2)
```

The Watch render callback expects:

```python
watch_chart_state, watch_default_range = normalize_watch_chart_state_for_render(...)
```

A previous newline repair restored the module but returned only the normalized
state dict. Unpacking that dict produced the warning and made the chart fall
back to `default_range="1D"`, which keeps daily replay hard to see.

Patch 34m restores the intended return contract:

```python
(normalized_state, default_range)
```

It also keeps:

- `1 hour` replay default range: `1D`
- `1 day` replay default range: `MAX`
- stale manual zoom reset on data/timeframe changes
