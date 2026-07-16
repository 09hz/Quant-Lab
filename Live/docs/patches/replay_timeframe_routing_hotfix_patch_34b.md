# Patch 34b — Replay Timeframe Routing Hotfix

This hotfix fixes a follow-up issue from Patch 34 where the replay range
guard could recognize the selected timeframe, but the actual range loader
still routed the IBKR request through `1 min`.

## Why

The terminal logs showed requests such as:

```text
[IB HISTORY_AT SEND] MSFT timeframe=1 min bar_size=1 min duration=1 D
[REPLAY SOURCE] requesting symbol=MSFT, timeframe=1 min
[BAR STORE WRITE] cache\replay\MSFT\1_min\...
```

even after the user selected `1 hour`.

## Behavior after this patch

The Watch range-load callback normalizes the selected timeframe and passes
that value into replay-service range/day load calls.

Expected terminal log examples:

```text
[WATCH LOAD REQUEST] symbol=MSFT timeframe=1 hour load_mode=range ...
```

Downstream history requests should no longer silently fall back to
`timeframe=1 min` for a selected 1-hour range.

## Notes

This patch does not implement background jobs. Long loads can still take
time, but they should now use the selected timeframe and therefore request
far fewer bars for 30-minute or 1-hour ranges.
