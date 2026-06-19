# Strategy Language Performance Guard Patch

This patch reduces replay/chart stalls caused by strategy scripts that generate too many markers or overlay lines.

## Changed file

- `Live/core/StrategyEngine.py`

## Fixes

- Caps rendered strategy overlay lines to 6.
- Caps rendered buy/sell markers to the most recent 250.
- Adds position-aware signal generation:
  - BUY fires only while flat.
  - SELL fires only while long.
  - This prevents repeated markers on every candle when a condition stays true.

## Install

```powershell
Copy-Item .\Live\core\StrategyEngine.py .\Live\core\StrategyEngine_backup.py
Copy-Item .\strategy_language_performance_guard_patch\Live\core\StrategyEngine.py .\Live\core\StrategyEngine.py
```

## Test

```powershell
python -m py_compile .\Live\core\StrategyEngine.py
python .\Live\app.py
```

## Commit

```powershell
git add Live\core\StrategyEngine.py
git commit -m "Add strategy render caps and position-aware signals"
git push
```
