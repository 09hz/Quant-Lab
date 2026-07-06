# Strategy AI Context Packet Patch 33b

This patch fixes a failure mode where the Strategy AI says it cannot find the current strategy even though the exported context contained one.

## Problem

The attached context can become noisy because backtest exports may include large serialized Plotly chart JSON. When that happens, the useful pieces can be buried or truncated:

- research brief
- current Strategy Lab script
- market/timeframe/cash/quantity
- headline backtest metrics

## Added files

- `Live/services/ai/context_packet.py`
- `Live/scripts/check_strategy_ai_context_packet.py`

## Updated files

- `Live/services/ai/advisor_callbacks.py`
- `Live/services/ai/__init__.py`

## Behavior

Before sending context to the LLM, the app now:

1. Detects whether the context includes a research brief.
2. Detects whether it includes a current strategy context.
3. Detects whether it includes a Strategy Script block.
4. Detects whether it includes current backtest results.
5. Removes bulky cumulative-PnL chart JSON.
6. Promotes the current Strategy Script near the top of the model context.
7. Adds Strategy Lab language rules so the model does not invent generic Python.

## Safety

This patch does not give the model broker access, file access, secret access, or external browsing.
It only restructures user-selected context before it is sent to the advisory LLM.
