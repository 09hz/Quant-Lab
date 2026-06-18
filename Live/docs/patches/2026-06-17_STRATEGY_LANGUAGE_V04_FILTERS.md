# Strategy Language v0.4 Filters Patch

This patch adds practical filters to Strategy Lab.

## New in v0.4

Supported indicator:

```text
atr = ta.atr(close, 14)
```

Supported session filter:

```text
inSession = session("0930-1600")
```

Supported time variables:

```text
hour
minute
dayofweek
time_hhmm
```

Examples:

```text
morning = time_hhmm >= 930 and time_hhmm <= 1130
weekday = dayofweek >= 0 and dayofweek <= 4
```

## Full example

```text
# Trend Filtered EMA + RSI + ATR Session Filter

fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
trend = ta.ema(close, 50)
r = ta.rsi(close, 14)
atr = ta.atr(close, 14)

bullCross = ta.crossover(fast, slow)
bearCross = ta.crossunder(fast, slow)

inSession = session("0930-1600")
aboveTrend = close > trend
notOverbought = r < 70
enoughVolatility = atr > 0.25

longSignal = inSession and bullCross and aboveTrend and notOverbought and enoughVolatility
exitSignal = bearCross or r > 80

plot fast
plot slow
plot trend

buy when longSignal
sell when exitSignal
```

## Notes

- `atr` is calculated internally from high, low, and close.
- The source argument in `ta.atr(close, 14)` is accepted so the current two-argument assignment parser stays stable.
- RSI/ATR/volume are best used as filters until the chart supports lower indicator panels.
