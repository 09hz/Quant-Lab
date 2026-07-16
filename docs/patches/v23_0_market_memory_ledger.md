# v23.0 — Persistent Market Memory Ledger

## Purpose

Add the first durable memory layer for the Newsroom / AI researcher / Auto Lab ecosystem.

This creates a persistent market memory web so research context is not wiped every boot.

The system stores:

```text
evidence -> entities -> relationships -> hypotheses -> research runs -> strategy memory
```

## Scope

This is a safe foundation patch.

```text
No main UI changes.
No broker connection.
No live orders.
No PaperBroker calls.
No account credentials.
No trade execution.
No network calls.
```

## Files added

```text
Live/services/ai/market_memory/__init__.py
Live/services/ai/market_memory/models.py
Live/services/ai/market_memory/storage.py
Live/services/ai/market_memory/relationship_engine.py
Live/services/ai/market_memory/ingest.py
Live/services/ai/market_memory/reports.py
Live/services/ai/market_memory/ingest_latest.py
Live/services/ai/market_memory/self_test.py
```

## Data created at runtime

```text
Live/data/market_memory/
  market_memory.sqlite
  evidence_ledger.jsonl
  memory_reports/
    market_memory_report.md
    entity_report.md
    relationship_report.md
    hypothesis_report.md
    memory_snapshot.json
```

## Recommended first use

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\v23_0_market_memory_ledger.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --run-self-test
```

Then ingest latest local research artifacts:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\Live\services\ai\market_memory\ingest_latest.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --limit 80 `
  --seed-sample
```

## Design notes

- SQLite is the durable source of truth.
- JSONL evidence ledger is an append-readable audit stream.
- Markdown reports are for human review.
- Existing research files are read-only inputs.
- Memory is append/update by default and is never wiped by this patch.
