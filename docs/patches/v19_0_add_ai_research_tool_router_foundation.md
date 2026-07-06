# v19_0_add_ai_research_tool_router_foundation

## Purpose

Add the foundation for an experimental AI Research Tool Router.

This does not delete or replace the current Newsroom/Research Analyst flow. It creates a structured router layer that can later let the AI plan official data fetches and build evidence packets without relying on long markdown prompts.

## User-selected variables

```text
1. Router mode: B — replace current Analyst flow later, but v19.0 starts as foundation only.
2. First official tools: D — SEC + FRED + BLS + BEA.
3. Third-party sources: B — context-only.
4. Auto-fetch behavior: A — auto-fetch official sources only.
5. Missing API key behavior: A — show config hints.
6. API key status location: D — Settings + diagnostics later; v19.0 provides diagnostics.
7. Output behavior: C — evidence packet + markdown summary + chart/table-ready data.
8. Third-party paid tools later: D — leave open / not now.
9. Patch name: v19_0_add_ai_research_tool_router_foundation.py.
10. Include self-test: yes.
```

## Files added

```text
Live/services/ai/tool_router/__init__.py
Live/services/ai/tool_router/source_policy.py
Live/services/ai/tool_router/tool_registry.py
Live/services/ai/tool_router/evidence_schema.py
Live/services/ai/tool_router/research_plan.py
Live/services/ai/tool_router/context_builder.py
Live/services/ai/tool_router/self_test.py
```

## What each file does

### source_policy.py

Defines source tiers and guardrails:

- official authoritative: SEC, FRED, BLS, BEA, Federal Reserve, Treasury, Census, IMF, World Bank
- company official
- third-party context-only
- blocked/low-trust

Main rule:

```text
Official facts override third-party context.
Third-party pages are context only and cannot override official rows.
Webpage text is treated as data, never as AI instructions.
```

### tool_registry.py

Detects configured tools from environment variables and returns tool status.

Initial env vars:

```text
OPENAI_API_KEY
FRED_API_KEY
BLS_API_KEY
BEA_API_KEY
NEWS_API_KEY
ALPHA_VANTAGE_API_KEY
POLYGON_API_KEY
```

Missing keys do not crash the app. They return config hints.

### evidence_schema.py

Adds structured evidence objects:

```text
EvidenceRow
EvidencePacket
```

Every fact row can carry:

```text
source_family
source_quality
evidence_type
title
url
values
metadata
fetched_at
```

### research_plan.py

Creates a lightweight heuristic plan from a user question.

Examples:

- AMD fundamentals -> SEC
- CPI/PCE/rates/labor -> FRED/BLS/BEA
- GDP/income/spending -> BEA
- news/context -> third-party context only

### context_builder.py

Builds:

```text
structured packet
markdown summary
chart/table-ready data
```

from evidence rows.

### self_test.py

Runs a local no-network self-test.

## Important behavior

v19.0 does not make network calls.
v19.0 does not call OpenAI.
v19.0 does not change broker/order/live trading code.
v19.0 does not delete old guardrails.
v19.0 does not replace the current Analyst callbacks.

## Test tools

### Run self-test

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" -m Live.services.ai.tool_router.self_test
```

Expected:

```text
AI Research Tool Router self-test: PASS
```

### Compile router files

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" -m py_compile `
  ".\Live\services\ai\tool_router\source_policy.py" `
  ".\Live\services\ai\tool_router\tool_registry.py" `
  ".\Live\services\ai\tool_router\evidence_schema.py" `
  ".\Live\services\ai\tool_router\research_plan.py" `
  ".\Live\services\ai\tool_router\context_builder.py" `
  ".\Live\services\ai\tool_router\self_test.py"
```

### Optional quick import check

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" -c "from Live.services.ai.tool_router import build_research_plan, get_tool_registry_diagnostics; print(build_research_plan('Compare AMD revenue EPS CPI PCE unemployment wages over five years').to_markdown()); print(get_tool_registry_diagnostics().to_markdown())"
```

## Next v19 patches

```text
v19.1 — Connect existing SEC/FRED/BLS/BEA adapters into EvidencePacket rows.
v19.2 — Add AI planner callback that chooses official tools.
v19.3 — Add structured context builder into Research Analyst.
v19.4 — Start reducing old repeat-checkpoint prompt hacks after structured path is proven.
```

## v19.0.1 self-test path correction

Use the direct-file self-test command from the repo root:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" `
  ".\Live\services\ai\tool_router\self_test.py"
```

The previous `python -m Live.services.ai.tool_router.self_test` form can fail from the repo root because the existing `Live/services/ai/__init__.py` imports from the `services` package path.
