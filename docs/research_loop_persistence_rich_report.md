# Research Loop Persistence + Rich Report Fix

v24.9.2 improves the v24.9.0 Research Loop foundation.

## Why this patch exists

The first loop report was intentionally simple. It proved the end-to-end flow:

```text
candidate generation -> proxy scoring -> reports -> Quant Dashboard path
```

But it did not yet provide enough explanation, and on some local databases it could not persist because `experiment_runs` already existed with an older schema.

## What changed

### Schema-compatible persistence

The loop now inspects table columns before inserting.

For example, if the local table has:

```text
run_id, status, created_at
```

the loop inserts those fields and skips unsupported fields like `experiment_id`.

If the local table has the newer typed schema, it inserts richer typed fields.

### Richer reports

Reports now include:

- What the Research Loop does
- How it differs from Auto Lab
- Candidate strategy parameters
- Per-symbol simulated results
- Pass/fail gates
- Walk-forward proxy metrics
- Universe robustness metrics
- Next recommended action

### Adapter hooks

v24.9.2 adds adapter classes that define the future boundary to real engines:

```text
AutoLabAdapter
BacktestAdapter
WalkForwardAdapter
UniverseAdapter
```

The next patch can implement these adapters to call the real BackTestEngine / Auto Lab modules safely.

## Important distinction

Auto Lab is the experiment worker.

Research Loop is the research manager.

```text
Auto Lab:
  Generate/test/mutate strategy ideas.

Research Loop:
  Choose theme/symbols, call workers, score outcomes, store results, write memory feedback, decide next test.
```

## Still simulation-only

v24.9.2 still uses deterministic proxy scoring. It is not yet a real historical backtest adapter.

Next recommended patch:

```text
v24.9.3 — Real BackTestEngine Adapter
```
