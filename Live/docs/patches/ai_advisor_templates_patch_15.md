# Patch 15 — AI Advisor prompt templates and CLI

## Purpose

Add a safer, more useful way to test the advisory AI layer without adding UI,
broker access, order placement, or tool calling.

## Added files

- `Live/services/ai/prompt_templates.py`
- `Live/scripts/ask_ai_advisor.py`

## Design

The advisor flow remains:

```text
script/UI
  -> AIAdvisorService
    -> AI safety policy
    -> LLM provider
```

The prompt templates are advisory-only and remind the model not to place trades,
request secrets, or imply broker/account access.

## Usage

List templates:

```powershell
python .\Live\scripts\ask_ai_advisor.py --list-templates
```

Tiny test:

```powershell
python .\Live\scripts\ask_ai_advisor.py --prompt "Reply with exactly: AI_OK" --max-output-tokens 30
```

Debug provider output:

```powershell
python .\Live\scripts\check_llm_provider.py --provider openai > llm_check.txt
python .\Live\scripts\ask_ai_advisor.py --template error_debug --context-file .\llm_check.txt --prompt "What is wrong here?"
```

## Safety

This patch does not add:

- broker access
- order placement
- external tool calling
- browser API key entry
- autonomous trading

It only adds prompt templates and a command-line wrapper around the already
existing advisory AI service.
