# Patch 35a — Replay background range job manager

This patch adds a service-only background job manager for replay range loading.

It does **not** wire the Watch UI yet. That is intentional. The goal of 35a is to
add and test the backend job primitive before touching Dash callbacks.

## Added

- `Live/services/replay/range_job_manager.py`
- `Live/scripts/check_replay_range_job_manager.py`
- `Live/docs/patches/replay_background_job_manager_patch_35a.md`

## Why

Long replay range loads can make the app feel frozen because the current Watch
range load runs inside the Dash callback request path. A background job manager
lets the UI start the load quickly, then poll progress.

## Design

The manager is intentionally small:

- in-process threads
- no external queue
- no database
- no Dash imports
- cooperative cancellation
- serializable snapshots for future `dcc.Store` usage

## Important limitation

Cancellation is cooperative. If a loader is inside a blocking IBKR request,
cancel may not stop it immediately. It will become effective when the loader
checks the reporter before or after the blocking call.

## Next patch

Patch 35b should connect this manager to the Watch tab:

- start range job from `replay-load-range`
- show progress in Watch status
- add cancel button
- trigger chart render after success
