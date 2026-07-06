# v19_1_connect_legacy_newsroom_to_router_evidence_packet

## Purpose

Connect selected legacy Newsroom/Research Brief rows into the new v19 AI Research Tool Router evidence schema.

This keeps the current Newsroom/Analyst flow intact. It adds an experimental bridge that converts selected SEC/FRED/BLS/BEA-style brief rows into structured `EvidenceRow` objects and writes a structured `EvidencePacket` diagnostic.

## User-selected variables

```text
1. Connect selected Research Brief rows first: yes.
2. Write debug files: yes.
3. Include BEA placeholder schema support: yes.
4. Modify Analyst prompt now: no.
5. Include self-test using sample SEC/FRED/BLS rows: yes.
```

## Files added / changed

Added:

```text
Live/services/ai/tool_router/legacy_bridge.py
Live/services/ai/tool_router/legacy_bridge_self_test.py
```

Changed:

```text
Live/services/ai/tool_router/__init__.py
Live/services/research/newsroom_callbacks.py
```

## Behavior

When the Research Brief markdown is rendered, v19.1 writes:

```text
Live/data/autolab_payload/router_last_evidence_packet.json
Live/data/autolab_payload/router_last_evidence_packet.md
Live/data/autolab_payload/router_last_chart_ready_data.json
Live/data/autolab_payload/router_last_legacy_bridge_status.json
```

This is diagnostic-only for now. It does not replace the current Analyst prompt or current Newsroom behavior.

## Test tools

### Apply patch

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\v19_1_connect_legacy_newsroom_to_router_evidence_packet.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --run-self-test
```

### Expected

```text
v19.1 legacy Newsroom -> Router EvidencePacket bridge patch complete.
- compile: PASS

Running legacy bridge self-test...
AI Research Tool Router legacy bridge self-test: PASS
```

### Direct self-test

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\Live\services\ai\tool_router\legacy_bridge_self_test.py"
```

### Restart Dash

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\app.py"
```

### Newsroom test search/topic

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
3. Select useful SEC, FRED, and BLS rows.
4. Add Selected to Brief.
5. Open/refresh Research Brief preview.
6. Check router debug files.
```

### Debug checks

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

Get-Content ".\data\autolab_payload\router_last_legacy_bridge_status.json"

Select-String -Path ".\data\autolab_payload\router_last_evidence_packet.md" `
  -Pattern "Source inventory|SEC|FRED|BLS|BEA|Chart-ready"

Get-Content ".\data\autolab_payload\router_last_chart_ready_data.json"
```

### Analyst question for manual comparison

```text
Give me a practical research analyst read on AMD using the current Newsroom Research Brief.

Use the AUTHORITATIVE NEWSROOM EVIDENCE TABLES first.
If the evidence context contains SEC, FRED, or BLS AUTHORITATIVE REPEAT CHECKPOINTS, use those repeat checkpoints as authoritative evidence.

First inventory the evidence by source.

SEC companyfacts evidence:
Inventory every SEC row you received. If SEC card count is 6, inventory all six SEC rows.

FRED evidence:
Inventory every FRED numeric row and separate metadata-only FRED links.

BLS evidence:
Inventory every BLS row you received.

Then interpret:
1. Company fundamentals from SEC
2. Inflation and price-level context from FRED and BLS
3. Labor and wage context from BLS
4. Combined practical read
5. Missing, metadata-only, or weak evidence

Keep this research-only and simulation/advisory only. No live trading instructions, broker actions, order placement, position sizing, or personalized financial advice.
```

## Safety

- No backups are created.
- No live trading/broker/order execution behavior is added.
- No current Analyst prompt is modified.
- No existing guardrails are deleted.
- Third-party sources remain context-only in the router policy.
