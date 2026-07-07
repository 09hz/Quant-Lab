# v23.4.1 — Data Library Runtime Wiring Fix

## Purpose

Fix the case where the v23.4 Data Library self-test passes, but the Data Library does not appear in the running Dash app.

## Likely cause

The v23.4 integration block was appended near the bottom of `Live/app.py`. If the Dash server starts before that appended block is reached, the runtime app never attaches the Data Library even though import-time self-tests pass.

## Fix

Insert a stronger Data Library integration block before the main run guard / app.run call.

## Safety

Research/simulation only.

- No live orders
- No broker connection
- No trade execution
- No file moves
- No file deletes
