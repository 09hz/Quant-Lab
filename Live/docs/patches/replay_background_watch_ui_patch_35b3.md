# Patch 35b3 - Watch background replay range UI newline/checker hotfix

This patch connects Patch 35a's in-process replay range job manager to the Watch
tab.

## What changed

- Adds an app-level job store:
  - `replay-range-job-store`
- Adds a Watch tab progress panel:
  - `replay-range-progress`
  - `replay-range-cancel`
- Starts replay range loads through `ReplayRangeJobManager.start_for_replay_service(...)`
  when `REPLAY_BACKGROUND_RANGE_JOBS_ENABLED=true`.
- Polls job status with the existing `ui-interval`.
- Updates the replay slider and chart render trigger after the background job succeeds.
- Supports cooperative cancellation.

## Important limitation

Cancellation cannot instantly interrupt an IBKR request already in progress. It is
cooperative: the job will cancel between blocking provider calls.

## Env flag

```env
REPLAY_BACKGROUND_RANGE_JOBS_ENABLED=true
```

Set it to `false` to temporarily return to the old synchronous range-load path.

## Test

```powershell
python -m py_compile .\Live\services\replay\range_job_manager.py
python -m py_compile .\Live\callbacks.py
python -m py_compile .\Live\ui\tabs_ui.py
python -m py_compile .\Live\scripts\check_replay_range_job_watch_ui.py
python .\Live\scripts\check_replay_range_job_watch_ui.py
python .\Live\app.py
```


## Patch 35b3 note

This corrected applier writes checker/CSS/docs content with real newlines instead of literal `\n` characters.
