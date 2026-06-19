# Strategy Language Background Regime Patch

Adds TradingView-style background regime shading to Strategy Language.

## New command

```text
bgcolor conditionName color="green"
bgcolor conditionExpression color="red"
```

Examples:

```text
bullMarket = close > trend and fast > slow
bearMarket = close < trend and fast < slow

bgcolor bullMarket color="green"
bgcolor bearMarket color="red"
```

## Performance protections

The engine merges consecutive true bars into ranges instead of drawing one shape per candle.

Current caps:

```text
MAX_RENDERED_BACKGROUNDS = 80
MAX_RENDERED_STRATEGY_LINES = 6
MAX_RENDERED_STRATEGY_SIGNALS = 250
```

## Files changed

```text
Live/core/StrategyEngine.py
Live/callbacks.py
Live/docs/strategy_examples/background_regime_test.txt
```

## Test

```powershell
python -m py_compile .\Live\core\StrategyEngine.py
python -m py_compile .\Live\callbacks.py
python .\Live\app.py
```

Paste `background_regime_test.txt` in Strategy Lab and run it.
