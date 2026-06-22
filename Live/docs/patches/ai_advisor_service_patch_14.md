# Patch 14 — AI Advisor Service

This patch adds the first real AI integration point, but keeps it advisory-only.

## Added files

- `Live/services/ai/__init__.py`
- `Live/services/ai/advisor.py`
- `Live/scripts/check_ai_advisor.py`

## Updated files

- `Live/.env.example`

## What it does

The new `AIAdvisorService` is a small facade over:

1. the central AI safety policy
2. the configured LLM provider
3. secret redaction and friendly errors

Future UI callbacks should call the advisor service instead of calling an LLM
provider directly.

## What it does not do

- No order placement
- No broker/account access
- No external tool calling
- No API key entry in the browser
- No autonomous trading

## Test

```powershell
python -m py_compile .\Live\services\ai\advisor.py
python -m py_compile .\Live\scripts\check_ai_advisor.py

python .\Live\scripts\check_ai_advisor.py --prompt "Reply with exactly: AI_ADVISOR_OK" --max-output-tokens 30
```

## Expected result when AI is enabled and the LLM account has quota

```text
AI_ADVISOR_OK
```

## Expected result when AI is disabled

The script should print a blocked message instead of calling the LLM.
