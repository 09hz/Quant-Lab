# Strategy parser + replay performance cache fix

Files included:

- `Live/core/StrategyEngine.py`
- `Live/callbacks.py`

Fixes:

1. Parser order bug:
   `rsiRecover = crossover(rsiSlow, 35)` no longer gets treated as an unsupported indicator assignment.

2. Strategy overlay replay slowdown:
   Watch chart strategy overlays now cache the heavy strategy result and refresh only when the script/data changes.
   Replay ticks filter the cached result to the current visible chart instead of recalculating the whole strategy every tick.

3. Keeps existing safeguards:
   - max rendered strategy lines
   - max rendered strategy signals
   - position-aware buy/sell signal stream

Install from project root:

```powershell
Copy-Item .\Live\core\StrategyEngine.py .\Live\core\StrategyEngine_backup.py
Copy-Item .\Live\callbacks.py .\Live\callbacks_backup.py

Copy-Item .\strategy_performance_cache_parser_fix\Live\core\StrategyEngine.py .\Live\core\StrategyEngine.py
Copy-Item .\strategy_performance_cache_parser_fix\Live\callbacks.py .\Live\callbacks.py

python -m py_compile .\Live\core\StrategyEngine.py
python -m py_compile .\Live\callbacks.py
python .\Live\app.py
```
