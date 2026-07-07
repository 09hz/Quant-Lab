# v23.2.2.1 — Fix v23.2.2 Callback Format Error

## Purpose

Fix the v23.2.2 patch failure:

```text
KeyError: '_v23_2_2_memory_callback_error'
```

## Cause

The previous patch used Python `.format(...)` on a template that also contained f-string braces. The braces inside the embedded callback block were interpreted as `.format` placeholders.

## Fix

- Rewrites the missing Market Memory panel files.
- Reapplies the direct AI Auto Lab panel attachment.
- Adds callback registration using a placeholder replacement instead of `.format`.
- Adds/updates CSS.
- Runs a self-test.

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
No network calls.
```
