# Strategy Engine v0.2 Numeric Threshold Patch

Replace:

- `Live/core/StrategyEngine.py`

Optional example updates:

- `Live/docs/strategy_examples/rsi_mean_reversion.txt`
- `Live/docs/strategy_examples/boolean_crossover.txt`

## Fixes

This patch adds support for numeric crossover/crossunder thresholds:

```text
r = ta.rsi(close, 14)

plot r

buy when ta.crossunder(r, 30)
sell when ta.crossover(r, 70)
```

It also keeps support for:

```text
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)

bullCross = ta.crossover(fast, slow)
bearCross = ta.crossunder(fast, slow)

plot fast
plot slow

buy when bullCross
sell when bearCross
```

## Test

```powershell
python -m py_compile .\Live\core\StrategyEngine.py
python .\Live\app.py
```
