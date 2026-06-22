# Patch 11 — Central AI Safety Policy

This patch adds a central, code-level safety policy for future AI features.

## Files added

```text
Live/services/safety/__init__.py
Live/services/safety/ai_policy.py
Live/scripts/check_ai_safety_policy.py
Live/docs/patches/settings_ai_policy_patch_11.md
```

## Purpose

The Settings tab can show AI locks, but future AI features also need a code-level gate.

This patch creates a single policy object that future LLM adapters, AI tools, and broker-facing assistants can call before doing sensitive actions.

## Safe defaults

```env
AI_FEATURES_ENABLED=false
AI_ADVISORY_ONLY=true
AI_ALLOW_ORDER_PLACEMENT=false
AI_ALLOW_BROKER_ACCESS=false
AI_ALLOW_EXTERNAL_TOOLS=false
AI_REQUIRE_HUMAN_CONFIRMATION=true
LLM_PROVIDER=none
LLM_BASE_URL=
OPENAI_API_KEY=
```

## Safety behavior

By default:

- AI is disabled.
- AI cannot access broker tools.
- AI cannot place orders.
- AI cannot use external tools.
- Human confirmation remains required for any future order-capable workflow.

## Diagnostic command

```powershell
python .\Live\scripts\check_ai_safety_policy.py
```

JSON output:

```powershell
python .\Live\scripts\check_ai_safety_policy.py --json
```

Strict validation:

```powershell
python .\Live\scripts\check_ai_safety_policy.py --strict
```

## Security notes

Do not store API tokens in Dash browser state.

Do not expose AI or broker endpoints publicly without authentication, HTTPS, rate limits, audit logs, and strict permission checks.

Do not let an LLM directly place trades. Future AI trade ideas should remain advisory unless a separate human-confirmation workflow explicitly approves an action.
