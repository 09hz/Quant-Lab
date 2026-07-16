# BackTestEngine Bars Adapter

v24.9.5 connects the Research Loop to a real `bars` input so your actual `BackTestEngine.run(...)` can be exercised instead of immediately falling back.

## Why this is needed

The probe showed the real engine is being imported, but the adapter could not satisfy a required parameter named `bars`.

That means the current problem is not strategy generation. The blocker is data plumbing.

## What the bars adapter does

It searches for historical OHLCV-like data in the repo, then normalizes it into a form that the adapter can hand to `BackTestEngine.run`.

Supported sources:

- CSV files under `Live/data`
- CSV files under `Live/data/catalog`
- CSV files elsewhere in the repo that look like market datasets

If no suitable file exists, the adapter can synthesize a simulation-only bars series so the pipeline can continue to be tested safely.

## Current limitations

This is still a generic adapter.

It does not yet know the exact `bars` class or schema your `BackTestEngine` prefers, so the next patch may need to bind it more precisely after observing the real engine output.

## Safety

Simulation/research only. No live orders, no broker calls, no trade execution.
