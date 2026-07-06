# v22_2_4_clientside_capital_summary

## Purpose

Make the AI Auto Lab capital summary update in the browser immediately.

## Why

The v22.2.3 diagnostic showed the Python/Dash server wiring is correct. If the visible UI still does not update, likely causes are stale browser/server state or a Dash callback transport issue. This patch removes that dependency for the capital panel by using a Dash clientside callback.

## Change

Replace the Python server callback:

```text
capital inputs -> Python callback -> markdown
```

with a browser-side callback:

```text
capital inputs -> JavaScript callback -> markdown
```

The report-running callback remains server-side.

## Safety

Research/simulation only. No live orders, no broker connection, no PaperBroker calls, no account credentials, no trade execution.
