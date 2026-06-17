# Strategy Language v0.1

This is the supported Strategy Lab scripting language.

The language is Pine-inspired, but it is not full TradingView Pine Script.

## Current supported syntax

### Price series

```text
open
high
low
close
volume

fast = sma(close, 9)
slow = ema(close, 21)
r = rsi(close, 14)

sma(source, length)
ema(source, length)
rsi(source, length)
highest(source, length)
lowest(source, length)

crossover(a, b)
crossunder(a, b)

plot fast
plot slow

buy when crossover(fast, slow)
sell when crossunder(fast, slow)

## Strategy Language v0.3 expressions

Supported comparison operators:

>
<
>=
<=
==
!=
and
or
not

##Example:
fast = sma(close, 9)
slow = ema(close, 21)

plot fast
plot slow

buy when crossover(fast, slow)
sell when crossunder(fast, slow)

BUY signal opens a long position when flat.
SELL signal closes the long position when open.

## Example strategy with multiple conditions:

aboveTrend = close > trend
notOverbought = r < 70

longSignal = bullCross and aboveTrend and notOverbought
exitSignal = bearCross or r > 80

buy when longSignal
sell when exitSignal

Long-only
Fixed quantity
No commission
No slippage
No shorting
No stop loss
No take profit
No portfolio-level sizing

Planned features:
ta.ema()
ta.sma()
ta.rsi()
ta.atr()
ta.supertrend()
and / or / not
> >= < <= == !=
parentheses
boolean variable assignments
plot metadata
plotshape
session filters

Unplanned features:
strategy.entry(...)
strategy.close(...)
input.string(...)
input.bool(...)
alertcondition(...)
label.new(...)
request.security(...)
arrays
loops
custom functions
multi-timeframe requests
live order execution