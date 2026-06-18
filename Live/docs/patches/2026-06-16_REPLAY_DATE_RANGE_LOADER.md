# Replay Date Range Loader Rewrite

This package contains the cleaned files/sections for the Watch replay date range loader.

## Files

- `Live/ui/tabs_ui.py`
  - Full replacement for your current `Live/ui/tabs_ui.py`.
  - Adds:
    - Watch Interval dropdown
    - Replay Start date picker
    - Replay End date picker
    - Load Range button
    - Weekend-disabled date picker helper
  - Keeps the Strategy Lab, Paper Trading, and Trade Analytics workspace tabs.

- `Live/services/replay_service_date_range_method.py`
  - Paste the method inside your `ReplayService` class in:
    - `Live/services/replay_service.py`

- `Live/callbacks_patches/callbacks_helper_to_add.py`
  - Paste this helper inside `register_callbacks(...)`.

- `Live/callbacks_patches/callbacks_replay_date_range_section.py`
  - Replace your existing Watch replay request-builder clientside callback and your
    `load_watch_symbol_from_request(...)` callback with this section.

## Why callbacks.py is provided as a section, not a full replacement

Your current callbacks file has many recent local changes:
Strategy Lab, backtest UI, paper trading, analytics, watch chart rendering, etc.
Replacing the whole file from an older snapshot would be risky.

## Required imports in callbacks.py

Make sure these are already present near the top:

```python
import pandas as pd
from dash import Input, Output, State, ctx, no_update
```

## Test

```bash
python -m py_compile Live/ui/tabs_ui.py
python -m py_compile Live/services/replay_service.py
python -m py_compile Live/callbacks.py
python Live/app.py
```

Then test:

- Start Monday, End Tuesday, Load Range
- Start Friday, End Monday, Load Range

Friday to Monday should skip Saturday/Sunday and load 2 trading days.
