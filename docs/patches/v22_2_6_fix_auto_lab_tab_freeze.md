# v22_2_6_fix_auto_lab_tab_freeze

## Purpose

Fix the AI Auto Lab tab freeze caused by the v22.2.5 DOM fallback script.

## Cause

The previous browser script used a `MutationObserver` plus repeated DOM writes. Updating the capital summary changed the DOM, which could trigger the observer again, causing a loop/freeze in the tab.

## Fix

Replace:

```text
MutationObserver + setInterval DOM rewrite loop
```

with:

```text
event-delegated input/change listener + no observer + no endless DOM rewrite
```

The new script:

- listens for visible input changes
- renders only when the computed HTML actually changed
- does not use `MutationObserver`
- does not use a repeated polling interval
- updates after tab clicks and page load using short one-shot timers

## Safety

Research/simulation only.

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
```
