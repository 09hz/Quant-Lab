# v22_2_2_split_live_capital_callback

## Purpose

Fix the AI Auto Lab capital panel so it updates independently when the user edits:

```text
Starting cash
Target cash
Cash exposure %
Sizing mode
```

## Why v22.2.1 was not enough

v22.2.1 moved the capital fields to `Input(...)`, but they were still inside the large report-running callback.

This patch splits the capital summary into its own small callback:

```text
capital inputs -> capital summary only
```

That avoids report refresh/load work blocking or masking the capital-panel update.

## Also updates

- Sets the numeric capital inputs to `debounce=False`.
- Removes `main-autolab-capital-summary` from the large runner callback outputs.
- Adds a self-test that confirms:
  - one dedicated callback owns `main-autolab-capital-summary`
  - the large runner callback does not output `main-autolab-capital-summary`
  - capital input fields are present in the UI

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
```
