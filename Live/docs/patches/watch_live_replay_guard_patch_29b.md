# Patch 29b — Watch live/replay range guard

This patch disables the replay date range controls while Watch is considered to
be in live mode.

## Why

When Watch is live, the replay range controls can accidentally trigger slower
historical range loads while the user is switching live symbols. That can make
the app feel frozen, especially when IBKR history requests are synchronous.

## Behavior

When live mode is enabled:

- `replay-date` is disabled
- `replay-end-date` is disabled
- `replay-load-range` is disabled

Replay/local/historical mode remains available when the live guard says the
market is closed or when live mode is not enabled.

## Safety

This does not touch broker logic, order routing, strategy execution, Plotly
charts, Tradier, or the market-data providers.

## Notes

If the app still freezes when switching symbols after this patch, the next fix
should move the Watch symbol-change history request into a queued/debounced
background load instead of doing it directly in a Dash callback.
