# Strategy Language v0.5

Strategy Lab uses a safe, Pine-inspired language. It is not full TradingView Pine Script and it never executes arbitrary Python.

## Price series and indicators

```text
high
low
close
volume

fast = ta.sma(close, 9)
slow = ta.ema(close, 21)
r = ta.rsi(close, 14)
atrValue = ta.atr(close, 14)
windowHigh = ta.highest(high, 20)
windowLow = ta.lowest(low, 20)
```

The `ta.` prefix is optional for supported indicators. Supported condition functions are `crossover(a, b)` and `crossunder(a, b)`.

## Conditions and plots

```text
bullCross = ta.crossover(fast, slow)
bearCross = ta.crossunder(fast, slow)
aboveTrend = close > slow
notOverbought = r < 70

longSignal = bullCross and aboveTrend and notOverbought
exitSignal = bearCross or r > 80

plot fast
plot slow
```

Boolean expressions support `and`, `or`, `not`, parentheses, and the comparison operators `>`, `<`, `>=`, `<=`, `==`, and `!=`.

## Strategy orders

Legacy long-only rules remain supported:

```text
buy when longSignal
sell when exitSignal
```

Phase 6 adds equivalent named long-only orders:

```text
entry Long long when longSignal
close Long when exitSignal
```

Both forms generate the same position-aware `BUY` and `SELL` signals. They also create normalized market-order intent records for chart review and backtesting.

Order intents are safe data objects only. They have `auto_execute=False`, do not call the paper broker, and do not submit live orders. Automatic paper execution requires a separate, explicitly armed future workflow.

## Position behavior

- Long-only.
- An entry is generated only while flat.
- A close is generated only while a long position is open.
- Repeated true conditions do not create duplicate entries or closes.
- Existing chart overlays and backtests continue to consume the generated signals.

## Unsupported syntax

The following remain unsupported:

- `strategy.entry(...)` and `strategy.close(...)` Pine calls.
- Short entries.
- Imports, Python functions, classes, loops, and arbitrary code execution.
- `input.string(...)`, `input.bool(...)`, `alertcondition(...)`, and `label.new(...)`.
- `request.security(...)`, arrays, custom functions, and multi-timeframe requests.
- Automatic paper or live broker execution.
