# v22_2_5_dom_capital_summary_fallback

## Purpose

Fix the AI Auto Lab capital summary panel using a browser-side DOM fallback.

## Why

The screenshot showed the input fields changed, but the "Current capital assumptions" panel still showed old values.

Earlier diagnostics showed the Python methods and Dash callback wiring were correct. To avoid more callback transport/caching issues, this patch makes the panel update directly in the browser from the visible input fields.

## What changes

- Replaces the capital summary component with a plain `html.Div`.
- Removes any Dash callback output targeting `main-autolab-capital-summary`.
- Adds `Live/assets/auto_lab_capital_live.js`.
- The JS listens to:
  - `main-autolab-initial-cash`
  - `main-autolab-target-cash`
  - `main-autolab-cash-exposure`
  - `main-autolab-sizing-mode`
- The panel updates on input/change/keyup and a light polling fallback.

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
```
