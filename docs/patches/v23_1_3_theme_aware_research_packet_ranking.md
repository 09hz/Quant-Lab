# v23.1.3 — Theme-Aware Research Packet Ranking

## Purpose

Make Market Memory research packets better match the requested research theme.

After v23.1.1/v23.1.2, symbol noise was cleaned, but packets for:

```text
AI infrastructure semiconductors
```

could still show unrelated hypotheses near the top, such as Consumer discretionary hypotheses.

v23.1.3 adds theme-aware ranking and quality checks.

## Adds

```text
Live/services/ai/market_memory/theme_ranking.py
Live/services/ai/market_memory/self_test_v23_1_3.py
```

## Patches

```text
Live/services/ai/market_memory/research_packet.py
Live/services/ai/market_memory/__init__.py
```

## New packet fields

```text
packet_quality_score
warning_flags
theme_match_summary
```

## Behavior

- Ranks hypotheses by requested theme.
- Ranks relationships by requested theme.
- Ranks evidence by requested theme.
- Boosts theme-relevant symbols.
- De-prioritizes unrelated hypotheses.
- Flags low-quality packets before they are used by Auto Lab.
- Keeps the system research/simulation only.

## Safety

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
No network calls.
```
