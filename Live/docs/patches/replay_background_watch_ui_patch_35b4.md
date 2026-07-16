# Patch 35b4 - Watch background replay callback indentation repair

This patch repairs Patch 35b3 by inserting the Watch background replay range
callbacks inside `register_callbacks(...)` with the correct four-space indentation.

## Why this patch exists

Patch 35b3 accidentally dedented the replacement callback block. That made
`@app.callback(...)` appear at module scope in `Live/callbacks.py`, causing:

```text
NameError: name 'app' is not defined
```

## Required cleanup before running

If `Live/callbacks.py` is currently broken, restore only that file first:

```powershell
git restore .\Live\callbacks.py
```

Then run this applier.

## Test

```powershell
python -m py_compile .\Live\services\replay\range_job_manager.py
python -m py_compile .\Live\callbacks.py
python -m py_compile .\Live\ui\tabs_ui.py
python -m py_compile .\Live\scripts\check_replay_range_job_watch_ui.py
python -m py_compile .\Live\app.py
python .\Live\scripts\check_replay_range_job_watch_ui.py
```
