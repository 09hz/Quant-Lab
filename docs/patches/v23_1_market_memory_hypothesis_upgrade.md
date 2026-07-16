# v23.1 — Market Memory Relationship + Hypothesis Upgrade

## Purpose

Upgrade the persistent market memory layer so the AI researcher does more than store evidence.

v23.1 adds:

```text
evidence -> stronger extraction -> hypotheses -> strategy memory -> Auto Lab research packet
```

## What changes

- Adds hypothesis generation from market memory evidence.
- Adds strategy-memory extraction from Auto Lab and walk-forward artifacts.
- Adds a research packet builder that turns the memory web into an Auto Lab-ready research brief.
- Updates ingest so future artifacts automatically contribute hypotheses and strategy memory.
- Updates reports so humans can review hypotheses and strategy memory.

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
No network calls.
```

## Files added

```text
Live/services/ai/market_memory/hypothesis_engine.py
Live/services/ai/market_memory/research_packet.py
Live/services/ai/market_memory/build_research_packet.py
Live/services/ai/market_memory/self_test_v23_1.py
```

## Files patched

```text
Live/services/ai/market_memory/__init__.py
Live/services/ai/market_memory/ingest.py
Live/services/ai/market_memory/reports.py
```
