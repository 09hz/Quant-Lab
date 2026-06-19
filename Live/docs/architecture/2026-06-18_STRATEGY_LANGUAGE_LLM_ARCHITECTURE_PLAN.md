# Strategy Language, LLM Integration, and Future Architecture Plan

_Last updated: 2026-06-16_

This document preserves the planning notes for the next major phases of the Stock Visualizer / Live app, starting with the upgraded Strategy Lab language and extending through LLM integration, LLM safety, macro/news/fundamental data, multi-asset support, and future paper/live automation.

## 1. Current Strategy Lab Capability

The current Strategy Lab language is a small safe signal language, not full Python and not full Pine Script.

Current working style:

```text
fast = sma(close, 9)
slow = ema(close, 21)

plot fast
plot slow

buy when crossover(fast, slow)
sell when crossunder(fast, slow)
```

Current supported concepts:

- Built-in OHLCV series: `open`, `high`, `low`, `close`, `volume`
- Indicator assignments: `fast = sma(close, 9)`
- Indicator functions: `sma`, `ema`, `rsi`, `highest`, `lowest`
- Plot lines: `plot fast`
- Signal rules: `buy when ...`, `sell when ...`
- Backtest: long-only, fixed quantity, no commission/slippage/stops/shorting yet

## 2. Long-Term Strategy Language Goal

The goal is to build toward Pine-like scripts with inputs, presets, session filters, boolean expressions, ternary expressions, `ta.` namespace, Supertrend, ATR, plots, plot shapes, labels, alerts, strategy entries/exits, backtesting, paper automation, and future live automation behind strict safeguards.

Near-term target style:

```text
fastEMA = ta.ema(close, 9)
slowEMA = ta.ema(close, 21)
supertrendLine, trendDirection = ta.supertrend(3.0, 10)

emaBullCross = ta.crossover(fastEMA, slowEMA)
emaBearCross = ta.crossunder(fastEMA, slowEMA)
supertrendBull = trendDirection < 0

longSignal = emaBullCross and supertrendBull
exitSignal = emaBearCross

plot fastEMA title="Fast EMA"
plot slowEMA title="Slow EMA"
plot supertrendLine title="Supertrend"

buy when longSignal
sell when exitSignal
```

## 3. Strategy Language Upgrade Roadmap

### Phase 1 — Boolean Expressions and Comparisons

Add:

```text
> < >= <= == !=
and or not
parentheses
```

Target:

```text
fast = ema(close, 9)
slow = ema(close, 21)
trend = ema(close, 50)

longSignal = crossover(fast, slow) and close > trend
exitSignal = crossunder(fast, slow)

plot fast
plot slow
plot trend

buy when longSignal
sell when exitSignal
```

### Phase 2 — Pine-Style `ta.` Namespace

Support both existing and Pine-style names:

```text
ema(close, 9)
ta.ema(close, 9)
sma(close, 20)
ta.sma(close, 20)
rsi(close, 14)
ta.rsi(close, 14)
```

Add:

```text
ta.atr(length)
ta.supertrend(factor, atrLength)
ta.crossover(a, b)
ta.crossunder(a, b)
```

### Phase 3 — Inputs

Start with simple syntax:

```text
input marketPreset = "NAS100"
input useSupertrendFilter = true
input fastLen = 9
input slowLen = 21
input atrLen = 10
input factor = 3.0
input session = "0930-1600"
```

Later support Pine-like input calls:

```text
marketPreset = input.string("NAS100", "Market Preset", options=["NAS100", "GOLD"])
useSupertrendFilter = input.bool(true, "Use Supertrend Filter")
```

### Phase 4 — Session Filters

Target:

```text
inSession = session("0930-1600")
longSignal = inSession and crossover(fastEMA, slowEMA)
```

### Phase 5 — Plot Metadata and Shapes

Upgrade from:

```text
plot fast
```

To:

```text
plot fastEMA title="Fast EMA" color="blue"
plot slowEMA title="Slow EMA" color="teal"
plot supertrendLine title="Supertrend" color="gold"

plotshape longSignal title="Buy Signal" text="BUY" location="belowbar"
plotshape exitSignal title="Sell Signal" text="SELL" location="abovebar"
```

### Phase 6 — Strategy Orders

Start with a safe simplified syntax:

```text
entry Long long when longSignal
close Long when exitSignal
```

Later add Pine-like compatibility:

```text
strategy.entry("Long", strategy.long)
strategy.close("Long")
```

Internally both should produce the same safe order-intent object.

## 4. Use Libraries Instead of Rewriting Everything

Use a hybrid approach:

```text
Use libraries for indicator/math implementations.
Use our own safe DSL/parser/runtime for control, validation, and execution.
```

Recommended libraries:

- `pandas-ta-classic` for indicators/math adapters.
- `lark` for grammar parsing and better syntax errors.
- Optional later: study PyneCore/Pine-like runtimes, but do not make them core until proven compatible.

Install later:

```bash
pip install pandas-ta-classic lark
```

Add to `requirements.txt`:

```text
pandas-ta-classic
lark
```

## 5. Function Registry as the Source of Truth

Create:

```text
Live/core/StrategyFunctionRegistry.py
```

Example registry entry:

```python
FUNCTION_REGISTRY = {
    "ta.ema": {
        "category": "Trend",
        "signature": "ta.ema(source, length)",
        "returns": "series",
        "description": "Exponential moving average.",
        "example": "fast = ta.ema(close, 9)",
        "backend": "pandas_ta_classic",
        "status": "supported",
    },
    "ta.supertrend": {
        "category": "Trend",
        "signature": "ta.supertrend(factor, atr_length)",
        "returns": "series, series",
        "description": "Supertrend line and trend direction.",
        "example": "line, direction = ta.supertrend(3.0, 10)",
        "backend": "pandas_ta_classic/custom-adapter",
        "status": "supported",
    },
}
```

The same registry should power parser validation, runtime dispatch, autocomplete, function reference UI, docs generation, LLM prompt constraints, error messages, and backtest compatibility.

Main rule:

```text
STRATEGY_LANGUAGE.md + FUNCTION_REGISTRY = truth
```

## 6. User Education and In-App Documentation

Add Strategy Lab helper tabs/panels:

```text
Strategy Lab
├── Script Editor
├── Run Script
├── Run Backtest
├── Docs / Help
├── Examples
├── Function Reference
└── AI Strategy Assistant
```

Create:

```text
Live/docs/STRATEGY_LANGUAGE.md
Live/docs/strategy_examples/
├── ema_crossover.txt
├── ema_supertrend.txt
├── rsi_mean_reversion.txt
├── breakout_highest_lowest.txt
└── session_filtered_strategy.txt
```

Docs should cover supported syntax, data series, functions, examples, common errors, unsupported Pine features, and the current language version.

Visible label:

```text
Strategy Language: v0.2
```

Optional script header later:

```text
//@sv_version=0.2
```

## 7. LLM Interaction with Strategy Lab

The LLM should not invent unsupported syntax. It should be constrained by:

- `STRATEGY_LANGUAGE.md`
- `FUNCTION_REGISTRY`
- Strategy examples
- Current script
- Parser errors
- Loaded symbol/timeframe/date range
- Backtest summary when available

LLM modes:

```text
Generate strategy
Explain strategy
Fix script error
Optimize strategy variants
Summarize backtest
Create paper-trading experiment plan
```

LLM output should be structured JSON:

```json
{
  "script": "fastEMA = ta.ema(close, 9)\nslowEMA = ta.ema(close, 21)\n...",
  "explanation": "This strategy buys when the fast EMA crosses above the slow EMA.",
  "warnings": ["Backtest before paper trading."],
  "unsupported_requests": [],
  "risk_notes": ["No live orders are placed."]
}
```

The app flow:

```text
LLM output
  ↓
JSON parse
  ↓
extract script
  ↓
StrategyEngine.validate(script)
  ↓
show user
  ↓
Run Backtest button
```

The LLM should never return executable Python for trading logic.

## 8. LLM Provider Architecture

Create an adapter layer so Dash does not care which model provider is used.

```text
Dash UI
  ↓
LLMStrategyService
  ↓
LLMProvider interface
  ├── OllamaProvider      local
  ├── OpenAIProvider      cloud
  └── MockProvider        testing/offline
  ↓
StrategyEngine validator
  ↓
Backtest / Paper / Future Live execution
```

Suggested files:

```text
Live/services/llm/
├── base.py
├── ollama_provider.py
├── openai_provider.py
├── llm_strategy_service.py
└── prompts.py
```

### Base Provider Interface

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional


@dataclass
class LLMRequest:
    system: str
    user: str
    model: str
    temperature: float = 0.2
    json_mode: bool = True


@dataclass
class LLMResponse:
    text: str
    raw: dict | None = None
    error: Optional[str] = None


class LLMProvider(Protocol):
    def chat(self, request: LLMRequest) -> LLMResponse:
        ...
```

### Ollama Provider

```python
from __future__ import annotations

import requests

from services.llm.base import LLMRequest, LLMResponse


class OllamaProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")

    def chat(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        if request.json_mode:
            payload["format"] = "json"

        try:
            res = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            res.raise_for_status()
            data = res.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(text=content, raw=data)
        except Exception as exc:
            return LLMResponse(text="", raw=None, error=str(exc))
```

### OpenAI Provider

```python
from __future__ import annotations

import os

from openai import OpenAI

from services.llm.base import LLMRequest, LLMResponse


class OpenAIProvider:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def chat(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self.client.responses.create(
                model=request.model,
                input=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                temperature=request.temperature,
            )
            return LLMResponse(
                text=response.output_text,
                raw=response.model_dump() if hasattr(response, "model_dump") else None,
            )
        except Exception as exc:
            return LLMResponse(text="", raw=None, error=str(exc))
```

## 9. LLM Security Model

### Local Ollama Mode

Preferred first implementation.

Local flow:

```text
App → localhost Ollama
No cloud API key
No market data leaves the machine
No strategy script leaves the machine
No external webhook needed
```

Security rules:

- Bind Ollama to `127.0.0.1` only.
- Do not expose port `11434` publicly.
- Do not run it behind a public tunnel.
- Do not let the LLM directly call broker APIs.
- Validate every generated script before running.
- Log every generated script and paper/backtest action.

### Cloud LLM Mode

Cloud mode is more powerful but must be explicit opt-in.

Rules:

- API keys stored only in environment variables or secret manager.
- Never commit `.env`.
- Never send broker credentials.
- Never send account IDs.
- Minimize market data sent to the model.
- No direct order execution by LLM.
- Use HTTPS provider APIs only.
- Log cloud requests at a high level without leaking secrets.

`.env.example` later:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
LLM_ALLOW_CLOUD=false
```

UI toggles:

```text
Provider: Local Ollama / Cloud API / Disabled
Send data to cloud: OFF by default
Max bars sent to LLM: 200
Allow paper automation: OFF by default
Allow live automation: disabled
```

Avoid initially:

- Public webhooks
- Inbound external requests
- Remote agents calling the app
- LLM with broker credentials
- LLM with unrestricted file/network access

## 10. LLM Paper Automation and Future Live Trading

The LLM should be an assistant/compiler helper, not the broker.

Paper mode flow:

```text
User asks for strategy
LLM generates Strategy Lab script
Parser validates script
Backtest runs on loaded replay/history data
User enables paper automation
PaperTradingService trades from validated strategy signals
RiskGuard still applies soft limits
Audit log stores script, prompt, signals, and orders
```

Even for paper, do not let the LLM place arbitrary orders directly.

Live mode later:

```text
New bar closes
Strategy runtime evaluates script
Strategy creates order intent
RiskGuard validates:
    symbol allowed
    max position size
    max daily loss
    max orders per minute
    market session
    paper/live mode enabled
    duplicate signal protection
Broker executes only approved intent
Trade is logged
Analytics updates
```

Required live safeguards:

- Live Automation OFF by default
- Explicit confirmation every session
- Max position size required
- Max daily loss required
- Max trades per day required
- Kill switch visible
- No duplicate orders per signal
- Full audit trail
- Paper mode test requirement before live mode

Main safety rule:

```text
LLM writes strategy scripts.
Your app validates and executes them.
The LLM never talks directly to IBKR, PaperBroker, or LiveBroker.
```

## 11. Market, News, Fundamental, and Macro Data

Add a separate research data layer. Do not put this inside `ReplayService`.

Suggested services:

```text
Live/services/
├── market_data_service.py
├── fundamentals_service.py
├── macro_data_service.py
├── news_service.py
├── sentiment_service.py
└── research_context_service.py
```

Data categories:

```text
Market data:
OHLCV, quotes, volume, spreads

Fundamentals:
Revenue, EPS, margins, debt, cash flow, filings

News/sentiment:
Headlines, summaries, event tags, source credibility

Macro:
CPI, unemployment, Fed funds rate, yield curve, GDP, payrolls

Calendar:
Earnings, FOMC, CPI releases, jobs reports
```

Good starting sources:

- SEC EDGAR APIs for filings/fundamentals.
- FRED API for unemployment, rates, CPI, GDP, and macro series.
- News provider later.
- Market data provider for price bars.

The LLM should receive a controlled research bundle:

```json
{
  "symbol": "AAPL",
  "asset_class": "stock",
  "price_context": "...",
  "fundamental_context": "...",
  "macro_context": "...",
  "news_context": "...",
  "backtest_summary": "..."
}
```

## 12. Multi-Asset Architecture

To add crypto, forex, futures, options, indices, etc., move from raw symbols to an `Instrument` model.

Example:

```python
from dataclasses import dataclass

@dataclass
class Instrument:
    symbol: str
    asset_class: str  # stock, crypto, forex, futures, option, index
    exchange: str | None = None
    currency: str = "USD"
    provider_symbol: str | None = None
    timezone: str = "America/New_York"
    session: str | None = "0930-1600"
```

Services should eventually accept `Instrument`, not only a string symbol:

```text
ReplayService.load(instrument, timeframe, start, end)
BacktestEngine.run(instrument, bars, strategy)
PaperTradingService.place_order(instrument, intent)
RiskGuard.validate(instrument, order)
```

Different asset classes have different rules:

```text
Stocks:
market hours, earnings, splits, dividends, PDT/margin rules

Crypto:
24/7 trading, exchanges, custody/wallet risks

Forex:
24/5 trading, pairs, pip size, lot size, rollover/swaps

Futures:
contracts expire, tick size, multiplier, margin

Options:
expiration, strikes, Greeks, spreads, assignment/exercise risk
```

## 13. Market Data Provider Interface

Avoid locking the app to a single vendor.

Create a provider interface:

```python
class MarketDataProvider:
    def get_bars(self, instrument, timeframe, start, end):
        ...

    def get_quote(self, instrument):
        ...

    def search_symbols(self, query, asset_class=None):
        ...
```

Implementations later:

```text
IBKRProvider
AlpacaProvider
PolygonProvider
YahooProvider/dev only
R2CacheProvider
LocalCacheProvider
```

This helps avoid future barriers from stock-only/NASDAQ-only data plans.

Potential future barriers:

- Asset coverage limitations
- Exchange licensing
- Historical depth limits
- Redistribution restrictions
- Commercial-use restrictions
- API rate limits
- Real-time vs delayed data
- Separate broker vs data provider integration

## 14. Cloud Storage / Replay Cache Plan

Recommended model:

```text
Local cache = fastest recent data
Cloud object storage = backup/shared historical cache
IBKR/API = source of truth when cache misses
```

Recommended first cloud option:

- Cloudflare R2
  - S3-compatible
  - No normal egress fees
  - Good for replay OHLCV cache
  - Cheap/free starting point

Alternative:

- Backblaze B2
  - Cheap bulk storage
  - Good for lots of historical cache

Use Parquet instead of CSV for cloud cache.

Suggested cache layout:

```text
replay-cache/
    AAPL/1min/2026-05-15.parquet
    AAPL/1min/2026-05-16.parquet
    MSFT/1min/2026-05-15.parquet
```

Future `get_history()` path:

```text
1. Check memory cache
2. Check local disk cache
3. Check cloud cache
4. If missing, request IBKR/API
5. Save to local disk
6. Save to cloud
```

Security:

- Private bucket
- Least-privilege keys
- No `.env` committed
- Lifecycle rules later
- API keys in environment variables

## 15. GitHub, Docker, and Future Installer Plan

Use three distribution levels later:

```text
Level 1 — GitHub developer setup
Level 2 — Docker Compose setup
Level 3 — Windows installer
```

Recommended repo layout:

```text
Stock_Visualizer/
├── Live/
│   ├── app.py
│   ├── callbacks.py
│   ├── config.py
│   ├── core/
│   ├── services/
│   ├── ui/
│   ├── utils/
│   ├── assets/
│   ├── data/
│   └── cache/
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── docs/
│   ├── INSTALL.md
│   ├── IBKR_SETUP.md
│   ├── REPLAY_CACHE.md
│   └── TROUBLESHOOTING.md
└── .github/
    └── workflows/
        ├── test.yml
        └── docker-publish.yml
```

Docker first, Windows installer later.

## 16. Recommended Implementation Order

```text
1. Commit current stable replay/backtest state.
2. Create Strategy Language v0.2 spec.
3. Create StrategyFunctionRegistry.
4. Add pandas-ta-classic and Lark.
5. Add boolean expressions/comparisons.
6. Add ta. namespace.
7. Add ATR and Supertrend.
8. Add plot metadata and plotshape.
9. Add examples and in-app docs.
10. Add local Ollama LLMProvider.
11. Add Generate/Explain/Fix Strategy buttons.
12. Keep LLM output backtest-only first.
13. Add paper automation later with confirmation.
14. Add MarketDataProvider interface.
15. Add SEC/FRED research services.
16. Add Instrument model for multi-asset support.
17. Add cloud cache provider.
18. Add Docker/GitHub deployment flow.
19. Add live automation only after RiskGuard and audit logs are mature.
```

## 17. Core Design Principles

1. Keep replay/backtest/paper/live separate.
2. Keep Strategy Language safe and versioned.
3. Use libraries for indicators, but expose only tested functions.
4. Use `FUNCTION_REGISTRY` as the source of truth.
5. LLM cannot trade directly.
6. LLM generates scripts; app validates them.
7. Backtest before paper automation.
8. Paper before live automation.
9. Live automation must require explicit user approval and hard risk limits.
10. Multi-asset support requires an `Instrument` model.
11. Macro/news/fundamental data belongs in a research layer, not replay.
12. Cloud storage is for cache, not source-of-truth execution.
13. Do not hardcode credentials.
14. Keep local LLM as the safest first option.
15. Make the app self-documenting for users.

## 18. Near-Term Next Step

The next practical feature to implement should be:

```text
Strategy Language v0.2 foundation
```

Files to create:

```text
Live/core/StrategyFunctionRegistry.py
Live/docs/STRATEGY_LANGUAGE.md
Live/docs/strategy_examples/ema_crossover.txt
Live/docs/strategy_examples/ema_supertrend.txt
```

Then upgrade:

```text
Live/core/StrategyEngine.py
```

To support:

```text
ta. namespace
boolean expressions
comparisons
ATR
Supertrend
boolean signal variables
plot metadata
```
