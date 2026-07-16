# v23.1.2 — Market Memory Reindex + Noise Cleanup

## Purpose

Clean existing market memory rows created before symbol hygiene was added.

v23.1.1 filters future extraction, but old database rows can still contain noisy uppercase words such as:

```text
AI, PASS, ENV, WARN, SEND, LIVE, RSI, BUY
```

v23.1.2 adds a reindexer that:

- cleans `evidence_items.symbols_json`
- cleans `evidence_items.entities_json`
- removes noisy symbol entities
- removes noisy symbol relationships
- rebuilds hypotheses from cleaned evidence
- rebuilds strategy memory from cleaned evidence
- rewrites memory reports
- rebuilds a clean research packet

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
