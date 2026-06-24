# Patch 32 - Newsroom to Strategy AI handoff

## Purpose

This patch completes the first safe research-to-AI loop:

1. Fetch Newsroom results.
2. Add selected results to the research brief.
3. Send the selected brief to the Strategy AI attached-context field.
4. Ask the Strategy AI using the selected research context.

The handoff is advisory-only. It does not grant the AI broker access, order-placement access, arbitrary browsing, file reading, or secret access.

## Added

- `Live/services/research/brief_ai_handoff.py`
- `Live/scripts/check_newsroom_ai_handoff.py`

## Updated

- `Live/services/research/newsroom_callbacks.py`
- `Live/services/research/__init__.py`
- `Live/ui/newsroom_ui.py`
- `Live/assets/zz_newsroom_interactive.css`

## Behavior

The `Send Brief to Strategy AI` button starts disabled. It becomes enabled after the Newsroom brief contains at least one selected item.

When clicked, the selected brief is converted to a read-only markdown context block and placed into:

- `strategy-ai-advisor-context`

If the Strategy AI prompt is empty, a concise default prompt is inserted into:

- `strategy-ai-advisor-prompt`

## Validation

```powershell
python -m py_compile .\Live\services\research\brief_ai_handoff.py
python -m py_compile .\Live\services\research\newsroom_callbacks.py
python -m py_compile .\Live\scripts\check_newsroom_ai_handoff.py
python -m py_compile .\Live\app.py

python .\Live\scripts\check_newsroom_ai_handoff.py
```

## Manual test

1. Start the app.
2. Open Newsroom.
3. Search `inflation rate`.
4. Add one or more FRED structured cards to the brief.
5. Click `Send Brief to Strategy AI`.
6. Open Watch -> Strategy Lab -> AI Advisor.
7. Confirm the attached context contains `Attached Research Brief`.
8. Ask the advisor a concise question.
