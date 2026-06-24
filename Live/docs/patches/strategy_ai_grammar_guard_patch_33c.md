# Patch 33c — Strategy AI grammar guard

## Purpose

Patch 33 taught the AI the broad Strategy Lab language. Patch 33c adds a stricter
parser contract so the Strategy AI stops generating syntax that the current
Strategy Lab parser cannot read.

## Problem fixed

The AI produced output like:

```text
volOk = atr > 0.1 and atr > atrSma * 0.8
longSetup = inSession and bullCross and aboveTrend and r >= 40 and r <= 65 and volOk
sell when shortSetup
buy when exitShort
```

The current parser rejected this because of unsupported patterns:

- `>=` and `<=`
- inline arithmetic inside boolean comparisons, such as `atrSma * 0.8`
- packed condition assignments
- short-entry style `sell when shortSetup` / `buy when exitShort`

## Files added

```text
Live/services/ai/strategy_grammar_guard.py
Live/scripts/check_strategy_ai_grammar_guard.py
Live/docs/patches/strategy_ai_grammar_guard_patch_33c.md
```

## Files updated

```text
Live/services/ai/advisor_callbacks.py
Live/services/ai/__init__.py
```

## Behavior

Every Strategy AI request now receives a strict Strategy Lab parser contract:

- no imports
- no pandas/numpy
- no `def strategy_script()`
- no `>=` / `<=`
- no inline math inside boolean comparisons
- break complex logic into simple variables
- use `buy when` for long entries
- use `sell when` for long exits
- avoid short logic unless explicitly supported

## Test

```powershell
python -m py_compile .\Live\services\ai\strategy_grammar_guard.py
python -m py_compile .\Live\services\ai\advisor_callbacks.py
python -m py_compile .\Live\scripts\check_strategy_ai_grammar_guard.py
python .\Live\scripts\check_strategy_ai_grammar_guard.py
python .\Live\scripts\check_strategy_ai_grammar_guard.py --good
```
