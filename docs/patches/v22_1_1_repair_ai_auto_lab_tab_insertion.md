# v22_1_1_repair_ai_auto_lab_tab_insertion

## Purpose

Repair the v22.1 main Dash tab insertion.

The v22.1 patch inserted the new `AI Auto Lab` tab at the line containing `label="Settings"`.
In this app structure, that placed a `dcc.Tab(...)` block inside the Settings `dcc.Tab(...)` call, causing:

```text
TypeError: Tab.__init__() got multiple values for argument 'children'
```

## Fix

This repair script:

1. Removes the misplaced `AI Auto Lab` `dcc.Tab(...)` block.
2. Finds the real start of the Settings `dcc.Tab(...)` block.
3. Reinserts `AI Auto Lab` immediately before the Settings tab.
4. Keeps the existing Auto Lab import/callback registration.
5. Runs syntax checks and optional main UI self-test.

## Safety

No backups are created.
No broker calls.
No live orders.
No PaperBroker calls.
Research/simulation UI only.
