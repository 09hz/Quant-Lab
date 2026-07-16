# v23.1.1 — Market Memory Symbol Hygiene

## Purpose

Fix noisy uppercase tokens entering the market memory research packet.

The first v23.1 packet included items like:

```text
AI, PASS, ENV, WARN, SEND, LIVE
```

Those came from broad uppercase-token extraction. Some are normal words from reports/logs, not symbols.

## Fix

Add symbol hygiene:

- Require candidate symbols to be in a known research symbol allow-list.
- Treat ambiguous uppercase market words as text unless explicitly supported later.
- Filter research-packet symbols through the hygiene layer.
- Theme-rank semiconductor/AI-infrastructure packets toward related symbols.

## Safety

Research/simulation only. No live orders, broker connections, PaperBroker calls, credentials, trade execution, or network calls.
