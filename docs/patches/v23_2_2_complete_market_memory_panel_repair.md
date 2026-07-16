# v23.2.2 — Complete Market Memory Panel Repair

## Purpose

Install the missing v23.2 Market Memory panel files and apply the stronger panel attachment repair in one script.

This fixes the state where v23.2.1.1 reported missing files:

```text
Live/ui/auto_lab_memory_packet_ui.py
Live/services/ai/auto_lab_orchestrator/market_memory_packet_callbacks.py
```

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

The Apply button only copies symbols into the Auto Lab symbols field. It does not run Auto Lab or place trades.
