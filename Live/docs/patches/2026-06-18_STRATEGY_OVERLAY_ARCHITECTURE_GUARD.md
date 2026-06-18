# Strategy Overlay Architecture Guard Patch

This patch stabilizes replay after adding `bgcolor` regime shading.

## Changes

- Keeps `bgcolor ... color="..."` parsing enabled.
- Keeps strategy result caching enabled.
- Renders background regime shading only when replay is paused/manual.
- Skips expensive background `vrect` rendering while replay is actively playing.
- Reduces default overlay caps:
  - strategy lines: 4
  - strategy signals: 150
  - background ranges: 20
- Adds `Live/services/strategy_overlay_service.py` as a reusable cache service scaffold for the next refactor step.

## Why

Plotly layout shapes (`add_vrect`) are expensive when rebuilt every replay tick.
The app can still replay smoothly if backgrounds are cached but only drawn while paused.

## Install

```powershell
Copy-Item .\Live\core\StrategyEngine.py .\Live\core\StrategyEngine_arch_guard_backup.py
Copy-Item .\Live\callbacks.py .\Live\callbacks_arch_guard_backup.py

Copy-Item .\strategy_overlay_architecture_guard_patch\Live\core\StrategyEngine.py .\Live\core\StrategyEngine.py
Copy-Item .\strategy_overlay_architecture_guard_patch\Live\callbacks.py .\Live\callbacks.py
Copy-Item .\strategy_overlay_architecture_guard_patch\Live\services\strategy_overlay_service.py .\Live\services\strategy_overlay_service.py
```

## Test

```powershell
python -m py_compile .\Live\core\StrategyEngine.py
python -m py_compile .\Live\callbacks.py
python -m py_compile .\Live\services\strategy_overlay_service.py
python .\Live\app.py
```

Expected:

- Replay stays responsive while playing.
- Background shading appears when paused or when manually moving through replay.
- Strategy signals/lines still render with caps.
