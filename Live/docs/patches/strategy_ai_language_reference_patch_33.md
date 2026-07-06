# Patch 33 — Strategy AI language reference

This patch gives the Strategy AI a compact reference for the app's Strategy Lab script language.

## Problem

The AI could answer with generic Python such as:

```python
import numpy as np
import pandas as pd

def strategy_script(df, cash):
    ...
```

That is not the format expected by the app's restricted Strategy Lab editor.

## Change

Added:

- `Live/services/ai/strategy_language_reference.py`
- `Live/scripts/check_strategy_ai_language_reference.py`

Updated:

- `Live/services/ai/advisor_callbacks.py`
- `Live/services/ai/__init__.py`

The Strategy AI now receives a small app-language reference whenever it answers from the Strategy AI panel.

## Safety

The reference is advisory-only and does not add broker access, file access, secret access, order placement, arbitrary browsing, or external tools.

## Validation

```powershell
python -m py_compile .\Live\services\ai\strategy_language_reference.py
python -m py_compile .\Live\services\ai\advisor_callbacks.py
python -m py_compile .\Live\scripts\check_strategy_ai_language_reference.py

python .\Live\scripts\check_strategy_ai_language_reference.py
python .\Live\scripts\check_strategy_ai_language_reference.py --sample-output "import pandas as pd`ndef strategy_script(df, cash): pass"
```

## Expected behavior

When the user asks the Strategy AI to improve a script, it should avoid generic pandas/numpy code and should prefer the current app-compatible Strategy Lab style.
