# Patch 12 — Advisory LLM Provider Scaffold

This patch starts AI integration safely by adding an advisory-only LLM provider layer.

## Files added

```text
Live/services/llm/__init__.py
Live/services/llm/base.py
Live/services/llm/noop_provider.py
Live/services/llm/openai_compatible_provider.py
Live/services/llm/provider_factory.py
Live/scripts/check_llm_provider.py
```

## Safe behavior

By default, AI remains disabled:

```env
AI_FEATURES_ENABLED=false
LLM_PROVIDER=none
```

When disabled, the factory returns `NoOpLLMProvider`.

## What this patch does not do

```text
No broker access
No order placement
No account access
No tool calling
No Dash browser secret entry
No automatic trading
No chart or UI changes
```

## Local model example

```powershell
$env:AI_FEATURES_ENABLED="true"
$env:AI_ADVISORY_ONLY="true"
$env:LLM_PROVIDER="ollama"
$env:LLM_BASE_URL="http://127.0.0.1:11434/v1"
$env:LLM_MODEL="your-local-model"

python .\Live\scripts\check_llm_provider.py --prompt "Explain what advisory-only mode means."
```

## OpenAI-compatible remote example

```powershell
$env:AI_FEATURES_ENABLED="true"
$env:AI_ADVISORY_ONLY="true"
$env:LLM_PROVIDER="openai-compatible"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="your-model"
$env:OPENAI_API_KEY="your-key"

python .\Live\scripts\check_llm_provider.py --prompt "Give a high-level explanation of a moving average crossover."
```

Do not commit `.env` or API keys.
