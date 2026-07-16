# force_fix_v19_0_self_test_escape_warning_v19_0_3

## Purpose

Force-clean the remaining self-test docstring warning:

```text
SyntaxWarning: invalid escape sequence '\L'
python .\Live\services\ai\tool_router\self_test.py
```

The self-test itself already passes. This patch only cleans the warning text by replacing any Windows-backslash path examples inside `self_test.py` with forward-slash examples.

## What changed

Patches:

```text
Live/services/ai/tool_router/self_test.py
```

Replaces every occurrence of:

```text
.\Live\services\ai\tool_router\self_test.py
```

with:

```text
./Live/services/ai/tool_router/self_test.py
```

Also replaces the shorter router path fragment if present.

## Test tools

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\force_fix_v19_0_self_test_escape_warning_v19_0_3.py" `
  --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader" `
  --run-self-test
```

Expected:

```text
v19.0.3 forced self-test escape-warning cleanup complete.
- compile: PASS

Running direct-file self-test...
AI Research Tool Router self-test: PASS
```

No `SyntaxWarning` should appear.

## Safety

- No router logic changed.
- No current Newsroom/Analyst flow changed.
- No broker/order/live-trading behavior added.
- No backups created.
