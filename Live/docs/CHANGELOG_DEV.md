# Development Changelog

## Current Stable State

- Replay date-range loading works.
- Strategy Language supports `ta.*` aliases.
- Boolean signal variables work.
- Comparison expressions and `and` / `or` / `not` work.
- ATR, session, and time filters work.
- Strategy overlay caching started.
- Background regime shading exists, but needs renderer architecture improvements.
- Watch Architecture Refactor v1A foundation files were added.

## Known Issues

- Watch tab render path is still heavy.
- Zoom/pan/range state needs full viewport-service integration.
- Background shading should move to a lighter renderer.
- Long-term chart engine may need client-side rendering.

## Next Work

- Wire `BarViewService` into the Watch render callback.
- Move chart rendering into `WatchChartRenderer`.
- Split chart, metrics, and stats callbacks.
- Stabilize viewport/follow/manual/range behavior.
