# v20_0_router_only_research_analyst_rework

## Purpose

Rework the Research Analyst handoff so the v19 router evidence packet becomes the only authoritative Analyst context.

The current stack has too many legacy layers:

```text
Newsroom markdown
→ old SEC/FRED/BLS context builders
→ repeat checkpoints / tail guards
→ combined legacy context
→ Analyst prompt overrides
→ router packet added beside it
```

This can produce stale mixes like:

```text
visible/router packet: FRED exists, SEC = 4
old context: SEC = 6
Analyst answer: FRED missing, SEC = 6
```

v20.0 changes the rule:

```text
If router_last_evidence_packet.json exists and has rows:
    Analyst uses ONLY the router packet.
    Old SEC/FRED/BLS contexts and tail guards are ignored.

If router_last_evidence_packet.json is missing or empty:
    Analyst should say selected router evidence is missing and ask the user to add selected rows to the Research Brief first.
```

## User-selected variables

```text
1. Rework mode: A — router-only Analyst now.
2. Missing router packet behavior: A — show error / ask user to add selected rows first.
3. Delete old tail-guard debug files automatically: A — yes.
4. Remove old prompt checkpoint code now or bypass first: B — bypass first, remove later.
5. Keep Research Brief markdown preview: A — yes, display-only.
6. Modify only Research Analyst in v20.0: A — yes.
7. Third-party context in v20.0: B — context-only but not connected yet.
8. Patch name accepted: v20_0_router_only_research_analyst_rework.py.
```

## Files changed

```text
Live/services/ai/research_analyst_callbacks.py
```

## Files removed by patch/runtime cleanup

```text
Live/data/autolab_payload/research_analyst_last_sec_tail_guard.txt
Live/data/autolab_payload/research_analyst_last_fred_tail_guard.txt
Live/data/autolab_payload/research_analyst_last_bls_tail_guard.txt
```

These are old tail-guard debug files only. The patch does not delete SEC/FRED/BLS adapters.

## Guardrails kept

```text
1. Official facts win.
   SEC/FRED/BLS/BEA/Fed/Treasury rows override third-party context.

2. Third-party is context-only.
   Third-party rows cannot override official numeric rows.

3. Every numeric fact should come from an EvidenceRow.
   value, unit, date, source, URL, source_quality.

4. Missing router packet fails clearly.
   No selected router packet means the user needs to add rows to the Research Brief first.

5. Research-only safety remains.
   No broker orders, no live trading execution, no personalized position sizing.
```

## What this patch does not delete

```text
Live/services/research/sec_newsroom_adapter.py
Live/services/research/fred_newsroom_adapter.py
Live/services/research/bls_newsroom_adapter.py
Live/services/research/sec_companyfacts_parser.py
Live/services/ai/tool_router/
Live/services/research/newsroom_callbacks.py
Live/ui/newsroom_ui.py
```

Those remain useful. The rework targets the Analyst handoff only.

## Test tools

### Apply patch

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\v20_0_router_only_research_analyst_rework.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader"
```

Expected:

```text
v20.0 router-only Research Analyst rework complete.
- compile: PASS
```

### Restart Dash

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\app.py"
```

### Newsroom search/topic

```text
AMD CPI core CPI PCE core PCE inflation labor unemployment payrolls wages company fundamentals revenue cash EPS operating income net income shares
```

### Source checkboxes

```text
SEC EDGAR
FRED
BLS
```

### UI test steps

```text
1. Clear Brief.
2. Fetch Research.
3. Select exactly the rows you want included.
4. Add Selected to Brief.
5. Confirm Research Brief preview shows those rows.
6. Ask the Analyst question below.
```

### Analyst question

```text
Give me a practical research analyst read on AMD using the current selected Research Brief.

Use the ROUTER SELECTED RESEARCH BRIEF EVIDENCE PACKET as the only source of truth.
Do not use older SEC/FRED/BLS legacy contexts, tail guards, compact source lists, or previous brief states.

First inventory the evidence by source exactly as present in the router packet.

SEC companyfacts:
Inventory only the SEC rows present in the router packet.
Do not add SEC metrics that are not in the router packet.

FRED:
Inventory every FRED row present in the router packet.
Separate numeric FRED rows from metadata-only FRED source links.
Do not say FRED is missing if the router packet contains FRED rows.

BLS:
Inventory every BLS row present in the router packet.

Then interpret:
1. Company fundamentals from SEC
2. Inflation and price-level context from FRED and BLS
3. Labor and wage context from BLS
4. Combined practical read
5. Missing, metadata-only, or weak evidence

Keep this research-only and simulation/advisory only.
Do not give live trading instructions, broker actions, order placement, position sizing, or personalized financial advice.
```

### Debug checks after Ask

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

Get-Content ".\data\autolab_payload\router_last_legacy_bridge_status.json"

Select-String -Path ".\data\autolab_payload\research_analyst_last_router_only_context.txt" `
  -Pattern "ROUTER ONLY|Source inventory|FRED|SEC|BLS|CPIAUCSL|CPILFESL|cash|operating_income"

Test-Path ".\data\autolab_payload\research_analyst_last_sec_tail_guard.txt"
Test-Path ".\data\autolab_payload\research_analyst_last_fred_tail_guard.txt"
Test-Path ".\data\autolab_payload\research_analyst_last_bls_tail_guard.txt"
```

Expected tail-guard test result:

```text
False
False
False
```

## Expected pass

If the router packet says:

```text
FRED: 4
BLS: 4
SEC: 4
```

the Analyst should inventory:

```text
FRED: 4
BLS: 4
SEC: 4
```

It should not invent stale:

```text
SEC: 6
FRED: missing
```
