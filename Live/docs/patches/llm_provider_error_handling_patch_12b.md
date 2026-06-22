# Patch 12b — LLM Chat Completions Compatibility

This patch fixes model-specific Chat Completions parameter handling.

## Problem

Some newer OpenAI models reject the older Chat Completions parameter:

```text
max_tokens
```

and expect:

```text
max_completion_tokens
```

The app was reaching OpenAI successfully, but the provider failed with:

```text
Unsupported parameter: 'max_tokens' is not supported with this model.
Use 'max_completion_tokens' instead.
```

## Files changed

```text
Live/services/llm/openai_compatible_provider.py
Live/scripts/check_llm_provider.py
Live/docs/patches/llm_provider_error_handling_patch_12b.md
```

## Behavior added

```text
Auto-select max_completion_tokens for GPT-5 / o-series style models
Keep max_tokens for older/local OpenAI-compatible servers
Retry once when a provider reports an unsupported token parameter
Retry once without temperature if a model rejects temperature
Print friendly LLM errors instead of full Python tracebacks
```

## Optional environment overrides

```env
LLM_CHAT_TOKEN_PARAM=auto
LLM_SEND_TEMPERATURE=auto
```

Allowed values:

```text
LLM_CHAT_TOKEN_PARAM=auto|max_tokens|max_completion_tokens
LLM_SEND_TEMPERATURE=auto|true|false
```

## Safety

This patch does not add broker access, order placement, tool calling, account access, or UI secret entry.
