# v22_2_1_live_capital_summary_refresh

## Purpose

Fix the AI Auto Lab capital summary so it updates when the user edits:

```text
Starting cash
Target cash
Cash exposure %
Sizing mode
```

## Cause

In v22.2, those fields were registered as Dash `State`, not `Input`.

That means the callback could read the values only after a button click, but editing the values alone did not trigger the summary to refresh.

## Fix

Move the capital fields from `State(...)` to `Input(...)`.

Now the capital summary updates when those fields change.

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
```
