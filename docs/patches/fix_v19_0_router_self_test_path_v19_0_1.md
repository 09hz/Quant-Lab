# fix_v19_0_router_self_test_path_v19_0_1

## Purpose

Fix the v19.0 self-test command issue.

The v19.0 files compiled successfully, but the `--run-self-test` step failed with:

```text
ModuleNotFoundError: No module named 'services'
```

This was not a router logic failure. It happened because the test command tried to run:

```text
python -m Live.services.ai.tool_router.self_test
```

from the repository root. The existing app package `Live/services/ai/__init__.py` imports `services.ai...`, which only resolves cleanly when `Live` is on `PYTHONPATH` or when the working directory is `Live`.

## What changed

Patches:

```text
Live/services/ai/tool_router/self_test.py
```

The self-test can now run directly by file path without depending on the parent `services.ai` package import path:

```powershell
& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" `
  ".\Live\services\ai\tool_router\self_test.py"
```

It uses an isolated runtime package only for direct-file self-testing, so relative imports inside the router modules still work.

## What did not change

- No current Newsroom/Analyst flow is replaced.
- No guardrails are deleted.
- No broker/order/live trading behavior is added.
- No backups are created.
- No network calls are added.

## Test tools

### Run from repo root

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" `
  ".\Live\services\ai\tool_router\self_test.py"
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

### Optional import check from Live working directory

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" -c "from services.ai.tool_router import build_research_plan, get_tool_registry_diagnostics; print(build_research_plan('Compare AMD revenue EPS CPI PCE unemployment wages over five years').to_markdown()); print(get_tool_registry_diagnostics().to_markdown())"
```

## Next patch after this passes

```text
v19.1 — Connect existing SEC/FRED/BLS/BEA-style adapter outputs into EvidencePacket rows.
```
