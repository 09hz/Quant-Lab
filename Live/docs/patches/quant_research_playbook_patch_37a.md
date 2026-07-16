# Patch 37a - Quant Research Playbook backend

## Purpose

Convert a Research Analyst evidence packet into research-only quant hypotheses and a backtest plan.

This patch does not add live trading, broker access, auto-execution, or unrestricted browsing.

## Files added

- `Live/services/ai/quant_research_playbook.py`
- `Live/scripts/check_quant_research_playbook.py`
- `Live/docs/patches/quant_research_playbook_patch_37a.md`

## File updated

- `Live/services/ai/research_analyst_callbacks.py`

## Behavior

When the Research Analyst builds an evidence packet, the callback now also builds a quant research playbook from the packet items and appends it to the AI context.

The playbook includes:

- regime label
- supportive evidence
- risk evidence
- missing evidence
- testable hypotheses
- symbols to test
- strategy family
- filters
- invalidation rules
- required backtest metrics
- safeguards

## Safety

The playbook is research-only. It explicitly does not place trades, connect to brokers, or make live execution recommendations.

## Checks

```powershell
python -m py_compile .\Live\services\ai\quant_research_playbook.py
python -m py_compile .\Live\services\ai\research_analyst_callbacks.py
python .\Live\scripts\check_quant_research_playbook.py
```
