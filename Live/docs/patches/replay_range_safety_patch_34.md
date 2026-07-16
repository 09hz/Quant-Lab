# Patch 34 — Replay range safety and timeframe-aware loading

## Purpose

This patch prevents the Watch/Replay UI from appearing frozen when a user accidentally starts a very large interactive replay range load, especially months of `1 min` bars.

The app should use interactive range loading for small ranges and use cached/batch-prepared data for large history.

## Added files

- `Live/services/replay/range_safety.py`
- `Live/scripts/check_replay_range_safety.py`
- `Live/docs/patches/replay_range_safety_patch_34.md`

## Updated files

- `Live/callbacks.py`
- `Live/.env.example`

## Behavior

Interactive range limits:

| Timeframe | Interactive purpose |
|---|---|
| `1 min` | Small, detailed replay windows |
| `5 min` | Medium ranges |
| `15 min` / `30 min` | Larger intraday review |
| `1 hour` / `1 day` | Months/years |

Large `1 min` ranges are blocked with a clear message instead of starting a long blocking IBKR download.

## Environment options

```env
REPLAY_RANGE_GUARD_ENABLED=true
REPLAY_RANGE_FORCE_ALLOW=false
```

`REPLAY_RANGE_FORCE_ALLOW=true` bypasses the guard for one local session, but the UI may block while the request runs.

## Recommended workflow

For months/years:

1. Start with `15 min`, `30 min`, `1 hour`, or `1 day`.
2. Load the large range.
3. Identify interesting dates.
4. Switch to `1 min` only for the smaller window that needs detailed replay.
5. Use the batch exporter/cache builder for months of `1 min` data.

## Validation

```powershell
python .\Live\scripts\check_replay_range_safety.py --timeframe "1 min" --start 2026-01-01 --end 2026-06-23
python .\Live\scripts\check_replay_range_safety.py --timeframe "15 min" --start 2026-01-01 --end 2026-06-23
```
