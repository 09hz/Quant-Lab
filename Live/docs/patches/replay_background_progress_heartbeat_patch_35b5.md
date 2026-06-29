# Patch 35b5 - Watch Replay Background Progress Heartbeat

Patch 35b moved long Watch replay range loads into a background worker, but the
existing `ReplayService.load_date_range(...)` call still reports progress only
at the beginning and end of the operation.

This hotfix keeps the progress panel from appearing stuck at 0% by adding a
conservative heartbeat percent while a job is running.

## What changed

- Added `_replay_job_display_percent(...)` to `Live/callbacks.py`.
- The Watch progress panel now displays a running heartbeat while the worker is
  active.
- If a later ReplayService progress callback reports true per-day progress, the
  UI will use the real percent automatically.

## Important

This patch does not claim exact per-day progress yet. It fixes the stale 0% UI.
True cache/day progress should be a follow-up patch that teaches
`ReplayService.load_date_range(...)` to report cache hits, misses, and current
date to the job reporter.
