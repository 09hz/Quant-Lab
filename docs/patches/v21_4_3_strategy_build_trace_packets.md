# v21_4_3_strategy_build_trace_packets

## Purpose

Add transparent strategy/algorithm trace files to each Auto Lab mutation run.

This is not hidden AI chain-of-thought. It is a deterministic, auditable strategy build trace that explains:

```text
parent strategy
→ parent code
→ mutation applied
→ final strategy code
→ plain-English algorithm
→ score breakdown
→ why it passed/failed
→ next test idea
```

## User-selected variables

```text
1. Trace format: C — both markdown + JSON.
2. Include full strategy code: A — yes.
3. Include plain-English algorithm: A — yes.
4. Include score breakdown: A — yes.
5. Include mutation lineage: A — parent → mutation → result.
6. Include AI explanation text: A — deterministic template only for now.
7. UI changes: A — no UI yet, report files only.
8. Patch name: v21_4_3_strategy_build_trace_packets.py.
```

## Files added

```text
Live/services/ai/auto_lab_orchestrator/strategy_trace.py
Live/services/ai/auto_lab_orchestrator/strategy_trace_from_run.py
Live/services/ai/auto_lab_orchestrator/strategy_trace_self_test.py
```

## Files patched

```text
Live/services/ai/auto_lab_orchestrator/csv_mutation_retest_sized.py
```

The sized CSV runner now writes strategy trace artifacts after mutation reports.

## Output files per run

```text
strategy_build_trace.md
strategy_build_trace.json
top_strategy_algorithm.md
```

## UI use later

The first UI can show:

```text
Ranked results table
→ click a strategy row
→ load strategy_build_trace.json
→ show parent code, final code, mutation, algorithm, score breakdown, pass/fail notes
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_4_3_strategy_build_trace_packets.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-trace-self-test
```

## Generate trace for latest run

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\strategy_trace_from_run.py" `
  --latest
```

## Inspect trace files

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\strategy_build_trace.md"
notepad "$($latest.FullName)\\top_strategy_algorithm.md"
notepad "$($latest.FullName)\\strategy_build_trace.json"
```

## Safety

```text
Simulation/research only.
No broker execution.
No live orders.
No PaperBroker calls.
No account credentials.
No secrets.
```
