# v24.9.2.1 — Research Loop Rich Report Self-Test Fix

## Purpose

Fix the v24.9.2 self-test failure:

```text
AssertionError: Rich report missing next action.
```

## Cause

The rich report included next-action guidance, but the self-test expected the literal text `v24.9.3` in the generated Markdown. Depending on the survivor/reject path, the report could recommend the real BackTestEngine adapter without including that exact version string.

## Fix

1. Add an explicit `v24.9.3 — Real BackTestEngine Adapter` section to every Research Loop report.
2. Make the self-test check for both the version and adapter guidance.
3. Keep the persistence compatibility fix from v24.9.2 unchanged.

## Safety

- No Data Library edits
- No main app layout edits
- No broker calls
- No live trading
- No order placement
- No credentials written
- No file moves or deletes
