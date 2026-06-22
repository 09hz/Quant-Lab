# Patch 15c — AI Advisor raw/healthcheck mode

## Purpose

The normal `ask_ai_advisor.py` command uses advisory prompt templates. Those
templates are useful for trading-app questions, but they can interfere with tiny
connectivity tests like:

```text
Reply with exactly: AI_OK
```

The model may treat that as an incomplete trading-advisor prompt and ask for a
symbol/timeframe instead of returning the exact healthcheck string.

## Changed files

- `Live/scripts/ask_ai_advisor.py`
- `Live/docs/patches/ai_advisor_healthcheck_patch_15c.md`

## New commands

Minimal LLM healthcheck through the AI advisor safety layer:

```powershell
python .\Live\scripts\ask_ai_advisor.py --healthcheck
```

Expected output:

```text
AI_OK
```

Raw exact-output test:

```powershell
python .\Live\scripts\ask_ai_advisor.py --raw --prompt "Reply with exactly: AI_OK" --max-output-tokens 30
```

Normal advisory mode is unchanged:

```powershell
python .\Live\scripts\ask_ai_advisor.py --template provider_status --prompt "Explain my provider status."
```

## Safety

`--healthcheck` and `--raw` still use `AIAdvisorService`, so they remain behind
the central AI safety policy. They do not add broker access, order placement,
tool calling, or browser API-key entry.
